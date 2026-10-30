"""
P-03: caso de uso de la adscripción (validaciones C1 a C10, R1 a R4).

Confirmar adscribe o reasigna en una sola transacción: cierra la anterior,
crea la nueva, cancela las citas del consultorio anterior con el camino que
ya existe (CitasRepository.update_estatus) y las deja por reagendar.
"""

from datetime import timedelta
from unittest import mock

from django.test import RequestFactory
from django.utils import timezone

from apps.administracion.models import AuditoriaEvento
from apps.authentication.models import SyUsuario
from apps.catalogos.models import MotivoCita
from apps.recepcion.models import (
    AdscripcionCitaAfectada,
    AdscripcionConsultorio,
    AdscripcionPaciente,
    CitaEstatusLog,
    EstatusCita,
    HorarioDisponible,
)
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.tests._adscripcion_base import AdscripcionTestBase, fila_sermed
from apps.recepcion.uses_case.adscripcion_usecase import (
    AdscripcionError,
    Operador,
    adscribir,
    descartar_cita_afectada,
    previsualizar,
    vincular_reagenda,
)


class AdscripcionUseCaseBase(AdscripcionTestBase):
    def setUp(self):
        super().setUp()
        self.cons5a = self._consultorio(self.clinica5, 1)
        self.cons5b = self._consultorio(self.clinica5, 2)
        self.cons7 = self._consultorio(self.clinica7, 1)
        self.paciente = self._paciente()
        usuario = SyUsuario.objects.create(
            usuario="recepcion.p03", correo="recepcion.p03@example.com", clave_hash="x", est_activo=True,
        )
        self.operador5 = Operador(usuario=usuario, id_centro_atencion=self.clinica5.id)
        self.operador7 = Operador(usuario=usuario, id_centro_atencion=self.clinica7.id)
        self.request = RequestFactory().post("/api/v1/recepcion/adscripcion")
        self.motivo = MotivoCita.objects.create(
            name="Cambio de consultorio familiar", aplica_a=MotivoCita.AplicaA.CANCELACION, is_active=True,
        )

    def _confirmar(self, consultorio, *, esperada=None, citas=(), motivo=None, operador=None, clinica="5"):
        with self._sermed(titular=fila_sermed(cd_clinica=clinica)):
            return adscribir(
                id_paciente=self.paciente.pk,
                consultorio_id=consultorio.pk,
                id_adscripcion_esperada=esperada,
                citas_a_cancelar_ids=[c.pk for c in citas],
                motivo_cancelacion_id=motivo.pk if motivo else None,
                origen=AdscripcionPaciente.Origen.CHECKIN,
                fue_sugerida=True,
                observaciones=None,
                operador=operador or self.operador5,
                request=self.request,
            )

    def assertError(self, codigo, funcion, *args, **kwargs):
        with self.assertRaises(AdscripcionError) as ctx:
            funcion(*args, **kwargs)
        self.assertEqual(ctx.exception.code, codigo)
        return ctx.exception


class PrimeraAdscripcionTests(AdscripcionUseCaseBase):
    def test_crea_la_adscripcion_con_los_datos_de_sermed_y_del_consultorio(self):
        resultado = self._confirmar(self.cons5b)
        adscripcion = resultado.adscripcion
        self.assertFalse(resultado.sin_cambios)
        self.assertEqual(adscripcion.estatus, AdscripcionPaciente.Estatus.ACTIVA)
        self.assertEqual(adscripcion.centro_id, self.clinica5.id)
        self.assertEqual(adscripcion.clave_clinica_sermed, "5")
        self.assertEqual(adscripcion.turno_id, self.cons5b.id_turn_id)
        self.assertEqual(adscripcion.origen, AdscripcionPaciente.Origen.CHECKIN)
        self.assertTrue(adscripcion.fue_sugerida)
        self.assertEqual(adscripcion.id_usuario_creacion, self.operador5.id_usuario)

    def test_queda_auditada(self):
        resultado = self._confirmar(self.cons5a)
        evento = AuditoriaEvento.objects.get(accion="ADSCRIPCION_ASIGNAR")
        self.assertEqual(evento.resultado, "SUCCESS")
        self.assertEqual(evento.recurso_tipo, "adscripcion_paciente")
        self.assertEqual(evento.recurso_id, resultado.adscripcion.id)
        self.assertIsNone(evento.datos_antes)
        self.assertEqual(evento.datos_despues["idConsultorio"], self.cons5a.id)

    def test_la_primera_adscripcion_no_cancela_citas(self):
        cita = self._cita(self.paciente, self.cons5b)
        self._confirmar(self.cons5a)
        cita.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.AGENDADA)
        self.assertFalse(AdscripcionCitaAfectada.objects.exists())


