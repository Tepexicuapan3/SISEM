"""Recetas en el motor de autorizaciones (F5, plan autorizadores-medicos).

Interruptor AUTORIZACIONES_RECETAS_V2 (apagado por defecto):
- apagado: todo igual que antes (no se crea solicitud en el motor);
- encendido: la autorizacion de receta crea/recalcula su solicitud, la pantalla
  vieja ya no decide esas recetas y la decision del motor se refleja aqui.
"""
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.authentication.models import SyUsuario
from apps.autorizaciones.models import Solicitud, SolicitudTransicion
from apps.autorizaciones.tests.fabricas import (
    agregar_alcance,
    asignar_tipo,
    crear_autorizador,
    motivo,
)
from apps.autorizaciones.uses_case.solicitud_use_case import SolicitudUseCase
from apps.catalogos.models import CatCies, Consultorios, Medicamentos, Turnos
from apps.catalogos.tests.designacion_factories import make_center
from apps.consulta_medica.models import PrescriptionAuthorization, VisitPrescription
from apps.consulta_medica.services import autorizacion_motor_service as motor
from apps.consulta_medica.tests.test_note_cancellation import _CancellationBase
from apps.consulta_medica.uses_case.consultation_usecase import save_diagnosis
from apps.consulta_medica.uses_case.prescription_item_usecase import (
    add_prescription_item,
    authorize_prescription,
    reject_prescription,
)
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

AUTORIZAR = ["clinico:recetas:authorize"]
CLAVE = "Clave_12345"


def _hook(**kwargs):
    return None


class _Base(TestCase):
    def setUp(self):
        self.doctor_id = SyUsuario.objects.create(
            usuario="doctor_motor", correo="doctor_motor@example.com", clave_hash="x",
        ).id_usuario
        self.validador_id = SyUsuario.objects.create(
            usuario="validador_motor", correo="validador_motor@example.com", clave_hash="x",
        ).id_usuario
        CatCies.objects.create(code="I10", description="HIPERTENSION ESENCIAL", version="CIE-10", is_active=True)
        self.especial = Medicamentos.objects.create(
            name="Medicamento Especial X", cuadro_basico=Medicamentos.CuadroBasico.ESPECIAL, is_controlled=False,
        )
        self.controlado = Medicamentos.objects.create(
            name="Medicamento Controlado Y", cuadro_basico=Medicamentos.CuadroBasico.BASICO, is_controlled=True,
        )
        self.centro = make_center()
        self.consultorio = Consultorios.objects.create(
            name="C1", numero=1, id_turn=Turnos.objects.create(name="Matutino"), id_center=self.centro,
        )
        hoy = timezone.localdate()
        self.autorizador = crear_autorizador(inicio=hoy - timedelta(days=5), fin=hoy + timedelta(days=100))
        agregar_alcance(asignar_tipo(self.autorizador, "REC"), "CENTRO", self.centro)

    def _visita(self, *, con_consultorio=True):
        n = Visit.objects.count() + 1
        visit = Visit.objects.create(
            folio=f"MOTOR-{n}", no_exp=f"EXP{7000 + n}", arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=f"APP-MOTOR-{n}", status="en_consulta",
            consultorio=self.consultorio if con_consultorio else None,
        )
        save_diagnosis(
            visit_id=visit.id_visit, roles=["DOCTOR"], primary_diagnosis="Dx", final_note="Nota",
            doctor_id=self.doctor_id, audit_hook=_hook,
        )
        return visit

    def _agregar(self, visit, medicamento):
        return add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=medicamento.id, quantity=1,
            indications="Una vez al dia", actor_id=self.doctor_id,
        )


class InterruptorApagadoTests(_Base):
    def test_no_crea_solicitud_y_la_pantalla_actual_sigue_igual(self):
        self._agregar(self._visita(), self.especial)
        autorizacion = PrescriptionAuthorization.objects.get()
        self.assertFalse(Solicitud.objects.exists())

        resultado = authorize_prescription(
            autorizacion.pk, ["FARMACIA"], actor_id=self.validador_id, permissions=AUTORIZAR, audit_hook=_hook,
        )
        self.assertEqual(resultado["status"], "autorizada")


