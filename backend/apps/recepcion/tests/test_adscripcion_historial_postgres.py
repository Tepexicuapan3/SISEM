"""
P-03: el historial de adscripciones protegido por la base (migración 0033).

Solo en PostgreSQL (TESTS_EN_POSTGRES=True): en SQLite el trigger y la vista
no existen y estas pruebas se saltan.
"""

from datetime import timedelta
from unittest import skipUnless

from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.recepcion.models import AdscripcionPaciente
from apps.recepcion.tests._adscripcion_base import ID_USUARIO, AdscripcionTestBase


@skipUnless(connection.vendor == "postgresql", "El trigger y la vista solo existen en PostgreSQL")
class HistorialProtegidoTests(AdscripcionTestBase):
    def setUp(self):
        super().setUp()
        self.consultorio = self._consultorio(self.clinica5, 1)
        self.otro = self._consultorio(self.clinica5, 2)
        self.paciente = self._paciente()
        self.adscripcion = self._adscribir(self.paciente, self.consultorio)

    def _cerrar(self, adscripcion, motivo=AdscripcionPaciente.MotivoCierre.REASIGNACION):
        AdscripcionPaciente.objects.filter(pk=adscripcion.pk).update(
            estatus=AdscripcionPaciente.Estatus.CERRADA,
            fecha_fin=adscripcion.fecha_inicio + timedelta(minutes=1),
            id_usuario_cierre=ID_USUARIO,
            motivo_cierre=motivo,
        )

    def test_no_se_borra(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            AdscripcionPaciente.objects.filter(pk=self.adscripcion.pk).delete()

    def test_cerrar_esta_permitido(self):
        self._cerrar(self.adscripcion)
        self.adscripcion.refresh_from_db()
        self.assertEqual(self.adscripcion.estatus, AdscripcionPaciente.Estatus.CERRADA)

    def test_una_cerrada_no_se_modifica(self):
        self._cerrar(self.adscripcion)
        with self.assertRaises(DatabaseError), transaction.atomic():
            AdscripcionPaciente.objects.filter(pk=self.adscripcion.pk).update(observaciones="cambio")

    def test_una_activa_no_cambia_de_consultorio(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            AdscripcionPaciente.objects.filter(pk=self.adscripcion.pk).update(consultorio=self.otro)

    def test_una_activa_no_cambia_la_clave_de_sermed(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            AdscripcionPaciente.objects.filter(pk=self.adscripcion.pk).update(clave_clinica_sermed="7")

    def test_vista_registra_el_cambio_de_clinica(self):
        self._cerrar(self.adscripcion, AdscripcionPaciente.MotivoCierre.CAMBIO_CLINICA)
        nuevo = self._consultorio(self.clinica7, 1)
        AdscripcionPaciente.objects.create(
            paciente=self.paciente, centro=self.clinica7, clave_clinica_sermed="7",
            consultorio=nuevo, turno=nuevo.id_turn, origen=AdscripcionPaciente.Origen.MANUAL,
            fecha_inicio=timezone.now() + timedelta(minutes=2), id_usuario_creacion=ID_USUARIO,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT clave_clinica_anterior, clave_clinica_nueva, id_consultorio_anterior, "
                "id_consultorio_nuevo, motivo_cambio FROM adscripcion_paciente_cambios "
                "WHERE id_paciente = %s",
                [self.paciente.pk],
            )
            filas = cursor.fetchall()
        self.assertEqual(filas, [("5", "7", self.consultorio.pk, nuevo.pk, "CAMBIO_CLINICA")])
