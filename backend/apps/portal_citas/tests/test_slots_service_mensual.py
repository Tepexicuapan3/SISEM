"""
Tests de ``services.slots_service.get_disponibilidad_mensual``.

Cubre: agrupación por fecha, bordes del mes (día 1 y último, incluyendo
febrero bisiesto), exclusión de slots ``disponible=False`` y
``canal="PRESENCIAL"``, y que fechas de otros meses/consultorios no se
filtren por el rango.
"""

from datetime import date, datetime, timezone as dt_timezone
from unittest import mock

from django.test import TestCase

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.medicos.models import CatMedico
from apps.portal_citas.services.slots_service import get_disponibilidad_mensual
from apps.recepcion.models import HorarioDisponible


class GetDisponibilidadMensualTests(TestCase):
    def setUp(self):
        # Los horarios que ya pasaron no cuentan: se congela "ahora" antes
        # de todas las fechas fijas de estos tests.
        ahora_patcher = mock.patch(
            "django.utils.timezone.now",
            return_value=datetime(2026, 7, 1, 12, 0, tzinfo=dt_timezone.utc),
        )
        ahora_patcher.start()
        self.addCleanup(ahora_patcher.stop)

        self.centro = CatCentroAtencion.objects.create(
            name="Centro Mensual",
            code="CT-MES-01",
            center_type=CatCentroAtencion.TipoCentro.CLINICA,
            is_active=True,
        )
        self.turno = Turnos.objects.create(name="Matutino", is_active=True)
        self.consultorio = Consultorios.objects.create(
            name="Consultorio Mensual", numero=1, id_turn=self.turno, id_center=self.centro, is_active=True,
        )
        self.otro_consultorio = Consultorios.objects.create(
            name="Otro Consultorio", numero=2, id_turn=self.turno, id_center=self.centro, is_active=True,
        )

        usuario = SyUsuario.objects.create(
            usuario="medico.mensual", correo="medico.mensual@example.com", clave_hash="x", est_activo=True,
        )
        DetUsuario.objects.create(
            id_usuario=usuario, nombre="Dr", paterno="Mensual",
        )
        self.medico = CatMedico.objects.create(id_usuario=usuario)

    def _slot(self, consultorio, fecha, hora, canal="LINEA", disponible=True):
        return HorarioDisponible.objects.create(
            medico=self.medico, consultorio=consultorio,
            fecha=fecha, hora=hora, canal=canal, disponible=disponible,
        )

    def test_agrupa_por_fecha_dentro_del_mes(self):
        self._slot(self.consultorio, date(2026, 8, 3), "08:00")
        self._slot(self.consultorio, date(2026, 8, 3), "09:00")
        self._slot(self.consultorio, date(2026, 8, 4), "08:00")

        resultado = get_disponibilidad_mensual(self.consultorio.id, 2026, 8)

        por_fecha = {d["fecha"]: d["slotsDisponibles"] for d in resultado}
        self.assertEqual(por_fecha, {"2026-08-03": 2, "2026-08-04": 1})

    def test_respeta_bordes_del_mes_dia_1_y_ultimo(self):
        self._slot(self.consultorio, date(2026, 8, 1), "08:00")
        self._slot(self.consultorio, date(2026, 8, 31), "08:00")
        # Fuera del mes consultado: no debe aparecer.
        self._slot(self.consultorio, date(2026, 7, 31), "08:00")
        self._slot(self.consultorio, date(2026, 9, 1), "08:00")

        resultado = get_disponibilidad_mensual(self.consultorio.id, 2026, 8)

        fechas = {d["fecha"] for d in resultado}
        self.assertEqual(fechas, {"2026-08-01", "2026-08-31"})

    def test_respeta_bordes_de_febrero_bisiesto(self):
        # 2028 es bisiesto: febrero tiene 29 días.
        self._slot(self.consultorio, date(2028, 2, 29), "08:00")
        self._slot(self.consultorio, date(2028, 3, 1), "08:00")

        resultado = get_disponibilidad_mensual(self.consultorio.id, 2028, 2)

        fechas = {d["fecha"] for d in resultado}
        self.assertEqual(fechas, {"2028-02-29"})

    def test_ignora_slots_no_disponibles(self):
        self._slot(self.consultorio, date(2026, 8, 5), "08:00", disponible=False)

        self.assertEqual(get_disponibilidad_mensual(self.consultorio.id, 2026, 8), [])

    def test_ignora_canal_presencial(self):
        self._slot(self.consultorio, date(2026, 8, 5), "08:00", canal="PRESENCIAL")

        self.assertEqual(get_disponibilidad_mensual(self.consultorio.id, 2026, 8), [])

    def test_incluye_canal_ambos(self):
        self._slot(self.consultorio, date(2026, 8, 5), "08:00", canal="AMBOS")

        resultado = get_disponibilidad_mensual(self.consultorio.id, 2026, 8)

        self.assertEqual(resultado, [{"fecha": "2026-08-05", "slotsDisponibles": 1}])

    def test_no_mezcla_slots_de_otro_consultorio(self):
        self._slot(self.otro_consultorio, date(2026, 8, 5), "08:00")

        self.assertEqual(get_disponibilidad_mensual(self.consultorio.id, 2026, 8), [])

    def test_consultorio_inexistente_devuelve_lista_vacia(self):
        self.assertEqual(get_disponibilidad_mensual(999999, 2026, 8), [])
