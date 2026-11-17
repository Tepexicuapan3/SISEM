"""Redaccion de cada renglon de la receta impresa: la indicacion sale como
una frase que el paciente lee de corrido ("Tomar 1 tableta por via oral cada
8 horas durante 5 dias."), sin repetir el generico y con el envase en la
cantidad. Solo cambia la impresion: los datos guardados no se tocan."""

from django.test import SimpleTestCase

from apps.consulta_medica.impresion.receta import _administration_text, _drug_label, _quantity_unit


def _row(**kw):
    base = {
        "name": "", "generic_name": "", "presentation": "", "dose": "", "route": "",
        "route_label": "", "frequency": "", "duration": "", "indications": "", "quantity": 1,
    }
    return {**base, **kw}


IBUPROFENO = {"name": "IBUPROFENO 400 MG. TABLETA. CAJA CON 10", "generic_name": "IBUPROFENO"}
INSULINA = {
    "name": "INSULINA GLARGINA 100 UI/ML. SOLUCION INYECTABLE. PLUMA CON 3 ML",
    "generic_name": "INSULINA GLARGINA",
}


class AdministrationSentenceTests(SimpleTestCase):
    def test_oral_reads_as_one_sentence_with_tablet_unit(self):
        row = _row(**IBUPROFENO, dose="1", route="oral", route_label="Oral",
                   frequency="Cada 12 horas", duration="5 días",
                   indications="cada vez que se tenga dolor muy fuerte")
        self.assertEqual(
            _administration_text(row),
            "Tomar 1 tableta por vía oral cada 12 horas durante 5 días. "
            "Cada vez que se tenga dolor muy fuerte.",
        )

    def test_injectable_uses_aplicar_and_keeps_bare_dose(self):
        row = _row(**INSULINA, dose="10 UI", route="subcutanea", route_label="Subcutánea",
                   frequency="Cada 24 horas", duration="7 días")
        self.assertEqual(
            _administration_text(row), "Aplicar 10 UI por vía subcutánea cada 24 horas durante 7 días.",
        )

    def test_unit_is_plural_when_dose_is_more_than_one(self):
        row = _row(**IBUPROFENO, dose="2", route="oral", route_label="Oral", frequency="Cada 8 horas")
        self.assertEqual(_administration_text(row), "Tomar 2 tabletas por vía oral cada 8 horas.")

    def test_half_tablet_stays_singular(self):
        row = _row(**IBUPROFENO, dose="1/2", route="oral", route_label="Oral", frequency="Cada 8 horas")
        self.assertEqual(_administration_text(row), "Tomar 1/2 tableta por vía oral cada 8 horas.")

    def test_dose_with_unit_written_by_doctor_is_kept(self):
        row = _row(**IBUPROFENO, dose="1 tab", route="oral", route_label="Oral", frequency="Cada 8 horas")
        self.assertEqual(_administration_text(row), "Tomar 1 tab por vía oral cada 8 horas.")

    def test_single_dose_and_free_duration(self):
        row = _row(dose="1", route="intramuscular", route_label="Intramuscular",
                   frequency="Dosis única", duration="Hasta nueva indicación")
        self.assertEqual(
            _administration_text(row),
            "Aplicar 1 por vía intramuscular en dosis única hasta nueva indicación.",
        )

    def test_inhaled_uses_inhalar(self):
        row = _row(dose="2 disparos", route="inhalada", route_label="Inhalada", frequency="Cada 6 horas")
        self.assertEqual(_administration_text(row), "Inhalar 2 disparos por vía inhalada cada 6 horas.")

    def test_upper_case_capture_is_not_mangled(self):
        row = _row(route="oral", route_label="Oral", frequency="CADA 8 HRS", indications="CON ALIMENTOS")
        self.assertEqual(_administration_text(row), "Tomar por vía oral CADA 8 HRS. CON ALIMENTOS.")

    def test_indication_already_punctuated_is_not_doubled(self):
        row = _row(route="oral", route_label="Oral", frequency="Cada 8 horas", indications="Con agua!")
        self.assertEqual(_administration_text(row), "Tomar por vía oral cada 8 horas. Con agua!")

    def test_old_item_without_administration_prints_as_before(self):
        row = _row(dose="1 tab", indications="Cada 8 h")
        self.assertEqual(_administration_text(row), "1 tab · Cada 8 h")


class DrugLabelTests(SimpleTestCase):
    def test_secondary_does_not_repeat_the_generic(self):
        self.assertEqual(
            _drug_label(_row(**INSULINA)),
            {"primary": "INSULINA GLARGINA", "secondary": "100 UI/ML. SOLUCION INYECTABLE. PLUMA CON 3 ML"},
        )

    def test_name_that_does_not_start_with_generic_is_kept_whole(self):
        row = _row(name="Rivotril 2mg", generic_name="Clonazepam", presentation="Tableta")
        self.assertEqual(_drug_label(row), {"primary": "Clonazepam", "secondary": "Rivotril 2mg. Tableta"})


class QuantityUnitTests(SimpleTestCase):
    def test_container_from_presentation(self):
        self.assertEqual(_quantity_unit(_row(**IBUPROFENO, quantity=1)), "caja")
        self.assertEqual(_quantity_unit(_row(**INSULINA, quantity=2)), "plumas")

    def test_plural_of_consonant_ending(self):
        row = _row(name="SALBUTAMOL 100 MCG. SUSPENSION EN AEROSOL. INHALADOR CON 200 DOSIS", quantity=2)
        self.assertEqual(_quantity_unit(row), "inhaladores")

    def test_without_container_is_empty(self):
        self.assertEqual(_quantity_unit(_row(name="PARACETAMOL 500 MG", quantity=1)), "")


class MedicationBlockTests(SimpleTestCase):
    def _render(self, **item):
        from django.template.loader import render_to_string

        base = {"label": {"primary": "X", "secondary": ""}, "quantity": 2, "administration": "Tomar."}
        return render_to_string(
            "consulta_medica/impresion/receta/bloques/_medicamentos.html",
            {"sheet": {"items": [{**base, **item}], "first_number": 1}},
        )

    def test_quantity_shows_the_container(self):
        self.assertIn('<td class="qty">2<br><small>plumas</small></td>', self._render(quantity_unit="plumas"))

    def test_quantity_without_container_is_just_the_number(self):
        self.assertIn('<td class="qty">2</td>', self._render())

    def test_indication_cell_has_its_own_style(self):
        self.assertIn('<td class="admin">Tomar.</td>', self._render())
