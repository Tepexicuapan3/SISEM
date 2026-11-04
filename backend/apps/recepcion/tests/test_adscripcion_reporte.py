"""
P-03: reporte de adscritos (/api/v1/adscripcion/reporte/...).

Cuántos derechohabientes hay adscritos por centro, consultorio y turno, y quiénes
son. Solo lectura; el listado es una lectura masiva de datos personales y se
audita.
"""

import io

import openpyxl
from django.utils import timezone
from rest_framework import status

from apps.administracion.models import AuditoriaEvento
from apps.authentication.models import DetUsuario
from apps.catalogos.models import Permisos
from apps.recepcion.models import AdscripcionPaciente
from apps.recepcion.tests._adscripcion_base import ID_USUARIO
from apps.recepcion.tests.test_adscripcion_api import AdscripcionApiBase

BASE = "/api/v1/adscripcion/reporte"
REPORTE = "admin:reportes:adscripcion:read"
TODOS = "alcance:centros:todos"  # alcance de lectura, no el de adscribir de P-03


class ReporteBase(AdscripcionApiBase):
    def setUp(self):
        super().setUp()
        self.paciente.paternal_surname, self.paciente.first_name = "Pérez", "Ana"
        self.paciente.save()
        self.familiar = self._paciente(no_exp="EXP-1", pk_num=3)
        self.otro_titular = self._paciente(no_exp="EXP-2")
        self._adscribir(self.paciente, self.cons5a)
        self._adscribir(self.familiar, self.cons5a)
        self._adscribir(self.otro_titular, self.cons5b)

        self.cons7 = self._consultorio(self.clinica7, 1, self.vespertino)
        self._adscribir(self._paciente(no_exp="EXP-7"), self.cons7, clave="7")

        cerrada = self._adscribir(self._paciente(no_exp="EXP-9"), self.cons5b)
        AdscripcionPaciente.objects.filter(pk=cerrada.pk).update(
            estatus=AdscripcionPaciente.Estatus.CERRADA,
            motivo_cierre=AdscripcionPaciente.MotivoCierre.REASIGNACION,
            fecha_fin=timezone.now(), id_usuario_cierre=ID_USUARIO,
        )


class PermisoReporteTests(ReporteBase):
    def test_la_migracion_crea_el_permiso(self):
        self.assertTrue(Permisos.objects.filter(codigo=REPORTE).exists())

    def test_sin_permiso_responde_403(self):
        self._login("sin_reporte", ["recepcion:consultorio_familiar:read"])
        self.assertEqual(self.client.get(f"{BASE}/resumen").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(f"{BASE}/adscritos").status_code, status.HTTP_403_FORBIDDEN)


