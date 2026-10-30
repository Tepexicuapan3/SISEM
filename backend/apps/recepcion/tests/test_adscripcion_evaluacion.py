"""
P-03: evaluación de la persona (validaciones V0 a V10). Solo lee: compara la
clínica que SERMED le marca con su adscripción en SIRES.
"""

from datetime import timedelta
from unittest import mock

from django.utils import timezone

from apps.administracion.use_cases.expedientes.buscar_expediente import ExpedientesNoDisponible
from apps.consulta_medica.models import Patient
from apps.medicos.models import RelMedicoConsultorio
from apps.recepcion.models import AdscripcionClinicaCentro, AdscripcionConsultorio, EstatusCita
from apps.recepcion.services.adscripcion_evaluacion import EstadoAdscripcion, evaluar_adscripcion
from apps.recepcion.tests._adscripcion_base import BUSCAR_EXPEDIENTE, AdscripcionTestBase, fila_sermed


class EvaluacionSermedTests(AdscripcionTestBase):
    """V1 a V3: lo que se lee de SERMED."""

    def setUp(self):
        super().setUp()
        self._consultorio(self.clinica5, 1)
        self.paciente = self._paciente()

    def test_sin_fila_en_sermed(self):
        with self._sermed():
            self.assertEqual(evaluar_adscripcion(self.paciente).estado, EstadoAdscripcion.SIN_DATO_EXPEDIENTE)

    def test_sermed_no_responde_no_bloquea(self):
        with mock.patch(BUSCAR_EXPEDIENTE, side_effect=ExpedientesNoDisponible("caida")):
            self.assertEqual(evaluar_adscripcion(self.paciente).estado, EstadoAdscripcion.SIN_DATO_EXPEDIENTE)

    def test_titular_de_baja(self):
        with self._sermed(titular=fila_sermed(estatus="BAJA")):
            self.assertEqual(evaluar_adscripcion(self.paciente).estado, EstadoAdscripcion.NO_VIGENTE)

    def test_sin_clinica_en_sermed(self):
        with self._sermed(titular=fila_sermed(cd_clinica=None)):
            self.assertEqual(evaluar_adscripcion(self.paciente).estado, EstadoAdscripcion.SIN_DATO_EXPEDIENTE)

    def test_familiar_del_legado_sin_pk_num(self):
        paciente = Patient.objects.create(no_exp="EXP-2", pk_num=None, legacy_family_code=7)
        with self._sermed(titular=fila_sermed()):
            self.assertEqual(evaluar_adscripcion(paciente).estado, EstadoAdscripcion.SIN_DATO_EXPEDIENTE)


class EvaluacionCentroTests(AdscripcionTestBase):
    """V4 y V5: equivalencia de clínica y centro encendido."""

    def setUp(self):
        super().setUp()
        self.paciente = self._paciente()

    def test_clinica_sin_equivalencia(self):
        with self._sermed(titular=fila_sermed(cd_clinica="9")):
            evaluacion = evaluar_adscripcion(self.paciente)
        self.assertEqual(evaluacion.estado, EstadoAdscripcion.CLINICA_SIN_CENTRO)
        self.assertEqual(evaluacion.clave_clinica_sermed, "9")

    def test_equivalencia_inactiva(self):
        AdscripcionClinicaCentro.objects.filter(clave_clinica_sermed="5").update(esta_activo=False)
        with self._sermed(titular=fila_sermed(cd_clinica="5")):
            self.assertEqual(evaluar_adscripcion(self.paciente).estado, EstadoAdscripcion.CLINICA_SIN_CENTRO)

    def test_clave_con_espacios_se_normaliza(self):
        self._consultorio(self.clinica5, 1)
        with self._sermed(titular=fila_sermed(cd_clinica=" 5 ")):
            self.assertEqual(evaluar_adscripcion(self.paciente).centro_sermed_id, self.clinica5.id)

    def test_centro_sin_consultorios_familiares(self):
        self._consultorio(self.clinica5, 1, familiar=False)
        with self._sermed(titular=fila_sermed()):
            self.assertEqual(evaluar_adscripcion(self.paciente).estado, EstadoAdscripcion.P03_INACTIVO)

    def test_consultorio_familiar_inactivo_no_enciende_el_centro(self):
        consultorio = self._consultorio(self.clinica5, 1)
        AdscripcionConsultorio.objects.filter(consultorio=consultorio).update(esta_activo=False)
        with self._sermed(titular=fila_sermed()):
            self.assertEqual(evaluar_adscripcion(self.paciente).estado, EstadoAdscripcion.P03_INACTIVO)


