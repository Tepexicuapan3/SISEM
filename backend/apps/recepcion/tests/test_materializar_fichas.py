"""
Fichas automáticas: las citas que no son del portal generan su ficha el día
de la cita, sin check-in, para que aparezcan en la bandeja de recepción.
El check-in queda solo para las citas del portal en línea.
"""

import datetime
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import CatMedico, RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.recepcion.models import CitaMedica, EstatusCita, OrigenCanalCita, Visit, VisitStatusLog
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.uses_case import agendar_cita_usecase, materializar_fichas_usecase as caso
from apps.recepcion.uses_case.materializar_fichas_usecase import (
    NOTA_FICHA_AUTOMATICA,
    materializar_fichas_del_dia,
)

FILA = {"DS_PATERNO": "PEREZ", "DS_MATERNO": "LOPEZ", "DS_NOMBRE": "JUAN", "vigente": True}


class _FichasBase(TestCase):
    def setUp(self):
        # identity cachea médico -> usuario por id; otro test pudo dejar el suyo.
        cache.clear()
        self.addCleanup(cache.clear)
        self.hoy = timezone.localdate()
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        centro = CatCentroAtencion.objects.create(
            name="Centro Uno", code="C-1", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.consultorio = Consultorios.objects.create(
            name="Consultorio A", numero=1, id_turn=turno, id_center=centro, is_active=True,
        )
        self.usuario = SyUsuario.objects.create(usuario="dr.fichas", correo="dr@example.com", clave_hash="x")
        DetUsuario.objects.create(id_usuario=self.usuario, nombre="Ana", paterno="Ruiz")
        self.medico = CatMedico.objects.create(id_usuario=self.usuario)
        self.paciente = mock.patch.object(caso, "_resolver_paciente", return_value=("PEREZ LOPEZ JUAN", True))
        self.paciente.start()
        self.addCleanup(mock.patch.stopall)
        self._n = 0

    def _cita(self, dias=0, hora="12:00", *, no_exp="EXP-1", **extra):
        self._n += 1
        h, m = map(int, hora.split(":"))
        fecha = self.hoy + datetime.timedelta(days=dias)
        datos = dict(
            folio=f"CIT-F{self._n}", patient=paciente_de_llave(no_exp, 0), medico=self.medico,
            consultorio=self.consultorio, estatus=EstatusCita.AGENDADA, servicio_tipo="medicina_general",
            fecha_hora=timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(h, m))),
            motivo="Control",
        )
        datos.update(extra)
        return CitaMedica.objects.create(**datos)


class MaterializarFichasTests(_FichasBase):
    def test_crea_la_ficha_en_espera_sin_check_in(self):
        cita = self._cita(hora="12:30")

        resumen = materializar_fichas_del_dia()

        self.assertEqual(resumen["creadas"], 1)
        visit = Visit.objects.get(appointment_id=cita.folio)
        self.assertEqual(
            (visit.status, visit.arrival_type, visit.fecha_consulta, visit.hora_consulta),
            ("en_espera", Visit.ArrivalType.APPOINTMENT, self.hoy, datetime.time(12, 30)),
        )
        self.assertEqual(visit.doctor_id, self.usuario.id_usuario)
        # El número de ficha se asigna cuando el paciente llega.
        self.assertIsNone(visit.num_ficha)
        log = VisitStatusLog.objects.get(visit=visit)
        self.assertEqual((log.to_status, log.notes), ("en_espera", NOTA_FICHA_AUTOMATICA))
        cita.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.CONFIRMADA)
        self.assertIsNone(cita.verificado_en)

    def test_no_crea_para_portal_otro_dia_ni_canceladas(self):
        self._cita(origen_canal=OrigenCanalCita.PORTAL)
        self._cita(dias=1)
        self._cita(dias=-1)
        self._cita(estatus=EstatusCita.CANCELADA)

        resumen = materializar_fichas_del_dia()

        self.assertEqual(resumen["creadas"], 0)
        self.assertFalse(Visit.objects.exists())

    def test_correrla_dos_veces_no_duplica(self):
        self._cita()

        materializar_fichas_del_dia()
        segunda = materializar_fichas_del_dia()

        self.assertEqual(segunda["creadas"], 0)
        self.assertEqual(Visit.objects.count(), 1)

    def test_no_exige_la_anticipacion_del_check_in(self):
        # Cita que ya pasó: el check-in la rechazaría por fuera de tiempo.
        self._cita(hora="00:01")

        self.assertEqual(materializar_fichas_del_dia()["creadas"], 1)

    def test_paciente_con_visita_abierta_se_omite_con_su_motivo(self):
        Visit.objects.create(
            folio="VIS-ABIERTA", patient=paciente_de_llave("EXP-1", 0), arrival_type=Visit.ArrivalType.WALK_IN,
            status="en_consulta", fecha_consulta=self.hoy,
        )
        cita = self._cita()

        resumen = materializar_fichas_del_dia()

        self.assertEqual(resumen["creadas"], 0)
        self.assertEqual(resumen["omitidas"], [{"folio": cita.folio, "motivo": "VISIT_DUPLICATE_SUBMIT"}])

    def test_paciente_sin_vigencia_se_omite(self):
        self.paciente.stop()
        cita = self._cita()
        with mock.patch.object(caso, "_resolver_paciente", return_value=("PEREZ LOPEZ JUAN", False)):
            resumen = materializar_fichas_del_dia()

        self.assertEqual(resumen["omitidas"], [{"folio": cita.folio, "motivo": "PATIENT_NO_SERVICE"}])
        self.assertFalse(Visit.objects.exists())

    def test_el_comando_crea_las_fichas_de_hoy(self):
        self._cita()
        salida = StringIO()

        call_command("materializar_fichas", stdout=salida)

        self.assertEqual(Visit.objects.count(), 1)
        self.assertIn("1", salida.getvalue())


    def test_la_tarea_crea_las_fichas_de_hoy(self):
        from apps.recepcion.tasks import materializar_fichas

        self._cita()

        self.assertEqual(materializar_fichas()["creadas"], 1)

class FichaAlAgendarParaHoyTests(_FichasBase):
    """Si recepción agenda para hoy, la ficha sale en ese momento."""

    def setUp(self):
        super().setUp()
        rel = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha_inicio=self.hoy - datetime.timedelta(days=30), is_active=True,
        )
        for dias in (0, 1):
            RelMedicoConsultorioHorario.objects.create(
                rel_medico_consultorio=rel, dia_semana=dia_semana(self.hoy + datetime.timedelta(days=dias)),
                hora_inicio="23:00", hora_fin="23:40", intervalo_cita_min=20, canal="AMBOS",
            )
        CitasRepository.generar_slots_medico(medico_id=self.medico.id, dias_adelante=2)
        mock.patch.object(agendar_cita_usecase, "tiene_vigencia", return_value=True).start()
        mock.patch.object(agendar_cita_usecase, "centro_del_paciente", return_value=None).start()

    def _agendar(self, dias):
        fecha = self.hoy + datetime.timedelta(days=dias)
        return agendar_cita_usecase.agendar_cita(
            no_exp="EXP-2", pk_num=0, medico_id=self.medico.id, consultorio_id=self.consultorio.id,
            fecha_hora=timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(23, 20))),
            created_by_id=None, operador=None, request=None,
        )

    def test_cita_para_hoy_crea_la_ficha_al_agendar(self):
        cita = self._agendar(0)

        self.assertTrue(Visit.objects.filter(appointment_id=cita["folio"]).exists())

    def test_cita_para_otro_dia_no_crea_ficha_todavia(self):
        self._agendar(1)

        self.assertFalse(Visit.objects.exists())
