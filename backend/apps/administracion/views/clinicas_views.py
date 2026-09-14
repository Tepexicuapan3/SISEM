"""
Listado de referencia de CatClinica (solo lectura, replicada de Oracle).
No es un catalogo administrable (no tiene create/update/delete) -- por eso
vive fuera de apps/catalogos, como un simple endpoint de referencia para
poblar selects en formularios (agenda de cirugias, solicitudes de
ambulancia, etc.). Cualquier usuario autenticado puede leerlo.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administracion.models import CatClinica

from .rbac_views import _authorize


class ClinicasListView(APIView):
    def get(self, request):
        user, error = _authorize(request)
        if error:
            return error

        clinicas = CatClinica.objects.order_by("ds_clinica")
        items = [
            {"id": clinica.cd_clinica, "name": clinica.ds_clinica}
            for clinica in clinicas
        ]
        return Response({"items": items, "total": len(items)}, status=status.HTTP_200_OK)