class ResumenTests(ReporteBase):
    def test_cuenta_titulares_y_familiares_por_consultorio(self):
        self._login("coordinador", [REPORTE])
        response = self.client.get(f"{BASE}/resumen")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        centros = response.data["centros"]
        self.assertEqual([c["idCentroAtencion"] for c in centros], [self.clinica5.id])
        centro = centros[0]
        self.assertEqual((centro["titulares"], centro["familiares"], centro["total"]), (2, 1, 3))

        por_consultorio = {c["consultorioId"]: c for c in centro["consultorios"]}
        a, b = por_consultorio[self.cons5a.id], por_consultorio[self.cons5b.id]
        self.assertEqual((a["titulares"], a["familiares"], a["total"]), (1, 1, 2))
        self.assertEqual((b["titulares"], b["familiares"], b["total"]), (1, 0, 1))  # la cerrada no cuenta
        self.assertEqual(a["turno"], "Matutino")
        self.assertEqual(a["medicos"], ["Dr Familiar"])
        self.assertEqual(response.data["totales"], {"titulares": 2, "familiares": 1, "total": 3})

    def test_consultorio_familiar_sin_adscritos_aparece_en_cero(self):
        vacio = self._consultorio(self.clinica5, 3, self.vespertino)
        self._login("coordinador", [REPORTE])
        response = self.client.get(f"{BASE}/resumen")
        fila = next(c for c in response.data["centros"][0]["consultorios"] if c["consultorioId"] == vacio.id)
        self.assertEqual((fila["total"], fila["turno"]), (0, "Vespertino"))

    def test_con_todos_los_centros(self):
        self._login("coordinador_general", [REPORTE, TODOS])
        response = self.client.get(f"{BASE}/resumen")
        self.assertEqual(
            {c["idCentroAtencion"] for c in response.data["centros"]}, {self.clinica5.id, self.clinica7.id},
        )
        self.assertEqual(response.data["totales"]["total"], 4)

        filtrado = self.client.get(f"{BASE}/resumen", {"centroId": self.clinica7.id})
        self.assertEqual([c["idCentroAtencion"] for c in filtrado.data["centros"]], [self.clinica7.id])

    def test_otro_centro_sin_permiso_de_todos(self):
        self._login("coordinador", [REPORTE])
        response = self.client.get(f"{BASE}/resumen", {"centroId": self.clinica7.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "CENTRO_NO_PERMITIDO")

    def test_sin_centro_asignado_no_ve_nada(self):
        user = self._login("sin_centro", [REPORTE])
        DetUsuario.objects.filter(id_usuario=user).update(id_centro_atencion=None)
        response = self.client.get(f"{BASE}/resumen")
        self.assertEqual(response.data["centros"], [])
        self.assertEqual(self.client.get(f"{BASE}/adscritos").data["total"], 0)

    def test_el_resumen_no_se_audita(self):
        self._login("coordinador", [REPORTE])
        self.client.get(f"{BASE}/resumen")
        self.assertFalse(AuditoriaEvento.objects.filter(accion="ADSCRIPCION_REPORTE_LISTAR").exists())


class ListadoTests(ReporteBase):
    def test_lista_solo_activas_del_centro(self):
        self._login("coordinador", [REPORTE])
        response = self.client.get(f"{BASE}/adscritos")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 3)
        ids = {i["idPaciente"] for i in response.data["items"]}
        self.assertEqual(ids, {self.paciente.pk, self.familiar.pk, self.otro_titular.pk})

        ana = next(i for i in response.data["items"] if i["idPaciente"] == self.paciente.pk)
        self.assertEqual(ana["tipo"], "TITULAR")
        self.assertEqual(ana["nombre"], "Pérez Ana")
        self.assertEqual(ana["noExp"], "EXP-1")
        self.assertEqual(ana["consultorioId"], self.cons5a.id)
        self.assertEqual(ana["turno"], "Matutino")
        self.assertEqual(ana["centro"], "Clínica 5")

    def test_filtros(self):
        self._login("coordinador", [REPORTE])
        familiares = self.client.get(f"{BASE}/adscritos", {"tipo": "FAMILIAR"})
        self.assertEqual([i["idPaciente"] for i in familiares.data["items"]], [self.familiar.pk])
        self.assertEqual(familiares.data["items"][0]["tipo"], "FAMILIAR")

        por_consultorio = self.client.get(f"{BASE}/adscritos", {"consultorioId": self.cons5b.id})
        self.assertEqual([i["idPaciente"] for i in por_consultorio.data["items"]], [self.otro_titular.pk])

        por_turno = self.client.get(f"{BASE}/adscritos", {"turnoId": self.vespertino.id})
        self.assertEqual(por_turno.data["total"], 0)

        por_nombre = self.client.get(f"{BASE}/adscritos", {"q": "pérez"})
        self.assertEqual([i["idPaciente"] for i in por_nombre.data["items"]], [self.paciente.pk])

        por_expediente = self.client.get(f"{BASE}/adscritos", {"q": "EXP-2"})
        self.assertEqual([i["idPaciente"] for i in por_expediente.data["items"]], [self.otro_titular.pk])

    def test_paginado(self):
        self._login("coordinador", [REPORTE])
        response = self.client.get(f"{BASE}/adscritos", {"page": 2, "pageSize": 2})
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual((response.data["page"], response.data["pageSize"]), (2, 2))
        self.assertEqual((response.data["total"], response.data["totalPages"]), (3, 2))

    def test_filtro_invalido(self):
        self._login("coordinador", [REPORTE])
        response = self.client.get(f"{BASE}/adscritos", {"tipo": "OTRO"})
        self.assertEqual(response.status_code, 422)

    def test_otro_centro_sin_permiso_de_todos(self):
        self._login("coordinador", [REPORTE])
        response = self.client.get(f"{BASE}/adscritos", {"centroId": self.clinica7.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_con_todos_los_centros(self):
        self._login("coordinador_general", [REPORTE, TODOS])
        self.assertEqual(self.client.get(f"{BASE}/adscritos").data["total"], 4)

    def test_audita_la_consulta_con_sus_filtros(self):
        user = self._login("coordinador", [REPORTE])
        self.client.get(f"{BASE}/adscritos", {"tipo": "TITULAR"})
        evento = AuditoriaEvento.objects.get(accion="ADSCRIPCION_REPORTE_LISTAR")
        self.assertEqual(evento.resultado, "SUCCESS")
        self.assertEqual(evento.actor_usuario_id, user.id_usuario)
        self.assertEqual(evento.meta["filtros"]["tipo"], "TITULAR")
        self.assertEqual(evento.meta["filtros"]["centrosDelAlcance"], [self.clinica5.id])
        self.assertFalse(evento.meta["filtros"]["todosLosCentros"])
        self.assertEqual(evento.meta["total"], 2)


class ExportarTests(ReporteBase):
    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def _libro(self, response):
        return openpyxl.load_workbook(io.BytesIO(response.content))

    def test_exporta_resumen_y_adscritos_sin_paginar(self):
        self._login("coordinador", [REPORTE])
        response = self.client.get(f"{BASE}/adscritos", {"export": "xlsx", "pageSize": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], self.XLSX)
        self.assertIn("attachment;", response["Content-Disposition"])

        libro = self._libro(response)
        self.assertEqual(libro.sheetnames, ["Resumen", "Adscritos"])

        filas = list(libro["Adscritos"].iter_rows(values_only=True))
        self.assertEqual(filas[0][:4], ("Expediente", "Nombre", "Tipo", "Centro"))
        self.assertEqual(len(filas) - 1, 3)  # todas, aunque pageSize sea 1
        ana = next(f for f in filas[1:] if f[1] == "Pérez Ana")
        self.assertEqual(ana[2], "Titular")
        self.assertEqual(ana[4], self.cons5a.numero)
        self.assertEqual(ana[6], "Matutino")

        resumen = list(libro["Resumen"].iter_rows(values_only=True))
        self.assertEqual(resumen[0][:3], ("Centro", "Consultorio", "Nombre"))
        fila_a = next(f for f in resumen[1:] if f[1] == self.cons5a.numero)
        self.assertEqual(fila_a[3:7], ("Matutino", 1, 1, 2))

    def test_respeta_los_filtros(self):
        self._login("coordinador", [REPORTE])
        response = self.client.get(f"{BASE}/adscritos", {"export": "xlsx", "tipo": "FAMILIAR"})
        filas = list(self._libro(response)["Adscritos"].iter_rows(values_only=True))
        self.assertEqual([f[2] for f in filas[1:]], ["Familiar"])

    def test_otro_centro_sin_alcance(self):
        self._login("coordinador", [REPORTE])
        response = self.client.get(f"{BASE}/adscritos", {"export": "xlsx", "centroId": self.clinica7.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_se_audita_como_exportacion(self):
        self._login("coordinador", [REPORTE])
        self.client.get(f"{BASE}/adscritos", {"export": "xlsx"})
        evento = AuditoriaEvento.objects.get(accion="ADSCRIPCION_REPORTE_EXPORTAR")
        self.assertEqual(evento.meta["total"], 3)
        self.assertFalse(AuditoriaEvento.objects.filter(accion="ADSCRIPCION_REPORTE_LISTAR").exists())
