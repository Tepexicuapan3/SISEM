"""Parametros operativos por centro (change parametros-centro, reemplazo de ope_param)."""
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.administracion.models import AuditoriaEvento
from apps.catalogos.models import CatCentroAtencion, ParametroCentro, ParametroDefinicion
from apps.catalogos.services import parametro_service
from apps.catalogos.services.parametro_service import ParametroValueError, get_param, parse_value

from .designacion_factories import make_center
from .test_designacion_api import _login_client

URL = "/api/v1/parameters/"
SEEDED = {
    "citas.max_por_paciente_dia",
    "citas.max_por_expediente_dia",
    "portal.max_citas_futuras",
    "citas.anticipacion_checkin_min",
    "incapacidad.max_dias",
    "incapacidad.max_dias_maternidad",
    "receta.leyenda",
}


class _CacheIsolated:
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)


class SeedMigrationTests(_CacheIsolated, TestCase):
    def test_only_consumed_parameters_are_seeded(self):
        self.assertEqual(set(ParametroDefinicion.objects.values_list("key", flat=True)), SEEDED)

    def test_citas_limits_are_general_only(self):
        for key in (
            "citas.max_por_paciente_dia", "citas.max_por_expediente_dia", "portal.max_citas_futuras",
            "citas.anticipacion_checkin_min",
        ):
            self.assertFalse(ParametroDefinicion.objects.get(key=key).allows_center_override)

    def test_seeded_values(self):
        self.assertEqual(get_param("incapacidad.max_dias"), 60)
        self.assertEqual(get_param("receta.leyenda"), "CUIDA TU PESO, ALIMENTATE SANAMENTE")
        self.assertEqual(get_param("citas.anticipacion_checkin_min"), 30)


class ParseValueTests(TestCase):
    def _definition(self, value_type, min_value=None, max_value=None):
        return ParametroDefinicion(value_type=value_type, min_value=min_value, max_value=max_value)

    def test_integer_with_limits(self):
        definition = self._definition("ENTERO", Decimal("1"), Decimal("10"))
        self.assertEqual(parse_value(definition, " 7 "), 7)
        for bad in ("0", "11", "2.5", "abc", "NaN", ""):
            with self.subTest(bad=bad), self.assertRaises(ParametroValueError):
                parse_value(definition, bad)

    def test_boolean(self):
        definition = self._definition("BOOLEANO")
        self.assertIs(parse_value(definition, "S"), True)
        self.assertIs(parse_value(definition, "false"), False)
        with self.assertRaises(ParametroValueError):
            parse_value(definition, "tal vez")

    def test_decimal(self):
        self.assertEqual(parse_value(self._definition("DECIMAL"), "3000.50"), Decimal("3000.50"))


class GetParamTests(_CacheIsolated, TestCase):
    def setUp(self):
        super().setUp()
        self.center = make_center()
        self.other = make_center()
        self.definition = ParametroDefinicion.objects.get(key="incapacidad.max_dias")

    def test_center_override_wins_only_for_that_center(self):
        ParametroCentro.objects.create(definition=self.definition, center=self.center, value="30")
        self.assertEqual(get_param("incapacidad.max_dias", center_id=self.center.pk), 30)
        self.assertEqual(get_param("incapacidad.max_dias", center_id=self.other.pk), 60)
        self.assertEqual(get_param("incapacidad.max_dias"), 60)

    def test_override_ignored_when_definition_is_general_only(self):
        definition = ParametroDefinicion.objects.get(key="citas.max_por_paciente_dia")
        ParametroCentro.objects.create(definition=definition, center=self.center, value="5")
        self.assertEqual(get_param("citas.max_por_paciente_dia", center_id=self.center.pk), int(definition.general_value))

    def test_missing_definition_uses_default_or_raises(self):
        self.assertEqual(get_param("no.existe", default=7), 7)
        with self.assertRaises(LookupError):
            get_param("no.existe")

    def test_inactive_definition_uses_default(self):
        ParametroDefinicion.objects.filter(pk=self.definition.pk).update(is_active=False)
        self.assertEqual(get_param("incapacidad.max_dias", default=99), 99)

    def test_cache_unavailable_falls_back_to_db(self):
        with mock.patch.object(parametro_service.cache, "get", side_effect=ConnectionError("redis down")), \
                mock.patch.object(parametro_service.cache, "set", side_effect=ConnectionError("redis down")):
            self.assertEqual(get_param("incapacidad.max_dias"), 60)