class ReasignacionTests(AdscripcionUseCaseBase):
    def setUp(self):
        super().setUp()
        self.actual = self._adscribir(self.paciente, self.cons5a)

    def test_mismo_consultorio_no_escribe_nada(self):
        resultado = self._confirmar(self.cons5a, esperada=self.actual.id)
        self.assertTrue(resultado.sin_cambios)
        self.assertEqual(resultado.adscripcion, self.actual)
        self.assertEqual(AdscripcionPaciente.objects.count(), 1)
        self.assertFalse(AuditoriaEvento.objects.filter(recurso_tipo="adscripcion_paciente").exists())

    def test_reasigna_dentro_del_centro_y_cierra_la_anterior(self):
        resultado = self._confirmar(self.cons5b, esperada=self.actual.id)
        self.actual.refresh_from_db()
        self.assertEqual(self.actual.estatus, AdscripcionPaciente.Estatus.CERRADA)
        self.assertEqual(self.actual.motivo_cierre, AdscripcionPaciente.MotivoCierre.REASIGNACION)
        self.assertEqual(self.actual.id_usuario_cierre, self.operador5.id_usuario)
        self.assertIsNotNone(self.actual.fecha_fin)
        self.assertEqual(resultado.adscripcion.consultorio_id, self.cons5b.id)
        evento = AuditoriaEvento.objects.get(accion="ADSCRIPCION_REASIGNAR")
        self.assertEqual(evento.datos_antes["idConsultorio"], self.cons5a.id)
        self.assertEqual(evento.datos_despues["idConsultorio"], self.cons5b.id)

    def test_cancela_las_citas_del_consultorio_anterior_y_las_deja_por_reagendar(self):
        cita = self._cita(self.paciente, self.cons5a, dias=3)
        slot = HorarioDisponible.objects.create(
            medico=self.medico, consultorio=self.cons5a, fecha=cita.fecha_hora.date(),
            hora=cita.fecha_hora.time(), disponible=False, cita=cita,
        )
        resultado = self._confirmar(self.cons5b, esperada=self.actual.id, citas=[cita], motivo=self.motivo)
        cita.refresh_from_db()
        slot.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.CANCELADA)
        self.assertEqual(cita.motivo_cancelacion_id, self.motivo.pk)
        self.assertTrue(slot.disponible)
        self.assertTrue(CitaEstatusLog.objects.filter(cita=cita, to_status=EstatusCita.CANCELADA).exists())
        afectada = AdscripcionCitaAfectada.objects.get(cita_cancelada=cita)
        self.assertEqual(afectada.adscripcion, resultado.adscripcion)
        self.assertEqual(afectada.estatus, AdscripcionCitaAfectada.Estatus.PENDIENTE)
        self.assertEqual(resultado.citas_canceladas, (cita,))

    def test_no_cancela_citas_que_ya_son_del_consultorio_nuevo(self):
        en_destino = self._cita(self.paciente, self.cons5b, dias=4)
        self._confirmar(self.cons5b, esperada=self.actual.id)
        en_destino.refresh_from_db()
        self.assertEqual(en_destino.estatus, EstatusCita.AGENDADA)

    def test_cambio_de_clinica_en_sermed(self):
        cita = self._cita(self.paciente, self.cons5a)
        resultado = self._confirmar(
            self.cons7, esperada=self.actual.id, citas=[cita], motivo=self.motivo,
            operador=self.operador7, clinica="7",
        )
        self.actual.refresh_from_db()
        self.assertEqual(self.actual.motivo_cierre, AdscripcionPaciente.MotivoCierre.CAMBIO_CLINICA)
        self.assertEqual(resultado.adscripcion.centro_id, self.clinica7.id)
        self.assertEqual(resultado.adscripcion.clave_clinica_sermed, "7")

    def test_consultorio_que_deja_de_ser_familiar(self):
        AdscripcionConsultorio.objects.filter(consultorio=self.cons5a).update(esta_activo=False)
        self._confirmar(self.cons5b, esperada=self.actual.id)
        self.actual.refresh_from_db()
        self.assertEqual(self.actual.motivo_cierre, AdscripcionPaciente.MotivoCierre.CONSULTORIO_INACTIVO)


