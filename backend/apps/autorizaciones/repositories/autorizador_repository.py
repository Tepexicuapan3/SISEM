"""Acceso a datos de autorizadores. Lee usuarios, cedulas y centros de sus
modulos dueños sin modificarlos."""
from datetime import timedelta

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.authentication.models import DetUsuarioCedula, SyUsuario
from apps.catalogos.models import CatCentroAtencion

from ..domain.vigencia import DIAS_AVISO_PREDETERMINADO, EstadoVigencia
from ..models import (
    Autorizador,
    AutorizadorAlcance,
    AutorizadorMovimiento,
    AutorizadorTipo,
    Motivo,
    TipoAutorizacion,
)


class AutorizadorRepository:
    # ------------------------------------------------------------------ #
    # Autorizador                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def base_queryset():
        return Autorizador.objects.select_related("usuario__detalle", "motivo_estatus")

    @staticmethod
    def obtener(id_autorizador):
        return AutorizadorRepository.base_queryset().filter(pk=id_autorizador).first()

    @staticmethod
    def obtener_para_actualizar(id_autorizador):
        """Solo dentro de transaction.atomic(). Bloquea solo la fila del autorizador."""
        return (
            Autorizador.objects.select_for_update(of=("self",))
            .filter(pk=id_autorizador)
            .first()
        )

    @staticmethod
    def existe_vigente_para_usuario(id_usuario, excluir_id=None):
        consulta = Autorizador.objects.filter(usuario_id=id_usuario, fecha_baja__isnull=True)
        if excluir_id:
            consulta = consulta.exclude(pk=excluir_id)
        return consulta.exists()

    @staticmethod
    def registrar_movimiento(
        autorizador, tipo_movimiento, *, id_usuario_responsable, motivo=None,
        descripcion_motivo=None, datos_anteriores=None, datos_nuevos=None, identificador_peticion=None,
    ):
        return AutorizadorMovimiento.objects.create(
            autorizador=autorizador,
            tipo_movimiento=tipo_movimiento,
            motivo=motivo,
            descripcion_motivo=descripcion_motivo,
            datos_anteriores=datos_anteriores,
            datos_nuevos=datos_nuevos,
            id_usuario_responsable=id_usuario_responsable,
            identificador_peticion=identificador_peticion,
        )

    @staticmethod
    def movimientos(id_autorizador):
        return (
            AutorizadorMovimiento.objects.filter(autorizador_id=id_autorizador)
            .select_related("motivo")
            .order_by("-id_movimiento")
        )

    # ------------------------------------------------------------------ #
    # Tipos y alcance                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def tipos_activos(id_autorizador):
        return list(
            AutorizadorTipo.objects.filter(
                autorizador_id=id_autorizador, esta_activo=True, fecha_baja__isnull=True,
            )
            .select_related("tipo_autorizacion")
            .order_by("tipo_autorizacion__clave")
        )

    @staticmethod
    def alcances_activos(ids_autorizador_tipo):
        return list(
            AutorizadorAlcance.objects.filter(
                autorizador_tipo_id__in=ids_autorizador_tipo, esta_activo=True, fecha_baja__isnull=True,
            )
            .select_related("centro_atencion")
            .order_by("id_autorizador_alcance")
        )

    @staticmethod
    def tipos_por_clave(claves):
        return {
            t.clave: t
            for t in TipoAutorizacion.objects.filter(clave__in=claves, esta_activo=True, fecha_baja__isnull=True)
        }

    @staticmethod
    def ids_centros_existentes(ids_centro):
        return set(CatCentroAtencion.objects.filter(pk__in=ids_centro).values_list("pk", flat=True))

    # ------------------------------------------------------------------ #
    # Usuarios y motivos (solo lectura)                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def usuario(id_usuario):
        return SyUsuario.objects.filter(pk=id_usuario).only("id_usuario", "est_activo").first()

    @staticmethod
    def usuario_tiene_cedula(id_usuario):
        return DetUsuarioCedula.objects.filter(id_usuario_id=id_usuario).exists()

    @staticmethod
    def cedulas_por_usuario(ids_usuario):
        resultado = {i: [] for i in ids_usuario}
        for cedula in DetUsuarioCedula.objects.filter(id_usuario_id__in=ids_usuario).order_by("orden"):
            resultado[cedula.id_usuario_id].append(cedula)
        return resultado

    @staticmethod
    def motivo(id_motivo):
        return Motivo.objects.filter(pk=id_motivo, esta_activo=True).first()

    # ------------------------------------------------------------------ #
    # Tareas programadas (F7)                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def ids_por_vencer(hoy, dias_aviso):
        """Activos o suspendidos cuya vigencia termina en los proximos `dias_aviso`
        dias y que todavia no tienen aviso para esa fecha de fin."""
        return AutorizadorRepository._sin_movimiento_para_su_fin(
            Autorizador.objects.filter(
                fecha_fin_vigencia__gte=hoy, fecha_fin_vigencia__lte=hoy + timedelta(days=dias_aviso),
            ),
            AutorizadorMovimiento.TipoMovimiento.AVISO_POR_VENCER,
        )

    @staticmethod
    def ids_vencidos_sin_registrar(hoy):
        return AutorizadorRepository._sin_movimiento_para_su_fin(
            Autorizador.objects.filter(fecha_fin_vigencia__lt=hoy),
            AutorizadorMovimiento.TipoMovimiento.VENCIMIENTO,
        )

    @staticmethod
    def _sin_movimiento_para_su_fin(consulta, tipo_movimiento):
        # Uno por fecha de fin: si se renueva y vuelve a vencer, es otro aviso.
        candidatos = consulta.filter(
            fecha_baja__isnull=True,
            estatus__in=[Autorizador.Estatus.ACTIVO, Autorizador.Estatus.SUSPENDIDO],
        ).values_list("pk", "fecha_fin_vigencia")
        registrados = set(
            AutorizadorMovimiento.objects.filter(
                tipo_movimiento=tipo_movimiento, autorizador_id__in=[pk for pk, _ in candidatos],
            ).values_list("autorizador_id", "datos_nuevos__fechaFinVigencia")
        )
        return [pk for pk, fin in candidatos.order_by("pk") if (pk, fin.isoformat()) not in registrados]

    @staticmethod
    def ids_usuarios_que_renuevan():
        """Usuarios activos que hoy pueden renovar autorizadores (admin:autorizadores:update).
        La decision final la toma el resolvedor central de permisos."""
        from apps.administracion.models import RelRolPermiso, RelUsuarioOverride, RelUsuarioRol
        from apps.administracion.services.rbac_resolver import RBACResolver

        permiso = "admin:autorizadores:update"
        roles = RelRolPermiso.objects.filter(
            fch_baja__isnull=True, id_permiso__codigo=permiso,
        ).values_list("id_rol", flat=True)
        con_rol = RelUsuarioRol.objects.filter(fch_baja__isnull=True).filter(
            Q(id_rol__is_admin=True) | Q(id_rol__in=roles)
        ).values_list("id_usuario", flat=True)
        con_excepcion = RelUsuarioOverride.objects.filter(
            fch_baja__isnull=True, efecto="ALLOW", id_permiso__codigo=permiso,
        ).values_list("id_usuario", flat=True)
        candidatos = SyUsuario.objects.filter(est_activo=True).filter(
            Q(pk__in=con_rol) | Q(pk__in=con_excepcion)
        ).order_by("pk")
        resultado = []
        for usuario in candidatos:
            efectivos = RBACResolver.get_effective_permissions(usuario)
            if "*" in efectivos or permiso in efectivos:
                resultado.append(usuario.pk)
        return resultado

    @staticmethod
    def usuarios_elegibles(busqueda, limite=20):
        ya_autorizador = Autorizador.objects.filter(
            usuario_id=OuterRef("pk"), fecha_baja__isnull=True,
        )
        consulta = (
            SyUsuario.objects.filter(est_activo=True)
            .exclude(Exists(ya_autorizador))
            .select_related("detalle")
            .annotate(tiene_cedula=Exists(DetUsuarioCedula.objects.filter(id_usuario_id=OuterRef("pk"))))
        )
        if busqueda:
            consulta = consulta.filter(
                Q(usuario__icontains=busqueda) | Q(detalle__nombre_completo__icontains=busqueda)
            )
        return list(consulta.order_by("usuario")[:limite])

    # ------------------------------------------------------------------ #
    # Listado con filtros                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def listar(*, busqueda=None, id_usuario=None, clave_tipo=None, id_centro=None, estatus=None,
               vigencia=None, fecha_inicio_desde=None, fecha_fin_hasta=None, hoy=None):
        hoy = hoy or timezone.localdate()
        consulta = AutorizadorRepository.base_queryset()

        if busqueda:
            consulta = consulta.filter(
                Q(usuario__usuario__icontains=busqueda)
                | Q(usuario__detalle__nombre_completo__icontains=busqueda)
                | Q(cargo__icontains=busqueda)
            )
        if id_usuario:
            consulta = consulta.filter(usuario_id=id_usuario)
        if estatus:
            consulta = consulta.filter(estatus=estatus)
        if fecha_inicio_desde:
            consulta = consulta.filter(fecha_inicio_vigencia__gte=fecha_inicio_desde)
        if fecha_fin_hasta:
            consulta = consulta.filter(fecha_fin_vigencia__lte=fecha_fin_hasta)

        if vigencia:
            limite_aviso = hoy + timedelta(days=DIAS_AVISO_PREDETERMINADO)
            consulta = consulta.filter({
                EstadoVigencia.PENDIENTE_INICIO: Q(fecha_inicio_vigencia__gt=hoy),
                EstadoVigencia.VENCIDO: Q(fecha_fin_vigencia__lt=hoy),
                EstadoVigencia.POR_VENCER: Q(
                    fecha_inicio_vigencia__lte=hoy, fecha_fin_vigencia__gte=hoy,
                    fecha_fin_vigencia__lte=limite_aviso,
                ),
                EstadoVigencia.VIGENTE: Q(fecha_inicio_vigencia__lte=hoy, fecha_fin_vigencia__gt=limite_aviso),
            }[EstadoVigencia(vigencia)])

        if clave_tipo or id_centro:
            tipos = AutorizadorTipo.objects.filter(
                autorizador_id=OuterRef("pk"), esta_activo=True, fecha_baja__isnull=True,
            )
            if clave_tipo:
                tipos = tipos.filter(tipo_autorizacion__clave=clave_tipo)
            if id_centro:
                # Cubre el centro: asignado directo, por su tipo de centro o GLOBAL.
                tipo_centro = (
                    CatCentroAtencion.objects.filter(pk=id_centro).values_list("center_type", flat=True).first()
                )
                tipos = tipos.filter(Exists(
                    AutorizadorAlcance.objects.filter(
                        autorizador_tipo_id=OuterRef("pk"), esta_activo=True, fecha_baja__isnull=True,
                    ).filter(
                        Q(tipo_alcance="CENTRO", centro_atencion_id=id_centro)
                        | Q(tipo_alcance="TIPO_CENTRO", tipo_centro=tipo_centro)
                        | Q(tipo_alcance="GLOBAL")
                    )
                ))
            consulta = consulta.filter(Exists(tipos))

        return consulta.order_by("-fecha_creacion", "-id_autorizador")
