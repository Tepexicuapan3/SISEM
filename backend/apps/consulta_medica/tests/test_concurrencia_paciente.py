"""
Plan identidad del paciente, Fase 0: linea base de concurrencia en Postgres.

SQLite (los tests normales) serializa todo y no reproduce lo que pasa cuando
dos personas agendan o abren la historia del mismo familiar en el mismo
instante. Aqui varios hilos, cada uno con su propia conexion, crean el mismo
paciente a la vez: tiene que quedar UN solo registro (1 afiliacion = 1
id_paciente).

Se corre solo en el servidor, contra una base de prueba descartable:
    TESTS_EN_POSTGRES=1 python manage.py test \
        apps.consulta_medica.tests.test_concurrencia_paciente --tag=postgres

SimpleTestCase (sin transaccion ni TRUNCATE al final): los hilos confirman de
verdad, y los triggers de bitacora inmutable rechazarian el TRUNCATE de
TransactionTestCase. La base test_<nombre> se destruye al terminar la corrida.
"""
import threading
import uuid
from unittest import skipUnless

from django.db import connection, connections
from django.test import SimpleTestCase, tag

from apps.consulta_medica.models import Patient
from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository

HILOS = 8


def _en_paralelo(funcion, hilos=HILOS):
    """Arranca `hilos` llamadas a la vez (barrera) y devuelve resultados y errores."""
    barrera = threading.Barrier(hilos)
    resultados, errores = [], []
    candado = threading.Lock()

    def correr():
        try:
            barrera.wait()
            valor = funcion()
            with candado:
                resultados.append(valor)
        except Exception as exc:  # se reporta en la asercion
            with candado:
                errores.append(exc)
        finally:
            connections.close_all()

    trabajadores = [threading.Thread(target=correr) for _ in range(hilos)]
    for trabajador in trabajadores:
        trabajador.start()
    for trabajador in trabajadores:
        trabajador.join()
    return resultados, errores


@tag("postgres")
@skipUnless(connection.vendor == "postgresql", "Solo en Postgres (TESTS_EN_POSTGRES=1).")
class AltaConcurrenteDePacienteTests(SimpleTestCase):
    databases = {"default"}

    def _no_exp_unico(self):
        # Prefijo propio: nunca coincide con un expediente real ni entre corridas.
        return f"T{uuid.uuid4().hex[:12]}"

    def test_familiar_creado_a_la_vez_queda_un_solo_registro(self):
        no_exp = self._no_exp_unico()

        resultados, errores = _en_paralelo(lambda: PatientRepository.get_or_create(no_exp, 48411)[0].pk)

        self.assertEqual(errores, [], f"Fallaron {len(errores)} hilos: {errores[:3]}")
        self.assertEqual(len(set(resultados)), 1, "Cada hilo obtuvo un id_paciente distinto")
        self.assertEqual(Patient.objects.filter(no_exp=no_exp, pk_num=48411).count(), 1)

    def test_titular_creado_a_la_vez_queda_un_solo_registro(self):
        no_exp = self._no_exp_unico()

        resultados, errores = _en_paralelo(lambda: PatientRepository.get_or_create(no_exp, 0)[0].pk)

        self.assertEqual(errores, [], f"Fallaron {len(errores)} hilos: {errores[:3]}")
        self.assertEqual(len(set(resultados)), 1)
        self.assertEqual(Patient.objects.filter(no_exp=no_exp, pk_num=0).count(), 1)
