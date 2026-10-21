"""La app contratos_oxigeno no tenia NINGUN test antes de esta auditoria.
Estos cubren especificamente el fix de sucursal (CharField libre ->
ForeignKey real a catalogos.CatSucursal, ver migracion
0005_sucursal_fk_integrity), que es el cambio de mas riesgo de esta ronda:
el contrato de API (leer/escribir el NOMBRE de la sucursal, no su id) tiene
que quedar identico al de antes."""

from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.authentication.models import SyUsuario
from apps.authentication.services.session_registry import start_session
from apps.catalogos.models import CatSucursal
from apps.contratos_oxigeno.models import ContratoOxigeno
from apps.contratos_oxigeno.serializers import ContratoOxigenoSerializer


def _contrato_kwargs(sucursal, **overrides):
    base = dict(
        sucursal=sucursal,
        num_contrato=f"CTR-{ContratoOxigeno.objects.count() + 1}",
        nombre="Paciente de Prueba",
        expediente="EXP001",
        clinica="Clinica Centro",
        servicio="CONCENTRADOR",
    )
    base.update(overrides)
    return base


class SucursalSerializerTests(TestCase):
    def setUp(self):
        self.matriz = CatSucursal.objects.create(name="MATRIZ")
        self.norte = CatSucursal.objects.create(name="NORTE")

    def test_read_returns_sucursal_name_not_id(self):
        contrato = ContratoOxigeno.objects.create(**_contrato_kwargs(self.matriz))

        data = ContratoOxigenoSerializer(contrato).data

        self.assertEqual(data["sucursal"], "MATRIZ")

    def test_write_with_valid_sucursal_name_resolves_fk(self):
        contrato = ContratoOxigeno.objects.create(**_contrato_kwargs(self.matriz))

        serializer = ContratoOxigenoSerializer(contrato, data={"sucursal": "NORTE"}, partial=True)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.sucursal_id, self.norte.id)

    def test_write_with_invalid_sucursal_name_is_rejected(self):
        contrato = ContratoOxigeno.objects.create(**_contrato_kwargs(self.matriz))

        serializer = ContratoOxigenoSerializer(contrato, data={"sucursal": "NO_EXISTE"}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn("sucursal", serializer.errors)

    def test_cannot_delete_sucursal_referenced_by_contrato(self):
        ContratoOxigeno.objects.create(**_contrato_kwargs(self.matriz))

        with self.assertRaises(ProtectedError):
            self.matriz.delete()


class ContratoOxigenoApiTests(APITestCase):
    def setUp(self):
        self.matriz = CatSucursal.objects.create(name="MATRIZ")
        self.norte = CatSucursal.objects.create(name="NORTE")
        user = SyUsuario.objects.create(
            usuario="oxigeno_user", correo="oxigeno@example.com", clave_hash="x", est_activo=True, cambiar_clave=False, terminos_acept=True,
        )
        access, _refresh, _sid = start_session(user, ip_address="127.0.0.1", user_agent="test-agent")
        self.client.cookies["access_token_cookie"] = access

    def test_estadisticas_por_sucursal_is_keyed_by_name(self):
        ContratoOxigeno.objects.create(**_contrato_kwargs(self.matriz))
        ContratoOxigeno.objects.create(**_contrato_kwargs(self.matriz))
        ContratoOxigeno.objects.create(**_contrato_kwargs(self.norte))

        response = self.client.get("/api/v1/contratos-oxigeno/estadisticas/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["porSucursal"], {"MATRIZ": 2, "NORTE": 1})

    def test_filter_by_sucursal_name_case_insensitive(self):
        # get_queryset() a nivel ORM -- no via HTTP: el action list() enriquece
        # con info_vigencia_por_expedientes(), que pega contra la conexion
        # 'expedientes' (Oracle, cross-DB) no disponible en este entorno de
        # test. Eso es preexistente y no tiene relacion con el fix de sucursal.
        ContratoOxigeno.objects.create(**_contrato_kwargs(self.matriz))
        ContratoOxigeno.objects.create(**_contrato_kwargs(self.norte))

        qs = ContratoOxigeno.objects.filter(sucursal__name__iexact="matriz")

        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().sucursal.name, "MATRIZ")
