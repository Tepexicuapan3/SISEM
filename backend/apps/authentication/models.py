from django.db import models
from django.db.models import CharField, F, Func, GeneratedField, Value
from django.db.models.functions import Coalesce, NullIf, Trim

# Postgres's CONCAT_WS()/CONCAT() are marked STABLE (not IMMUTABLE) because
# they accept a variadic "any" argument list, so they are rejected by
# Postgres in GENERATED column expressions ("la expresion de generacion no
# es inmutable"). We reproduce the same skip-empty-join semantics using only
# the IMMUTABLE `||` concatenation operator, NULLIF, COALESCE and TRIM.


def _name_part_with_trailing_space(field_name: str):
    # "<valor> " si el campo tiene contenido, "" si esta vacio/NULL.
    # Concatenar estas piezas y hacer TRIM() al final reproduce
    # " ".join(part for part in [nombre, paterno, materno] if part)
    # sin espacios sobrantes cuando alguna de las 3 partes esta vacia
    # (no solo materno -- nombre/paterno tambien pueden venir en "").
    return Coalesce(
        Func(
            NullIf(F(field_name), Value("")),
            Value(" "),
            template="%(expressions)s",
            arg_joiner=" || ",
            output_field=CharField(),
        ),
        Value(""),
        output_field=CharField(),
    )


_NOMBRE_COMPLETO_EXPRESSION = Trim(
    Func(
        _name_part_with_trailing_space("nombre"),
        _name_part_with_trailing_space("paterno"),
        _name_part_with_trailing_space("materno"),
        template="%(expressions)s",
        arg_joiner=" || ",
        output_field=CharField(max_length=255),
    )
)


class SyUsuario(models.Model):
    # Usuario principal para autenticacion.
    id_usuario = models.BigAutoField(primary_key=True, db_column="id_usuario")
    usuario = models.CharField(max_length=50, unique=True)
    correo = models.CharField(max_length=255, unique=True, null=True, blank=True)
    clave_hash = models.CharField(max_length=255)
    est_activo = models.BooleanField(db_index=True, default=True)
    est_bloqueado = models.BooleanField(db_index=True, default=False)
    cambiar_clave = models.BooleanField(default=False)
    terminos_acept = models.BooleanField(default=False)
    fch_terminos = models.DateTimeField(null=True, blank=True)
    last_conexion = models.DateTimeField(null=True, blank=True, db_index=True)
    ip_ultima = models.GenericIPAddressField(null=True, blank=True)
    fch_alta = models.DateTimeField(auto_now_add=True)
    fch_modf = models.DateTimeField(null=True, blank=True)
    fch_baja = models.DateTimeField(null=True, blank=True)
    usr_alta = models.ForeignKey(
        "self",
        db_column="usr_alta",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="usuarios_creados",
    )
    usr_modf = models.ForeignKey(
        "self",
        db_column="usr_modf",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="usuarios_modificados",
    )
    usr_baja = models.ForeignKey(
        "self",
        db_column="usr_baja",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="usuarios_baja",
    )

    class Meta:
        db_table = "sy_usuarios"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.usuario

    @property
    def is_authenticated(self):
        # DRF espera esta propiedad en el user.
        return True


class DetUsuario(models.Model):
    # Perfil del usuario.
    id_usuario = models.OneToOneField(
        SyUsuario,
        db_column="id_usuario",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="detalle",
    )
    nombre = models.CharField(max_length=80)
    paterno = models.CharField(max_length=80, null=True, blank=True)
    materno = models.CharField(max_length=80, null=True, blank=True)
    nombre_completo = GeneratedField(
        expression=_NOMBRE_COMPLETO_EXPRESSION,
        output_field=CharField(max_length=255),
        db_persist=True,
        db_index=True,
    )
    id_centro_atencion = models.ForeignKey(
        "catalogos.CatCentroAtencion",
        db_column="id_centro_atencion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    no_exp = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_column="no_exp",
    )
    id_area_clinica = models.ForeignKey(
        "catalogos.CatAreaClinica",
        db_column="id_area_clinica",
        db_constraint=False,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    cd_laboral = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column="cd_laboral",
    )
    id_escolaridad = models.ForeignKey(
        "catalogos.Escolaridad",
        db_column="id_escolaridad",
        db_constraint=False,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    id_escuela = models.ForeignKey(
        "catalogos.Escuelas",
        db_column="id_escuela",
        db_constraint=False,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    telefono  = models.CharField(max_length=20,  null=True, blank=True, db_column="telefono")
    direccion = models.CharField(max_length=255, null=True, blank=True, db_column="direccion")
    sexo      = models.CharField(max_length=1,   null=True, blank=True, db_column="sexo",
                                  choices=[("M","Masculino"),("F","Femenino"),("O","Otro")])
    fecha_nac = models.DateField(null=True, blank=True, db_column="fecha_nac")
    id_tipo_personal = models.ForeignKey(
        "catalogos.CatTipoPersonal",
        db_column="id_tipo_personal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        db_table = "det_usuarios"
        verbose_name = "Detalle Usuario"
        verbose_name_plural = "Detalles Usuarios"

    def __str__(self):
        return self.nombre_completo


class DetUsuarioCedula(models.Model):
    id = models.BigAutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        SyUsuario,
        db_column="id_usuario",
        on_delete=models.CASCADE,
        related_name="cedulas",
    )
    numero = models.CharField(max_length=30, db_column="numero")
    tipo = models.CharField(max_length=80, default="", db_column="tipo")
    es_principal = models.BooleanField(default=False, db_column="es_principal")
    orden = models.IntegerField(db_column="orden")

    class Meta:
        db_table = "det_usuario_cedulas"
        ordering = ["orden"]
        unique_together = [("id_usuario", "orden")]
        verbose_name = "Cédula de Usuario"
        verbose_name_plural = "Cédulas de Usuario"

    def __str__(self):
        return f"{self.tipo}: {self.numero}"


class SesionUsuario(models.Model):
    # Historial de conexiones (control de sesion unica + auditoria de accesos).
    class CierrePor(models.TextChoices):
        LOGOUT = "LOGOUT", "Logout"
        EXPIRACION = "EXPIRACION", "Expiración"

    id_sesion = models.BigAutoField(primary_key=True, db_column="id_sesion")
    usuario = models.ForeignKey(
        SyUsuario,
        db_column="id_usuario",
        on_delete=models.CASCADE,
        related_name="sesiones",
    )
    session_id = models.CharField(max_length=64, db_index=True)
    ip_origen = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    fch_inicio = models.DateTimeField(auto_now_add=True, db_index=True)
    fch_fin = models.DateTimeField(null=True, blank=True, db_index=True)
    cerrada_por = models.CharField(
        max_length=10, choices=CierrePor.choices, null=True, blank=True
    )

    class Meta:
        db_table = "sy_sesiones_usuario"
        ordering = ["-fch_inicio"]
        verbose_name = "Sesión de Usuario"
        verbose_name_plural = "Sesiones de Usuario"

    def __str__(self):
        return f"{self.usuario_id} @ {self.fch_inicio}"
