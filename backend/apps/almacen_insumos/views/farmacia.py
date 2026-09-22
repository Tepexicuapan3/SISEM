from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.authentication.services.cookie_auth import CookieJWTAuthentication

from ..models.farmacia import MedicamentoInsumo
from ..serializers.farmacia import MedicamentoInsumoSerializer
from ._base import StandardListPagination


class MedicamentoInsumoViewSet(viewsets.ModelViewSet):
    """CRUD del mapeo Medicamento -> CatInsumo (sdd/dispensacion-farmacia).
    Mismo patron que CatInsumoViewSet (apps/almacen_insumos/views/catalogos.py)."""

    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = MedicamentoInsumoSerializer
    pagination_class = StandardListPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["medicamento__name", "insumo__nombre", "insumo__codigo"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = MedicamentoInsumo.objects.select_related("medicamento", "insumo").all()
        params = self.request.query_params

        if not params.get("includeInactive"):
            qs = qs.filter(is_active=True)

        if medicamento_id := params.get("medicamentoId"):
            qs = qs.filter(medicamento_id=medicamento_id)

        return qs