class RechazosTests(AdscripcionUseCaseBase):
    """Cada rechazo deja todo como estaba y queda auditado como FAIL."""

    def setUp(self):
        super().setUp()
        self.actual = self._adscribir(self.paciente, self.cons5a)
        self.cita = self._cita(self.paciente, self.cons5a)

    def _nada_cambio(self):
        self.actual.refresh_from_db()
        self.cita.refresh_from_db()
        self.assertEqual(self.actual.estatus, AdscripcionPaciente.Estatus.ACTIVA)
        self.assertEqual(AdscripcionPaciente.objects.filter(paciente=self.paciente).count(), 1)
        self.assertEqual(self.cita.estatus, EstatusCita.AGENDADA)
        self.assertFalse(AdscripcionCitaAfectada.objects.exists())

    def test_adscripcion_modificada(self):
        self.assertError(
            "ADSCRIPCION_MODIFICADA", self._confirmar, self.cons5b,
            esperada=None, citas=[self.cita], motivo=self.motivo,
        )
        self._nada_cambio()

    def test_citas_modificadas(self):
        error = self.assertError("CITAS_MODIFICADAS", self._confirmar, self.cons5b, esperada=self.actual.id)
        self.assertEqual([c["idCita"] for c in error.details["citas"]], [self.cita.id])
        self._nada_cambio()

    def test_motivo_requerido(self):
        self.assertError(
            "MOTIVO_REQUERIDO", self._confirmar, self.cons5b, esperada=self.actual.id, citas=[self.cita],
        )
        self._nada_cambio()

    def test_motivo_que_no_aplica_a_cancelacion(self):
        no_asistio = MotivoCita.objects.create(name="No llegó", aplica_a=MotivoCita.AplicaA.NO_ASISTIO)
        self.assertError(
            "MOTIVO_REQUERIDO", self._confirmar, self.cons5b,
            esperada=self.actual.id, citas=[self.cita], motivo=no_asistio,
        )
        self._nada_cambio()

    def test_centro_no_permitido(self):
        self.assertError(
            "CENTRO_NO_PERMITIDO", self._confirmar, self.cons5b, esperada=self.actual.id,
            citas=[self.cita], motivo=self.motivo, operador=self.operador7,
        )
        self._nada_cambio()

    def test_perfil_central_puede_operar_cualquier_centro(self):
        central = Operador(usuario=self.operador7.usuario, id_centro_atencion=None, todos_centros=True)
        resultado = self._confirmar(
            self.cons5b, esperada=self.actual.id, citas=[self.cita], motivo=self.motivo, operador=central,
        )
        self.assertEqual(resultado.adscripcion.consultorio_id, self.cons5b.id)

    def test_consultorio_de_otro_centro(self):
        self.assertError(
            "CONSULTORIO_NO_ELEGIBLE", self._confirmar, self.cons7,
            esperada=self.actual.id, citas=[self.cita], motivo=self.motivo,
        )
        self._nada_cambio()

    def test_consultorio_que_no_es_familiar(self):
        no_familiar = self._consultorio(self.clinica5, 9, familiar=False)
        self.assertError(
            "CONSULTORIO_NO_ELEGIBLE", self._confirmar, no_familiar,
            esperada=self.actual.id, citas=[self.cita], motivo=self.motivo,
        )

    def test_consultorio_lleno(self):
        AdscripcionConsultorio.objects.filter(consultorio=self.cons5b).update(capacidad_maxima=1)
        self._adscribir(self._paciente(no_exp="EXP-OTRO"), self.cons5b)
        self.assertError(
            "CONSULTORIO_LLENO", self._confirmar, self.cons5b,
            esperada=self.actual.id, citas=[self.cita], motivo=self.motivo,
        )
        self._nada_cambio()

    def test_paciente_no_vigente(self):
        with self._sermed(titular=fila_sermed(estatus="BAJA")):
            self.assertError(
                "PACIENTE_NO_VIGENTE", adscribir,
                id_paciente=self.paciente.pk, consultorio_id=self.cons5b.pk,
                id_adscripcion_esperada=self.actual.id, citas_a_cancelar_ids=[self.cita.pk],
                motivo_cancelacion_id=self.motivo.pk, origen=AdscripcionPaciente.Origen.MANUAL,
                operador=self.operador5, request=self.request,
            )
        self._nada_cambio()

    def test_si_falla_una_cancelacion_no_queda_nada_escrito(self):
        with mock.patch(
            "apps.recepcion.uses_case.adscripcion_usecase.CitasRepository.update_estatus",
            side_effect=VisitDomainError("CITA_TRANSICION_INVALIDA", "Transición inválida.", 409),
        ):
            with self.assertRaises(VisitDomainError):
                self._confirmar(self.cons5b, esperada=self.actual.id, citas=[self.cita], motivo=self.motivo)
        self._nada_cambio()

    def test_el_rechazo_queda_auditado(self):
        with self.assertRaises(AdscripcionError):
            self._confirmar(self.cons5b, esperada=self.actual.id)
        evento = AuditoriaEvento.objects.get(accion="ADSCRIPCION_ASIGNAR", resultado="FAIL")
        self.assertEqual(evento.codigo_error, "CITAS_MODIFICADAS")


