"""Pases de laboratorio y gabinete en el motor de autorizaciones (F5).

Decisiones confirmadas (2026-10-27): dispara la bandera cat_estudiosmed.autorizado='S'
(sw_autoriza del legado); el tipo sale del pase (laboratorio -> LAB, gabinete -> GAB,
asi los estudios IMG viajan como gabinete); un rechazo cancela SOLO el pase.
Interruptor AUTORIZACIONES_PASES_V2, apagado por defecto.
"""
from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from apps.autorizaciones.models import Solicitud
from apps.autorizaciones.tests.fabricas import agregar_alcance, asignar_tipo, crear_autorizador, motivo
from apps.autorizaciones.uses_case.solicitud_use_case import SolicitudUseCase
from apps.catalogos.models import Consultorios, EstudiosMed, Turnos
from apps.catalogos.tests.designacion_factories import make_center
from apps.consulta_medica.tests.test_consultation_audit_api import _ConsultationAuditApiTestBase
from apps.consulta_medica.tests.test_note_cancellation import _CancellationBase
from apps.pases.models import Referral
from apps.pases.services import autorizacion_motor_service as motor
from apps.pases.uses_case.referral_usecase import cancel_referral, create_referral
from apps.recepcion.models import Visit

CLAVE = "Clave_12345"
LAB = Referral.ReferralType.LABORATORIO
GAB = Referral.ReferralType.GABINETE


class _Base(_ConsultationAuditApiTestBase):
    def setUp(self):
        super().setUp()
        self.centro = make_center()
        self.consultorio = Consultorios.objects.create(
            name="C1", numero=1, id_turn=Turnos.objects.create(name="Matutino"), id_center=self.centro,
        )
        self.visit = self._visit_with_consultation()
        Visit.objects.filter(pk=self.visit.pk).update(consultorio=self.consultorio)
        self.marcado = EstudiosMed.objects.create(
            name="Tomografía de cráneo", study_type="IMG", indication="TAC simple", is_authorized="S",
        )
        self.marcado_lab = EstudiosMed.objects.create(
            name="Perfil tiroideo", study_type="LAB", indication="TSH, T3, T4", is_authorized="S",
        )
        hoy = timezone.localdate()
        self.autorizador = crear_autorizador(inicio=hoy - timedelta(days=5), fin=hoy + timedelta(days=100))
        for clave in ("LAB", "GAB"):
            agregar_alcance(asignar_tipo(self.autorizador, clave), "CENTRO", self.centro)

    def _pase(self, tipo, *estudios):
        resultado = create_referral(
            self.visit.id_visit, ["DOCTOR"], referral_type=tipo,
            studies=[{"studyTypeId": e.id} for e in estudios], actor_id=self.doctor_user.id_usuario,
        )
        return Referral.objects.get(pk=resultado["id"]), resultado


class InterruptorApagadoTests(_Base):
    def test_no_crea_solicitud(self):
        pase, contrato = self._pase(LAB, self.marcado_lab)
        self.assertEqual(pase.estatus_autorizacion, "NO_REQUIERE")
        self.assertEqual(contrato["authorizationStatus"], "NO_REQUIERE")
        self.assertFalse(Solicitud.objects.exists())


