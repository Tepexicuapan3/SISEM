"""La app almacen_insumos no tenia NINGUN test antes de esta auditoria.
Estos cubren el fix de ConsumoConsulta.medico (CharField libre ->
ForeignKey real a medicos.CatMedico, ver migracion 0002_medico_fk_integrity).
paciente e id_cita quedan fuera de alcance a proposito -- ver memoria del
proyecto (sires/db-integrity/consumoconsulta-pendiente)."""

from django.contrib.auth.hashers import make_password
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.almacen_insumos.models.catalogos import Almacen, CatCategoriaInsumo, CatInsumo, CatUnidadMedida
from apps.almacen_insumos.models.kardex import ConsumoConsulta, ExistenciaAlmacen
from apps.almacen_insumos.serializers.kardex import ConsumoConsultaSerializer
from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.session_registry import start_session
from apps.catalogos.models import CatCentroAtencion
from apps.medicos.models import CatMedico


def _make_medico(username, nombre_completo):
    user = SyUsuario.objects.create(
        usuario=username, correo=f"{username}@example.com", clave_hash=make_password("x"),
        est_activo=True,
    )
    partes = nombre_completo.split()
    nombre, paterno = partes[0], partes[1] if len(partes) > 1 else ""
    materno = " ".join(partes[2:])
    DetUsuario.objects.create(
        id_usuario=user, nombre=nombre, paterno=paterno, materno=materno,
    )
    return CatMedico.objects.create(id_usuario=user)


def _make_almacen():
    centro = CatCentroAtencion.objects.create(
        name="Centro Test Almacen", code="ALM-TEST-001",
        center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
    )
    return Almacen.objects.create(nombre="Almacen Test", id_centro_atencion=centro)


