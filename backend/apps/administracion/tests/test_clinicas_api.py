"""
GET /clinicas: listado de cat_clinicas (replicada de Oracle) para los selects
de ambulancias y cirugias. Cualquier usuario con sesion lo lee; sin sesion, 401.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.catalogos.tests.test_designacion_api import _login_client

URL = "/api/v1/clinicas"


def _clinicas(*filas):
    # cat_clinicas vive en la base "expedientes", que no existe bajo los tests.
    return mock.patch(
        "apps.administracion.views.clinicas_views.CatClinica.objects.order_by",
        return_value=[SimpleNamespace(cd_clinica=cd, ds_clinica=nombre) for cd, nombre in filas],
    )


class ClinicasApiTests(TestCase):
    def test_con_sesion_de_cookies_lista_las_clinicas(self):
        client, _ = _login_client("clinicas_user", [])

        with _clinicas(("01", "CLINICA CENTRAL")):
            response = client.get(URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"], [{"id": "01", "name": "CLINICA CENTRAL"}])

    def test_sin_sesion_responde_401(self):
        with _clinicas():
            response = APIClient().get(URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