@override_settings(AUTORIZACIONES_PASES_V2=True)
class InterruptorEncendidoTests(_Base):
    def test_estudio_marcado_crea_solicitud_de_laboratorio(self):
        pase, contrato = self._pase(LAB, self.marcado_lab, self.study_type)

        self.assertEqual(pase.estatus_autorizacion, "PENDIENTE")
        self.assertEqual(contrato["authorizationStatus"], "PENDIENTE")
        solicitud = Solicitud.objects.get()
        self.assertEqual(solicitud.tipo_autorizacion.clave, "LAB")
        self.assertEqual((solicitud.tipo_origen, solicitud.id_origen), ("PASE_LABORATORIO", pase.pk))
        self.assertEqual(solicitud.centro_atencion_id, self.centro.id)
        self.assertEqual(solicitud.folio_origen, pase.folio)
        self.assertEqual(solicitud.motivos, ["ESTUDIO_MARCADO"])
        # Minimo necesario: solo los estudios que exigen autorizacion.
        self.assertEqual(
            list(solicitud.items.filter(esta_activo=True).values_list("descripcion", flat=True)),
            ["Perfil tiroideo"],
        )

    def test_pase_de_gabinete_con_estudio_de_imagen_va_como_gabinete(self):
        pase, _ = self._pase(GAB, self.marcado)
        solicitud = Solicitud.objects.get()
        self.assertEqual((solicitud.tipo_autorizacion.clave, solicitud.tipo_origen), ("GAB", "PASE_GABINETE"))
        self.assertEqual(solicitud.id_origen, pase.pk)

    def test_sin_estudios_marcados_no_requiere(self):
        pase, _ = self._pase(LAB, self.study_type)
        self.assertEqual(pase.estatus_autorizacion, "NO_REQUIERE")
        self.assertFalse(Solicitud.objects.exists())

    def test_especialidad_no_pasa_por_el_motor(self):
        create_referral(
            self.visit.id_visit, ["DOCTOR"], referral_type=Referral.ReferralType.ESPECIALIDAD,
            actor_id=self.doctor_user.id_usuario,
        )
        self.assertFalse(Solicitud.objects.exists())

    def test_sin_centro_resoluble_no_crea_solicitud(self):
        Visit.objects.filter(pk=self.visit.pk).update(consultorio=None)
        pase, _ = self._pase(LAB, self.marcado_lab)
        self.assertEqual(pase.estatus_autorizacion, "NO_REQUIERE")
        self.assertFalse(Solicitud.objects.exists())

    def _decidir(self, decision, **extra):
        solicitud = Solicitud.objects.get()
        return SolicitudUseCase.decidir(
            solicitud.uuid_publico,
            {"decision": decision, "version": solicitud.version, "credencial": CLAVE, **extra},
            actor=self.autorizador.usuario, auditoria=mock.Mock(),
        )

    def test_autorizado_en_el_motor(self):
        pase, _ = self._pase(LAB, self.marcado_lab)
        self._decidir("APROBAR")
        pase.refresh_from_db()
        self.assertEqual((pase.estatus_autorizacion, pase.status), ("AUTORIZADO", "activo"))

    def test_rechazo_cancela_solo_el_pase(self):
        pase, _ = self._pase(LAB, self.marcado_lab)
        otro_pase, _ = self._pase(GAB, self.study_type)
        self._decidir("RECHAZAR", motivoId=motivo("RECHAZO", "NO_JUSTIFICADO").id_motivo)

        pase.refresh_from_db()
        otro_pase.refresh_from_db()
        self.assertEqual((pase.estatus_autorizacion, pase.status), ("RECHAZADO", "cancelado"))
        self.assertEqual(otro_pase.status, "activo")
        self.visit.refresh_from_db()
        self.assertNotEqual(self.visit.status, "cancelada")

    def test_vencida(self):
        pase, _ = self._pase(LAB, self.marcado_lab)
        Solicitud.objects.update(fecha_limite=timezone.now() - timedelta(minutes=1))
        SolicitudUseCase.vencer_pendientes()
        pase.refresh_from_db()
        self.assertEqual(pase.estatus_autorizacion, "VENCIDO")

    def test_cancelar_el_pase_cancela_la_solicitud(self):
        pase, _ = self._pase(LAB, self.marcado_lab)
        motivo_cita = self._motivo_cancelacion()
        cancel_referral(
            pase.pk, ["DOCTOR"], cancellation_reason_id=motivo_cita.pk, actor_id=self.doctor_user.id_usuario,
        )
        self.assertEqual(Solicitud.objects.get().estatus, "CANCELADA")

    def _motivo_cancelacion(self):
        from apps.catalogos.models import MotivoCita

        return MotivoCita.objects.exclude(aplica_a=MotivoCita.AplicaA.NO_ASISTIO).filter(is_active=True).first() or (
            MotivoCita.objects.create(name="Error de captura", aplica_a=MotivoCita.AplicaA.CANCELACION)
        )


@override_settings(AUTORIZACIONES_PASES_V2=True)
class CancelacionDeNotaTests(_CancellationBase):
    def test_cancelar_la_nota_cancela_la_solicitud_del_pase(self):
        # La base crea el pase antes de asignar consultorio: se marca el estudio
        # y se sincroniza aqui, ya con centro.
        EstudiosMed.objects.filter(pk=self.study_type.pk).update(is_authorized="S")
        motor.sincronizar_solicitud(
            self.referral, self.visit, id_usuario_solicitante=self.doctor_user.id_usuario,
        )
        self.assertEqual(Solicitud.objects.get().estatus, "PENDIENTE")

        self._cancel(detail="se duplico")

        self.assertEqual(Solicitud.objects.get().estatus, "CANCELADA")
