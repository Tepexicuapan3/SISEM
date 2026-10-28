"""Cancelacion de nota con el modulo de autorizadores (F5, interruptor AUTORIZACIONES_NOTA_V2).

Apagado: decide la designacion vieja (cat_designacion_autorizador), sin cambios.
Encendido: decide el contrato nuevo (tipo CNO) y la cabecera guarda el
autorizador y el tipo con los que se autorizo; id_designacion queda vacio.
"""
import json
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.test import override_settings

from apps.authentication.models import DetUsuarioCedula
from apps.autorizaciones.tests.fabricas import agregar_alcance, asignar_tipo, crear_autorizador
from apps.catalogos.models import DesignacionAutorizador
from apps.consulta_medica.models import ConsultationCancellation
from apps.consulta_medica.tests.test_note_cancellation import _CancellationBase
from apps.consulta_medica.uses_case.note_cancellation_usecase import get_cancellation_preview
from apps.recepcion.services.errors import VisitDomainError

CANCEL_PERMS = ["clinico:notas:cancel"]


class _MotorBase(_CancellationBase):
    def _autorizador_nuevo(self, *, con_cedula=True):
        if con_cedula:
            DetUsuarioCedula.objects.create(
                id_usuario=self.canceller, numero="CED-NOTA-1", tipo="Médico cirujano",
                es_principal=True, orden=1,
            )
        hoy = date.today()
        autorizador = crear_autorizador(
            self.canceller, inicio=hoy - timedelta(days=30), fin=hoy + timedelta(days=365),
        )
        tipo = asignar_tipo(autorizador, "CNO")
        agregar_alcance(tipo, "CENTRO", self.center)
        return autorizador, tipo

    def _sin_designacion_vieja(self):
        DesignacionAutorizador.objects.filter(pk=self.designation.pk).update(is_active=False)

    def _preview(self):
        return get_cancellation_preview(self.visit.id_visit, self.canceller, CANCEL_PERMS)


@override_settings(AUTORIZACIONES_NOTA_V2=True)
class CancelacionConContratoNuevoTests(_MotorBase):
    def test_autoriza_el_autorizador_nuevo_y_la_cabecera_lo_registra(self):
        self._sin_designacion_vieja()
        autorizador, tipo = self._autorizador_nuevo()

        self._cancel()

        cabecera = ConsultationCancellation.objects.get()
        self.assertIsNone(cabecera.designation_id)
        self.assertEqual(cabecera.authorizer_record_id, autorizador.pk)
        self.assertEqual(cabecera.authorizer_type_id, tipo.pk)
        self.assertEqual(cabecera.applied_scope, "CENTRO")
        firmado = json.loads(cabecera.canonical_snapshot)["autorizador"]
        self.assertEqual(firmado["authorizerTypeId"], tipo.pk)
        self.assertIsNone(firmado["designationId"])

    def test_la_designacion_vieja_ya_no_alcanza(self):
        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel()

        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("AUTHORIZER_NOT_DESIGNATED", 403))
        self.assertFalse(ConsultationCancellation.objects.exists())

    def test_sin_cedula_no_autoriza(self):
        self._autorizador_nuevo(con_cedula=False)

        with self.assertRaises(VisitDomainError) as ctx:
            self._cancel()

        self.assertEqual(ctx.exception.code, "AUTHORIZER_NOT_DESIGNATED")

    def test_la_vista_previa_usa_el_contrato_nuevo(self):
        self.assertFalse(self._preview()["puedeAutorizar"])

        self._autorizador_nuevo()

        vista = self._preview()
        self.assertTrue(vista["puedeAutorizar"])
        self.assertTrue(vista["cancelable"])


class CancelacionConInterruptorApagadoTests(_MotorBase):
    def test_sigue_decidiendo_la_designacion_vieja_y_el_snapshot_no_cambia(self):
        self._autorizador_nuevo()

        self._cancel()

        cabecera = ConsultationCancellation.objects.get()
        self.assertEqual(cabecera.designation_id, self.designation.pk)
        self.assertIsNone(cabecera.authorizer_record_id)
        self.assertIsNone(cabecera.authorizer_type_id)
        self.assertNotIn("authorizerTypeId", json.loads(cabecera.canonical_snapshot)["autorizador"])


class CabeceraSinAutorizacionTests(_MotorBase):
    def test_la_base_exige_designacion_o_autorizador(self):
        self._cancel()
        cabecera = ConsultationCancellation.objects.get()

        with self.assertRaises(IntegrityError), transaction.atomic():
            ConsultationCancellation.objects.filter(pk=cabecera.pk).update(designation=None)
