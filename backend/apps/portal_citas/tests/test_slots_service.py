"""
Tests de ``services.slots_service.get_slots_portal``.

Cubre el cambio de eje de filtro (Portal de Citas — Disponibilidad por
Consultorio): filtrar por ``consultorio_id`` devuelve solo slots de ese
consultorio; sin filtros devuelve todos los slots aptos para portal de la
fecha; ``especialidad_id`` (DEPRECATED) sigue funcionando solo; y ambos
filtros combinados aplican AND.

Cubre también REQ-4 (portal-citas-filtro-clinica): el dict de cada slot
NUNCA incluye la key ``medicoNombre`` -- el nombre del médico no debe
viajar al navegador antes de que el paciente reserve.
"""

from datetime import date, datetime, timezone as dt_timezone
from unittest import mock

from django.test import TestCase

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Especialidades, Turnos
from apps.medicos.models import CatMedico, RelMedicoEspecialidad
from apps.portal_citas.services.slots_service import get_slots_portal
from apps.recepcion.models import HorarioDisponible

FECHA = date(2026, 8, 3)


class GetSlotsPortalTests(TestCase):
    def setUp(self):
        # Los horarios que ya pasaron no se listan: se congela "ahora" antes
        # de FECHA.
        ahora_patcher = mock.patch(
            "django.utils.timezone.now",
            return_value=datetime(2026, 7, 1, 12, 0, tzinfo=dt_timezone.utc),
        )
        ahora_patcher.start()
        self.addCleanup(ahora_patcher.stop)

        self.centro = CatCentroAtencion.objects.create(
            name="Centro Slots",
            code="CT-SLOTS-01",
            center_type=CatCentroAtencion.TipoCentro.CLINICA,
            is_active=True,
        )
        self.turno = Turnos.objects.create(name="Matutino", is_active=True)

        self.consultorio_a = Consultorios.objects.create(
            name="Consultorio A", numero=1, id_turn=self.turno, id_center=self.centro, is_active=True,
        )
        self.consultorio_b = Consultorios.objects.create(
            name="Consultorio B", numero=2, id_turn=self.turno, id_center=self.centro, is_active=True,
        )

        self.medico_a = self._crear_medico("medico.a")
        self.medico_b = self._crear_medico("medico.b")

        self.especialidad = Especialidades.objects.create(name="Cardiología", is_active=True)
        RelMedicoEspecialidad.objects.create(
            medico=self.medico_a, especialidad=self.especialidad, es_principal=True,
        )

        # Slot en consultorio A, médico A (con especialidad), canal LINEA.
        self.slot_a = HorarioDisponible.objects.create(
            medico=self.medico_a, consultorio=self.consultorio_a,
            fecha=FECHA, hora="08:00", canal="LINEA",
        )
        # Slot en consultorio B, médico B (sin especialidad), canal AMBOS.
        self.slot_b = HorarioDisponible.objects.create(
            medico=self.medico_b, consultorio=self.consultorio_b,
            fecha=FECHA, hora="09:00", canal="AMBOS",
        )
        # Slot presencial: nunca debe aparecer en el portal, con o sin filtro.
        HorarioDisponible.objects.create(
            medico=self.medico_a, consultorio=self.consultorio_a,
            fecha=FECHA, hora="10:00", canal="PRESENCIAL",
        )

    def _crear_medico(self, username):
        usuario = SyUsuario.objects.create(
            usuario=username, correo=f"{username}@example.com", clave_hash="x", est_activo=True,
        )
        DetUsuario.objects.create(
            id_usuario=usuario, nombre="Dr", paterno=username,
        )
        return CatMedico.objects.create(id_usuario=usuario)

    def test_sin_filtros_devuelve_todos_los_slots_aptos_para_portal(self):
        resultado = get_slots_portal(FECHA)

        slot_ids = {s["slotId"] for s in resultado}
        self.assertEqual(slot_ids, {self.slot_a.id, self.slot_b.id})

    def test_filtro_por_consultorio_devuelve_solo_sus_slots(self):
        resultado = get_slots_portal(FECHA, consultorio_id=self.consultorio_a.id)

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["slotId"], self.slot_a.id)

    def test_filtro_legado_por_especialidad_sigue_funcionando(self):
        resultado = get_slots_portal(FECHA, especialidad_id=self.especialidad.id)

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["slotId"], self.slot_a.id)

    def test_ambos_filtros_combinados_aplican_and(self):
        # consultorio_a + especialidad del medico_a -> coincide.
        resultado = get_slots_portal(
            FECHA, consultorio_id=self.consultorio_a.id, especialidad_id=self.especialidad.id,
        )
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["slotId"], self.slot_a.id)

        # consultorio_b + especialidad del medico_a -> no coincide con nada.
        resultado_sin_match = get_slots_portal(
            FECHA, consultorio_id=self.consultorio_b.id, especialidad_id=self.especialidad.id,
        )
        self.assertEqual(resultado_sin_match, [])

    def test_slots_no_incluyen_medico_nombre(self):
        resultado = get_slots_portal(FECHA)

        self.assertTrue(resultado)
        for slot in resultado:
            self.assertNotIn("medicoNombre", slot)
            self.assertEqual(
                set(slot.keys()),
                {
                    "slotId",
                    "fecha",
                    "hora",
                    "consultorioNombre",
                    "especialidadPrincipal",
                    "estado",
                },
            )