class PrevisualizarTests(AdscripcionUseCaseBase):
    def test_muestra_las_citas_que_se_cancelarian_sin_escribir(self):
        actual = self._adscribir(self.paciente, self.cons5a)
        cita = self._cita(self.paciente, self.cons5a)
        self._cita(self.paciente, self.cons5b)
        with self._sermed(titular=fila_sermed()):
            vista = previsualizar(id_paciente=self.paciente.pk, consultorio_id=self.cons5b.pk)
        self.assertFalse(vista.sin_cambios)
        self.assertEqual(vista.evaluacion.adscripcion, actual)
        self.assertEqual(list(vista.citas_a_cancelar), [cita])
        self.assertEqual(AdscripcionPaciente.objects.count(), 1)

    def test_mismo_consultorio(self):
        self._adscribir(self.paciente, self.cons5a)
        with self._sermed(titular=fila_sermed()):
            vista = previsualizar(id_paciente=self.paciente.pk, consultorio_id=self.cons5a.pk)
        self.assertTrue(vista.sin_cambios)
        self.assertEqual(vista.citas_a_cancelar, ())


class CitasPorReagendarTests(AdscripcionUseCaseBase):
    def setUp(self):
        super().setUp()
        actual = self._adscribir(self.paciente, self.cons5a)
        self.cita = self._cita(self.paciente, self.cons5a)
        resultado = self._confirmar(self.cons5b, esperada=actual.id, citas=[self.cita], motivo=self.motivo)
        self.afectada = AdscripcionCitaAfectada.objects.get(adscripcion=resultado.adscripcion)

    def test_descartar_con_motivo(self):
        descartar_cita_afectada(
            id_cita_afectada=self.afectada.pk, motivo="Ya no la necesita",
            operador=self.operador5, request=self.request,
        )
        self.afectada.refresh_from_db()
        self.assertEqual(self.afectada.estatus, AdscripcionCitaAfectada.Estatus.DESCARTADA)
        self.assertEqual(self.afectada.motivo_descarte, "Ya no la necesita")
        self.assertEqual(self.afectada.id_usuario_resolucion, self.operador5.id_usuario)

    def test_descartar_sin_motivo(self):
        self.assertError(
            "MOTIVO_REQUERIDO", descartar_cita_afectada,
            id_cita_afectada=self.afectada.pk, motivo="  ", operador=self.operador5, request=self.request,
        )

    def test_reagendar_en_el_consultorio_nuevo(self):
        nueva = self._cita(self.paciente, self.cons5b, dias=9)
        vincular_reagenda(
            id_cita_afectada=self.afectada.pk, cita_nueva=nueva, operador=self.operador5, request=self.request,
        )
        self.afectada.refresh_from_db()
        self.assertEqual(self.afectada.estatus, AdscripcionCitaAfectada.Estatus.REAGENDADA)
        self.assertEqual(self.afectada.cita_nueva, nueva)

    def test_reagendar_en_otro_consultorio(self):
        nueva = self._cita(self.paciente, self.cons5a, dias=9)
        self.assertError(
            "CONSULTORIO_FAMILIAR_DIFERENTE", vincular_reagenda,
            id_cita_afectada=self.afectada.pk, cita_nueva=nueva, operador=self.operador5, request=self.request,
        )

    def test_reagendar_con_cita_de_otro_paciente(self):
        otra = self._cita(self._paciente(no_exp="EXP-OTRO"), self.cons5b, dias=9)
        self.assertError(
            "CITA_DE_OTRO_PACIENTE", vincular_reagenda,
            id_cita_afectada=self.afectada.pk, cita_nueva=otra, operador=self.operador5, request=self.request,
        )

    def test_no_se_resuelve_dos_veces(self):
        descartar_cita_afectada(
            id_cita_afectada=self.afectada.pk, motivo="Ya no la necesita",
            operador=self.operador5, request=self.request,
        )
        nueva = self._cita(self.paciente, self.cons5b, dias=9)
        self.assertError(
            "CITA_AFECTADA_RESUELTA", vincular_reagenda,
            id_cita_afectada=self.afectada.pk, cita_nueva=nueva, operador=self.operador5, request=self.request,
        )
