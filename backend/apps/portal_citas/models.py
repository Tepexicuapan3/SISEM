"""
apps/portal_citas/models.py
============================

Modelo de datos del portal de autoservicio "Citas en Línea".

Estos modelos son 100% managed=True (Django crea y administra las tablas),
a diferencia de los catálogos replicados desde Oracle (CatEmpleado,
CatFamiliar) que viven en la BD "expedientes" con managed=False.

``no_exp`` / ``pk_num`` aquí NO son ForeignKey reales hacia CatEmpleado /
CatFamiliar: esos catálogos viven en otra base de datos (alias
"expedientes") y Django no permite FKs entre bases distintas. Se replican
como campos planos del mismo tipo/longitud, siguiendo la misma convención
que ya usan ``recepcion.Visit`` y ``recepcion.CitaMedica``.

Fase 1: solo modelo de datos. Sin vistas, serializers, autenticación,
lógica de OTP/JWT, PDF/QR ni tareas de Celery — eso es de fases posteriores.
"""

import uuid

from django.db import models


class PortalMiembro(models.Model):
    """
    Identidad de un trabajador o derechohabiente dentro del portal.

    ``no_exp`` / ``pk_num`` replican el esquema de identificación de
    paciente ya usado en ``recepcion.Visit`` / ``recepcion.CitaMedica``:
    ``pk_num`` = 0 es el propio trabajador (titular), > 0 es un
    derechohabiente (cat_familiar.pk_num).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identificación del núcleo familiar (mismo esquema que CatEmpleado/CatFamiliar,
    # sin FK real porque viven en la BD "expedientes").
    no_exp = models.CharField(max_length=20, db_index=True)
    pk_num = models.IntegerField(default=0)
    # Plan identidad, Fase 5: el registro (afiliacion) atendido. Se resuelve
    # solo al guardar: consulta_medica.services.operational_link_service.
    patient = models.ForeignKey(
        "consulta_medica.Patient", db_column="id_paciente", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )

    nombre_visible = models.CharField(max_length=150)
    es_titular_login = models.BooleanField(default=False)

    # Vacío hasta que se capture en una fase posterior.
    correo = models.EmailField(null=True, blank=True)
    correo_verificado = models.BooleanField(default=False)

    # Auditoría
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portal_miembros"
        unique_together = [("no_exp", "pk_num")]
        indexes = [
            models.Index(fields=["no_exp", "pk_num"], name="portal_miembro_noexp_pknum_idx"),
        ]

    def __str__(self):
        return f"{self.nombre_visible} ({self.no_exp}/{self.pk_num})"


class PortalSesion(models.Model):
    """
    Sesión de autoservicio activa. El ``id`` (UUID) es el valor que viaja
    embebido en el JWT emitido al miembro — la emisión/validación del
    token es lógica de una fase posterior, este modelo solo la respalda.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    portal_miembro = models.ForeignKey(
        PortalMiembro,
        on_delete=models.CASCADE,
        related_name="sesiones",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()
    ip_origen = models.GenericIPAddressField(null=True, blank=True)
    revocado = models.BooleanField(default=False)

    class Meta:
        db_table = "portal_sesiones"
        indexes = [
            models.Index(fields=["portal_miembro", "revocado"], name="portal_sesion_miembro_rev_idx"),
            models.Index(fields=["expira_en"], name="portal_sesion_expira_idx"),
        ]

    def __str__(self):
        return f"Sesión {self.id} — miembro {self.portal_miembro_id}"


class PortalOTP(models.Model):
    """
    Código de un solo uso (OTP) enviado por correo para validar la
    identidad del miembro. Nunca se guarda el código en texto plano —
    ``codigo_hash`` guarda su hash; el hasheo/verificación es lógica de
    una fase posterior.
    """

    portal_miembro = models.ForeignKey(
        PortalMiembro,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="otps",
    )
    correo_destino = models.EmailField()
    codigo_hash = models.CharField(max_length=255)
    expira_en = models.DateTimeField()
    intentos = models.PositiveSmallIntegerField(default=0)
    usado = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "portal_otps"
        indexes = [
            models.Index(fields=["correo_destino", "usado"], name="portal_otp_correo_usado_idx"),
        ]

    def __str__(self):
        return f"OTP para {self.correo_destino} (usado={self.usado})"
