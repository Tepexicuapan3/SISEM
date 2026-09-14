"""
Solicitudes de traslado en ambulancia entre unidades medicas propias
(traslado INTERNO, no ambulancia de emergencia externa). Equivalente
moderno de det_ambulancias/det_ambulanciasfec del legado
(java-main/investigacion/consolidado_assets/sisem/usuarios/clinicam/
body-ambulancia.jsp, body-fecambulancia.jsp).

Diferencias deliberadas frente al legado:
- El folio se genera de forma sincrona en la misma transaccion (igual que
  apps.pases.Referral), sin el token `temporal` del legado.
- La autorizacion depende del permiso RBAC `clinico:ambulancias:authorize`
  en vez de la contrasena guardada en `det_clinicas.pw_autoriza` del
  legado -- nunca se replica una contrasena en texto plano.
- El destino siempre se normaliza contra `CatDestinoAmbulancia` en vez de
  recapturar texto libre de direccion por solicitud (el legado tenia ambos).
- `legacy_folio` guarda el `cd_fsolicitud` original solo como referencia
  textual para una futura carga historica -- NUNCA debe usarse como FK; los
  catalogos del legado deben resolverse por NOMBRE/descripcion, nunca por ID
  crudo (`cd_motivoamb`, `cd_traslado`, `cd_servicioa`, `cd_dambulancia`).
"""
from django.db import models


class AmbulanceRequest(models.Model):
    class Status(models.TextChoices):
        ACTIVA = "activa", "Activa"
        BAJA = "baja", "Baja"

    class AuthorizationStatus(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        AUTORIZADA = "autorizada", "Autorizada"
        RECHAZADA = "rechazada", "Rechazada"

    id = models.BigAutoField(primary_key=True, db_column="id_solicitud")
    folio = models.CharField(max_length=32, unique=True, db_column="folio")
    legacy_folio = models.CharField(
        max_length=20, null=True, blank=True, db_column="folio_legado",
    )

    no_exp = models.CharField(max_length=20, db_column="no_exp", db_index=True)
    pk_num = models.IntegerField(db_column="pk_num", default=0)

    # CharField y NO ForeignKey: CatClinica vive en la base de datos
    # "expedientes" (ver routers.ExpedientesRouter), fisicamente distinta de
    # la BD "default" donde vive este modelo -- Postgres no soporta FK entre
    # bases de datos distintas. Se valida/resuelve por la capa de aplicacion.
    requesting_clinic_id = models.CharField(max_length=10, db_column="cd_clinica")
    requested_by_name = models.CharField(max_length=200, db_column="nombre_solicita")
    requested_by_relationship = models.ForeignKey(
        "catalogos.Parentesco", db_column="id_parentesco",
        on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    social_work_notes = models.TextField(
        null=True, blank=True, db_column="notas_trabajo_social",
    )

    reason = models.ForeignKey(
        "catalogos.CatMotivoTraslado", db_column="id_motivo",
        on_delete=models.PROTECT, related_name="+",
    )
    reason_notes = models.TextField(null=True, blank=True, db_column="notas_motivo")
    diagnosis_text = models.TextField(null=True, blank=True, db_column="diagnostico")

    origin_street = models.CharField(max_length=200, null=True, blank=True, db_column="calle_origen")
    origin_zip = models.CharField(max_length=10, null=True, blank=True, db_column="cp_origen")
    origin_neighborhood = models.CharField(max_length=150, null=True, blank=True, db_column="colonia_origen")
    origin_borough = models.CharField(max_length=150, null=True, blank=True, db_column="delegacion_origen")
    origin_phone = models.CharField(max_length=40, null=True, blank=True, db_column="telefono_origen")
    origin_reference = models.TextField(null=True, blank=True, db_column="referencia_origen")

    destination = models.ForeignKey(
        "catalogos.CatDestinoAmbulancia", db_column="id_destino",
        on_delete=models.PROTECT, related_name="+",
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVA,
        db_column="estatus",
    )
    authorization_status = models.CharField(
        max_length=20, choices=AuthorizationStatus.choices,
        default=AuthorizationStatus.PENDIENTE, db_column="estatus_autorizacion",
    )
    authorized_by_id = models.BigIntegerField(
        null=True, blank=True, db_column="autorizado_por",
    )
    authorized_at = models.DateTimeField(
        null=True, blank=True, db_column="fecha_autorizacion",
    )
    service_number = models.CharField(
        max_length=30, null=True, blank=True, db_column="no_servicio",
    )
    rejection_notes = models.TextField(null=True, blank=True, db_column="notas_rechazo")

    is_active = models.BooleanField(db_column="est_activo", default=True)
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="fch_modf", auto_now=True)
    deleted_at = models.DateTimeField(db_column="fch_baja", null=True, blank=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)
    updated_by_id = models.BigIntegerField(db_column="usr_modf", null=True, blank=True)
    deleted_by_id = models.BigIntegerField(db_column="usr_baja", null=True, blank=True)

    class Meta:
        db_table = "amb_request"
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="amb_request_patient_idx"),
            models.Index(fields=["authorization_status"], name="amb_request_authstatus_idx"),
        ]


class AmbulanceRequestSchedule(models.Model):
    """Fechas/horarios de traslado, 1:N con la solicitud. Reemplaza det_ambulanciasfec."""

    class Status(models.TextChoices):
        ACTIVA = "activa", "Activa"
        BAJA = "baja", "Baja"

    id = models.BigAutoField(primary_key=True, db_column="id_solicitud_fecha")
    request = models.ForeignKey(
        AmbulanceRequest, db_column="id_solicitud",
        on_delete=models.PROTECT, related_name="schedules",
    )
    transfer_date = models.DateField(db_column="fecha_traslado")
    transfer_time = models.TimeField(db_column="hora_traslado")
    transfer_type = models.ForeignKey(
        "catalogos.CatTipoTraslado", db_column="id_tipo_traslado",
        on_delete=models.PROTECT, related_name="+",
    )
    service_type = models.ForeignKey(
        "catalogos.CatTipoServicioAmbulancia", db_column="id_tipo_servicio",
        on_delete=models.PROTECT, related_name="+",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVA,
        db_column="estatus",
    )
    created_at = models.DateTimeField(db_column="fch_alta", auto_now_add=True)
    created_by_id = models.BigIntegerField(db_column="usr_alta", null=True, blank=True)

    class Meta:
        db_table = "amb_request_schedule"
        indexes = [
            models.Index(fields=["request"], name="amb_reqsched_request_idx"),
        ]
