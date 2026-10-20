"""Los call sites que imprimen el nombre del médico usan `identity.display_name`
(nombre del DetUsuario del usuario asociado; todo médico tiene usuario)."""

from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.medicos.tests.factories import crear_medico
from apps.medicos.uses_case.medico_usecase import list_medicos
from apps.portal_citas.services.pdf_comprobante_service import generar_pdf_comprobante
from apps.recepcion.models import CitaMedica, EstatusCita
from apps.recepcion.repositories.citas_repository import _serialize_cita
from apps.recepcion.services.notificacion_service import NotificacionCitaService
from apps.recepcion.uses_case.qr_checkin_usecase import _nombre_medico


class MedicoCallSitesTests(TestCase):
    def setUp(self):
        self.medico = crear_medico(
            id=4321, nombre="Rosa", paterno="Villalobos", materno="Cruz",
        )
        self.cita = CitaMedica.objects.create(
            folio=CitaMedica.generar_folio(), no_exp="40041", pk_num=0,
            medico=self.medico, fecha_hora=timezone.now() + timedelta(days=1),
            duracion_min=20, servicio_tipo="medicina_general",
            estatus=EstatusCita.AGENDADA, motivo="Prueba",
        )

    def test_pdf_comprobante_no_crashea_y_muestra_nombre(self):
        from reportlab.pdfgen import canvas

        dibujados = []
        original = canvas.Canvas.drawRightString

        def spy(self_, x, y, text, *args, **kwargs):
            dibujados.append(text)
            return original(self_, x, y, text, *args, **kwargs)

        with mock.patch.object(canvas.Canvas, "drawRightString", spy):
            pdf = generar_pdf_comprobante(
                self.cita, SimpleNamespace(nombre_visible="Paciente Prueba")
            )

        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("Dr(a). Rosa Villalobos Cruz", dibujados)

    def test_serialize_cita_usa_nombre_del_usuario(self):
        self.assertEqual(_serialize_cita(self.cita)["medicoNombre"], "Rosa Villalobos Cruz")

    def test_qr_checkin_nombre_medico(self):
        self.assertEqual(_nombre_medico(self.cita), "Rosa Villalobos Cruz")

    def test_notificacion_cuerpos_incluyen_nombre(self):
        servicio = NotificacionCitaService()

        self.assertIn("Dr(a). Rosa Villalobos Cruz", servicio._cuerpo_confirmacion(self.cita))
        self.assertIn("Dr(a). Rosa Villalobos Cruz", servicio._cuerpo_recordatorio(self.cita))


class ListMedicosTests(TestCase):
    """El listado ordena y busca por el nombre del usuario."""

    def setUp(self):
        self.beto = crear_medico(id=20, nombre="Beto", paterno="Beta", materno="X", usuario="dr_beta")
        self.ana = crear_medico(id=30, nombre="Ana", paterno="Alfa", materno="Z", usuario="dr_ana")
        self.carlos = crear_medico(id=10, nombre="Carlos", paterno="Gamma", materno="W", usuario="dr_carlos")

    def test_orden_por_nombre_completo_del_usuario(self):
        ids = [m.id for m in list_medicos()]

        # "Ana Alfa Z" < "Beto Beta X" < "Carlos Gamma W"
        self.assertEqual(ids, [30, 20, 10])

    def test_busqueda_por_nombre_del_usuario(self):
        self.assertEqual([m.id for m in list_medicos(search="Gamma")], [10])
        self.assertEqual([m.id for m in list_medicos(search="ana alfa")], [30])

    def test_busqueda_por_digito_encuentra_no_medico(self):
        self.assertEqual([m.id for m in list_medicos(search="30")], [30])
