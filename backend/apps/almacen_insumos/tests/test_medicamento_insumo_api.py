"""
sdd/dispensacion-farmacia, tarea 4.3: CRUD de MedicamentoInsumo, patron
CatInsumoViewSet. Done-criteria de tasks.md: alta duplicada -> 400.
"""
from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APITestCase

from apps.almacen_insumos.models.catalogos import CatCategoriaInsumo, CatInsumo, CatUnidadMedida
from apps.almacen_insumos.models.farmacia import MedicamentoInsumo
from apps.authentication.models import SyUsuario
from apps.authentication.services.session_registry import start_session
from apps.catalogos.models import Medicamentos


class MedicamentoInsumoApiTests(APITestCase):
    def setUp(self):
        categoria = CatCategoriaInsumo.objects.create(nombre="Categoria MedIns Test")
        unidad = CatUnidadMedida.objects.create(nombre="Unidad MedIns Test", abreviacion="u")
        self.insumo = CatInsumo.objects.create(
            nombre="Insumo MedIns Test", codigo="INS-MEDINS-001",
            id_categoria=categoria, id_unidad=unidad,
        )
        self.otro_insumo = CatInsumo.objects.create(
            nombre="Otro Insumo MedIns Test", codigo="INS-MEDINS-002",
            id_categoria=categoria, id_unidad=unidad,
        )
        self.medicamento = Medicamentos.objects.create(
            name="Medicamento MedIns Test", cuadro_basico=Medicamentos.CuadroBasico.BASICO,
        )

        actor = SyUsuario.objects.create(
            usuario="medins_user", correo="medins@example.com", clave_hash=make_password("x"),
            est_activo=True,
        )
        access, _refresh, _sid = start_session(actor, ip_address="127.0.0.1", user_agent="test-agent")
        self.client.cookies["access_token_cookie"] = access

    def test_alta_de_mapeo_valido(self):
        response = self.client.post(
            "/api/v1/almacen/medicamento-insumos/",
            {
                "idMedicamento": self.medicamento.id,
                "idInsumo": self.insumo.pk,
                "factorConversion": "2.0000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(
            MedicamentoInsumo.objects.filter(medicamento=self.medicamento, is_active=True).exists()
        )

    def test_alta_duplicada_es_rechazada(self):
        MedicamentoInsumo.objects.create(
            medicamento=self.medicamento, insumo=self.insumo, factor_conversion=1,
        )

        response = self.client.post(
            "/api/v1/almacen/medicamento-insumos/",
            {
                "idMedicamento": self.medicamento.id,
                "idInsumo": self.otro_insumo.pk,
                "factorConversion": "1.0000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            MedicamentoInsumo.objects.filter(medicamento=self.medicamento, is_active=True).count(), 1,
        )

    def test_edicion_y_baja_logica(self):
        mapeo = MedicamentoInsumo.objects.create(
            medicamento=self.medicamento, insumo=self.insumo, factor_conversion=1,
        )

        response = self.client.patch(
            f"/api/v1/almacen/medicamento-insumos/{mapeo.pk}/",
            {"factorConversion": "3.0000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        mapeo.refresh_from_db()
        self.assertEqual(mapeo.factor_conversion, 3)

        response = self.client.patch(
            f"/api/v1/almacen/medicamento-insumos/{mapeo.pk}/",
            {"isActive": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        mapeo.refresh_from_db()
        self.assertFalse(mapeo.is_active)
