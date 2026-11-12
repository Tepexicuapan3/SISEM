"""Catalogo de medicamentos: clave (D2) e import masivo por Excel.

Reusa el motor generico de import (`CATALOG_IMPORT_REGISTRY`): solo alta,
todo-o-nada, el ID existente es error (nunca se pisa un registro).
"""

import io

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.catalogos.imports.registry import CATALOG_IMPORT_REGISTRY
from apps.catalogos.models import Medicamentos
from apps.catalogos.serializers import MedicamentosListSerializer, MedicamentosWriteSerializer
from apps.catalogos.services.catalog_import_service import build_template, parse_and_validate
from apps.catalogos.uses_case.catalog_import_use_case import ConfirmCatalogImportUseCase

HEADERS = [
    "ID", "Clave", "Nombre", "Generico", "Presentacion",
    "Cuadro", "Controlado", "Maximo de cajas", "Activo",
]


def _upload(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for row in rows:
        ws.append(list(row))
    buffer = io.BytesIO()
    wb.save(buffer)
    return SimpleUploadedFile("medicamentos.xlsx", buffer.getvalue())


def _row(id_=100, clave="010.000.0104.00", nombre="PARACETAMOL 500 MG", generico="PARACETAMOL",
         presentacion="TABLETA. CAJA CON 10", cuadro="Basico", controlado="No", cajas="2", activo="Si"):
    return (id_, clave, nombre, generico, presentacion, cuadro, controlado, cajas, activo)


def _validate(*rows):
    return parse_and_validate(CATALOG_IMPORT_REGISTRY["medications"], _upload(rows))


class MedicamentosClaveTests(TestCase):
    def test_clave_unica_entre_las_cargadas(self):
        Medicamentos.objects.create(name="A", code="010.000.0104.00")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Medicamentos.objects.create(name="B", code="010.000.0104.00")

    def test_sin_clave_no_choca(self):
        Medicamentos.objects.create(name="A")
        Medicamentos.objects.create(name="B")
        Medicamentos.objects.create(name="C", code="")
        Medicamentos.objects.create(name="D", code="")
        self.assertEqual(Medicamentos.objects.count(), 4)

    def test_el_crud_expone_la_clave(self):
        med = Medicamentos.objects.create(name="A", code="X1")
        self.assertEqual(MedicamentosListSerializer(med).data["code"], "X1")

    def test_el_crud_rechaza_una_clave_repetida(self):
        Medicamentos.objects.create(name="A", code="X1")
        serializer = MedicamentosWriteSerializer(data={"name": "B", "code": "X1"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_el_crud_permite_conservar_la_propia_clave(self):
        med = Medicamentos.objects.create(name="A", code="X1")
        serializer = MedicamentosWriteSerializer(med, data={"name": "A2", "code": "X1"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class MedicamentosImportTemplateTests(TestCase):
    def test_plantilla_con_las_columnas_del_catalogo(self):
        wb = openpyxl.load_workbook(io.BytesIO(build_template(CATALOG_IMPORT_REGISTRY["medications"])))
        self.assertEqual([c.value for c in wb.active[1]], HEADERS)


class MedicamentosImportValidationTests(TestCase):
    def test_fila_valida(self):
        result = _validate(_row(cuadro="especial", controlado="Sí"))
        self.assertEqual(result["total_errores"], 0, result["rows"])
        record = result["records"][0]
        self.assertEqual(record["code"], "010.000.0104.00")
        self.assertEqual(record["generic_name"], "PARACETAMOL")
        self.assertEqual(record["cuadro_basico"], Medicamentos.CuadroBasico.ESPECIAL)
        self.assertIs(record["is_controlled"], True)
        self.assertEqual(record["max_quantity"], 2)

    def test_vacios_toman_los_valores_por_defecto_del_catalogo(self):
        record = _validate(_row(clave="", generico="", presentacion="", cuadro="", controlado="", cajas=""))["records"][0]
        self.assertIsNone(record["code"])
        self.assertIsNone(record["generic_name"])
        self.assertIsNone(record["presentation"])
        self.assertEqual(record["cuadro_basico"], Medicamentos.CuadroBasico.BASICO)
        # Vacio NO es controlado: un controlado tiene que marcarse a proposito.
        self.assertIs(record["is_controlled"], False)
        self.assertIsNone(record["max_quantity"])

    def test_cuadro_invalido(self):
        error = _validate(_row(cuadro="Generico"))["rows"][0]["ERROR"]
        self.assertIn("Cuadro debe ser", error)

    def test_controlado_invalido(self):
        error = _validate(_row(controlado="x"))["rows"][0]["ERROR"]
        self.assertIn("Controlado debe ser 'Si' o 'No'", error)

    def test_maximo_de_cajas_invalido(self):
        for value in ("0", "-1", "2.5", "dos"):
            error = _validate(_row(cajas=value))["rows"][0]["ERROR"]
            self.assertIn("Maximo de cajas debe ser un entero mayor a 0", error, value)

    def test_nombre_obligatorio(self):
        self.assertIn("Nombre vacío", _validate(_row(nombre=""))["rows"][0]["ERROR"])

    def test_nombre_o_clave_repetidos_en_el_archivo(self):
        result = _validate(_row(id_=1), _row(id_=2))
        for row in result["rows"]:
            self.assertIn("Clave repetido en el archivo", row["ERROR"])
            self.assertIn("Nombre repetido en el archivo", row["ERROR"])

    def test_claves_vacias_no_se_consideran_repetidas(self):
        result = _validate(_row(id_=1, clave="", nombre="A"), _row(id_=2, clave="", nombre="B"))
        self.assertEqual(result["total_errores"], 0, result["rows"])

    def test_nombre_o_clave_que_ya_existen_en_el_catalogo(self):
        Medicamentos.objects.create(name="paracetamol 500 mg", code="010.000.0104.00")
        error = _validate(_row())["rows"][0]["ERROR"]
        self.assertIn("Clave ya existe en el catálogo", error)
        self.assertIn("Nombre ya existe en el catálogo", error)

    def test_id_existente_no_se_pisa(self):
        Medicamentos.objects.create(id=100, name="OTRO")
        self.assertIn("El ID ya existe", _validate(_row(id_=100))["rows"][0]["ERROR"])


class MedicamentosImportConfirmTests(TestCase):
    def test_alta_de_un_lote_valido(self):
        result = ConfirmCatalogImportUseCase().execute(
            spec=CATALOG_IMPORT_REGISTRY["medications"],
            file=_upload([_row(id_=100), _row(id_=101, clave="", nombre="CLONAZEPAM 2 MG", controlado="Si")]),
            user_id=7,
        )
        self.assertFalse(result["has_errors"], result["rows"])
        clonazepam = Medicamentos.objects.get(pk=101)
        self.assertTrue(clonazepam.is_controlled)
        self.assertIsNone(clonazepam.code)
        self.assertEqual(clonazepam.created_by_id, 7)
        self.assertEqual(Medicamentos.objects.get(pk=100).code, "010.000.0104.00")

    def test_un_error_no_da_de_alta_nada(self):
        result = ConfirmCatalogImportUseCase().execute(
            spec=CATALOG_IMPORT_REGISTRY["medications"],
            file=_upload([_row(id_=100), _row(id_=101, nombre="OTRO", clave="Y", cuadro="mal")]),
            user_id=7,
        )
        self.assertTrue(result["has_errors"])
        self.assertEqual(Medicamentos.objects.count(), 0)
