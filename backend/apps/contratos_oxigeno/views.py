import math
from datetime import date, timedelta

from django.db.models import Count
from django.http import HttpResponse
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.authentication.services.cookie_auth import CookieJWTAuthentication
from apps.consulta_medica.services.paciente_entrada import llave_publica
from .derechohabiente_service import buscar_derechohabientes, info_vigencia_por_expedientes
from .document_service import generar_formato_oxigeno
from .email_service import build_vencimiento_html, enviar_notificacion
from .models import ContratoOxigeno
from .serializers import ContratoOxigenoSerializer


# ── Paginación estándar ── formato {items, page, pageSize, total, totalPages} ─

class StandardListPagination(PageNumberPagination):
    page_size              = 20
    page_size_query_param  = "pageSize"
    max_page_size          = 200
    page_query_param       = "page"

    def get_paginated_response(self, data):
        page_size   = self.get_page_size(self.request) or self.page_size
        total       = self.page.paginator.count
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return Response({
            "items":      data,
            "page":       self.page.number,
            "pageSize":   page_size,
            "total":      total,
            "totalPages": total_pages,
        })


# ── ViewSet ───────────────────────────────────────────────────────────────────

class ContratoOxigenoViewSet(viewsets.ModelViewSet):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated]
    serializer_class       = ContratoOxigenoSerializer
    pagination_class       = StandardListPagination
    filter_backends        = [filters.SearchFilter, filters.OrderingFilter]
    search_fields    = ["nombre", "num_contrato", "expediente", "diagnostico"]
    ordering_fields  = [
        "num_contrato", "nombre", "fecha_renovar",
        "dias_faltan", "status", "sucursal", "clinica",
    ]
    ordering = ["num_contrato"]

    def get_queryset(self):
        ContratoOxigeno.refresh_estados()
        qs     = ContratoOxigeno.objects.all()
        params = self.request.query_params

        if sucursal := params.get("sucursal"):
            qs = qs.filter(sucursal__name__iexact=sucursal)

        if status_val := params.get("status"):
            qs = qs.filter(status=status_val)

        if tp_der := params.get("tpDer"):
            qs = qs.filter(tp_der=tp_der)

        if clinica := params.get("clinica"):
            qs = qs.filter(clinica__icontains=clinica)

        return qs

    # ── GET /contratos-oxigeno/ ── lista, enriquecida con vigencia/edad/nacimiento ─

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        items = page if page is not None else queryset

        dh_info = info_vigencia_por_expedientes([llave_publica(c) for c in items])
        context = {**self.get_serializer_context(), "dh_info": dh_info}

        if page is not None:
            serializer = self.get_serializer(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True, context=context)
        return Response(serializer.data)

    # ── GET /contratos-oxigeno/estadisticas/ ──────────────────────────────────

    @action(detail=False, methods=["get"], url_path="estadisticas")
    def estadisticas(self, request):
        ContratoOxigeno.refresh_estados()
        qs      = ContratoOxigeno.objects.all()
        today   = date.today()
        prox_30 = today + timedelta(days=30)

        por_status   = {
            item["status"]: item["total"]
            for item in qs.values("status").annotate(total=Count("id"))
        }
        por_sucursal = {
            item["sucursal__name"]: item["total"]
            for item in qs.values("sucursal__name").annotate(total=Count("id"))
        }

        return Response({
            "total":          qs.count(),
            "vigentes":       por_status.get("VIGENTE",    0),
            "porVencer":      por_status.get("POR_VENCER", 0),
            "vencidos":       por_status.get("VENCIDO",    0),
            "porStatus":      por_status,
            "porSucursal":    por_sucursal,
            "porVencer30Dias": qs.filter(
                fecha_renovar__gte=today,
                fecha_renovar__lte=prox_30,
            ).count(),
        })

    # ── GET /contratos-oxigeno/buscar-derechohabiente/ ────────────────────────

    @action(detail=False, methods=["get"], url_path="buscar-derechohabiente")
    def buscar_derechohabiente(self, request):
        q       = request.query_params.get("q", "").strip()
        clinica = request.query_params.get("clinica")

        if len(q) < 3:
            return Response({"results": []})

        return Response({"results": buscar_derechohabientes(q, clinica)})

    # ── GET /contratos-oxigeno/{id}/formato/ ── descarga el .docx llenado ─────

    @action(detail=True, methods=["get"], url_path="formato")
    def formato(self, request, pk=None):
        contrato  = self.get_object()
        docx_bytes = generar_formato_oxigeno(contrato)

        response = HttpResponse(
            docx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        nombre_archivo = f"formato_oxigeno_{contrato.num_contrato}.docx"
        response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
        return response

    # ── POST /contratos-oxigeno/notificar/ ────────────────────────────────────

    @action(detail=False, methods=["post"], url_path="notificar")
    def notificar(self, request):
        destinatarios = request.data.get("destinatarios", [])
        asunto        = request.data.get("asunto", "").strip()
        cuerpo        = request.data.get("cuerpo",  "").strip()
        contratos_ids = request.data.get("contratosIds", [])

        if not destinatarios:
            return Response(
                {"error": "Se requiere al menos un destinatario."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not asunto:
            return Response(
                {"error": "El asunto es requerido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Si vienen IDs → generar HTML de vencimiento automáticamente
        if contratos_ids:
            contratos = ContratoOxigeno.objects.filter(id__in=contratos_ids)
            cuerpo_html = build_vencimiento_html(contratos, cuerpo_intro=cuerpo)
        else:
            # Redacción libre — envolver el texto en HTML mínimo
            cuerpo_escaped = cuerpo.replace("\n", "<br>")
            cuerpo_html = f"<div style='font-family:sans-serif;color:#374151'>{cuerpo_escaped}</div>"

        # Archivos adjuntos (multipart/form-data)
        adjuntos = [
            (f.name, f.read(), f.content_type)
            for f in request.FILES.values()
        ]

        try:
            resultado = enviar_notificacion(destinatarios, asunto, cuerpo_html, adjuntos or None)
            return Response(resultado)
        except Exception as exc:
            return Response(
                {"error": f"No se pudo enviar el correo: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
