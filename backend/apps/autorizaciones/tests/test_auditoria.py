"""Auditoria de solicitudes (trazabilidad NOM-024).

Decisiones de la usuaria (2026-10-28):
  - Permisos propios admin:autorizaciones-auditoria:read / :export.
  - Sin datos clinicos: folio, tipo, centro, conteos y hash; nunca nombres de
    medicamentos o estudios ni datos del paciente.
  - Exportacion a Excel (maximo 5,000 filas) registrada en la bitacora de accesos.
"""
import io
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import BitacoraAcceso
from apps.autorizaciones.models import Solicitud
from apps.autorizaciones.uses_case.auditoria_use_case import AuditoriaUseCase

from .fabricas import agregar_alcance, asignar_tipo, crear_autorizador, crear_centro, crear_usuario, motivo
from .test_autorizador_api import _cliente
from .test_solicitudes import ITEMS, _Base as _BaseSolicitudes

URL = "/api/v1/autorizaciones/auditoria/solicitudes/"
LEER = "admin:autorizaciones-auditoria:read"
EXPORTAR = "admin:autorizaciones-auditoria:export"
CLINICO = "Metilfenidato"  # descripcion del item en ITEMS: nunca debe salir en la auditoria


class AuditoriaUseCaseTests(_BaseSolicitudes):
    def test_lista_con_resumen_sin_datos_clinicos(self):
        solicitud = self.solicitar()
        self.decidir(solicitud, self.aut_a)

        filas = AuditoriaUseCase.listar({})

        fila = next(f for f in filas if f["folio"] == solicitud.folio)
        self.assertEqual(
            (fila["claveTipo"], fila["estatus"], fila["totalItems"], fila["aprobaciones"]),
            ("REC", "AUTORIZADA", 1, 1),
        )
        self.assertEqual(fila["centroNombre"], self.centro.name)
        self.assertTrue(fila["solicitanteNombre"])
        self.assertTrue(fila["resolvioNombre"])
        self.assertNotIn(CLINICO, str(fila))
        self.assertFalse({"idPaciente", "paciente", "items"} & set(fila))

    def test_filtros(self):
        autorizada = self.solicitar(id_origen=1)
        self.decidir(autorizada, self.aut_a)
        pendiente = self.solicitar(id_origen=2)

        folios = lambda filtros: {f["folio"] for f in AuditoriaUseCase.listar(filtros)}  # noqa: E731
        self.assertEqual(folios({"estatus": "PENDIENTE"}), {pendiente.folio})
        self.assertEqual(folios({"autorizadorId": self.aut_a.pk}), {autorizada.folio})
        self.assertEqual(folios({"centroId": crear_centro().id}), set())
        self.assertEqual(folios({"tipo": "LAB"}), set())
        manana = timezone.localdate() + timedelta(days=1)
        self.assertEqual(folios({"fechaDesde": manana}), set())
        self.assertEqual(folios({"fechaHasta": timezone.localdate()}), {autorizada.folio, pendiente.folio})

    def test_linea_de_tiempo_con_firma_y_destinatarios(self):
        solicitud = self.solicitar()
        self.decidir(solicitud, self.aut_a, "RECHAZAR", motivoId=motivo("RECHAZO", "OTRO").pk,
                     descripcionMotivo="Fuera de cuadro básico")

        linea = AuditoriaUseCase.linea_de_tiempo(solicitud.uuid_publico)

        solicitud.refresh_from_db()
        decision = linea["decisiones"][0]
        self.assertEqual(decision["decision"], "RECHAZAR")
        self.assertEqual(decision["ipOrigen"], "10.0.0.1")
        self.assertEqual(decision["agenteUsuario"], "pruebas")
        self.assertEqual(decision["hashContenido"], solicitud.hash_contenido)
        self.assertTrue(decision["firmaVigente"])
        self.assertTrue(decision["numeroCedula"])
        self.assertEqual(decision["descripcionMotivo"], "Fuera de cuadro básico")
        self.assertEqual([e["evento"] for e in linea["eventos"]][:1], ["CREADA"])
        self.assertIn("RECHAZADA", [e["evento"] for e in linea["eventos"]])
        self.assertEqual({d["tipoSeleccion"] for d in linea["destinatarios"]}, {"ELEGIBLES"})
        self.assertEqual(linea["solicitud"]["hashContenido"], solicitud.hash_contenido)
        self.assertNotIn(CLINICO, str(linea))

    def test_solicitud_inexistente(self):
        import uuid

        self.assertIsNone(AuditoriaUseCase.linea_de_tiempo(uuid.uuid4()))


class AuditoriaApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        hoy = timezone.localdate()
        self.centro = crear_centro()
        autorizador = crear_autorizador(inicio=hoy - timedelta(days=5), fin=hoy + timedelta(days=100))
        agregar_alcance(asignar_tipo(autorizador, "REC"), "CENTRO", self.centro)
        from apps.autorizaciones.contracts import solicitar_autorizacion

        self.solicitud = solicitar_autorizacion(
            clave_tipo="REC", id_origen=90, folio_origen="RX-2026-000090", id_centro=self.centro.id,
            id_usuario_solicitante=crear_usuario().id_usuario, items=ITEMS, motivos=["MEDICAMENTO_CONTROLADO"],
        )
        self.auditor = _cliente("auditor", [LEER, EXPORTAR])[0]
        self.lector = _cliente("auditor_lector", [LEER])[0]

    def test_listado_paginado(self):
        respuesta = self.lector.get(URL)

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.assertEqual(respuesta.data["total"], 1)
        self.assertEqual(respuesta.data["items"][0]["folio"], self.solicitud.folio)

    def test_filtro_invalido(self):
        respuesta = self.lector.get(URL, {"estatus": "INVENTADO"})
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_linea_de_tiempo(self):
        respuesta = self.lector.get(f"{URL}{self.solicitud.uuid_publico}/")

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.assertEqual(respuesta.data["solicitud"]["folio"], self.solicitud.folio)
        self.assertEqual(self.lector.get(f"{URL}00000000-0000-0000-0000-000000000000/").status_code, 404)

    def test_sin_permiso(self):
        ajeno = _cliente("auditor_ajeno", ["admin:autorizaciones-config:read"])[0]
        self.assertEqual(ajeno.get(URL).status_code, status.HTTP_403_FORBIDDEN)

    def test_exportar_exige_su_permiso(self):
        self.assertEqual(self.lector.get(URL, {"export": "xlsx"}).status_code, status.HTTP_403_FORBIDDEN)

    def test_exportar_excel_queda_en_bitacora(self):
        import openpyxl

        respuesta = self.auditor.get(URL, {"export": "xlsx"})

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertIn("attachment", respuesta["Content-Disposition"])
        filas = list(openpyxl.load_workbook(io.BytesIO(respuesta.content)).active.iter_rows(values_only=True))
        self.assertEqual(filas[0][0], "Folio")
        self.assertEqual(filas[1][0], self.solicitud.folio)
        self.assertNotIn(CLINICO, str(filas))
        self.assertTrue(
            BitacoraAcceso.objects.filter(accion=BitacoraAcceso.Accion.EXPORTAR,
                                          recurso="auditoria_autorizaciones").exists()
        )

    def test_no_expone_la_solicitud_en_otros_estatus_inexistentes(self):
        # El total cuenta solo lo filtrado.
        Solicitud.objects.filter(pk=self.solicitud.pk).update(estatus="CANCELADA")
        self.assertEqual(self.lector.get(URL, {"estatus": "PENDIENTE"}).data["total"], 0)