@override_settings(AUTORIZACIONES_RECETAS_V2=True)
class InterruptorEncendidoTests(_Base):
    def test_crea_la_solicitud_en_el_motor(self):
        visit = self._visita()
        self._agregar(visit, self.especial)
        autorizacion = PrescriptionAuthorization.objects.get()
        solicitud = Solicitud.objects.get()

        self.assertEqual(solicitud.tipo_autorizacion.clave, "REC")
        self.assertEqual((solicitud.tipo_origen, solicitud.id_origen), ("RECETA", autorizacion.pk))
        self.assertEqual(solicitud.centro_atencion_id, self.centro.id)
        self.assertEqual(solicitud.id_usuario_solicitante, self.doctor_id)
        self.assertEqual(solicitud.folio_origen, VisitPrescription.objects.get().folio)
        self.assertEqual(solicitud.motivos, ["MEDICAMENTO_ESPECIAL"])
        self.assertEqual(
            list(solicitud.items.filter(esta_activo=True).values_list("descripcion", flat=True)),
            ["Medicamento Especial X"],
        )
        self.assertTrue(solicitud.destinatarios.filter(autorizador=self.autorizador).exists())

    def test_agregar_otro_medicamento_recalcula_la_misma_solicitud(self):
        visit = self._visita()
        self._agregar(visit, self.especial)
        self._agregar(visit, self.controlado)

        solicitud = Solicitud.objects.get()
        self.assertEqual(sorted(solicitud.motivos), ["MEDICAMENTO_CONTROLADO", "MEDICAMENTO_ESPECIAL"])
        self.assertEqual(solicitud.items.filter(esta_activo=True).count(), 2)
        self.assertTrue(SolicitudTransicion.objects.filter(solicitud=solicitud, evento="RECALCULADA").exists())

    def test_la_pantalla_anterior_ya_no_decide_esa_receta(self):
        self._agregar(self._visita(), self.especial)
        autorizacion = PrescriptionAuthorization.objects.get()

        for decidir, extra in ((authorize_prescription, {}), (reject_prescription, {"reason": "x"})):
            with self.assertRaises(VisitDomainError) as capturado:
                decidir(
                    autorizacion.pk, ["FARMACIA"], actor_id=self.validador_id, permissions=AUTORIZAR,
                    audit_hook=_hook, **extra,
                )
            self.assertEqual((capturado.exception.code, capturado.exception.status_code),
                             ("AUTHORIZATION_MANAGED_BY_INBOX", 409))
            # La pantalla lleva al usuario a la solicitud en la bandeja.
            self.assertEqual(capturado.exception.details,
                             {"solicitudUuid": str(Solicitud.objects.get().uuid_publico)})
        autorizacion.refresh_from_db()
        self.assertEqual(autorizacion.status, "pendiente")

    def _decidir(self, decision, **extra):
        solicitud = Solicitud.objects.get()
        return SolicitudUseCase.decidir(
            solicitud.uuid_publico,
            {"decision": decision, "version": solicitud.version, "credencial": CLAVE, **extra},
            actor=self.autorizador.usuario, auditoria=mock.Mock(),
        )

    def test_autorizar_en_el_motor_autoriza_la_receta(self):
        self._agregar(self._visita(), self.especial)
        self._decidir("APROBAR")

        autorizacion = PrescriptionAuthorization.objects.get()
        self.assertEqual(autorizacion.status, "autorizada")
        self.assertEqual(autorizacion.authorized_by_id, self.autorizador.usuario_id)
        self.assertIsNotNone(autorizacion.authorized_at)

    def test_rechazar_en_el_motor_rechaza_la_receta_con_el_motivo(self):
        self._agregar(self._visita(), self.especial)
        self._decidir(
            "RECHAZAR", motivoId=motivo("RECHAZO", "NO_JUSTIFICADO").id_motivo,
            descripcionMotivo="Hay alternativa disponible",
        )

        autorizacion = PrescriptionAuthorization.objects.get()
        self.assertEqual(autorizacion.status, "rechazada")
        self.assertIn("No está justificado clínicamente", autorizacion.rejection_reason)
        self.assertIn("Hay alternativa disponible", autorizacion.rejection_reason)

    def test_sin_centro_resoluble_sigue_el_flujo_anterior(self):
        self._agregar(self._visita(con_consultorio=False), self.especial)
        autorizacion = PrescriptionAuthorization.objects.get()
        self.assertFalse(Solicitud.objects.exists())

        resultado = authorize_prescription(
            autorizacion.pk, ["FARMACIA"], actor_id=self.validador_id, permissions=AUTORIZAR, audit_hook=_hook,
        )
        self.assertEqual(resultado["status"], "autorizada")


@override_settings(AUTORIZACIONES_RECETAS_V2=True)
class CancelacionDeNotaTests(_CancellationBase):
    def test_cancelar_la_nota_cancela_la_solicitud_del_motor(self):
        # En la base de cancelacion los items se agregan antes de asignar el
        # consultorio: se sincroniza aqui, ya con centro.
        autorizacion = PrescriptionAuthorization.objects.get()
        motor.sincronizar_solicitud(autorizacion)
        solicitud = Solicitud.objects.get()
        self.assertEqual(solicitud.estatus, "PENDIENTE")

        self._cancel(detail="se duplico")

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estatus, "CANCELADA")
