"""Configuracion del modulo: tipos, reglas por centro y motivos.

Decisiones de la usuaria (2026-10-28):
  - Permisos propios admin:autorizaciones-config:read / :update.
  - Pestañas: tipos (solo editar), reglas por centro (alta, edicion, baja) y motivos
    (alta, edicion, activar/desactivar). Disparadores fuera: ningun flujo los lee.
  - Un cambio aplica solo a solicitudes NUEVAS: cada solicitud guarda sus reglas al crearse.
Fuera de la pantalla: dias_aviso_vencimiento (el aviso es por autorizador) y
metodo_firma_minimo (EFIRMA bloquearia todas las decisiones: no esta implementada).
"""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento
from apps.autorizaciones.contracts import solicitar_autorizacion
from apps.autorizaciones.models import Motivo, ReglaCentro, Solicitud, TipoAutorizacion
from apps.autorizaciones.uses_case.configuracion_use_case import ConfiguracionError, ConfiguracionUseCase as UseCase

from .fabricas import agregar_alcance, asignar_tipo, crear_autorizador, crear_centro, crear_usuario, tipo
from .test_autorizador_api import _cliente

URL = "/api/v1/autorizaciones/configuracion/"
LEER = "admin:autorizaciones-config:read"
EDITAR = "admin:autorizaciones-config:update"


class _Base(TestCase):
    def setUp(self):
        self.actor = crear_usuario()
        self.auditoria = mock.Mock()
        self.centro = crear_centro()

    def comun(self):
        return {"actor_id": self.actor.id_usuario, "auditoria": self.auditoria}

    def assertError(self, codigo, http, funcion, *args, **kwargs):
        with self.assertRaises(ConfiguracionError) as ctx:
            funcion(*args, **kwargs)
        self.assertEqual((ctx.exception.code, ctx.exception.http_status), (codigo, http))


# --------------------------------------------------------------------- #
# Tipos                                                                  #
# --------------------------------------------------------------------- #

class TiposTests(_Base):
    def test_edita_los_valores_que_usa_el_motor_y_sube_la_version(self):
        rec = tipo("REC")

        actualizado = UseCase.actualizar_tipo(rec.pk, {
            "version": rec.version, "modalidadPredeterminada": "MULTIPLE", "aprobacionesRequeridas": 2,
            "horasVigenciaSolicitud": 48, "horasEscalamiento": 12, "permiteRechazo": False,
            "rechazoResuelveSolicitud": False, "requiereCedula": False,
        }, **self.comun())

        self.assertEqual(actualizado.version, rec.version + 1)
        self.assertEqual(
            (actualizado.modalidad_predeterminada, actualizado.aprobaciones_requeridas,
             actualizado.horas_vigencia_solicitud, actualizado.horas_escalamiento,
             actualizado.permite_rechazo, actualizado.rechazo_resuelve_solicitud, actualizado.requiere_cedula),
            ("MULTIPLE", 2, 48, 12, False, False, False),
        )
        accion, id_recurso, antes, despues = self.auditoria.call_args.args
        self.assertEqual((accion, id_recurso), ("ConfigTipoActualizado", rec.pk))
        self.assertEqual((antes["aprobacionesRequeridas"], despues["aprobacionesRequeridas"]), (1, 2))

    def test_primero_valido_exige_una_aprobacion(self):
        rec = tipo("REC")
        self.assertError("CONFIG_INVALID", 400, UseCase.actualizar_tipo, rec.pk, {
            "version": rec.version, "modalidadPredeterminada": "PRIMERO_VALIDO", "aprobacionesRequeridas": 2,
        }, **self.comun())

    def test_aprobaciones_entre_1_y_10(self):
        rec = tipo("REC")
        for valor in (0, 11):
            self.assertError("CONFIG_INVALID", 400, UseCase.actualizar_tipo, rec.pk, {
                "version": rec.version, "modalidadPredeterminada": "MULTIPLE", "aprobacionesRequeridas": valor,
            }, **self.comun())

    def test_el_escalamiento_ocurre_antes_del_vencimiento(self):
        rec = tipo("REC")
        self.assertError("CONFIG_INVALID", 400, UseCase.actualizar_tipo, rec.pk, {
            "version": rec.version, "horasVigenciaSolicitud": 24, "horasEscalamiento": 24,
        }, **self.comun())

    def test_version_vieja_se_rechaza(self):
        rec = tipo("REC")
        self.assertError("STALE_VERSION", 409, UseCase.actualizar_tipo, rec.pk, {
            "version": rec.version + 5, "horasVigenciaSolicitud": 48,
        }, **self.comun())

    def test_aplica_solo_a_solicitudes_nuevas(self):
        hoy = timezone.localdate()
        autorizador = crear_autorizador(inicio=hoy - timedelta(days=5), fin=hoy + timedelta(days=100))
        agregar_alcance(asignar_tipo(autorizador, "REC"), "CENTRO", self.centro)
        datos = dict(
            clave_tipo="REC", id_centro=self.centro.id, id_usuario_solicitante=crear_usuario().id_usuario,
            items=[{"tipoItem": "MEDICAMENTO", "idItemOrigen": 1, "descripcion": "x", "motivo": "MEDICAMENTO_CONTROLADO"}],
            motivos=["MEDICAMENTO_CONTROLADO"],
        )
        anterior = solicitar_autorizacion(id_origen=1, **datos)
        rec = tipo("REC")

        UseCase.actualizar_tipo(rec.pk, {
            "version": rec.version, "modalidadPredeterminada": "MULTIPLE", "aprobacionesRequeridas": 2,
        }, **self.comun())
        nueva = solicitar_autorizacion(id_origen=2, **datos)

        anterior.refresh_from_db()
        self.assertEqual((anterior.modalidad, anterior.aprobaciones_requeridas), ("PRIMERO_VALIDO", 1))
        self.assertEqual((nueva.modalidad, nueva.aprobaciones_requeridas), ("MULTIPLE", 2))


