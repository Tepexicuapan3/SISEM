from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import filters, serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services.cookie_auth import CookieJWTAuthentication
from apps.medicos.identity import annotate_display_name, with_identity
from apps.medicos.models import CatMedico

from ..models.catalogos import Almacen, CatInsumo, CatProveedor
from ..models.kardex import (
    ConteoFisico,
    ConteoFisicoDetalle,
    ConsumoConsulta,
    ConsumoConsultaDetalle,
    EntradaInventario,
    EntradaInventarioDetail,
    ExistenciaAlmacen,
    KardexMovimiento,
    LoteInsumo,
    SalidaInventario,
    SalidaInventarioDetail,
)
from ..serializers.kardex import (
    ConteoFisicoSerializer,
    ConsumoConsultaSerializer,
    EntradaInventarioSerializer,
    ExistenciaAlmacenSerializer,
    KardexMovimientoSerializer,
    LoteInsumoSerializer,
    LoteInsumoCreateSerializer,
    SalidaInventarioSerializer,
)
from ..services import kardex_service
from ._base import StandardListPagination


class LoteInsumoViewSet(viewsets.ModelViewSet):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]
    pagination_class       = StandardListPagination
    filter_backends        = [filters.SearchFilter, filters.OrderingFilter]
    search_fields          = ["num_lote", "id_insumo__nombre", "id_insumo__codigo"]
    ordering_fields        = ["num_lote", "fecha_caducidad", "fch_alta"]
    ordering               = ["-fch_alta"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return LoteInsumoCreateSerializer
        return LoteInsumoSerializer

    def get_queryset(self):
        qs = LoteInsumo.objects.select_related("id_insumo", "id_proveedor")
        id_insumo = self.request.query_params.get("idInsumo")
        if id_insumo:
            qs = qs.filter(id_insumo_id=id_insumo)
        return qs


class EntradaInventarioViewSet(viewsets.ModelViewSet):
    """ViewSet para registrar entradas de inventario con sus detalles.

    El payload de creación acepta:
    {
        "idAlmacen": int,
        "idProveedor": int | null,
        "numRemision": str,
        "fchEntrada": "YYYY-MM-DD",
        "observaciones": str,
        "detalles": [
            {
                "idInsumo": int,
                "idLote": int | null,
                "loteDatos": {"numLote": str, "fechaCaducidad": str | null} | null,
                "cantidad": str,
                "costoUnitario": str | null
            }
        ]
    }

    Si idLote es null y loteDatos está presente, se crea el lote automáticamente.
    """

    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]
    serializer_class       = EntradaInventarioSerializer
    pagination_class       = StandardListPagination
    filter_backends        = [filters.SearchFilter, filters.OrderingFilter]
    search_fields          = ["num_remision", "id_almacen__nombre", "id_proveedor__nombre"]
    ordering_fields        = ["fch_entrada", "created_at"]
    ordering               = ["-fch_entrada"]
    http_method_names      = ["get", "post", "head", "options"]  # sin PUT/PATCH/DELETE: entradas son inmutables

    def get_queryset(self):
        qs = EntradaInventario.objects.select_related(
            "id_almacen", "id_proveedor"
        ).prefetch_related(
            "detalles__id_insumo",
            "detalles__id_lote",
        )
        id_almacen = self.request.query_params.get("idAlmacen")
        if id_almacen:
            qs = qs.filter(id_almacen_id=id_almacen)
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data

        # ── Validar campos de cabecera ──────────────────────────────────────
        id_almacen  = data.get("idAlmacen")
        fch_entrada = data.get("fchEntrada")
        detalles    = data.get("detalles", [])

        if not id_almacen or not fch_entrada:
            return Response(
                {"detail": "idAlmacen y fchEntrada son requeridos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not detalles:
            return Response(
                {"detail": "Se requiere al menos un detalle."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            almacen   = Almacen.objects.get(pk=id_almacen)
            proveedor = CatProveedor.objects.get(pk=data["idProveedor"]) if data.get("idProveedor") else None
        except (Almacen.DoesNotExist, CatProveedor.DoesNotExist) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            entrada = EntradaInventario.objects.create(
                id_almacen    = almacen,
                id_proveedor  = proveedor,
                num_remision  = data.get("numRemision", ""),
                fch_entrada   = fch_entrada,
                observaciones = data.get("observaciones", ""),
                created_by_id = request.user.id_usuario,
            )

            for det in detalles:
                try:
                    insumo = CatInsumo.objects.get(pk=det["idInsumo"])
                except CatInsumo.DoesNotExist:
                    raise drf_serializers.ValidationError(
                        f"Insumo {det.get('idInsumo')} no encontrado."
                    )

                lote = None
                if det.get("idLote"):
                    try:
                        lote = LoteInsumo.objects.get(pk=det["idLote"])
                    except LoteInsumo.DoesNotExist:
                        raise drf_serializers.ValidationError(
                            f"Lote {det.get('idLote')} no encontrado."
                        )
                elif det.get("loteDatos"):
                    ld = det["loteDatos"]
                    lote, _ = LoteInsumo.objects.get_or_create(
                        id_insumo=insumo,
                        num_lote=ld["numLote"],
                        defaults={
                            "id_proveedor": proveedor,
                            "fecha_caducidad": ld.get("fechaCaducidad"),
                        },
                    )

                EntradaInventarioDetail.objects.create(
                    id_entrada     = entrada,
                    id_insumo      = insumo,
                    id_lote        = lote,
                    cantidad       = Decimal(str(det["cantidad"])),
                    costo_unitario = Decimal(str(det["costoUnitario"])) if det.get("costoUnitario") else None,
                )
                # ↑ post_save signal → kardex_service.registrar_movimiento()

        serializer = EntradaInventarioSerializer(entrada, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class KardexMovimientoViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]
    serializer_class       = KardexMovimientoSerializer
    pagination_class       = StandardListPagination
    filter_backends        = [filters.SearchFilter, filters.OrderingFilter]
    search_fields          = ["id_insumo__nombre", "id_insumo__codigo", "tipo_movimiento"]
    ordering_fields        = ["fch_movimiento"]
    ordering               = ["-fch_movimiento"]

    def get_queryset(self):
        qs = KardexMovimiento.objects.select_related(
            "id_insumo", "id_lote", "id_almacen"
        )
        id_insumo  = self.request.query_params.get("idInsumo")
        id_almacen = self.request.query_params.get("idAlmacen")
        id_lote    = self.request.query_params.get("idLote")
        if id_insumo:
            qs = qs.filter(id_insumo_id=id_insumo)
        if id_almacen:
            qs = qs.filter(id_almacen_id=id_almacen)
        if id_lote:
            qs = qs.filter(id_lote_id=id_lote)
        return qs


class ExistenciaViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]
    serializer_class       = ExistenciaAlmacenSerializer
    pagination_class       = StandardListPagination
    filter_backends        = [filters.SearchFilter, filters.OrderingFilter]
    search_fields          = ["id_insumo__nombre", "id_insumo__codigo"]
    ordering_fields        = ["id_insumo__nombre", "cantidad"]
    ordering               = ["id_insumo__nombre"]

    def get_queryset(self):
        qs = ExistenciaAlmacen.objects.select_related(
            "id_insumo", "id_lote", "id_almacen"
        )
        id_almacen = self.request.query_params.get("idAlmacen")
        id_insumo  = self.request.query_params.get("idInsumo")
        solo_bajo  = self.request.query_params.get("soloBajoCritico")
        if id_almacen:
            qs = qs.filter(id_almacen_id=id_almacen)
        if id_insumo:
            qs = qs.filter(id_insumo_id=id_insumo)
        if solo_bajo:
            qs = qs.filter(cantidad__lte=F("id_insumo__stock_minimo"))
        return qs


# ─── Phase 3: Salidas ────────────────────────────────────────────────────────

class SalidaInventarioViewSet(viewsets.ModelViewSet):
    """POST payload:
    {
        "idAlmacen": int,
        "tipoSalida": "SALIDA"|"MERMA"|"DEVOLUCION",
        "numFolio": str,
        "fchSalida": "YYYY-MM-DD",
        "motivo": str,
        "detalles": [{"idInsumo": int, "idLote": int|null, "cantidad": str}]
    }
    """

    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]
    serializer_class       = SalidaInventarioSerializer
    pagination_class       = StandardListPagination
    filter_backends        = [filters.SearchFilter, filters.OrderingFilter]
    search_fields          = ["num_folio", "id_almacen__nombre", "motivo"]
    ordering_fields        = ["fch_salida", "created_at"]
    ordering               = ["-fch_salida"]
    http_method_names      = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = SalidaInventario.objects.select_related("id_almacen").prefetch_related(
            "detalles__id_insumo", "detalles__id_lote"
        )
        id_almacen  = self.request.query_params.get("idAlmacen")
        tipo_salida = self.request.query_params.get("tipoSalida")
        if id_almacen:
            qs = qs.filter(id_almacen_id=id_almacen)
        if tipo_salida:
            qs = qs.filter(tipo_salida=tipo_salida)
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data
        id_almacen = data.get("idAlmacen")
        fch_salida = data.get("fchSalida")
        detalles   = data.get("detalles", [])

        if not id_almacen or not fch_salida:
            return Response({"detail": "idAlmacen y fchSalida son requeridos."}, status=status.HTTP_400_BAD_REQUEST)
        if not detalles:
            return Response({"detail": "Se requiere al menos un detalle."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            almacen = Almacen.objects.get(pk=id_almacen)
        except Almacen.DoesNotExist as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                salida = SalidaInventario.objects.create(
                    id_almacen    = almacen,
                    tipo_salida   = data.get("tipoSalida", SalidaInventario.TipoSalida.SALIDA),
                    num_folio     = data.get("numFolio", ""),
                    fch_salida    = fch_salida,
                    motivo        = data.get("motivo", ""),
                    created_by_id = request.user.id_usuario,
                )

                for det in detalles:
                    try:
                        insumo = CatInsumo.objects.get(pk=det["idInsumo"])
                    except CatInsumo.DoesNotExist:
                        raise drf_serializers.ValidationError(f"Insumo {det.get('idInsumo')} no encontrado.")

                    lote = None
                    if det.get("idLote"):
                        try:
                            lote = LoteInsumo.objects.get(pk=det["idLote"])
                        except LoteInsumo.DoesNotExist:
                            raise drf_serializers.ValidationError(f"Lote {det.get('idLote')} no encontrado.")

                    SalidaInventarioDetail.objects.create(
                        id_salida = salida,
                        id_insumo = insumo,
                        id_lote   = lote,
                        cantidad  = Decimal(str(det["cantidad"])),
                    )
                    # ↑ post_save signal → kardex_service.registrar_movimiento()

        except kardex_service.InsufficientStockError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        serializer = SalidaInventarioSerializer(salida, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ─── Phase 4: Conteo Físico ──────────────────────────────────────────────────

class ConteoFisicoViewSet(viewsets.ModelViewSet):
    """POST /api/v1/almacen/conteos/ — crear conteo con detalles pre-cargados del sistema.
    POST /api/v1/almacen/conteos/{id}/cerrar/ — generar ajustes y cerrar.
    """

    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]
    serializer_class       = ConteoFisicoSerializer
    pagination_class       = StandardListPagination
    filter_backends        = [filters.SearchFilter, filters.OrderingFilter]
    search_fields          = ["id_almacen__nombre"]
    ordering_fields        = ["fch_conteo", "created_at"]
    ordering               = ["-fch_conteo"]
    http_method_names      = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = ConteoFisico.objects.select_related("id_almacen").prefetch_related(
            "detalles__id_insumo", "detalles__id_lote"
        )
        id_almacen = self.request.query_params.get("idAlmacen")
        if id_almacen:
            qs = qs.filter(id_almacen_id=id_almacen)
        return qs

    def create(self, request, *args, **kwargs):
        """Crea el conteo y pre-carga cant_sistema desde ExistenciaAlmacen."""
        data = request.data
        id_almacen = data.get("idAlmacen")
        fch_conteo = data.get("fchConteo")

        if not id_almacen or not fch_conteo:
            return Response({"detail": "idAlmacen y fchConteo son requeridos."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            almacen = Almacen.objects.get(pk=id_almacen)
        except Almacen.DoesNotExist as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            conteo = ConteoFisico.objects.create(
                id_almacen    = almacen,
                fch_conteo    = fch_conteo,
                observaciones = data.get("observaciones", ""),
                created_by_id = request.user.id_usuario,
            )
            # Pre-cargar cant_sistema desde ExistenciaAlmacen
            existencias = ExistenciaAlmacen.objects.filter(
                id_almacen=almacen
            ).select_related("id_insumo", "id_lote")

            for ex in existencias:
                ConteoFisicoDetalle.objects.create(
                    id_conteo    = conteo,
                    id_insumo    = ex.id_insumo,
                    id_lote      = ex.id_lote,
                    cant_sistema = ex.cantidad,
                    cant_fisica  = ex.cantidad,  # default igual — el usuario ajusta
                )

        serializer = ConteoFisicoSerializer(conteo, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="cerrar")
    def cerrar(self, request, pk=None):
        """Compara cant_fisica vs cant_sistema, genera AJUSTE_POS/NEG y cierra el conteo."""
        conteo = self.get_object()

        if conteo.cerrado:
            return Response({"detail": "El conteo ya está cerrado."}, status=status.HTTP_400_BAD_REQUEST)

        # Actualizar cant_fisica desde el payload si se envía
        actualizaciones = {str(d["id"]): d for d in request.data.get("detalles", [])}

        try:
            with transaction.atomic():
                for det in conteo.detalles.select_related("id_insumo", "id_lote"):
                    if str(det.pk) in actualizaciones:
                        det.cant_fisica = Decimal(str(actualizaciones[str(det.pk)].get("cantFisica", det.cant_fisica)))
                        det.save(update_fields=["cant_fisica"])

                    diferencia = det.cant_fisica - det.cant_sistema
                    if diferencia == 0:
                        continue

                    tipo = (
                        KardexMovimiento.TipoMovimiento.AJUSTE_POSITIVO
                        if diferencia > 0
                        else KardexMovimiento.TipoMovimiento.AJUSTE_NEGATIVO
                    )
                    kardex_service.registrar_movimiento(
                        insumo=det.id_insumo,
                        lote=det.id_lote,
                        almacen=conteo.id_almacen,
                        tipo=tipo,
                        cantidad=abs(diferencia),
                        ref_modelo="ConteoFisicoDetalle",
                        ref_id=det.pk,
                        created_by_id=request.user.id_usuario,
                    )

                conteo.cerrado    = True
                conteo.fch_cierre = timezone.now()
                conteo.save(update_fields=["cerrado", "fch_cierre"])

        except kardex_service.InsufficientStockError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response({"detail": "Conteo cerrado y ajustes aplicados."})


# ─── Phase 5: Dashboard ──────────────────────────────────────────────────────

class DashboardAlmacenView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]

    def get(self, request):
        hoy = date.today()

        total_insumos = CatInsumo.objects.filter(is_active=True).count()

        bajo_stock = (
            ExistenciaAlmacen.objects.filter(cantidad__lte=F("id_insumo__stock_minimo"))
            .values("id_insumo")
            .distinct()
            .count()
        )

        entradas_mes = EntradaInventario.objects.filter(
            fch_entrada__year=hoy.year, fch_entrada__month=hoy.month
        ).count()

        salidas_mes = SalidaInventario.objects.filter(
            fch_salida__year=hoy.year, fch_salida__month=hoy.month
        ).count()

        consumos_mes = ConsumoConsulta.objects.filter(
            fch_consumo__year=hoy.year, fch_consumo__month=hoy.month
        ).count()

        movimientos_recientes = KardexMovimiento.objects.select_related(
            "id_insumo", "id_almacen"
        ).order_by("-fch_movimiento")[:10]

        return Response({
            "totalInsumos":         total_insumos,
            "bajoStock":            bajo_stock,
            "entradasMes":          entradas_mes,
            "salidasMes":           salidas_mes,
            "consumosMes":          consumos_mes,
            "movimientosRecientes": KardexMovimientoSerializer(movimientos_recientes, many=True).data,
        })


# ─── Phase 6: Consumos por Consulta ─────────────────────────────────────────

class ConsumoConsultaViewSet(viewsets.ModelViewSet):
    """POST payload:
    {
        "idAlmacen": int,
        "idCita": int|null,
        "paciente": str,
        "medico": str,
        "fchConsumo": "YYYY-MM-DD",
        "observaciones": str,
        "detalles": [{"idInsumo": int, "idLote": int|null, "cantidad": str}]
    }
    """

    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]
    serializer_class       = ConsumoConsultaSerializer
    pagination_class       = StandardListPagination
    filter_backends        = [filters.SearchFilter, filters.OrderingFilter]
    search_fields          = ["paciente", "medico__id_usuario__detalle__nombre_completo",
                              "medico__nombre", "medico__paterno", "medico__materno",
                              "id_almacen__nombre"]
    ordering_fields        = ["fch_consumo", "created_at"]
    ordering               = ["-fch_consumo"]
    http_method_names      = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = with_identity(
            ConsumoConsulta.objects.select_related("id_almacen"), prefix="medico__"
        ).prefetch_related(
            "detalles__id_insumo", "detalles__id_lote"
        )
        id_almacen = self.request.query_params.get("idAlmacen")
        id_cita    = self.request.query_params.get("idCita")
        if id_almacen:
            qs = qs.filter(id_almacen_id=id_almacen)
        if id_cita:
            qs = qs.filter(id_cita=id_cita)
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data
        id_almacen  = data.get("idAlmacen")
        fch_consumo = data.get("fchConsumo")
        detalles    = data.get("detalles", [])

        if not id_almacen or not fch_consumo:
            return Response({"detail": "idAlmacen y fchConsumo son requeridos."}, status=status.HTTP_400_BAD_REQUEST)
        if not detalles:
            return Response({"detail": "Se requiere al menos un detalle."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            almacen = Almacen.objects.get(pk=id_almacen)
        except Almacen.DoesNotExist as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        medico = None
        medico_nombre = (data.get("medico") or "").strip()
        if medico_nombre:
            candidatos = list(
                annotate_display_name(CatMedico.objects.all()).filter(
                    medico_nombre=medico_nombre
                )[:2]
            )
            if not candidatos:
                return Response(
                    {"detail": f"Médico '{medico_nombre}' no encontrado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if len(candidatos) > 1:
                return Response(
                    {"detail": f"Hay más de un médico con el nombre '{medico_nombre}'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            medico = candidatos[0]

        try:
            with transaction.atomic():
                consumo = ConsumoConsulta.objects.create(
                    id_almacen    = almacen,
                    id_cita       = data.get("idCita"),
                    paciente      = data.get("paciente", ""),
                    medico        = medico,
                    fch_consumo   = fch_consumo,
                    observaciones = data.get("observaciones", ""),
                    created_by_id = request.user.id_usuario,
                )

                for det in detalles:
                    try:
                        insumo = CatInsumo.objects.get(pk=det["idInsumo"])
                    except CatInsumo.DoesNotExist:
                        raise drf_serializers.ValidationError(f"Insumo {det.get('idInsumo')} no encontrado.")

                    lote = None
                    if det.get("idLote"):
                        try:
                            lote = LoteInsumo.objects.get(pk=det["idLote"])
                        except LoteInsumo.DoesNotExist:
                            raise drf_serializers.ValidationError(f"Lote {det.get('idLote')} no encontrado.")

                    ConsumoConsultaDetalle.objects.create(
                        id_consumo = consumo,
                        id_insumo  = insumo,
                        id_lote    = lote,
                        cantidad   = Decimal(str(det["cantidad"])),
                    )
                    # ↑ post_save signal → kardex_service CONSUMO

        except kardex_service.InsufficientStockError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        serializer = ConsumoConsultaSerializer(consumo, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
