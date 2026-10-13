"""
Casos de uso del import masivo de usuarios por Excel (plantilla + preview +
confirmar). Ver `apps/administracion/services/user_import_service.py` para el
parseo/validacion del archivo y
`apps/administracion/use_cases/users/create_user.py` para el alta real de
cada usuario (reusado fila por fila, igual que en el alta individual de
`UsersListCreateView.post`).
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.administracion.services.user_import_service import (
    build_template,
    parse_and_validate,
)
from apps.authentication.services.email_service import send_user_credentials_email_batch
from apps.catalogos.models import CatTipoPersonal, Escuelas, Roles

from .create_user import CedulaInput, CreateUserData, CreateUserUseCase
from .password_utils import generate_temporary_password

# Fases reportadas a `progress(phase, done, total)` -- mismos valores que
# `UserImportJob.Phase` (el job las persiste tal cual).
PHASE_VALIDATING = "VALIDATING"
PHASE_PREPARING = "PREPARING"
PHASE_SAVING = "SAVING"
PHASE_SENDING_EMAILS = "SENDING_EMAILS"

# PBKDF2 (hashlib) libera el GIL, asi que hilos SI paralelizan el hasheo:
# medido 2.5x con 8 hilos. Tope en 8 para no acaparar el host compartido.
_HASH_WORKERS = max(1, min(8, os.cpu_count() or 1))


def _noop_progress(phase, done, total):
    return None


def _hash_credentials(count, progress):
    """
    Genera `count` pares (password_temporal, hash) en paralelo, FUERA de
    cualquier transaccion. Es el 90% del tiempo de un import grande.
    """
    passwords = [generate_temporary_password() for _ in range(count)]
    hashes = [None] * count
    progress(PHASE_PREPARING, 0, count)
    with ThreadPoolExecutor(max_workers=_HASH_WORKERS) as executor:
        futures = {executor.submit(make_password, pwd): idx for idx, pwd in enumerate(passwords)}
        for done, future in enumerate(as_completed(futures), start=1):
            hashes[futures[future]] = future.result()
            progress(PHASE_PREPARING, done, count)
    return list(zip(passwords, hashes))

# Tipo asignado a la cedula capturada en el import masivo -- la plantilla solo
# trae un numero de cedula (columna "Cédula"), sin columna de tipo, a
# diferencia del alta individual en `rbac_views.py` donde el tipo lo captura
# el usuario en el formulario. Se marca como principal por ser la unica.
IMPORTED_CEDULA_TIPO = "Cédula Profesional"


class RoleVanishedDuringImport(Exception):
    """
    Se lanza si un rol validado en `parse_and_validate` deja de existir/estar
    activo en el instante de crear el usuario dentro de la transaccion
    (carrera muy improbable, pero preferimos abortar todo el import antes
    que crear un usuario sin rol).
    """

    def __init__(self, row_number: int, username: str):
        self.row_number = row_number
        self.username = username
        super().__init__(
            f"El rol de la fila {row_number} ({username}) ya no existe o esta inactivo."
        )


class TemplateUsersImportUseCase:
    def execute(self) -> bytes:
        return build_template()


class PreviewUsersImportUseCase:
    """Paso 1: valida el Excel y devuelve las filas con error. NO escribe en la BD."""

    def execute(self, file) -> dict:
        result = parse_and_validate(file)
        return {
            "totalRecords": result["total_records"],
            "totalErrores": result["total_errores"],
            "inserted": 0,
            "rows": result["rows"],
        }


class ConfirmUsersImportUseCase:
    """
    Paso 2: recibe el MISMO archivo (nunca filas ya validadas por el
    cliente) y re-corre `parse_and_validate` como unica autoridad.
    Todo-o-nada solo a nivel de VALIDACION: si queda un solo error, no se
    crea ningun usuario. Si todas las filas son validas, crea todos los
    usuarios dentro de una unica transaccion atomica SIN mandar correos
    (para no abrir/cerrar SMTP miles de veces con una transaccion de DB
    abierta, y para no dejar "emails fantasma" si un envio falla a mitad de
    un import grande y se revierte la transaccion). Una vez comprometida la
    transaccion, las credenciales se mandan en batch (una sola conexion
    SMTP) fuera de ella -- si algun correo falla ahi, el usuario ya existe
    en la BD igual; el fallo solo se reporta en `emailFailures` para
    reenviar manualmente.

    Lo ejecuta la tarea Celery `procesar_import_usuarios` (y el comando
    `importar_usuarios_excel`). `progress(phase, done, total)` es opcional;
    se llama SOLO fuera de la transaccion (validacion, hasheo y correos):
    una escritura de avance dentro del atomic no seria visible para el
    polling hasta el commit, y se revertiria junto con el lote.
    """

    def execute(self, file, actor, progress=None) -> dict:
        progress = progress or _noop_progress
        progress(PHASE_VALIDATING, 0, 0)
        result = parse_and_validate(file)

        if result["total_errores"] > 0:
            return {
                "totalRecords": result["total_records"],
                "totalErrores": result["total_errores"],
                "inserted": 0,
                "rows": result["rows"],
                "has_errors": True,
            }

        credentials = _hash_credentials(len(result["rows"]), progress)

        progress(PHASE_SAVING, 0, len(result["rows"]))
        inserted, pending_emails = self._create_all(result["rows"], actor, credentials)

        email_failures = []
        if pending_emails:
            total_emails = len(pending_emails)
            progress(PHASE_SENDING_EMAILS, 0, total_emails)
            batch_result = send_user_credentials_email_batch(
                pending_emails,
                on_progress=lambda done: progress(PHASE_SENDING_EMAILS, done, total_emails),
            )
            email_failures = batch_result["failed"]

        return {
            "totalRecords": result["total_records"],
            "totalErrores": 0,
            "inserted": inserted,
            "rows": result["rows"],
            "emailFailures": email_failures,
            "has_errors": False,
        }

    @transaction.atomic
    def _create_all(self, rows, actor, credentials):
        inserted = 0
        pending_emails = []
        # Catalogos resueltos una sola vez por id: con miles de filas que
        # repiten los mismos pocos roles/tipos/escuelas, consultar por fila
        # eran miles de queries redundantes.
        roles_cache, tipos_cache, escuelas_cache = {}, {}, {}
        for row, (temporary_password, clave_hash) in zip(rows, credentials):
            data = row["data"]
            role_id = data["roleId"]
            if role_id not in roles_cache:
                roles_cache[role_id] = Roles.objects.filter(id_rol=role_id, is_active=True).first()
            role = roles_cache[role_id]
            # `role` ya se valido en parse_and_validate; si desaparecio entre
            # preview y confirm (carrera improbable) fallamos duro para no
            # crear un usuario sin rol.
            if role is None:
                raise RoleVanishedDuringImport(row["row"], data["username"])

            # `is not None`, no truthiness: el ID 0 es un registro real en los
            # catálogos (p. ej. la escuela con ID 0) y no debe descartarse.
            tipo_personal = None
            if data["tipoPersonalId"] is not None:
                tipo_id = data["tipoPersonalId"]
                if tipo_id not in tipos_cache:
                    tipos_cache[tipo_id] = CatTipoPersonal.objects.filter(
                        id=tipo_id, is_active=True
                    ).first()
                tipo_personal = tipos_cache[tipo_id]

            escuela = None
            if data["escuelaId"] is not None:
                escuela_id = data["escuelaId"]
                if escuela_id not in escuelas_cache:
                    escuelas_cache[escuela_id] = Escuelas.objects.filter(
                        id=escuela_id, is_active=True
                    ).first()
                escuela = escuelas_cache[escuela_id]

            cedulas = []
            if data["cedula"]:
                cedulas = [
                    CedulaInput(
                        numero=data["cedula"],
                        tipo=IMPORTED_CEDULA_TIPO,
                        es_principal=True,
                    )
                ]

            create_result = CreateUserUseCase.execute(
                CreateUserData(
                    username=data["username"],
                    first_name=data["firstName"],
                    paternal_name=data["paternalName"],
                    maternal_name=data["maternalName"] or "",
                    email=data["email"],
                    role=role,
                    actor=actor,
                    no_exp=data["noExp"],
                    sexo=data["sexo"],
                    fecha_nac=data["fechaNacimiento"],
                    escuela=escuela,
                    cedulas=cedulas,
                    est_activo=data["isActive"],
                    tipo_personal=tipo_personal,
                    send_credentials_email=False,
                    temporary_password=temporary_password,
                    clave_hash=clave_hash,
                )
            )

            if data["email"]:
                pending_emails.append(
                    {
                        "email": data["email"],
                        "username": create_result.user.usuario,
                        "temporary_password": create_result.temporary_password,
                        "user_name": create_result.full_name,
                    }
                )

            inserted += 1

        return inserted, pending_emails
