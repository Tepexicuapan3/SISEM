"""
Horarios que ya pasaron: no se listan ni se pueden reservar.

Un ``HorarioDisponible`` sigue con ``disponible=True`` después de su hora
(nada lo da de baja), así que la regla se aplica al listar (portal y
recepción), en el calendario mensual del portal y al reservar en los dos
canales.

"Ahora" se congela en 2026-10-13 10:00 hora local (America/Mexico_City,
UTC-6) donde no hay token de portal de por medio; el endpoint de reserva
usa la hora real con un slot de ayer.
"""

from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.medicos.models import CatMedico
from apps.portal_citas.models import PortalMiembro, PortalSesion
from apps.portal_citas.services.slots_service import (
    get_disponibilidad_mensual,
    get_slots_portal,
)
from apps.portal_citas.services.token_service import issue_portal_access_token
from apps.recepcion.models import CitaMedica, HorarioDisponible
from apps.recepcion.repositories.citas_repository import (
    MENSAJE_HORARIO_PASADO,
    CitasRepository,
)

# 10:00 en Ciudad de México.
AHORA = datetime(2026, 10, 13, 16, 0, tzinfo=dt_timezone.utc)
HOY = date(2026, 10, 13)


def _crear_base(prefijo):
    centro = CatCentroAtencion.objects.create(
        name=f"Centro {prefijo}",
        code=f"CT-{prefijo}",
        center_type=CatCentroAtencion.TipoCentro.CLINICA,
        is_active=True,
    )
    turno = Turnos.objects.create(name="Matutino", is_active=True)
    consultorio = Consultorios.objects.create(
        name=f"Consultorio {prefijo}", numero=1, id_turn=turno, id_center=centro, is_active=True,
    )
    usuario = SyUsuario.objects.create(
        usuario=f"medico.{prefijo}", correo=f"medico.{prefijo}@example.com",
        clave_hash="x", est_activo=True,
    )
    DetUsuario.objects.create(id_usuario=usuario, nombre="Dr", paterno=prefijo)
    medico = CatMedico.objects.create(id_usuario=usuario)
    return consultorio, medico


class HorarioPasadoListadoTests(TestCase):
    def setUp(self):
        ahora_patcher = mock.patch("django.utils.timezone.now", return_value=AHORA)
        ahora_patcher.start()
        self.addCleanup(ahora_patcher.stop)

        self.consultorio, self.medico = _crear_base("pasado")

    def _slot(self, fecha, hora, canal="LINEA"):
        return HorarioDisponible.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha=fecha, hora=hora, canal=canal,
        )

    def test_portal_no_lista_horarios_de_hoy_que_ya_pasaron(self):
        self._slot(HOY, "09:00")
        self._slot(HOY, "10:00")  # empieza justo ahora: ya no se ofrece
        self._slot(HOY, "11:00")

        horas = [s["hora"] for s in get_slots_portal(HOY)]

        self.assertEqual(horas, ["11:00"])

    def test_portal_no_lista_horarios_de_dias_anteriores(self):
        self._slot(HOY - timedelta(days=1), "12:00")

        self.assertEqual(get_slots_portal(HOY - timedelta(days=1)), [])

    def test_calendario_mensual_no_cuenta_lo_que_ya_paso(self):
        self._slot(date(2026, 10, 12), "08:00")  # ayer
        self._slot(HOY, "09:00")                 # hoy, ya pasó
        self._slot(HOY, "11:00")                 # hoy, futuro
        self._slot(date(2026, 10, 14), "08:00")  # mañana

        dias = get_disponibilidad_mensual(self.consultorio.id, 2026, 10)

        self.assertEqual(
            dias,
            [
                {"fecha": "2026-10-13", "slotsDisponibles": 1},
                {"fecha": "2026-10-14", "slotsDisponibles": 1},
            ],
        )

    def test_recepcion_no_lista_horarios_que_ya_pasaron(self):
        self._slot(HOY, "09:00", canal="PRESENCIAL")
        self._slot(HOY, "11:00", canal="PRESENCIAL")

        horas = [
            s["hora"]
            for s in CitasRepository.get_slots_disponibles(medico_id=self.medico.id, fecha=HOY)
        ]

        self.assertEqual(horas, ["11:00"])


class HorarioPasadoRecepcionTests(TestCase):
    def test_recepcion_no_agenda_en_un_horario_pasado(self):
        consultorio, medico = _crear_base("recep")
        fecha_hora = timezone.now() - timedelta(hours=1)
        HorarioDisponible.objects.create(
            medico=medico, consultorio=consultorio,
            fecha=timezone.localtime(fecha_hora).date(),
            hora=timezone.localtime(fecha_hora).time().replace(second=0, microsecond=0),
            canal="PRESENCIAL",
        )

        with self.assertRaisesMessage(ValueError, MENSAJE_HORARIO_PASADO):
            CitasRepository.create(
                no_exp="EXP-PASADO", pk_num=0, medico_id=medico.id,
                fecha_hora=fecha_hora, consultorio_id=consultorio.id,
            )

        self.assertFalse(CitaMedica.objects.exists())


class HorarioPasadoReservaPortalTests(APITestCase):
    def setUp(self):
        familiares_patcher = mock.patch(
            "apps.portal_citas.services.nucleo_service._familiares_del_nucleo",
            return_value=[],
        )
        familiares_patcher.start()
        self.addCleanup(familiares_patcher.stop)

        self.miembro = PortalMiembro.objects.create(
            no_exp="EXP-PASADO", pk_num=0,
            nombre_visible="Paciente Pasado", es_titular_login=True,
        )
        sesion = PortalSesion.objects.create(
            portal_miembro=self.miembro,
            expira_en=timezone.now() + timedelta(minutes=25),
        )
        self.token = issue_portal_access_token(sesion)

        consultorio, medico = _crear_base("reserva")
        self.slot = HorarioDisponible.objects.create(
            medico=medico, consultorio=consultorio,
            fecha=timezone.localdate() - timedelta(days=1), hora="09:00", canal="LINEA",
        )

    def test_reservar_un_horario_pasado_responde_409(self):
        response = self.client.post(
            "/api/v1/portal/citas",
            {"miembroId": str(self.miembro.id), "slotId": self.slot.id},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["code"], "HORARIO_PASADO")
        self.assertFalse(CitaMedica.objects.exists())
        self.slot.refresh_from_db()
        self.assertTrue(self.slot.disponible)
