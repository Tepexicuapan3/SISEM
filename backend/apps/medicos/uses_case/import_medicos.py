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

El confirm lo ejecuta en segundo plano la tarea Celery
`apps.medicos.tasks.procesar_import_medicos` (ver `MedicoImportJob`).
"""

from django.db import connection, transaction

from apps.authentication.models import DetUsuarioCedula, SyUsuario
from apps.medicos.models import CatMedico, RelMedicoEspecialidad
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.medicos.identity import cedula_key
from apps.medicos.services.medico_import_service import build_template, parse_and_validate

# Fases reportadas a `progress(phase, done, total)` -- mismos valores que
# `MedicoImportJob.Phase`.
PHASE_VALIDATING = "VALIDATING"
PHASE_SAVING = "SAVING"


def _noop_progress(phase, done, total):
    return None


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
    """Paso 1: valida el Excel y devuelve errores/warnings por fila. NO escribe en la BD."""

    def execute(self, file) -> dict:
        result = parse_and_validate(file)
        return {
            "totalRecords": result["total_records"],
            "totalErrores": result["total_errores"],
            "totalWarnings": result["total_warnings"],
            "warningSummary": result["warning_summary"],
            "inserted": 0,
            "rows": result["rows"],
        }


def _lock_cat_medicos():
    """
    Serializa el confirm contra altas manuales/imports concurrentes (D5).
    Solo Postgres: el advisory lock serializa imports entre sí y el LOCK TABLE
    en SHARE ROW EXCLUSIVE evita que un alta con `nextval` tome un id
    explícito del Excel mientras se inserta. Se libera al cerrar la transacción.
    """
    if connection.vendor != "postgresql":
        return
    table = connection.ops.quote_name(CatMedico._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))", [CatMedico._meta.db_table]
        )
        cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")


def _sync_id_sequence():
    """
    Deja la secuencia en MAX(id)+1 (D4). `is_called=false` + COALESCE funciona
    también con la tabla vacía (a diferencia del setval de catalog_import, que
    con MAX NULL no hace nada). Solo Postgres; en SQLite el autoincrement
    ya continúa desde el id máximo.
    """
    if connection.vendor != "postgresql":
        return
    table = CatMedico._meta.db_table
    quoted = connection.ops.quote_name(table)
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT setval(pg_get_serial_sequence(%s, 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {quoted}), 0) + 1, false)",
            [table],
        )


class ConfirmMedicosImportUseCase:
    """
    Paso 2: recibe el MISMO archivo (nunca filas ya validadas por el
    cliente) y re-corre `parse_and_validate` como única autoridad.
    Todo-o-nada en dos niveles (idéntico a `ConfirmUsersImportUseCase`):

    1. Validación: si queda un solo ERROR en cualquier fila, NO se crea
       ningún médico (`has_errors=True` -> la vista responde 409). Los
       warnings NO bloquean.
    2. Persistencia: si todas las filas son válidas, se crean todos los
       médicos dentro de una única transacción atómica -- si una fila
       revienta (IntegrityError que el preview no vio), rollback total.

    La validación se repite DENTRO del lock de `cat_medicos` (D5): entre el
    preview y el lock otro alta pudo tomar un No. Médico del archivo.

    Orden de inserción (D6): primero las filas con No. Médico explícito,
    luego `setval` (D4) y al final las filas sin número, que toman `nextval`
    sin chocar con ningún id explícito de una fila posterior.

    NO reusa `medico_usecase.create_medico`: ese use case exige
    `usuarioId` numérico y valida `tipo_personal == "Médico"`. Acá `Usuario`
    es texto OPCIONAL (resuelto por `parse_and_validate` contra
    `SyUsuario.usuario`): sin usuario se crea con `id_usuario=NULL` + datos
    personales propios; este import es el ÚNICO camino de alta sin usuario.
    Se llama a `MedicoRepository.create` directo.

    `progress(phase, done, total)` es opcional (la tarea Celery lo usa para
    publicar el avance en la cache; ver `services/import_job_progress.py`).
    """

    def execute(self, file, actor, progress=None) -> dict:
        progress = progress or _noop_progress
        progress(PHASE_VALIDATING, 0, 0)
        result = parse_and_validate(file)
        if result["total_errores"] > 0:
            return self._rejected(result)

        with transaction.atomic():
            _lock_cat_medicos()
            # Re-validar con el lock tomado: el archivo se relee desde el inicio.
            if hasattr(file, "seek"):
                file.seek(0)
            result = parse_and_validate(file)
            if result["total_errores"] > 0:
                return self._rejected(result)
            inserted = self._create_all(result["rows"], actor, progress)

        return {
            "totalRecords": result["total_records"],
            "totalErrores": 0,
            "totalWarnings": result["total_warnings"],
            "warningSummary": result["warning_summary"],
            "inserted": inserted,
            "rows": result["rows"],
            "has_errors": False,
        }

    @staticmethod
    def _rejected(result) -> dict:
        return {
            "totalRecords": result["total_records"],
            "totalErrores": result["total_errores"],
            "totalWarnings": result["total_warnings"],
            "warningSummary": result["warning_summary"],
            "inserted": 0,
            "rows": result["rows"],
            "has_errors": True,
        }

    def _create_all(self, rows, actor, progress=_noop_progress):
        # Explícitas primero (orden del archivo), luego las que toman nextval.
        explicit = [r for r in rows if r["data"]["noMedico"] is not None]
        implicit = [r for r in rows if r["data"]["noMedico"] is None]
        total = len(rows)

        done = 0
        progress(PHASE_SAVING, done, total)
        for row in explicit:
            self._create_one(row, actor)
            done += 1
            progress(PHASE_SAVING, done, total)
        if explicit:
            _sync_id_sequence()
        for row in implicit:
            self._create_one(row, actor)
            done += 1
            progress(PHASE_SAVING, done, total)

        return total

    def _create_one(self, row, actor):
        data = row["data"]

        usuario = None
        if data["usuario"]:
            usuario = SyUsuario.objects.filter(usuario=data["usuario"]).first()
            # `usuario` ya se validó en parse_and_validate; si desapareció
            # o quedó vinculado a otro médico entre preview/confirm y este
            # instante (carrera improbable), fallamos duro en vez de crear
            # un médico inconsistente.
            if usuario is None:
                raise MedicoImportRaceError(row["row"], data["usuario"])
            if MedicoRepository.exists_for_usuario(usuario):
                raise MedicoImportRaceError(row["row"], data["usuario"])

        # Datos personales SOLO sin usuario (CheckConstraint del modelo).
        medico = MedicoRepository.create(
            usuario=usuario,
            id=data["noMedico"],
            paterno=None if usuario else data["paterno"],
            materno=None if usuario else data["materno"],
            nombre=None if usuario else data["nombre"],
            cedula_profesional=None if usuario else data["cedulaProfesional"],
            escuela_id=None if usuario else data["escuelaId"],
            sexo=None if usuario else data["sexo"],
            fecha_nac=None if usuario else data["fechaNac"],
            tipo_medico=data["tipoMedico"],
            servicio=data["servicio"],
            observaciones=data["observaciones"],
            estatus_medico=data["estatusMedico"],
            created_by_id=actor.id_usuario,
        )

        # Sin centro: la plantilla ya no trae Clave Clínica; los centros se
        # asignan después desde la ficha del médico.
        # `is not None`, no truthiness: el ID 0 es un registro real del catálogo.
        if data["especialidadId"] is not None:
            RelMedicoEspecialidad.objects.create(
                medico=medico,
                especialidad_id=data["especialidadId"],
                es_principal=True,
            )

        # Con usuario: la cédula se AGREGA a DetUsuarioCedula (un usuario
        # admite varias). Principal solo si no tenía ninguna; si ya tenía, va
        # como adicional con el siguiente `orden`. Nunca se sobrescribe ni se
        # duplica un número ya registrado (el preview lo avisa como warning).
        if usuario and data["cedulaProfesional"]:
            existentes = list(
                DetUsuarioCedula.objects.filter(id_usuario=usuario).values_list("numero", "orden")
            )
            numero_key = cedula_key(data["cedulaProfesional"])
            if numero_key not in {cedula_key(numero) for numero, _ in existentes}:
                DetUsuarioCedula.objects.create(
                    id_usuario=usuario,
                    numero=data["cedulaProfesional"],
                    tipo="PROFESIONAL",
                    es_principal=not existentes,
                    orden=max((orden for _, orden in existentes), default=0) + 1,
                )
