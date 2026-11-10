"""
Seguimientos por agendar: notas cerradas con fecha de seguimiento indicada
por el médico que todavía no tienen cita (el médico no eligió horario, o el
paciente tiene otro consultorio familiar y la cita la agenda recepción). La
fecha sale de consulta médica por su contrato (``seguimientos_indicados``),
no leyendo su tabla.
"""

import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.centro_scope import AlcanceCentros
from apps.catalogos.models import CatCentroAtencion
from apps.consulta_medica.models import VisitConsultation
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.medicos.models import CatMedico
from apps.recepcion.models import MOTIVO_CITA_SEGUIMIENTO, CitaMedica, EstatusCita, Visit
from apps.recepcion.uses_case.seguimientos_por_agendar_usecase import list_seguimientos_por_agendar

NOMBRE = "apps.recepcion.uses_case.seguimientos_por_agendar_usecase._nombre_paciente"


class SeguimientosPorAgendarTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.centro = CatCentroAtencion.objects.create(
            name="Centro Uno", code="C-1", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.otro_centro = CatCentroAtencion.objects.create(
            name="Centro Dos", code="C-2", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.doctor = SyUsuario.objects.create(usuario="dr.seg", correo="dr@example.com", clave_hash="x")
        DetUsuario.objects.create(id_usuario=self.doctor, nombre="Ana", paterno="Ruiz")
        self.medico = CatMedico.objects.create(id_usuario=self.doctor)
        self.alcance = AlcanceCentros(todos=False, centros=frozenset({self.centro.id}))
        self._n = 0
        patcher = mock.patch(NOMBRE, return_value="PEREZ LOPEZ JUAN")
        self.nombre = patcher.start()
        self.addCleanup(patcher.stop)

    def _nota(self, dias, *, status="cerrada", centro=None, no_exp=None, borrada=False):
        self._n += 1
        visit = Visit.objects.create(
            folio=f"VIS-S{self._n}", patient=paciente_de_llave(no_exp or f"EXP-{self._n}", 0),
            arrival_type=Visit.ArrivalType.WALK_IN, status=status, fecha_consulta=self.hoy,
            centro=centro or self.centro, doctor=self.doctor,
        )
        VisitConsultation.objects.create(
            id_visit=visit, doctor=self.doctor, primary_diagnosis="Hipertension", final_note="Control",
            follow_up_date=None if dias is None else self.hoy + datetime.timedelta(days=dias),
            deleted_at=timezone.now() if borrada else None,
        )
        return visit

    def _cita_de(self, visit, estatus=EstatusCita.AGENDADA):
        return CitaMedica.objects.create(
            folio=f"CIT-{visit.folio}", patient=visit.patient, medico=self.medico, estatus=estatus,
            fecha_hora=timezone.now() + datetime.timedelta(days=10), servicio_tipo="medicina_general",
            motivo=MOTIVO_CITA_SEGUIMIENTO, notas=f"Consulta {visit.folio}",
        )

    def _list(self, desde=-30, hasta=60):
        return list_seguimientos_por_agendar(
            self.alcance, fecha_desde=self.hoy + datetime.timedelta(days=desde),
            fecha_hasta=self.hoy + datetime.timedelta(days=hasta), page=1, page_size=20,
        )

    def test_lista_los_seguimientos_sin_cita_en_orden_y_marca_los_vencidos(self):
        despues = self._nota(14)
        vencido = self._nota(-3)

        items, total, _ = self._list()

        self.assertEqual(total, 2)
        self.assertEqual([i["visitFolio"] for i in items], [vencido.folio, despues.folio])
        self.assertEqual([i["vencido"] for i in items], [True, False])
        primero = items[1]
        self.assertEqual(primero["fechaSeguimiento"], (self.hoy + datetime.timedelta(days=14)).isoformat())
        self.assertEqual(primero["pacienteNombre"], "PEREZ LOPEZ JUAN")
        self.assertIn("Ana", primero["medicoNombre"])
        self.assertEqual((primero["noExp"], primero["pkNum"], primero["idPaciente"]),
                         (despues.patient.no_exp, 0, despues.patient_id))

    def test_el_que_ya_tiene_cita_no_aparece_y_vuelve_si_se_cancela(self):
        visit = self._nota(14)
        cita = self._cita_de(visit)

        self.assertEqual(self._list()[1], 0)

        CitaMedica.objects.filter(pk=cita.pk).update(estatus=EstatusCita.CANCELADA)
        self.assertEqual(self._list()[1], 1)

    def test_deja_fuera_otros_rangos_notas_abiertas_sin_fecha_borradas_y_otro_centro(self):
        self._nota(90)
        self._nota(14, status="en_consulta")
        self._nota(None)
        self._nota(14, borrada=True)
        self._nota(14, centro=self.otro_centro)

        self.assertEqual(self._list()[1], 0)

    def test_consulta_a_sermed_una_vez_por_paciente(self):
        self._nota(10, no_exp="EXP-X")
        self._nota(20, no_exp="EXP-X")

        self._list()

        self.assertEqual(self.nombre.call_count, 1)
