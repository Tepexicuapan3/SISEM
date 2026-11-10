"""
Próximas citas en recepción: las agendadas de los próximos días (incluidas
las que deja el médico al cerrar la consulta), con el nombre del paciente,
para saber quién viene sin tener que buscarlo.
"""

import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.centro_scope import AlcanceCentros
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.medicos.models import CatMedico
from apps.recepcion.models import MOTIVO_CITA_SEGUIMIENTO, CitaMedica, EstatusCita
from apps.recepcion.uses_case.proximas_citas_usecase import list_proximas_citas

FILA = "apps.recepcion.uses_case.proximas_citas_usecase.buscar_fila_paciente"


class ProximasCitasTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        self.centro = CatCentroAtencion.objects.create(
            name="Centro Uno", code="C-1", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.otro_centro = CatCentroAtencion.objects.create(
            name="Centro Dos", code="C-2", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.consultorio = Consultorios.objects.create(
            name="Consultorio A", numero=1, id_turn=turno, id_center=self.centro, is_active=True,
        )
        user = SyUsuario.objects.create(usuario="dr.proximas", correo="dr@example.com", clave_hash="x")
        DetUsuario.objects.create(id_usuario=user, nombre="Ana", paterno="Ruiz")
        self.medico = CatMedico.objects.create(id_usuario=user)
        self.alcance = AlcanceCentros(todos=False, centros=frozenset({self.centro.id}))
        self._n = 0

    def _cita(self, dias, hora="09:00", *, centro=None, estatus=EstatusCita.AGENDADA, motivo=None, notas=None,
              no_exp="EXP-1"):
        self._n += 1
        h, m = map(int, hora.split(":"))
        fecha = self.hoy + datetime.timedelta(days=dias)
        return CitaMedica.objects.create(
            folio=f"CIT-P{self._n}", patient=paciente_de_llave(no_exp, 0), medico=self.medico,
            consultorio=self.consultorio, centro=centro or self.centro, estatus=estatus,
            fecha_hora=timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(h, m))),
            motivo=motivo, notas=notas,
        )

    def _list(self, **kw):
        params = dict(fecha_desde=self.hoy, fecha_hasta=self.hoy + datetime.timedelta(days=7), page=1, page_size=20)
        params.update(kw)
        with mock.patch(FILA, return_value={"DS_PATERNO": "PEREZ", "DS_MATERNO": "LOPEZ", "DS_NOMBRE": "JUAN"}) as fila:
            result = list_proximas_citas(self.alcance, **params)
        return result, fila

    def test_lista_las_agendadas_en_orden_y_marca_los_seguimientos(self):
        seguimiento = self._cita(2, "08:00", motivo=MOTIVO_CITA_SEGUIMIENTO, notas="Consulta VIS-1")
        normal = self._cita(1, "10:00", motivo="Control")

        (items, total, _), _ = self._list()

        self.assertEqual(total, 2)
        self.assertEqual([i["id"] for i in items], [normal.id, seguimiento.id])
        self.assertEqual([i["esSeguimiento"] for i in items], [False, True])
        self.assertEqual(items[0]["pacienteNombre"], "PEREZ LOPEZ JUAN")

    def test_excluye_canceladas_atendidas_otro_centro_y_fuera_de_rango(self):
        self._cita(1, estatus=EstatusCita.CANCELADA)
        self._cita(1, estatus=EstatusCita.ATENDIDA)
        self._cita(1, centro=self.otro_centro)
        self._cita(10)
        confirmada = self._cita(3, estatus=EstatusCita.CONFIRMADA)

        (items, total, _), _ = self._list()

        self.assertEqual((total, [i["id"] for i in items]), (1, [confirmada.id]))

    def test_no_incluye_las_de_hoy_que_ya_pasaron(self):
        self._cita(0, "00:00")

        (items, _, _), _ = self._list()

        self.assertEqual(items, [])

    def test_solo_seguimientos(self):
        self._cita(1, motivo="Control")
        seguimiento = self._cita(2, motivo=MOTIVO_CITA_SEGUIMIENTO)

        (items, _, _), _ = self._list(solo_seguimiento=True)

        self.assertEqual([i["id"] for i in items], [seguimiento.id])

    def test_filtra_por_medico(self):
        self._cita(1)
        (items, _, _), _ = self._list(medico_id=self.medico.id + 999)
        self.assertEqual(items, [])

    def test_consulta_a_sermed_una_vez_por_paciente(self):
        self._cita(1, "09:00", no_exp="EXP-1")
        self._cita(2, "09:00", no_exp="EXP-1")
        self._cita(3, "09:00", no_exp="EXP-2")

        _, fila = self._list()

        self.assertEqual(fila.call_count, 2)

    def test_si_sermed_falla_el_nombre_queda_vacio(self):
        self._cita(1)
        with mock.patch(FILA, side_effect=RuntimeError("caido")):
            items, _, _ = list_proximas_citas(
                self.alcance, fecha_desde=self.hoy, fecha_hasta=self.hoy + datetime.timedelta(days=7),
                page=1, page_size=20,
            )
        self.assertEqual(items[0]["pacienteNombre"], "")