class EvaluacionAdscripcionTests(AdscripcionTestBase):
    """V6 a V10: adscripción, comparación y citas afectadas."""

    def setUp(self):
        super().setUp()
        self.consultorio5 = self._consultorio(self.clinica5, 1)
        self._consultorio(self.clinica7, 1)
        self.paciente = self._paciente()

    def test_sin_adscripcion(self):
        with self._sermed(titular=fila_sermed()):
            evaluacion = evaluar_adscripcion(self.paciente)
        self.assertEqual(evaluacion.estado, EstadoAdscripcion.SIN_ADSCRIPCION)
        self.assertEqual(evaluacion.centro_sermed_id, self.clinica5.id)
        self.assertIsNone(evaluacion.adscripcion)

    def test_vigente(self):
        adscripcion = self._adscribir(self.paciente, self.consultorio5)
        with self._sermed(titular=fila_sermed()):
            evaluacion = evaluar_adscripcion(self.paciente)
        self.assertEqual(evaluacion.estado, EstadoAdscripcion.VIGENTE)
        self.assertEqual(evaluacion.adscripcion, adscripcion)
        self.assertFalse(evaluacion.sin_medico_activo)
        self.assertFalse(evaluacion.requiere_reasignar)

    def test_vigente_avisa_si_no_hay_medico_activo(self):
        self._adscribir(self.paciente, self.consultorio5)
        RelMedicoConsultorio.objects.filter(consultorio=self.consultorio5).update(
            fecha_fin=timezone.localdate() - timedelta(days=1),
        )
        with self._sermed(titular=fila_sermed()):
            evaluacion = evaluar_adscripcion(self.paciente)
        self.assertEqual(evaluacion.estado, EstadoAdscripcion.VIGENTE)
        self.assertTrue(evaluacion.sin_medico_activo)

    def test_no_coincide_cuando_sermed_cambia_la_clinica(self):
        self._adscribir(self.paciente, self.consultorio5)
        with self._sermed(titular=fila_sermed(cd_clinica="7")):
            evaluacion = evaluar_adscripcion(self.paciente)
        self.assertEqual(evaluacion.estado, EstadoAdscripcion.NO_COINCIDE)
        self.assertEqual(evaluacion.centro_sermed_id, self.clinica7.id)
        self.assertTrue(evaluacion.requiere_reasignar)

    def test_no_coincide_lista_solo_citas_futuras_de_medicina_general(self):
        self._adscribir(self.paciente, self.consultorio5)
        agendada = self._cita(self.paciente, self.consultorio5, dias=3)
        confirmada = self._cita(self.paciente, self.consultorio5, dias=10, estatus=EstatusCita.CONFIRMADA)
        self._cita(self.paciente, self.consultorio5, dias=-2)
        self._cita(self.paciente, self.consultorio5, dias=5, servicio="especialidad")
        self._cita(self.paciente, self.consultorio5, dias=6, estatus=EstatusCita.CANCELADA)
        with self._sermed(titular=fila_sermed(cd_clinica="7")):
            evaluacion = evaluar_adscripcion(self.paciente)
        self.assertEqual([c.id for c in evaluacion.citas_futuras], [agendada.id, confirmada.id])

    def test_consultorio_dado_de_baja(self):
        self._adscribir(self.paciente, self.consultorio5)
        self._consultorio(self.clinica5, 2)
        self.consultorio5.is_active = False
        self.consultorio5.save()
        with self._sermed(titular=fila_sermed()):
            evaluacion = evaluar_adscripcion(self.paciente)
        self.assertEqual(evaluacion.estado, EstadoAdscripcion.CONSULTORIO_INACTIVO)
        self.assertTrue(evaluacion.requiere_reasignar)

    def test_consultorio_que_deja_de_ser_familiar(self):
        self._adscribir(self.paciente, self.consultorio5)
        self._consultorio(self.clinica5, 2)
        AdscripcionConsultorio.objects.filter(consultorio=self.consultorio5).update(esta_activo=False)
        with self._sermed(titular=fila_sermed()):
            self.assertEqual(evaluar_adscripcion(self.paciente).estado, EstadoAdscripcion.CONSULTORIO_INACTIVO)


class EvaluacionFamiliaTests(AdscripcionTestBase):
    """Trabajador, derechohabientes y recién nacido: cada uno con su clínica."""

    def setUp(self):
        super().setUp()
        self._consultorio(self.clinica5, 1)
        self._consultorio(self.clinica7, 1)

    def test_derechohabiente_usa_su_propia_clinica(self):
        hijo = self._paciente(pk_num=2)
        with self._sermed(
            titular=fila_sermed(cd_clinica="5"), familiares=[fila_sermed(cd_clinica="7", pk_num=2)],
        ):
            self.assertEqual(evaluar_adscripcion(hijo).centro_sermed_id, self.clinica7.id)

    def test_derechohabiente_no_vigente_aunque_el_titular_si(self):
        hijo = self._paciente(pk_num=2)
        with self._sermed(
            titular=fila_sermed(), familiares=[fila_sermed(estatus="NO ACTIVO", pk_num=2)],
        ):
            self.assertEqual(evaluar_adscripcion(hijo).estado, EstadoAdscripcion.NO_VIGENTE)

    def test_recien_nacido_usa_la_clinica_actual_del_titular(self):
        bebe = self._recien_nacido()
        with self._sermed(titular=fila_sermed(cd_clinica="7")):
            evaluacion = evaluar_adscripcion(bebe)
        self.assertEqual(evaluacion.estado, EstadoAdscripcion.SIN_ADSCRIPCION)
        self.assertEqual(evaluacion.centro_sermed_id, self.clinica7.id)

    def test_recien_nacido_con_provisional_vencido(self):
        bebe = self._recien_nacido(vigente=False)
        with self._sermed(titular=fila_sermed()):
            self.assertEqual(evaluar_adscripcion(bebe).estado, EstadoAdscripcion.NO_VIGENTE)

    def test_recien_nacido_usa_su_vigencia_y_no_la_del_titular(self):
        bebe = self._recien_nacido()
        with self._sermed(titular=fila_sermed(estatus="BAJA")):
            self.assertEqual(evaluar_adscripcion(bebe).estado, EstadoAdscripcion.SIN_ADSCRIPCION)
