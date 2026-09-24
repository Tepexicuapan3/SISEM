"""
apps/hospitalizacion/models.py
===============================
`HospitalAdmission` (bitacora de ingresos/altas hospitalarias, reemplaza
`his_hospital` del legado) + `HospitalAdmissionRevision` (versionado
append-only, NOM-024-SSA3).

Mismo mecanismo de proteccion que `ClinicalHistory`/`ClinicalHistoryRevision`
(apps/consulta_medica/models.py): el versionado NO vive en signals ni en un
override de `save()` de `HospitalAdmission` -- vive en el REPOSITORIO
(`apps.hospitalizacion.repositories.hospital_admission_repository`), envuelto
en `transaction.atomic()` en el USE-CASE
(`apps.hospitalizacion.uses_case.hospital_admission_usecase`). Ver Engram,
topic_key sdd/his-hospital-modelo-nom024/design, Decision 1.

MEJORA sobre `ClinicalHistoryRevision` (que hoy NO tiene esta proteccion):
`HospitalAdmissionRevision.save()`/`.delete()` bloquean re-guardado/borrado
una vez que la revision ya tiene PK (ver Decision 2 del design).
"""
from django.core.exceptions import ValidationError
from django.db import models


class HospitalAdmission(models.Model):
    """
    Un ingreso/alta hospitalario. Se captura de forma incremental: el alta
    (fechas/hora/medico/tipo de alta) puede no existir todavia al momento
    del ingreso. Las EDICIONES (pisar un valor ya cargado) SI quedan
    versionadas -- ver `HospitalAdmissionRevision` y el repositorio.

    `admitting_doctor`/`discharge_doctor`/`origin_center` son nullable con
    su codigo crudo (`*_code_legacy`) SIEMPRE poblado: la carga de datos del
    legado puede llegar antes de que el catalogo/medico correspondiente este
    resuelto. Ver `resolve_pending_fk()` para el backfill diferido que NO
    genera revision.
    """

    id = models.BigAutoField(primary_key=True, db_column="id_ingreso")

    # Identidad de la fila del legado -- NO editable, NO versionado (ver
    # Decision 1 del design: cambiar esto es otro registro, no una edicion).
    legacy_folio = models.CharField(max_length=20, unique=True, null=True, blank=True, db_column="folio_legado")
    hospital_service_folio = models.CharField(max_length=20, null=True, blank=True, db_column="folio_servicio")

    no_exp = models.CharField(max_length=20, db_column="no_exp")
    pk_num = models.IntegerField(default=0, db_column="pk_num")

    admission_type = models.ForeignKey(
        "catalogos.CatTipoHospitalizacion", db_column="id_tipo_hospitalizacion",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    reason = models.TextField(db_column="motivo")
    admission_date = models.DateField(db_column="fecha_ingreso")
    admission_time = models.TimeField(null=True, blank=True, db_column="hora_ingreso")

    admitting_doctor = models.ForeignKey(
        "medicos.CatMedico", db_column="id_medico_ingreso",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    # Codigo crudo de `his_hospital.cd_medicoing`, SIEMPRE guardado -- puente
    # de trazabilidad al legado, NO editable, NO versionado.
    admitting_doctor_code_legacy = models.CharField(max_length=10, null=True, blank=True, db_column="clave_medico_ingreso_legado")

    # Timestamp de CAPTURA del ingreso (distinto de admission_date, que es la
    # fecha real del ingreso) -- auditoria de creacion en el legado, historica.
    registered_at = models.DateTimeField(null=True, blank=True, db_column="fch_registro_ingreso")
    # Sin puente a SyUsuario: valores mixtos (username / no. de empleado) de
    # cat_usuarios (DBSIIM, otra base). Solo texto crudo.
    registered_by_code_legacy = models.CharField(max_length=20, null=True, blank=True, db_column="clave_usuario_ingreso_legado")
    clinical_note_code_legacy = models.CharField(max_length=20, null=True, blank=True, db_column="folio_nota_legado")

    discharge_date = models.DateField(null=True, blank=True, db_column="fecha_alta")
    discharge_time = models.TimeField(null=True, blank=True, db_column="hora_alta")
    discharge_doctor = models.ForeignKey(
        "medicos.CatMedico", db_column="id_medico_alta",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    discharge_doctor_code_legacy = models.CharField(max_length=10, null=True, blank=True, db_column="clave_medico_alta_legado")
    discharge_type = models.ForeignKey(
        "catalogos.CatTipoAlta", db_column="id_tipo_alta",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )

    is_scheduled = models.BooleanField(default=False, db_column="es_programado")

    origin_center = models.ForeignKey(
        "catalogos.CatCentroAtencion", db_column="id_centro_origen",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    # Codigo crudo de `his_hospital.cd_origeno` -- puente via
    # CatCentroAtencion.legacy_cd_clinica (migracion catalogos/0029).
    origin_center_code_legacy = models.IntegerField(null=True, blank=True, db_column="clave_clinica_origen_legado")

    external_folio = models.CharField(max_length=20, null=True, blank=True, db_column="folio_externo")

    # Soft-delete UNICAMENTE -- nunca DELETE fisico (retencion NOM-024, 5
    # anios desde el ultimo acto medico).
    is_active = models.BooleanField(default=True, db_column="est_activo")

    created_at = models.DateTimeField(auto_now_add=True, db_column="fch_alta")
    updated_at = models.DateTimeField(auto_now=True, db_column="fch_modf")
    deleted_at = models.DateTimeField(null=True, blank=True, db_column="fch_baja")
    created_by_id = models.BigIntegerField(null=True, blank=True, db_column="usr_alta")
    updated_by_id = models.BigIntegerField(null=True, blank=True, db_column="usr_modf")
    deleted_by_id = models.BigIntegerField(null=True, blank=True, db_column="usr_baja")

    class Meta:
        db_table = "hsp_admission"
        # Sin UniqueConstraint en (no_exp, pk_num): a diferencia de
        # ClinicalHistory (un registro por paciente), un paciente tiene N
        # ingresos hospitalarios a lo largo del tiempo.
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="hsp_admission_no_exp_pk_idx"),
            models.Index(fields=["admission_date"], name="hsp_admission_admdate_idx"),
            models.Index(fields=["is_active"], name="hsp_admission_active_idx"),
        ]
        ordering = ["-admission_date"]

    def __str__(self) -> str:
        return f"Ingreso {self.id} — {self.no_exp} ({self.admission_date})"

    @property
    def is_discharged(self) -> bool:
        return self.discharge_date is not None

    @property
    def length_of_stay_days(self):
        if self.discharge_date is None:
            return None
        return (self.discharge_date - self.admission_date).days

    @classmethod
    def resolve_pending_fk(cls, *, field, code_field, lookup):
        """Puentea un codigo legado crudo -> FK real, SIN generar revision.

        Guarda dura, por construccion: solo toca filas donde `field` es NULL
        y `code_field` NO es NULL -- transicion NULL -> valor, jamas
        valor -> otro valor (si la FK ya esta resuelta, esta fila se ignora
        y una reasignacion real tiene que pasar por
        `HospitalAdmissionRepository.update()`, que SI versiona).

        Usa `QuerySet.update()` a proposito: no pasa por `save()`, no
        dispara `auto_now` sobre `updated_at`, no llama al repositorio.
        Mismo criterio que `ContratoOxigeno.refresh_estados`
        (contratos_oxigeno/models.py), que usa `bulk_update` para no pisar
        `fch_modf`.

        No es una excepcion a la regla de dirty-check de
        `ClinicalHistoryRepository.update` (`getattr(...) not in (None, "")`
        -> vacio no versiona): es la MISMA regla, aplicada en la capa de
        carga de datos. `field`/`code_field` son nombres de columna del
        modelo (ej. `"admitting_doctor"`, `"admitting_doctor_code_legacy"`).
        `lookup` es un dict {codigo_crudo: valor_pk_resuelto} ya calculado
        por el caller (ej. `{legacy_cd_medico: id_medico}`).

        Deja un `AuditoriaEvento` de accion de SISTEMA (no una edicion
        clinica/administrativa normal) -- ver
        `apps.hospitalizacion.uses_case.hospital_admission_usecase`
        para el wrapper que arma ese evento; este metodo solo hace el
        `UPDATE` masivo.
        """
        pending = cls.objects.filter(**{f"{field}__isnull": True, f"{code_field}__isnull": False})
        resolved = 0
        for raw_code, resolved_value in lookup.items():
            resolved += pending.filter(**{code_field: raw_code}).update(**{field: resolved_value})
        return resolved


class HospitalAdmissionRevision(models.Model):
    """
    Snapshot del valor de `HospitalAdmission` justo ANTES de que se
    sobrescriba (ver `HospitalAdmissionRepository.update`). Mismo patron que
    `ClinicalHistoryRevision` -- versionado real requerido por NOM-024-SSA3,
    reemplaza el anti-patron confirmado del legado
    (`body-altaing.jsp:410` pisa `fe_alta` in-place sin dejar rastro; ver
    Engram, topic_key discovery/his-hospital-update-destructivo).

    MEJORA sobre `ClinicalHistoryRevision`: `save()`/`delete()` bloquean
    modificar/borrar una revision ya persistida (append-only REAL, no solo
    por convencion) y `change_reason` captura el "por que" del cambio.
    """

    admission = models.ForeignKey(
        HospitalAdmission, db_column="id_ingreso",
        on_delete=models.CASCADE, related_name="revisions",
    )

    previous_reason = models.TextField(null=True, blank=True, db_column="motivo_anterior")
    previous_admission_type = models.ForeignKey(
        "catalogos.CatTipoHospitalizacion", db_column="id_tipo_hospitalizacion_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_admission_date = models.DateField(null=True, blank=True, db_column="fecha_ingreso_anterior")
    previous_admission_time = models.TimeField(null=True, blank=True, db_column="hora_ingreso_anterior")
    previous_admitting_doctor = models.ForeignKey(
        "medicos.CatMedico", db_column="id_medico_ingreso_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_discharge_date = models.DateField(null=True, blank=True, db_column="fecha_alta_anterior")
    previous_discharge_time = models.TimeField(null=True, blank=True, db_column="hora_alta_anterior")
    previous_discharge_doctor = models.ForeignKey(
        "medicos.CatMedico", db_column="id_medico_alta_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_discharge_type = models.ForeignKey(
        "catalogos.CatTipoAlta", db_column="id_tipo_alta_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_is_scheduled = models.BooleanField(null=True, blank=True, db_column="es_programado_anterior")
    previous_origin_center = models.ForeignKey(
        "catalogos.CatCentroAtencion", db_column="id_centro_origen_anterior",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    previous_external_folio = models.CharField(max_length=20, null=True, blank=True, db_column="folio_externo_anterior")
    previous_is_active = models.BooleanField(null=True, blank=True, db_column="est_activo_anterior")

    # MEJORA sobre ClinicalHistoryRevision: el "por que" del cambio. NOM-024
    # pide quien/cuando/que; el por que es lo que hace auditable una
    # correccion de fecha de alta.
    change_reason = models.TextField(null=True, blank=True, db_column="motivo_cambio")
    changed_by_id = models.BigIntegerField(null=True, blank=True, db_column="usr_modf")
    changed_at = models.DateTimeField(auto_now_add=True, db_column="fch_modf")

    class Meta:
        db_table = "hsp_admission_revision"
        ordering = ["changed_at"]
        indexes = [
            models.Index(fields=["admission", "changed_at"], name="hsp_adm_rev_admission_idx"),
        ]

    def __str__(self) -> str:
        return f"Ingreso {self.admission_id} — revision {self.changed_at}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError(
                "HospitalAdmissionRevision es append-only (NOM-024-SSA3): "
                "una revision ya persistida no se modifica."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "HospitalAdmissionRevision es append-only (NOM-024-SSA3): "
            "el historial de cambios no se borra."
        )
