"""
Agendar una cita: las reglas de negocio que antes vivían en la vista de
``POST /citas`` (vigencia, clínica del paciente, P-03, horario libre y
reagendado) en un caso de uso que usan recepción y el médico.
"""

import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import CatMedico, RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.recepcion.models import CitaMedica, HorarioDisponible
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case import agendar_cita_usecase as caso
from apps.recepcion.uses_case.agendar_cita_usecase import agendar_cita


class AgendarCitaTests(TestCase):
    def setUp(self):
        self.fecha = timezone.localdate() + datetime.timedelta(days=3)
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        self.centro = CatCentroAtencion.objects.create(
            name="Centro Uno", code="C-1", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.consultorio = Consultorios.objects.create(
            name="Consultorio A", numero=1, id_turn=turno, id_center=self.centro, is_active=True,
        )
        user = SyUsuario.objects.create(usuario="dr.agendar", correo="dr@example.com", clave_hash="x")
        DetUsuario.objects.create(id_usuario=user, nombre="Ana", paterno="Ruiz")
        self.medico = CatMedico.objects.create(id_usuario=user)
        rel = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha_inicio=self.fecha - datetime.timedelta(days=30), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=rel, dia_semana=dia_semana(self.fecha),
            hora_inicio="09:00", hora_fin="10:00", intervalo_cita_min=20, canal="AMBOS",
        )
        CitasRepository.generar_slots_medico(medico_id=self.medico.id, dias_adelante=7)
        self.vigencia = mock.patch.object(caso, "tiene_vigencia", return_value=True)
        self.clinica = mock.patch.object(caso, "centro_del_paciente", return_value=None)
        self.vigencia.start()
        self.clinica.start()
        self.addCleanup(mock.patch.stopall)

    def _agendar(self, **extra):
        datos = dict(
            no_exp="EXP-1", pk_num=0, medico_id=self.medico.id, consultorio_id=self.consultorio.id,
            fecha_hora=timezone.make_aware(datetime.datetime.combine(self.fecha, datetime.time(9, 20))),
            created_by_id=None, operador=None, request=None,
        )
        datos.update(extra)
        return agendar_cita(**datos)

    def test_crea_la_cita_y_ocupa_el_horario(self):
        cita = self._agendar(motivo="Control")

        guardada = CitaMedica.objects.get(pk=cita["id"])
        self.assertEqual((guardada.medico_id, guardada.motivo), (self.medico.id, "Control"))
        self.assertEqual(HorarioDisponible.objects.get(cita=guardada).hora, datetime.time(9, 20))

    def test_sin_vigencia_no_se_agenda(self):
        self.vigencia.stop()
        with mock.patch.object(caso, "tiene_vigencia", return_value=False):
            with self.assertRaises(VisitDomainError) as raised:
                self._agendar()

        self.assertEqual((raised.exception.code, raised.exception.status_code), ("PATIENT_NO_SERVICE", 409))
        self.assertFalse(CitaMedica.objects.exists())

    def test_paciente_de_otra_clinica_no_se_agenda(self):
        self.clinica.stop()
        with mock.patch.object(caso, "centro_del_paciente", return_value=self.centro.id + 999):
            with self.assertRaises(VisitDomainError) as raised:
                self._agendar()

        self.assertEqual(raised.exception.code, "WRONG_CLINIC")
        self.assertFalse(CitaMedica.objects.exists())

    def test_aplica_el_consultorio_familiar(self):
        rechazo = VisitDomainError("CONSULTORIO_FAMILIAR_DIFERENTE", "Otro consultorio.", 409)
        with mock.patch.object(caso, "validar_consultorio_familiar", side_effect=rechazo) as p03:
            with self.assertRaises(VisitDomainError) as raised:
                self._agendar(excepcion_consultorio_familiar="")

        self.assertEqual(raised.exception.code, "CONSULTORIO_FAMILIAR_DIFERENTE")
        self.assertEqual(p03.call_args.kwargs["consultorio_id"], self.consultorio.id)
        self.assertFalse(CitaMedica.objects.exists())

    def test_horario_ocupado_es_cita_no_disponible(self):
        HorarioDisponible.objects.filter(medico=self.medico, hora="09:20").update(disponible=False)

        with self.assertRaises(VisitDomainError) as raised:
            self._agendar()

        self.assertEqual((raised.exception.code, raised.exception.status_code), ("CITA_NOT_AVAILABLE", 400))

    def test_si_el_reagendado_falla_la_cita_no_queda(self):
        rechazo = VisitDomainError("CITA_AFECTADA_RESUELTA", "Ya se reagendó.", 409)
        with mock.patch.object(caso, "vincular_reagenda", side_effect=rechazo):
            with self.assertRaises(VisitDomainError):
                self._agendar(id_cita_afectada=1, operador=mock.Mock())

        self.assertFalse(CitaMedica.objects.exists())
