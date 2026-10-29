from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.catalogos.models import TipoDeCitas
from apps.recepcion.models import Visit
from apps.recepcion.repositories.visit_repository import VisitRepository
from apps.recepcion.serializers import ListVisitsQuerySerializer
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


class ListVisitsQuerySerializerSearchTests(TestCase):
    """Tarea 1.3 (parte serializer): `q` exige minimo 3 caracteres."""

    def test_q_with_three_chars_is_valid(self):
        serializer = ListVisitsQuerySerializer(data={"q": "GAR"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["q"], "GAR")

    def test_q_shorter_than_three_chars_is_rejected(self):
        serializer = ListVisitsQuerySerializer(data={"q": "ab"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("q", serializer.errors)

    def test_q_is_optional(self):
        serializer = ListVisitsQuerySerializer(data={})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("q", serializer.validated_data)

    def test_pk_num_zero_is_accepted_by_serializer(self):
        # Gotcha D13: pkNum=0 es el titular, no debe tratarse como "ausente".
        serializer = ListVisitsQuerySerializer(data={"pkNum": 0})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["pkNum"], 0)


class VisitRepositorySearchFilterTests(TestCase):
    """Tareas 1.3/1.4: filtro `q` (icontains) y `pk_num` (exacto), separados."""

    def _make_visit(self, *, no_exp, pk_num, nombre_paciente, folio=None, status="en_espera"):
        return Visit.objects.create(
            folio=folio or f"VIS-{no_exp}-{pk_num}",
            patient=_paciente_de_llave(no_exp, pk_num),
            nombre_paciente=nombre_paciente,
            arrival_type=Visit.ArrivalType.WALK_IN,
            service_type=Visit.ServiceType.MEDICINA_GENERAL,
            status=status,
        )

    def test_q_matches_case_insensitive_by_name(self):
        match = self._make_visit(no_exp="100", pk_num=0, nombre_paciente="Juan Garcia Lopez")
        self._make_visit(no_exp="200", pk_num=0, nombre_paciente="Pedro Sanchez")

        visits, total, *_ = VisitRepository.list_paginated(page=1, page_size=20, q="GARC")

        self.assertEqual(total, 1)
        self.assertEqual(visits[0].id_visit, match.id_visit)

    def test_q_matches_by_folio_and_no_exp(self):
        by_folio = self._make_visit(
            no_exp="300", pk_num=0, nombre_paciente="Ana Ruiz", folio="VIS-ABC123",
        )
        by_no_exp = self._make_visit(no_exp="999888", pk_num=0, nombre_paciente="Luis Diaz")

        visits_folio, total_folio, *_ = VisitRepository.list_paginated(
            page=1, page_size=20, q="ABC123",
        )
        self.assertEqual(total_folio, 1)
        self.assertEqual(visits_folio[0].id_visit, by_folio.id_visit)

        visits_exp, total_exp, *_ = VisitRepository.list_paginated(
            page=1, page_size=20, q="999888",
        )
        self.assertEqual(total_exp, 1)
        self.assertEqual(visits_exp[0].id_visit, by_no_exp.id_visit)

    def test_q_too_short_is_a_serializer_concern_not_repository(self):
        # El repositorio no valida longitud -- eso es responsabilidad del
        # serializer (400 antes de ejecutar el icontains). Aca solo
        # confirmamos que un `q` de 2 caracteres, si llegara, seguiria
        # actuando como icontains normal (no es responsabilidad de esta capa
        # rechazarlo).
        self._make_visit(no_exp="400", pk_num=0, nombre_paciente="Ab Cd")
        visits, total, *_ = VisitRepository.list_paginated(page=1, page_size=20, q="Ab")
        self.assertEqual(total, 1)

    def test_q_digit_does_not_bleed_into_pk_num_filter(self):
        # Tarea 1.4: buscar "2" en `q` (sin pkNum) NO debe traer
        # automaticamente todos los integrantes pk_num=2 de otras familias.
        # Folio/no_exp/nombre de estas 2 visitas se eligen deliberadamente
        # SIN el digito "2" en ningun lado -- la unica forma en que "2"
        # aparece es como valor de `pk_num`, que NO debe participar de `q`.
        family_a_member_2 = self._make_visit(
            no_exp="100", pk_num=2, nombre_paciente="Carlos Mendez",
            folio="VIS-FAM-A",
        )
        family_b_member_2 = self._make_visit(
            no_exp="700", pk_num=2, nombre_paciente="Rosa Torres",
            folio="VIS-FAM-B",
        )
        # Unico registro cuyo nombre/folio/no_exp realmente contiene "2".
        matches_text = self._make_visit(
            no_exp="321", pk_num=0, nombre_paciente="Beatriz Contreras",
            folio="VIS-FAM-C",
        )

        visits, total, *_ = VisitRepository.list_paginated(page=1, page_size=20, q="2")

        ids = {v.id_visit for v in visits}
        self.assertIn(matches_text.id_visit, ids)
        self.assertNotIn(family_a_member_2.id_visit, ids)
        self.assertNotIn(family_b_member_2.id_visit, ids)
        self.assertEqual(total, len(ids))

    def test_pk_num_combined_with_no_exp_isolates_exact_member(self):
        titular = self._make_visit(no_exp="100", pk_num=0, nombre_paciente="Titular Uno")
        dependiente_1 = self._make_visit(no_exp="100", pk_num=1, nombre_paciente="Dependiente Uno")
        dependiente_2 = self._make_visit(no_exp="100", pk_num=2, nombre_paciente="Dependiente Dos")

        visits, total, *_ = VisitRepository.list_paginated(
            page=1, page_size=20, no_exp="100", pk_num=2,
        )

        self.assertEqual(total, 1)
        self.assertEqual(visits[0].id_visit, dependiente_2.id_visit)

    def test_pk_num_zero_filters_titular_and_is_not_discarded(self):
        # Gotcha critico D13: `if pk_num:` descartaria pk_num=0 en silencio.
        # El filtro debe usar `is not None` para que 0 SI filtre por titular.
        titular = self._make_visit(no_exp="500", pk_num=0, nombre_paciente="Titular Cero")
        dependiente = self._make_visit(no_exp="500", pk_num=1, nombre_paciente="Dependiente")

        visits, total, *_ = VisitRepository.list_paginated(
            page=1, page_size=20, no_exp="500", pk_num=0,
        )

        self.assertEqual(total, 1)
        self.assertEqual(visits[0].id_visit, titular.id_visit)

    def test_pk_num_none_does_not_filter_at_all(self):
        # pk_num=None (parametro ausente) no debe aplicar ningun filtro.
        self._make_visit(no_exp="600", pk_num=0, nombre_paciente="A")
        self._make_visit(no_exp="600", pk_num=1, nombre_paciente="B")

        visits, total, *_ = VisitRepository.list_paginated(
            page=1, page_size=20, no_exp="600", pk_num=None,
        )

        self.assertEqual(total, 2)


class VisitRepositoryTipoCitaQueryTests(TestCase):
    """Tarea 3.4: `select_related('tipo_cita')` no debe introducir N+1."""

    def _make_visit_with_tipo_cita(self, *, no_exp, tipo_cita):
        return VisitRepository.create(
            no_exp=no_exp,
            pk_num=0,
            arrival_type=Visit.ArrivalType.WALK_IN,
            tipo_cita_id=tipo_cita.id,
        )

    def _fetch_and_serialize(self):
        visits, total, total_pages, doctor_nombres, cita_fechas = VisitRepository.list_paginated(
            page=1, page_size=20,
        )
        for visit in visits:
            VisitRepository.to_contract(visit, doctor_nombres, cita_fechas)

    def test_list_paginated_resolves_tipo_cita_nombre_without_extra_queries_per_row(self):
        tipo_a = TipoDeCitas.objects.create(name="Consulta general")
        tipo_b = TipoDeCitas.objects.create(name="Especialidad")
        self._make_visit_with_tipo_cita(no_exp="TC001", tipo_cita=tipo_a)

        with CaptureQueriesContext(connection) as one_visit_ctx:
            self._fetch_and_serialize()
        baseline_queries = len(one_visit_ctx.captured_queries)

        # 3 visitas mas, alternando tipo_cita -- si `select_related` faltara,
        # cada fila dispararia una query extra para resolver `tipo_cita.name`.
        self._make_visit_with_tipo_cita(no_exp="TC002", tipo_cita=tipo_b)
        self._make_visit_with_tipo_cita(no_exp="TC003", tipo_cita=tipo_a)
        self._make_visit_with_tipo_cita(no_exp="TC004", tipo_cita=tipo_b)

        with CaptureQueriesContext(connection) as many_visits_ctx:
            self._fetch_and_serialize()

        self.assertEqual(
            len(many_visits_ctx.captured_queries),
            baseline_queries,
            "el numero de queries no debe crecer con mas visitas con tipo_cita seteado (N+1)",
        )
