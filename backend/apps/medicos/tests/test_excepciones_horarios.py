"""
Ausencias del médico (``RelMedicoExcepcion``) y horarios.

Decisiones (opción B): cualquier ausencia deja sin habilitar los horarios de
su rango; las citas ya agendadas NO se cancelan, se listan para que
recepción las reprograme; borrar la ausencia rehabilita lo que bloqueó; y
registrar una ausencia ya no cambia el estatus del médico.
"""

from datetime import datetime, time, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, MotivoCita, Turnos
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import (
    CatMedico,
    RelMedicoConsultorio,
    RelMedicoConsultorioHorario,
    RelMedicoExcepcion,
)
from apps.medicos.uses_case.excepcion_usecase import create_excepcion, delete_excepcion
from apps.portal_citas.models import PortalMiembro, PortalSesion
from apps.portal_citas.services.token_service import issue_portal_access_token
from apps.recepcion.models import CitaMedica, EstatusCita, HorarioDisponible
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave

DIA = timezone.localdate() + timedelta(days=10)


class _Base:
    def _crear_entorno(self):
        centro = CatCentroAtencion.objects.create(
            name="Centro Ausencias", code="CT-AUS",
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        self.consultorio = Consultorios.objects.create(
            name="Consultorio A", numero=1, id_turn=turno, id_center=centro, is_active=True,
        )
        self.otro_consultorio = Consultorios.objects.create(
            name="Consultorio B", numero=2, id_turn=turno, id_center=centro, is_active=True,
        )
        usuario = SyUsuario.objects.create(
            usuario="medico.ausencias", correo="medico.ausencias@example.com",
            clave_hash="x", est_activo=True,
        )
        DetUsuario.objects.create(id_usuario=usuario, nombre="Dr", paterno="Ausencias")
        self.medico = CatMedico.objects.create(id_usuario=usuario)

    def _slot(self, hora, consultorio=None, **extra):
        return HorarioDisponible.objects.create(
            medico=self.medico, consultorio=consultorio or self.consultorio,
            fecha=DIA, hora=hora, duracion_min=20, canal="AMBOS", **extra,
        )

    def _ausencia(self, tipo, hora_inicio=None, hora_fin=None, consultorio=None):
        return create_excepcion(
            self.medico.id,
            {
                "tipo": tipo,
                "fechaInicio": DIA, "fechaFin": DIA,
                "horaInicio": hora_inicio, "horaFin": hora_fin,
                "consultorioId": consultorio.id if consultorio else None,
            },
            actor_id=1,
        )

    def _cita_en(self, hora):
        fecha_hora = timezone.make_aware(datetime.combine(DIA, time.fromisoformat(hora)))
        cita = CitaMedica.objects.create(
            folio=CitaMedica.generar_folio(), patient=_paciente_de_llave("EXP-AUS", 0),
            medico=self.medico, consultorio=self.consultorio, fecha_hora=fecha_hora,
            duracion_min=20, servicio_tipo="medicina_general", estatus=EstatusCita.AGENDADA,
        )
        slot = self._slot(hora, disponible=False, cita=cita)
        return cita, slot


class AusenciaBloqueaHorariosTests(_Base, TestCase):
    def setUp(self):
        self._crear_entorno()

    def _disponibles(self):
        return sorted(
            str(h)[:5]
            for h in HorarioDisponible.objects.filter(disponible=True).values_list("hora", flat=True)
        )

    def test_hora_de_comida_bloquea_solo_su_ventana(self):
        for hora in ("09:00", "13:40", "13:50", "14:00", "14:40", "15:00"):
            self._slot(hora)

        resultado = self._ausencia("HORA_COMIDA", "14:00", "15:00")

        # 13:50 + 20 min se cruza con la comida; 13:40 termina justo a las 14:00.
        self.assertEqual(self._disponibles(), ["09:00", "13:40", "15:00"])
        self.assertEqual(resultado.horarios_bloqueados, 3)
        bloqueado = HorarioDisponible.objects.get(hora="14:00")
        self.assertEqual(bloqueado.bloqueado_por_excepcion, resultado.excepcion)

    def test_vacaciones_bloquean_el_dia_y_no_cambian_el_estatus(self):
        self._slot("09:00")
        self._slot("16:00")

        self._ausencia("VACACIONES")

        self.assertEqual(self._disponibles(), [])
        self.medico.refresh_from_db()
        self.assertEqual(self.medico.estatus_medico, "ACTIVO")

    def test_ausencia_con_consultorio_solo_afecta_ese_consultorio(self):
        self._slot("09:00", consultorio=self.consultorio)
        self._slot("10:00", consultorio=self.otro_consultorio)

        self._ausencia("PERMISO", consultorio=self.consultorio)

        self.assertEqual(self._disponibles(), ["10:00"])

    def test_cita_agendada_no_se_cancela_y_se_lista_como_afectada(self):
        cita, slot = self._cita_en("14:20")

        resultado = self._ausencia("HORA_COMIDA", "14:00", "15:00")

        cita.refresh_from_db()
        slot.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.AGENDADA)
        self.assertEqual(slot.cita, cita)
        self.assertEqual([c.folio for c in resultado.citas_afectadas], [cita.folio])

    def test_borrar_la_ausencia_rehabilita_sus_horarios(self):
        self._slot("14:00")
        resultado = self._ausencia("HORA_COMIDA", "14:00", "15:00")

        delete_excepcion(self.medico.id, resultado.excepcion.id)

        slot = HorarioDisponible.objects.get(hora="14:00")
        self.assertTrue(slot.disponible)
        self.assertIsNone(slot.bloqueado_por_excepcion)

    def test_borrar_una_ausencia_respeta_otra_que_sigue_activa(self):
        self._slot("14:00")
        self._slot("14:40")
        comida = self._ausencia("HORA_COMIDA", "14:00", "15:00")
        permiso = self._ausencia("PERMISO", "14:00", "14:30")

        delete_excepcion(self.medico.id, comida.excepcion.id)

        slot_permiso = HorarioDisponible.objects.get(hora="14:00")
        self.assertFalse(slot_permiso.disponible)
        self.assertEqual(slot_permiso.bloqueado_por_excepcion, permiso.excepcion)
        self.assertTrue(HorarioDisponible.objects.get(hora="14:40").disponible)

    def test_cancelar_una_cita_afectada_no_reabre_el_horario(self):
        cita, slot = self._cita_en("14:20")
        resultado = self._ausencia("HORA_COMIDA", "14:00", "15:00")
        motivo = MotivoCita.objects.create(name="Reprogramada por ausencia", is_active=True)

        CitasRepository.update_estatus(cita, EstatusCita.CANCELADA, motivo_cancelacion=motivo)

        slot.refresh_from_db()
        self.assertIsNone(slot.cita)
        self.assertFalse(slot.disponible)
        self.assertEqual(slot.bloqueado_por_excepcion, resultado.excepcion)


