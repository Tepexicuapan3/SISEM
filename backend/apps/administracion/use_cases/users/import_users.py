"""
Casos de uso del import masivo de usuarios por Excel (plantilla + preview +
confirmar). Ver `apps/administracion/services/user_import_service.py` para el
parseo/validacion del archivo y
`apps/administracion/use_cases/users/create_user.py` para el alta real de
cada usuario (reusado fila por fila, igual que en el alta individual de
`UsersListCreateView.post`).
"""

from django.db import transaction

from apps.administracion.services.user_import_service import (
    build_template,
    parse_and_validate,
)
from apps.authentication.services.email_service import send_user_credentials_email_batch
from apps.catalogos.models import CatTipoPersonal, Escuelas, Roles

from .create_user import CedulaInput, CreateUserData, CreateUserUseCase

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
    """

    def execute(self, file, actor) -> dict:
        result = parse_and_validate(file)

        if result["total_errores"] > 0:
            return {
                "totalRecords": result["total_records"],
                "totalErrores": result["total_errores"],
                "inserted": 0,
                "rows": result["rows"],
                "has_errors": True,
            }

        inserted, pending_emails = self._create_all(result["rows"], actor)

        email_failures = []
        if pending_emails:
            batch_result = send_user_credentials_email_batch(pending_emails)
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
    def _create_all(self, rows, actor):
        inserted = 0
        pending_emails = []
        for row in rows:
            data = row["data"]
            role = Roles.objects.filter(id_rol=data["roleId"], is_active=True).first()
            # `role` ya se valido en parse_and_validate; si desaparecio entre
            # preview y confirm (carrera improbable) fallamos duro para no
            # crear un usuario sin rol.
            if role is None:
                raise RoleVanishedDuringImport(row["row"], data["username"])

            tipo_personal = None
            if data["tipoPersonalId"]:
                tipo_personal = CatTipoPersonal.objects.filter(
                    id=data["tipoPersonalId"], is_active=True
                ).first()

            escuela = None
            if data["escuelaId"]:
                escuela = Escuelas.objects.filter(
                    id=data["escuelaId"], is_active=True
                ).first()

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
