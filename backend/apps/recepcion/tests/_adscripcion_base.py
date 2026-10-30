"""
Datos de prueba de P-03 (adscripción a consultorio familiar).

SERMED se simula con un patch de ``buscar_expediente``, igual que los tests
del portal: la réplica vive en otra base y en los tests no existe.
"""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.consulta_medica.models import Patient, ProvisionalPatient
from apps.medicos.models import CatMedico, RelMedicoConsultorio
from apps.recepcion.models import (
    AdscripcionClinicaCentro,
    AdscripcionConsultorio,
    AdscripcionPaciente,
    CitaMedica,
    EstatusCita,
)

BUSCAR_EXPEDIENTE = "apps.recepcion.services.vigencia_service.buscar_expediente"
ID_USUARIO = 900


def fila_sermed(cd_clinica="5", estatus="ACTIVO", pk_num=None):
    """Fila como la devuelve ``buscar_expediente`` (llaves en MAYÚSCULAS)."""
    fila = {"ESTATUS": estatus, "CD_CLINICA": cd_clinica}
    if pk_num is not None:
        fila["PK_NUM"] = pk_num
    return fila


class AdscripcionTestBase(TestCase):
    def setUp(self):
        self.matutino = Turnos.objects.create(name="Matutino", is_active=True)
        self.vespertino = Turnos.objects.create(name="Vespertino", is_active=True)
        usuario = SyUsuario.objects.create(
            usuario="medico.adscripcion", correo="medico.adscripcion@example.com",
            clave_hash="x", est_activo=True,
        )
        DetUsuario.objects.create(id_usuario=usuario, nombre="Dr", paterno="Familiar")
        self.medico = CatMedico.objects.create(id_usuario=usuario)
        self.clinica5 = self._centro("Clínica 5", "CT-5", "5")
        self.clinica7 = self._centro("Clínica 7", "CT-7", "7")

    # ── Catálogos ────────────────────────────────────────────────────────────

    def _centro(self, nombre, clues, clave):
        centro = CatCentroAtencion.objects.create(
            name=nombre, code=clues,
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        AdscripcionClinicaCentro.objects.create(
            clave_clinica_sermed=clave, centro=centro, id_usuario_creacion=ID_USUARIO,
        )
        return centro

    def _consultorio(self, centro, numero, turno=None, *, familiar=True, capacidad=None, con_medico=True):
        consultorio = Consultorios.objects.create(
            name=f"Consultorio {numero}", numero=numero,
            id_turn=turno or self.matutino, id_center=centro, is_active=True,
        )
        if familiar:
            AdscripcionConsultorio.objects.create(
                consultorio=consultorio, capacidad_maxima=capacidad, id_usuario_creacion=ID_USUARIO,
            )
        if con_medico:
            RelMedicoConsultorio.objects.create(
                medico=self.medico, consultorio=consultorio,
                fecha_inicio=timezone.localdate() - timedelta(days=30), is_active=True,
            )
        return consultorio

    # ── Pacientes ────────────────────────────────────────────────────────────

    def _paciente(self, no_exp="EXP-1", pk_num=0):
        return Patient.objects.create(no_exp=no_exp, pk_num=pk_num)

    def _recien_nacido(self, no_exp="EXP-1", *, cd_provisional=100_000_001, vigente=True, vinculado=False):
        paciente = Patient.objects.create(no_exp=no_exp, pk_num=None, provisional_code=cd_provisional)
        ProvisionalPatient.objects.create(
            patient=paciente, holder_no_exp=no_exp,
            valid_until=timezone.localdate() + timedelta(days=30 if vigente else -1),
            status=ProvisionalPatient.Status.LINKED if vinculado else ProvisionalPatient.Status.PENDING,
        )
        return paciente

    def _adscribir(self, paciente, consultorio, *, clave="5"):
        return AdscripcionPaciente.objects.create(
            paciente=paciente, centro=consultorio.id_center, clave_clinica_sermed=clave,
            consultorio=consultorio, turno=consultorio.id_turn,
            origen=AdscripcionPaciente.Origen.MANUAL, id_usuario_creacion=ID_USUARIO,
        )

    def _cita(self, paciente, consultorio, *, dias=7, servicio="medicina_general", estatus=EstatusCita.AGENDADA):
        return CitaMedica.objects.create(
            folio=CitaMedica.generar_folio(), patient=paciente, medico=self.medico,
            consultorio=consultorio, fecha_hora=timezone.now() + timedelta(days=dias),
            servicio_tipo=servicio, estatus=estatus,
        )

    # ── SERMED ───────────────────────────────────────────────────────────────

    def _sermed(self, titular=None, familiares=()):
        return mock.patch(
            BUSCAR_EXPEDIENTE,
            return_value={"empleados": [titular] if titular else [], "familiares": list(familiares)},
        )
