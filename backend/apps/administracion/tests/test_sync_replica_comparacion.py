"""
El sync de un expediente decide que filas de la replica actualizar
comparando la fila completa contra Oracle, no solo la fecha de
actualizacion.

Caso real (expediente 42393, 2026-11-12): en Oracle reasignaron una foto a
otro familiar (cambio pk_num) sin mover fec_actualizacion. El sync, que solo
comparaba fechas, no la actualizo y el expediente mostraba la foto con el
familiar equivocado. Otra foto tenia fec_actualizacion NULL en los dos lados
y nunca se actualizaba.
"""
import datetime as dt
import zlib
from decimal import Decimal

from django.test import SimpleTestCase

from apps.administracion.services.sync_service import _llaves_a_actualizar

COLUMNAS = ["id_empleado", "id_clave_foto", "pk_num", "tipo_foto", "foto", "fec_actualizacion"]
BLOBS = ["foto"]
FECHA = dt.datetime(2026, 10, 9, 15, 3, 51)


def _oracle(pk_num=0, foto=b"imagen", fecha=FECHA):
    return ["42393", "63013", pk_num, "F", foto, fecha]


def _replica(pk_num=0, foto=b"imagen", fecha=FECHA):
    # La replica guarda la foto comprimida y Postgres la entrega como memoryview.
    return ["42393", "63013", pk_num, "F", memoryview(zlib.compress(foto)), fecha]


def _llaves(fila_oracle, fila_replica):
    return _llaves_a_actualizar(
        {("42393", "63013"): fila_oracle},
        {("42393", "63013"): fila_replica},
        COLUMNAS, BLOBS,
    )


class LlavesAActualizarTests(SimpleTestCase):
    def test_fila_igual_no_se_actualiza(self):
        self.assertEqual(_llaves(_oracle(), _replica()), [])

    def test_misma_fecha_con_pk_num_distinto_se_actualiza(self):
        self.assertEqual(_llaves(_oracle(pk_num=7), _replica(pk_num=3)), [("42393", "63013")])

    def test_fecha_nula_en_ambos_con_foto_distinta_se_actualiza(self):
        self.assertEqual(
            _llaves(_oracle(foto=b"nueva", fecha=None), _replica(foto=b"vieja", fecha=None)),
            [("42393", "63013")],
        )

    def test_fecha_distinta_se_sigue_actualizando(self):
        self.assertEqual(
            _llaves(_oracle(fecha=FECHA + dt.timedelta(days=1)), _replica()),
            [("42393", "63013")],
        )

    def test_fecha_oracle_a_medianoche_contra_date_no_es_cambio(self):
        self.assertEqual(
            _llaves(_oracle(fecha=dt.datetime(2026, 10, 9)), _replica(fecha=dt.date(2026, 10, 9))),
            [],
        )

    def test_numero_oracle_contra_texto_de_la_replica_no_es_cambio(self):
        # NUMBER en Oracle, varchar/int en la replica: la llave y los valores se cruzan como texto.
        self.assertEqual(
            _llaves_a_actualizar(
                {(Decimal("42393"), Decimal("63013")): [Decimal("42393"), Decimal("63013"), Decimal("0"), "F", None, None]},
                {("42393", "63013"): ["42393", "63013", 0, "F", None, None]},
                COLUMNAS, BLOBS,
            ),
            [],
        )

    def test_foto_de_la_replica_sin_comprimir_se_compara_tal_cual(self):
        fila = _replica()
        fila[COLUMNAS.index("foto")] = b"imagen"
        self.assertEqual(_llaves(_oracle(), fila), [])

    def test_devuelve_la_llave_tal_como_la_tiene_la_replica(self):
        self.assertEqual(
            _llaves_a_actualizar(
                {(42393, 63013): _oracle(pk_num=7)},
                {("42393 ", "63013"): _replica(pk_num=3)},
                COLUMNAS, BLOBS,
            ),
            [("42393 ", "63013")],
        )

    def test_filas_que_solo_estan_de_un_lado_no_se_actualizan(self):
        # Altas y bajas ya las resuelven el INSERT y el DELETE.
        self.assertEqual(
            _llaves_a_actualizar(
                {("1", "1"): _oracle()}, {("2", "2"): _replica()}, COLUMNAS, BLOBS,
            ),
            [],
        )