class GeneracionYRecepcionTests(_Base, TestCase):
    def setUp(self):
        self._crear_entorno()
        rel = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha_inicio=timezone.localdate() - timedelta(days=30), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=rel, dia_semana=dia_semana(DIA),
            hora_inicio="09:00", hora_fin="16:00", intervalo_cita_min=20, canal="AMBOS",
        )

    def test_generar_horarios_dentro_de_una_ausencia_los_crea_bloqueados(self):
        comida = self._ausencia("HORA_COMIDA", "14:00", "15:00")

        CitasRepository.generar_slots_medico(medico_id=self.medico.id, dias_adelante=15)

        slot_comida = HorarioDisponible.objects.get(fecha=DIA, hora="14:20")
        self.assertFalse(slot_comida.disponible)
        self.assertEqual(slot_comida.bloqueado_por_excepcion, comida.excepcion)
        self.assertTrue(HorarioDisponible.objects.get(fecha=DIA, hora="10:00").disponible)

    def test_recepcion_respeta_todas_las_ausencias_del_dia(self):
        # Antes solo se miraba la primera ausencia del día.
        self._ausencia("HORA_COMIDA", "14:00", "15:00")
        self._ausencia("PERMISO", "10:00", "11:00")
        CitasRepository.generar_slots_medico(medico_id=self.medico.id, dias_adelante=15)
        # Fuerza el horario libre para probar la validación de la ausencia.
        HorarioDisponible.objects.filter(fecha=DIA, hora="10:20").update(
            disponible=True, bloqueado_por_excepcion=None,
        )

        with self.assertRaisesMessage(ValueError, "permiso de 10:00 a 11:00"):
            CitasRepository.create(
                no_exp="EXP-AUS", pk_num=0, medico_id=self.medico.id,
                fecha_hora=timezone.make_aware(datetime.combine(DIA, time(10, 20))),
                consultorio_id=self.consultorio.id,
            )


class PortalAusenciaTests(_Base, APITestCase):
    def setUp(self):
        self._crear_entorno()
        familiares_patcher = mock.patch(
            "apps.portal_citas.services.nucleo_service._familiares_del_nucleo",
            return_value=[],
        )
        familiares_patcher.start()
        self.addCleanup(familiares_patcher.stop)

        self.miembro = PortalMiembro.objects.create(
            no_exp="EXP-AUS", pk_num=0, nombre_visible="Paciente", es_titular_login=True,
        )
        sesion = PortalSesion.objects.create(
            portal_miembro=self.miembro, expira_en=timezone.now() + timedelta(minutes=25),
        )
        self.token = issue_portal_access_token(sesion)

    def test_portal_no_reserva_un_horario_libre_dentro_de_una_ausencia(self):
        slot = self._slot("14:20")
        # Ausencia registrada sin pasar por el caso de uso (como las que ya
        # existían antes de este cambio): el horario sigue libre.
        RelMedicoExcepcion.objects.create(
            medico=self.medico, tipo="HORA_COMIDA", fecha_inicio=DIA, fecha_fin=DIA,
            hora_inicio=time(14, 0), hora_fin=time(15, 0),
        )

        response = self.client.post(
            "/api/v1/portal/citas",
            {"miembroId": str(self.miembro.id), "slotId": slot.id},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["code"], "MEDICO_NO_DISPONIBLE")
        self.assertFalse(CitaMedica.objects.exists())