# --------------------------------------------------------------------- #
# Reglas por centro                                                      #
# --------------------------------------------------------------------- #

class ReglasCentroTests(_Base):
    def _crear(self, **cambios):
        datos = {"tipoId": tipo("REC").pk, "centroId": self.centro.id, "modalidad": "MULTIPLE",
                 "aprobacionesRequeridas": 2}
        datos.update(cambios)
        return UseCase.crear_regla(datos, **self.comun())

    def test_crea_la_excepcion_del_centro_y_el_motor_la_usa(self):
        regla = self._crear(horasVigenciaSolicitud=24)

        self.assertEqual((regla.modalidad, regla.aprobaciones_requeridas, regla.horas_vigencia_solicitud),
                         ("MULTIPLE", 2, 24))
        self.assertEqual(self.auditoria.call_args.args[0], "ReglaCentroCreada")

    def test_necesita_al_menos_un_valor_propio(self):
        self.assertError("CONFIG_INVALID", 400, self._crear, modalidad=None, aprobacionesRequeridas=None)

    def test_una_regla_vigente_por_tipo_y_centro(self):
        self._crear()
        self.assertError("RULE_EXISTS", 409, self._crear)

    def test_la_combinacion_efectiva_debe_ser_valida(self):
        # El tipo es PRIMERO_VALIDO: pedir 2 aprobaciones sin cambiar la modalidad es inconsistente.
        self.assertError("CONFIG_INVALID", 400, self._crear, modalidad=None, aprobacionesRequeridas=2)

    def test_centro_inexistente(self):
        self.assertError("CONFIG_INVALID", 400, self._crear, centroId=999999)

    def test_editar_y_dar_de_baja(self):
        regla = self._crear()
        regla = UseCase.actualizar_regla(regla.pk, {"version": regla.version, "aprobacionesRequeridas": 3},
                                         **self.comun())
        self.assertEqual(regla.aprobaciones_requeridas, 3)

        UseCase.dar_baja_regla(regla.pk, {"version": regla.version}, **self.comun())

        regla.refresh_from_db()
        self.assertFalse(regla.esta_activo)
        self.assertIsNotNone(regla.fecha_baja)
        self.assertEqual(self.auditoria.call_args.args[0], "ReglaCentroBaja")
        # Dada de baja, se puede volver a crear para ese tipo y centro.
        self._crear()


# --------------------------------------------------------------------- #
# Motivos                                                                #
# --------------------------------------------------------------------- #

class MotivosTests(_Base):
    def test_alta_con_clave_normalizada(self):
        motivo = UseCase.crear_motivo({
            "ambito": "RECHAZO", "clave": "dosis excesiva", "descripcion": "Dosis por encima de lo permitido",
            "requiereDescripcionLibre": False,
        }, **self.comun())

        self.assertEqual(motivo.clave, "DOSIS_EXCESIVA")
        self.assertEqual(self.auditoria.call_args.args[0], "MotivoCreado")

    def test_clave_repetida_en_el_mismo_ambito(self):
        existente = Motivo.objects.filter(ambito="RECHAZO").first()
        self.assertError("REASON_EXISTS", 409, UseCase.crear_motivo, {
            "ambito": "RECHAZO", "clave": existente.clave, "descripcion": "otra",
        }, **self.comun())

    def test_editar_descripcion_y_desactivar(self):
        motivo = UseCase.crear_motivo({"ambito": "RECHAZO", "clave": "X1", "descripcion": "Uno"}, **self.comun())

        motivo = UseCase.actualizar_motivo(motivo.pk, {
            "version": motivo.version, "descripcion": "Uno editado", "activo": False,
        }, **self.comun())

        self.assertEqual((motivo.descripcion, motivo.esta_activo), ("Uno editado", False))

    def test_la_clave_no_cambia(self):
        motivo = UseCase.crear_motivo({"ambito": "RECHAZO", "clave": "X2", "descripcion": "Dos"}, **self.comun())
        motivo = UseCase.actualizar_motivo(motivo.pk, {"version": motivo.version, "clave": "OTRA"}, **self.comun())
        self.assertEqual(motivo.clave, "X2")

    def test_no_se_puede_desactivar_el_ultimo_activo_del_ambito(self):
        activos = list(Motivo.objects.filter(ambito="SUSPENSION", esta_activo=True))
        for motivo in activos[1:]:
            UseCase.actualizar_motivo(motivo.pk, {"version": motivo.version, "activo": False}, **self.comun())
        ultimo = Motivo.objects.get(pk=activos[0].pk)

        self.assertError("LAST_ACTIVE_REASON", 409, UseCase.actualizar_motivo, ultimo.pk,
                         {"version": ultimo.version, "activo": False}, **self.comun())


