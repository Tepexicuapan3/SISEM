"""Integridad de BD de la designacion de autorizadores (S1, S2 + vigencia/unicidad)."""
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.catalogos.models import DesignacionAlcance, DesignacionAutorizador

from .designacion_factories import add_scope, make_center, make_designation, make_user, get_tipo


class DesignacionAlcanceConstraintTests(TestCase):
    def setUp(self):
        self.designation = make_designation()
        self.center = make_center()

    def _create(self, **kwargs):
        with transaction.atomic():
            return DesignacionAlcance.objects.create(designation=self.designation, **kwargs)

    def test_s1_centro_y_tipo_a_la_vez_es_rechazado(self):
        with self.assertRaises(IntegrityError):
            self._create(scope_type="CENTRO", center=self.center, center_type="CLINICA")

    def test_s2_item_vacio_no_equivale_a_global(self):
        with self.assertRaises(IntegrityError):
            self._create(scope_type="CENTRO")
        with self.assertRaises(IntegrityError):
            self._create(scope_type="TIPO_CENTRO")

    def test_global_con_centro_o_tipo_es_rechazado(self):
        with self.assertRaises(IntegrityError):
            self._create(scope_type="GLOBAL", center=self.center)
        with self.assertRaises(IntegrityError):
            self._create(scope_type="GLOBAL", center_type="CLINICA")

    def test_tipo_centro_fuera_de_catalogo_es_rechazado(self):
        with self.assertRaises(IntegrityError):
            self._create(scope_type="TIPO_CENTRO", center_type="QUIROFANO")

    def test_items_validos_se_aceptan(self):
        self._create(scope_type="CENTRO", center=self.center)
        self._create(scope_type="TIPO_CENTRO", center_type="HOSPITAL")
        self._create(scope_type="GLOBAL")
        self.assertEqual(self.designation.scopes.count(), 3)

    def test_unicos_parciales_solo_aplican_a_items_activos(self):
        scope = add_scope(self.designation, "CENTRO", self.center)
        with self.assertRaises(IntegrityError):
            self._create(scope_type="CENTRO", center=self.center)

        scope.is_active = False
        scope.save(update_fields=["is_active"])
        self._create(scope_type="CENTRO", center=self.center)  # alta tras baja logica

    def test_un_solo_item_global_activo_por_designacion(self):
        add_scope(self.designation, "GLOBAL")
        with self.assertRaises(IntegrityError):
            self._create(scope_type="GLOBAL")

    def test_un_solo_item_por_tipo_de_centro_activo(self):
        add_scope(self.designation, "TIPO_CENTRO", "CLINICA")
        with self.assertRaises(IntegrityError):
            self._create(scope_type="TIPO_CENTRO", center_type="CLINICA")
        self._create(scope_type="TIPO_CENTRO", center_type="HOSPITAL")


class DesignacionAutorizadorConstraintTests(TestCase):
    def test_fe_fin_menor_a_fe_inicio_es_rechazada(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_designation(start=date(2026, 5, 10), end=date(2026, 5, 9))

    def test_fe_fin_igual_a_fe_inicio_es_valida(self):
        make_designation(start=date(2026, 5, 10), end=date(2026, 5, 10))

    def test_una_designacion_activa_por_usuario_y_tipo(self):
        user, tipo = make_user(), get_tipo()
        first = make_designation(user, tipo)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_designation(user, tipo)

        first.is_active = False
        first.deleted_at = timezone.now()
        first.save(update_fields=["is_active", "deleted_at"])
        make_designation(user, tipo)  # permitido tras la baja logica

    def test_mismo_usuario_con_otro_tipo_es_valido(self):
        user = make_user()
        make_designation(user, get_tipo())
        make_designation(user, get_tipo("XX", "Otro tipo"))
        self.assertEqual(DesignacionAutorizador.objects.filter(user=user).count(), 2)
