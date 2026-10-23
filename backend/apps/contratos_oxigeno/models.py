from datetime import date

from django.db import models


class ContratoOxigeno(models.Model):

    class Status(models.TextChoices):
        VIGENTE    = "VIGENTE",    "Vigente"
        VENCIDO    = "VENCIDO",    "Vencido"
        POR_VENCER = "POR_VENCER", "Por Vencer"

    class TpDer(models.TextChoices):
        TITULAR    = "T", "Titular"
        ESPOSA     = "E", "Esposa/o"
        JUBILADO   = "J", "Jubilado"
        PENSIONADO = "P", "Pensionado"
        FAMILIAR   = "F", "Familiar"
        OTRO       = "O", "Otro"

    sucursal      = models.ForeignKey(
        "catalogos.CatSucursal",
        on_delete=models.PROTECT,
        related_name="contratos_oxigeno",
    )
    num_contrato  = models.CharField(max_length=50, unique=True)
    nombre        = models.CharField(max_length=200)
    expediente    = models.CharField(max_length=50)
    # pk_num = 0 → el propio trabajador (cat_empleados.no_exp).
    # pk_num > 0 → derechohabiente (cat_familiar.pk_num), ya que el mismo
    # expediente se repite entre varios familiares de un mismo trabajador.
    pk_num        = models.IntegerField(default=0)
    # Plan identidad, Fase 5: el registro (afiliacion) atendido. Se resuelve
    # solo al guardar: consulta_medica.services.operational_link_service.
    patient = models.ForeignKey(
        "consulta_medica.Patient", db_column="id_paciente", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    # Capturada al seleccionar el derechohabiente/trabajador en el buscador.
    # Se persiste porque cat_empleados/cat_familiar.no_edad puede quedar
    # desactualizado; la fecha de nacimiento nunca cambia, así que la edad
    # se recalcula siempre a partir de ella (ver fecha_service.calcular_edad).
    fecha_nacimiento = models.DateField(null=True, blank=True)
    tp_der        = models.CharField(max_length=100, default=TpDer.TITULAR, blank=True)
    clinica       = models.CharField(max_length=100)
    servicio      = models.CharField(max_length=100)
    servicio_2    = models.CharField(max_length=100, blank=True, null=True)
    servicio_3    = models.CharField(max_length=100, blank=True, null=True)
    # Teléfono de domicilio (tel_domicilio en formato_oxigeno.docx), distinto
    # de tel_oficina/celular de abajo.
    telefono      = models.CharField(max_length=20, blank=True)
    fecha_soporte  = models.DateField(null=True, blank=True)
    vigencia_meses = models.IntegerField(null=True, blank=True)
    vigencia_dias  = models.IntegerField(null=True, blank=True)
    fecha_renovar  = models.DateField(null=True, blank=True)
    dias_faltan    = models.IntegerField(null=True, blank=True)
    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.VIGENTE)
    diagnostico    = models.CharField(max_length=200, blank=True)

    # ── Domicilio desglosado (formato de oxígeno) ─────────────────────────────
    calle         = models.CharField(max_length=150, blank=True)
    num_ext       = models.CharField(max_length=20,  blank=True)
    num_int       = models.CharField(max_length=20,  blank=True)
    colonia       = models.CharField(max_length=100, blank=True)
    alcaldia      = models.CharField(max_length=100, blank=True)
    cp            = models.CharField(max_length=10,  blank=True)
    entre_calle_1 = models.CharField(max_length=150, blank=True)
    entre_calle_2 = models.CharField(max_length=150, blank=True)

    # ── Teléfonos adicionales (formato de oxígeno) ────────────────────────────
    tel_oficina = models.CharField(max_length=20, blank=True)
    celular     = models.CharField(max_length=20, blank=True)
    ext_tel     = models.CharField(max_length=10, blank=True)

    # ── Datos médicos del formato de oxígeno ──────────────────────────────────
    class HospitalAzura(models.TextChoices):
        CENTRO = "CENTRO", "Centro"
        VALLE  = "VALLE",  "Valle"

    hospital_azura             = models.CharField(max_length=10, choices=HospitalAzura.choices, blank=True)
    medico_tratante            = models.CharField(max_length=150, blank=True)
    especialidad      = models.ForeignKey(
        "catalogos.Especialidades",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contratos_oxigeno",
    )
    tercer_nivel                = models.BooleanField(default=False)
    institucion_referencia      = models.CharField(max_length=150, blank=True)
    medico_tratante_referencia  = models.CharField(max_length=150, blank=True)
    tramite_subsecuente         = models.BooleanField(default=False)

    fch_alta       = models.DateTimeField(auto_now_add=True)
    fch_modf       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = "contratos_oxigeno"
        ordering            = ["num_contrato"]
        verbose_name        = "Contrato de Oxígeno"
        verbose_name_plural = "Contratos de Oxígeno"

    # ── Cálculo automático de status ──────────────────────────────────────────

    def _recalculate_status(self) -> None:
        if self.fecha_renovar:
            self.dias_faltan = (self.fecha_renovar - date.today()).days
            if self.dias_faltan < 0:
                self.status = self.Status.VENCIDO
            elif self.dias_faltan <= 15:
                self.status = self.Status.POR_VENCER
            else:
                self.status = self.Status.VIGENTE
        else:
            self.dias_faltan = None
            self.status      = self.Status.VIGENTE

    def save(self, *args, **kwargs):
        self._recalculate_status()
        super().save(*args, **kwargs)

    @classmethod
    def refresh_estados(cls) -> None:
        """Recalcula dias_faltan/status de todos los contratos contra la fecha de hoy.

        dias_faltan y status dependen de date.today(), por lo que un valor
        guardado queda obsoleto con el paso de los días. Se refresca con
        bulk_update (sin pasar por save()) para no pisar fch_modf."""
        today      = date.today()
        contratos  = list(cls.objects.exclude(fecha_renovar__isnull=True))
        a_actualizar = []
        for c in contratos:
            dias = (c.fecha_renovar - today).days
            if dias < 0:
                estado = cls.Status.VENCIDO
            elif dias <= 15:
                estado = cls.Status.POR_VENCER
            else:
                estado = cls.Status.VIGENTE
            if c.dias_faltan != dias or c.status != estado:
                c.dias_faltan = dias
                c.status      = estado
                a_actualizar.append(c)
        if a_actualizar:
            cls.objects.bulk_update(a_actualizar, ["dias_faltan", "status"])

    def __str__(self) -> str:
        return f"{self.num_contrato} — {self.nombre}"