# --------------------------------------------------------------------- #
# API                                                                    #
# --------------------------------------------------------------------- #

class ConfiguracionApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.centro = crear_centro()
        self.editor = _cliente("config_editor", [LEER, EDITAR])[0]
        self.lector = _cliente("config_lector", [LEER])[0]

    def test_lista_tipos_sin_los_campos_que_no_se_editan(self):
        respuesta = self.lector.get(f"{URL}tipos/")

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        claves = {t["clave"] for t in respuesta.data["items"]}
        self.assertEqual(claves, {"LAB", "GAB", "REC", "CNO"})
        campos = set(respuesta.data["items"][0])
        self.assertTrue({"version", "horasEscalamiento", "modalidadPredeterminada"} <= campos)
        self.assertFalse({"diasAvisoVencimiento", "metodoFirmaMinimo"} & campos)

    def test_solo_lectura_no_puede_editar(self):
        rec = tipo("REC")
        respuesta = self.lector.patch(f"{URL}tipos/{rec.pk}/", {"version": rec.version, "horasVigenciaSolicitud": 48},
                                      format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_permiso_no_ve_nada(self):
        ajeno = _cliente("config_ajeno", ["admin:autorizadores:read"])[0]
        self.assertEqual(ajeno.get(f"{URL}tipos/").status_code, status.HTTP_403_FORBIDDEN)

    def test_editar_tipo_queda_auditado(self):
        rec = tipo("REC")
        respuesta = self.editor.patch(f"{URL}tipos/{rec.pk}/", {"version": rec.version, "horasVigenciaSolicitud": 48},
                                      format="json")

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.assertEqual(respuesta.data["tipo"]["horasVigenciaSolicitud"], 48)
        evento = AuditoriaEvento.objects.get(accion="ConfigTipoActualizado")
        self.assertEqual((evento.recurso_tipo, evento.recurso_id), ("autorizacion_configuracion", rec.pk))

    def test_version_vieja_responde_409(self):
        rec = tipo("REC")
        respuesta = self.editor.patch(f"{URL}tipos/{rec.pk}/", {"version": 999, "horasVigenciaSolicitud": 48},
                                      format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.data["code"], "STALE_VERSION")

    def test_ciclo_de_una_regla_por_centro(self):
        alta = self.editor.post(f"{URL}reglas/", {
            "tipoId": tipo("LAB").pk, "centroId": self.centro.id, "horasVigenciaSolicitud": 12,
        }, format="json")
        self.assertEqual(alta.status_code, status.HTTP_201_CREATED, alta.data)
        regla = alta.data["regla"]
        self.assertEqual((regla["claveTipo"], regla["centroNombre"]), ("LAB", self.centro.name))

        lista = self.lector.get(f"{URL}reglas/")
        self.assertEqual([r["id"] for r in lista.data["items"]], [regla["id"]])

        baja = self.editor.post(f"{URL}reglas/{regla['id']}/baja/", {"version": regla["version"]}, format="json")
        self.assertEqual(baja.status_code, status.HTTP_200_OK, baja.data)
        self.assertEqual(self.lector.get(f"{URL}reglas/").data["items"], [])
        self.assertFalse(ReglaCentro.objects.filter(esta_activo=True).exists())

    def test_motivos_por_ambito_incluye_inactivos(self):
        alta = self.editor.post(f"{URL}motivos/", {"ambito": "BAJA", "clave": "JUBILACION",
                                                   "descripcion": "Jubilación"}, format="json")
        self.assertEqual(alta.status_code, status.HTTP_201_CREATED, alta.data)
        motivo = alta.data["motivo"]
        self.editor.patch(f"{URL}motivos/{motivo['id']}/", {"version": motivo["version"], "activo": False},
                          format="json")

        lista = self.lector.get(f"{URL}motivos/?ambito=BAJA")

        fila = next(m for m in lista.data["items"] if m["clave"] == "JUBILACION")
        self.assertFalse(fila["activo"])
        self.assertTrue(all(m["ambito"] == "BAJA" for m in lista.data["items"]))
