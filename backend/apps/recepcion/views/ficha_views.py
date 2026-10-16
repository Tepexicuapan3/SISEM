"""
Endpoint (alias) para generar la Ficha de Consulta en PDF.
GET /api/v1/visits/{visit_id}/ficha

Delegado al caso de uso generico de ``apps.impresion`` (mismo guard,
bitacora y auditoria que ``/api/v1/impresion/ficha/{visit_id}``). El motor
(WeasyPrint | docx) se elige con ``settings.FICHA_ENGINE``.
"""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from apps.impresion.views import handle_print


@method_decorator(csrf_exempt, name="dispatch")
class FichaVisitView(APIView):
    """
    GET /visits/{visit_id}/ficha
    Descarga la ficha de consulta en PDF para la visita indicada.
    """

    authentication_classes = []
    permission_classes     = []

    def get(self, request, visit_id):
        return handle_print(request, "ficha", visit_id)
