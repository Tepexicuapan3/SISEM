"""
Casos de uso del import masivo de médicos por Excel (plantilla + preview +
confirmar). Ver `apps/medicos/services/medico_import_service.py` para el
parseo/validación del archivo.

Mecanismo STATELESS calcado de
`apps.administracion.use_cases.users.import_users` (ver Engram, topic_key
sdd/medicos-legacy-field-bulk-import/design, "Decisión 1"): no hay token,
cache ni sesión intermedia. El frontend retiene el mismo `File` entre
preview y confirm; el confirm re-corre `parse_and_validate` sobre ese MISMO
archivo como única autoridad -- nunca confía en las filas que el cliente
validó en preview.
"""

from django.db import transaction

from apps.authentication.models import SyUsuario
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.medicos.services.medico_import_service import build_template, parse_and_validate


class MedicoImportRaceError(Exception):
    """
    Se lanza si el `SyUsuario` de una fila (o su vínculo con `CatMedico`)
    validado en `parse_and_validate` cambia entre esa validación y el
    instante de crear el médico dentro de la transacción (carrera muy
    improbable, pero preferimos abortar todo el import antes que crear un
    médico inconsistente). Análogo exacto de `RoleVanishedDuringImport` en
    el import de usuarios.
    """

    def __init__(self, row_number: int, usuario: str):
        self.row_number = row_number
        self.usuario = usuario
        super().__init__(
            f"El usuario de la fila {row_number} ({usuario}) ya no existe "
            "o cambió de estado. No se creó ningún médico."
        )


class TemplateMedicosImportUseCase:
    def execute(self) -> bytes:
        return build_template()


class PreviewMedicosImportUseCase:
    """Paso 1: valida el Excel y devuelve las filas con error. NO escribe en la BD."""

    def execute(self, file) -> dict:
        result = parse_and_validate(file)
        return {
            "totalRecords": result["total_records"],
            "totalErrores": result["total_errores"],
            "inserted": 0,
            "rows": result["rows"],
        }


class ConfirmMedicosImportUseCase:
    """
    Paso 2: recibe el MISMO archivo (nunca filas ya validadas por el
    cliente) y re-corre `parse_and_validate` como única autoridad.
    Todo-o-nada en dos niveles (idéntico a `ConfirmUsersImportUseCase`):

    1. Validación: si queda un solo error en cualquier fila, NO se crea
       ningún médico (`has_errors=True` -> la vista responde 409).
    2. Persistencia: si todas las filas son válidas, se crean todos los
       médicos dentro de una única transacción atómica -- si una fila
       revienta (IntegrityError que el preview no vio), rollback total.

    Simplificación vs. usuarios: médicos no manda correos, así que no hay
    efecto lateral no transaccional que sacar de `_create_all` -- todo el
    confirm es atómico sin excepciones.

    NO reusa `medico_usecase.create_medico`: ese use case exige
    `usuarioId` numérico, valida `tipo_personal == "Médico"` y depende del
    flag `MEDICOS_ALLOW_SIN_USUARIO`. Acá `Usuario` es texto obligatorio
    (resuelto por `parse_and_validate` contra `SyUsuario.usuario`) y se
    llama a `MedicoRepository.create` directo.
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

        inserted = self._create_all(result["rows"], actor)

        return {
            "totalRecords": result["total_records"],
            "totalErrores": 0,
            "inserted": inserted,
            "rows": result["rows"],
            "has_errors": False,
        }

    @transaction.atomic
    def _create_all(self, rows, actor):
        inserted = 0
        for row in rows:
            data = row["data"]

            usuario = SyUsuario.objects.filter(usuario=data["usuario"]).first()
            # `usuario` ya se validó en parse_and_validate; si desapareció
            # o quedó vinculado a otro médico entre preview/confirm y este
            # instante (carrera improbable), fallamos duro en vez de crear
            # un médico inconsistente.
            if usuario is None:
                raise MedicoImportRaceError(row["row"], data["usuario"])
            if MedicoRepository.exists_for_usuario(usuario):
                raise MedicoImportRaceError(row["row"], data["usuario"])

            MedicoRepository.create(
                usuario=usuario,
                nombre_display=data["nombreDisplay"],
                tipo_medico=data["tipoMedico"],
                servicio=data["servicio"],
                observaciones=data["observaciones"],
                estatus_medico=data["estatusMedico"],
                legacy_cd_medico=data["legacyCdMedico"],
                created_by_id=actor.id_usuario,
            )
            inserted += 1

        return inserted
