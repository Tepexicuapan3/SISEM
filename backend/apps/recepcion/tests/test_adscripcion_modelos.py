"""
P-03: las reglas que protege la propia base, no el código. Si alguien escribe
directo en las tablas, la integridad se mantiene.
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.recepcion.models import (
    AdscripcionClinicaCentro,
    AdscripcionConsultorio,
    AdscripcionCitaAfectada,
    AdscripcionPaciente,
)
from apps.recepcion.tests._adscripcion_base import ID_USUARIO, AdscripcionTestBase


class AdscripcionPacienteRestriccionesTests(AdscripcionTestBase):
    def setUp(self):
        super().setUp()
        self.consultorio = self._consultorio(self.clinica5, 1)
        self.paciente = self._paciente()

    def test_una_sola_adscripcion_activa_por_paciente(self):
        self._adscribir(self.paciente, self.consultorio)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._adscribir(self.paciente, self._consultorio(self.clinica5, 2))

    def test_permite_historial_de_cerradas_y_una_activa(self):
        anterior = self._adscribir(self.paciente, self.consultorio)
        anterior.estatus = AdscripcionPaciente.Estatus.CERRADA
        anterior.fecha_fin = timezone.now()
        anterior.id_usuario_cierre = ID_USUARIO
        anterior.motivo_cierre = AdscripcionPaciente.MotivoCierre.REASIGNACION
        anterior.save()
        self._adscribir(self.paciente, self._consultorio(self.clinica5, 2))
        self.assertEqual(AdscripcionPaciente.objects.filter(paciente=self.paciente).count(), 2)

    def test_cerrada_exige_datos_de_cierre(self):
        adscripcion = self._adscribir(self.paciente, self.consultorio)
        adscripcion.estatus = AdscripcionPaciente.Estatus.CERRADA
        with self.assertRaises(IntegrityError), transaction.atomic():
            adscripcion.save()

    def test_activa_no_admite_datos_de_cierre(self):
        adscripcion = self._adscribir(self.paciente, self.consultorio)
        adscripcion.motivo_cierre = AdscripcionPaciente.MotivoCierre.REASIGNACION
        with self.assertRaises(IntegrityError), transaction.atomic():
            adscripcion.save()

    def test_fecha_fin_no_antes_del_inicio(self):
        adscripcion = self._adscribir(self.paciente, self.consultorio)
        adscripcion.estatus = AdscripcionPaciente.Estatus.CERRADA
        adscripcion.fecha_fin = adscripcion.fecha_inicio - timedelta(days=1)
        adscripcion.id_usuario_cierre = ID_USUARIO
        adscripcion.motivo_cierre = AdscripcionPaciente.MotivoCierre.REASIGNACION
        with self.assertRaises(IntegrityError), transaction.atomic():
            adscripcion.save()

    def test_origen_fuera_del_catalogo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AdscripcionPaciente.objects.create(
                paciente=self.paciente, centro=self.clinica5, clave_clinica_sermed="5",
                consultorio=self.consultorio, turno=self.matutino,
                origen="PORTAL", id_usuario_creacion=ID_USUARIO,
            )


class CatalogosAdscripcionRestriccionesTests(AdscripcionTestBase):
    def test_clave_de_clinica_unica(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AdscripcionClinicaCentro.objects.create(clave_clinica_sermed="5", centro=self.clinica7)

    def test_clave_de_clinica_no_vacia(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AdscripcionClinicaCentro.objects.create(clave_clinica_sermed="", centro=self.clinica7)

    def test_un_consultorio_se_configura_una_vez(self):
        consultorio = self._consultorio(self.clinica5, 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AdscripcionConsultorio.objects.create(consultorio=consultorio)

    def test_capacidad_mayor_a_cero(self):
        consultorio = self._consultorio(self.clinica5, 1, familiar=False)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AdscripcionConsultorio.objects.create(consultorio=consultorio, capacidad_maxima=0)


class AdscripcionCitaAfectadaRestriccionesTests(AdscripcionTestBase):
    def setUp(self):
        super().setUp()
        consultorio = self._consultorio(self.clinica5, 1)
        self.paciente = self._paciente()
        self.adscripcion = self._adscribir(self.paciente, consultorio)
        self.cita = self._cita(self.paciente, consultorio)

    def _afectada(self, **campos):
        return AdscripcionCitaAfectada.objects.create(
            adscripcion=self.adscripcion, cita_cancelada=self.cita,
            id_usuario_creacion=ID_USUARIO, **campos,
        )

    def test_nace_pendiente(self):
        self.assertEqual(self._afectada().estatus, AdscripcionCitaAfectada.Estatus.PENDIENTE)

    def test_una_cita_solo_se_registra_una_vez(self):
        self._afectada()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._afectada()

    def test_reagendada_exige_la_cita_nueva(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._afectada(
                estatus=AdscripcionCitaAfectada.Estatus.REAGENDADA, fecha_resolucion=timezone.now(),
            )

    def test_descartada_exige_motivo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._afectada(
                estatus=AdscripcionCitaAfectada.Estatus.DESCARTADA, fecha_resolucion=timezone.now(),
            )