class ParametroApiTests(_CacheIsolated, TestCase):
    def setUp(self):
        super().setUp()
        self.admin, _ = _login_client(
            "adm_param", ["admin:catalogos:parametros:read", "admin:catalogos:parametros:update"],
        )
        self.center = make_center()

    def test_requires_session_and_permission(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))
        reader, _ = _login_client("lector_param", ["admin:catalogos:parametros:read"])
        self.assertEqual(reader.get(URL).status_code, 200)
        response = reader.put(f"{URL}incapacidad.max_dias/", {"value": "30"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_list(self):
        response = self.admin.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual({p["key"] for p in response.data["items"]}, SEEDED)

    def test_update_general_validates_audits_and_refreshes_cache(self):
        self.assertEqual(get_param("incapacidad.max_dias"), 60)  # queda cacheado
        bad = self.admin.put(f"{URL}incapacidad.max_dias/", {"value": "0"}, format="json")
        self.assertEqual((bad.status_code, bad.data["code"]), (400, "VALIDATION_ERROR"))

        with self.captureOnCommitCallbacks(execute=True):
            ok = self.admin.put(f"{URL}incapacidad.max_dias/", {"value": "45"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data["parameter"]["generalValue"], "45")
        self.assertEqual(get_param("incapacidad.max_dias"), 45)
        event = AuditoriaEvento.objects.get(accion="ParameterGeneralUpdated")
        self.assertEqual((event.datos_antes["generalValue"], event.datos_despues["generalValue"]), ("60", "45"))

    def test_center_value_set_and_delete(self):
        url = f"{URL}incapacidad.max_dias/centers/{self.center.pk}/"
        with self.captureOnCommitCallbacks(execute=True):
            response = self.admin.put(url, {"value": "20"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["parameter"]["centerValues"][0]["value"], "20")
        self.assertEqual(get_param("incapacidad.max_dias", center_id=self.center.pk), 20)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.admin.delete(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_param("incapacidad.max_dias", center_id=self.center.pk), 60)
        self.assertTrue(AuditoriaEvento.objects.filter(accion="ParameterCenterValueDeleted").exists())

    def test_center_value_rejected_for_general_only_parameter(self):
        response = self.admin.put(
            f"{URL}citas.max_por_paciente_dia/centers/{self.center.pk}/", {"value": "2"}, format="json",
        )
        self.assertEqual((response.status_code, response.data["code"]), (409, "CENTER_OVERRIDE_NOT_ALLOWED"))

    def test_unknown_parameter_or_center_404(self):
        self.assertEqual(self.admin.get(f"{URL}no.existe/").status_code, 404)
        inactive = make_center()
        CatCentroAtencion.objects.filter(pk=inactive.pk).update(is_active=False)
        response = self.admin.put(f"{URL}incapacidad.max_dias/centers/{inactive.pk}/", {"value": "5"}, format="json")
        self.assertEqual((response.status_code, response.data["code"]), (404, "CENTER_NOT_FOUND"))

    def test_audit_failure_rolls_back(self):
        self.admin.raise_request_exception = False  # queremos ver el 500, no la excepcion
        with mock.patch(
            "apps.authentication.services.audit_service.AuditoriaEvento.objects.create",
            side_effect=RuntimeError("audit down"),
        ):
            response = self.admin.put(f"{URL}incapacidad.max_dias/", {"value": "45"}, format="json")
        self.assertGreaterEqual(response.status_code, 500)
        self.assertEqual(ParametroDefinicion.objects.get(key="incapacidad.max_dias").general_value, "60")