class MedicoSerializerTests(TestCase):
    def setUp(self):
        self.almacen = _make_almacen()
        self.medico = _make_medico("medico_consumo_1", "Juan Perez Lopez")

    def test_medico_defaults_to_none_when_not_set(self):
        consumo = ConsumoConsulta.objects.create(id_almacen=self.almacen, fch_consumo="2026-01-01")

        data = ConsumoConsultaSerializer(consumo).data

        self.assertIsNone(data["medico"])

    def test_read_returns_medico_full_name_not_id(self):
        consumo = ConsumoConsulta.objects.create(
            id_almacen=self.almacen, fch_consumo="2026-01-01", medico=self.medico
        )

        data = ConsumoConsultaSerializer(consumo).data

        self.assertEqual(data["medico"], "Juan Perez Lopez")

    def test_write_with_valid_medico_name_resolves_fk(self):
        consumo = ConsumoConsulta.objects.create(id_almacen=self.almacen, fch_consumo="2026-01-01")

        serializer = ConsumoConsultaSerializer(
            consumo, data={"medico": "Juan Perez Lopez"}, partial=True
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.medico_id, self.medico.pk)

    def test_write_with_invalid_medico_name_is_rejected(self):
        consumo = ConsumoConsulta.objects.create(id_almacen=self.almacen, fch_consumo="2026-01-01")

        serializer = ConsumoConsultaSerializer(
            consumo, data={"medico": "No Existe"}, partial=True
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("medico", serializer.errors)

    def test_write_with_ambiguous_medico_name_is_rejected(self):
        _make_medico("medico_consumo_2", "Juan Perez Lopez")
        consumo = ConsumoConsulta.objects.create(id_almacen=self.almacen, fch_consumo="2026-01-01")

        serializer = ConsumoConsultaSerializer(
            consumo, data={"medico": "Juan Perez Lopez"}, partial=True
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("más de un médico", str(serializer.errors["medico"][0]))

    def test_clearing_medico_with_empty_string_sets_none(self):
        consumo = ConsumoConsulta.objects.create(
            id_almacen=self.almacen, fch_consumo="2026-01-01", medico=self.medico
        )

        serializer = ConsumoConsultaSerializer(consumo, data={"medico": ""}, partial=True)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertIsNone(updated.medico_id)

    def test_cannot_delete_medico_referenced_by_consumo(self):
        ConsumoConsulta.objects.create(
            id_almacen=self.almacen, fch_consumo="2026-01-01", medico=self.medico
        )

        with self.assertRaises(ProtectedError):
            self.medico.delete()


class ConsumoConsultaCreateApiTests(APITestCase):
    """Cubre create(), que arma el ConsumoConsulta a mano (no via
    serializer.save()) -- la resolucion de nombre de medico ahi es codigo
    separado que tambien necesitaba el fix."""

    def setUp(self):
        self.almacen = _make_almacen()
        self.medico = _make_medico("medico_consumo_api", "Ana Garcia Ruiz")

        actor = SyUsuario.objects.create(
            usuario="almacen_user", correo="almacen@example.com", clave_hash=make_password("x"),
            est_activo=True,
        )
        access, _refresh, _sid = start_session(actor, ip_address="127.0.0.1", user_agent="test-agent")
        self.client.cookies["access_token_cookie"] = access

    def test_create_with_valid_medico_name_resolves_fk(self):
        categoria = CatCategoriaInsumo.objects.create(nombre="Categoria Test")
        unidad = CatUnidadMedida.objects.create(nombre="Pieza", abreviacion="pz")
        insumo = CatInsumo.objects.create(
            nombre="Insumo Test", codigo="INS-TEST-001",
            id_categoria=categoria, id_unidad=unidad,
        )
        # Stock inicial para no chocar con InsufficientStockError al
        # registrar el detalle del consumo (fuera del foco de este test).
        ExistenciaAlmacen.objects.create(
            id_almacen=self.almacen, id_insumo=insumo, cantidad=10,
        )

        response = self.client.post(
            "/api/v1/almacen/consumos/",
            {
                "idAlmacen": self.almacen.pk,
                "medico": "Ana Garcia Ruiz",
                "fchConsumo": "2026-01-01",
                "detalles": [{"idInsumo": insumo.pk, "idLote": None, "cantidad": "1"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["medico"], "Ana Garcia Ruiz")

        consumo = ConsumoConsulta.objects.get(pk=response.data["id"])
        self.assertEqual(consumo.medico_id, self.medico.pk)

    def test_create_with_unknown_medico_name_returns_400(self):
        response = self.client.post(
            "/api/v1/almacen/consumos/",
            {
                "idAlmacen": self.almacen.pk,
                "medico": "Nombre Inventado",
                "fchConsumo": "2026-01-01",
                "detalles": [{"idInsumo": 999999, "idLote": None, "cantidad": "1"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no encontrado", response.data["detail"])


class MedicoSinUsuarioKardexTests(APITestCase):
    """R5/S5.3: un médico sin usuario (alta por import Excel; nombre propio en
    CatMedico) se resuelve por nombre, se serializa y se encuentra en la
    búsqueda del listado de consumos."""

    def setUp(self):
        self.almacen = _make_almacen()
        self.medico = CatMedico.objects.create(
            id=777, nombre="Laura", paterno="Mendoza", materno="Ortiz",
        )
        actor = SyUsuario.objects.create(
            usuario="almacen_user_sin", correo="almacen_sin@example.com",
            clave_hash=make_password("x"), est_activo=True,
        )
        access, _refresh, _sid = start_session(actor, ip_address="127.0.0.1", user_agent="test-agent")
        self.client.cookies["access_token_cookie"] = access

    def test_serializer_reads_name_of_medico_without_user(self):
        consumo = ConsumoConsulta.objects.create(
            id_almacen=self.almacen, fch_consumo="2026-01-01", medico=self.medico
        )

        data = ConsumoConsultaSerializer(consumo).data

        self.assertEqual(data["medico"], "Laura Mendoza Ortiz")

    def test_serializer_write_resolves_medico_without_user_by_name(self):
        consumo = ConsumoConsulta.objects.create(id_almacen=self.almacen, fch_consumo="2026-01-01")

        serializer = ConsumoConsultaSerializer(
            consumo, data={"medico": "Laura Mendoza Ortiz"}, partial=True
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.save().medico_id, self.medico.pk)

    def test_list_search_matches_medico_without_user_by_name_part(self):
        ConsumoConsulta.objects.create(
            id_almacen=self.almacen, fch_consumo="2026-01-01", medico=self.medico
        )
        otro = _make_medico("medico_consumo_otro", "Pedro Ruiz Soto")
        ConsumoConsulta.objects.create(
            id_almacen=self.almacen, fch_consumo="2026-01-02", medico=otro
        )

        response = self.client.get("/api/v1/almacen/consumos/", {"search": "Mendoza"})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        resultados = response.data["results"] if "results" in response.data else response.data["items"]
        self.assertEqual([r["medico"] for r in resultados], ["Laura Mendoza Ortiz"])

    def test_create_resolves_medico_without_user_by_name(self):
        categoria = CatCategoriaInsumo.objects.create(nombre="Categoria Sin Usuario")
        unidad = CatUnidadMedida.objects.create(nombre="Pieza SU", abreviacion="psu")
        insumo = CatInsumo.objects.create(
            nombre="Insumo SU", codigo="INS-SU-001", id_categoria=categoria, id_unidad=unidad,
        )
        ExistenciaAlmacen.objects.create(id_almacen=self.almacen, id_insumo=insumo, cantidad=10)

        response = self.client.post(
            "/api/v1/almacen/consumos/",
            {
                "idAlmacen": self.almacen.pk,
                "medico": "Laura Mendoza Ortiz",
                "fchConsumo": "2026-01-01",
                "detalles": [{"idInsumo": insumo.pk, "idLote": None, "cantidad": "1"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(ConsumoConsulta.objects.get(pk=response.data["id"]).medico_id, 777)
