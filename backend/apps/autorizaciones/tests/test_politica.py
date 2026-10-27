"""Politica de autorizacion (F2): funcion pura, sin base de datos.

Combina usuario, estatus, vigencia del autorizador, tipo asignado y su
vigencia, cedula, centro y autoautorizacion. Cada negativa trae un motivo
concreto para que la pantalla explique por que no se puede autorizar.
"""
from datetime import date

from django.test import SimpleTestCase

from apps.autorizaciones.domain.politica import (
    DatosAutorizador,
    DatosTipoAsignado,
    Motivo,
    evaluar,
)

HOY = date(2026, 6, 15)
CENTRO = 10


def _tipo(**cambios):
    datos = {
        "id_autorizador_tipo": 5,
        "requiere_cedula": True,
        "fecha_inicio_vigencia": None,
        "fecha_fin_vigencia": None,
        "alcances": (("CENTRO", CENTRO, None),),
    }
    datos.update(cambios)
    return DatosTipoAsignado(**datos)


def _autorizador(**cambios):
    datos = {
        "id_autorizador": 1,
        "estatus": "ACTIVO",
        "fecha_inicio_vigencia": date(2026, 1, 1),
        "fecha_fin_vigencia": date(2026, 12, 31),
        "usuario_activo": True,
        "tiene_cedula": True,
        "tipo": _tipo(),
    }
    datos.update(cambios)
    return DatosAutorizador(**datos)


def _evaluar(autorizador, *, centro=CENTRO, tipo_centro="CLINICA", fecha=HOY, solicitante=False):
    return evaluar(autorizador, id_centro=centro, tipo_centro=tipo_centro, fecha=fecha, es_solicitante=solicitante)


class PoliticaTests(SimpleTestCase):
    def test_autorizador_activo_vigente_con_tipo_y_centro(self):
        decision = _evaluar(_autorizador())
        self.assertTrue(decision)
        self.assertEqual(decision.id_autorizador, 1)
        self.assertEqual(decision.id_autorizador_tipo, 5)
        self.assertEqual(decision.alcance_aplicado, "CENTRO")

    def test_quien_no_es_autorizador(self):
        self.assertEqual(_evaluar(None).motivo, Motivo.NO_ES_AUTORIZADOR)

    def test_centro_inexistente(self):
        self.assertEqual(_evaluar(_autorizador(), tipo_centro=None).motivo, Motivo.CENTRO_NO_ENCONTRADO)

    def test_usuario_inactivo_en_sires(self):
        self.assertEqual(_evaluar(_autorizador(usuario_activo=False)).motivo, Motivo.USUARIO_INACTIVO)

    def test_suspendido_e_inactivo(self):
        self.assertEqual(_evaluar(_autorizador(estatus="SUSPENDIDO")).motivo, Motivo.AUTORIZADOR_SUSPENDIDO)
        self.assertEqual(_evaluar(_autorizador(estatus="INACTIVO")).motivo, Motivo.AUTORIZADOR_INACTIVO)

    def test_vigencia_del_autorizador_con_limites_inclusivos(self):
        self.assertTrue(_evaluar(_autorizador(), fecha=date(2026, 1, 1)))
        self.assertTrue(_evaluar(_autorizador(), fecha=date(2026, 12, 31)))
        self.assertEqual(_evaluar(_autorizador(), fecha=date(2025, 12, 31)).motivo, Motivo.VIGENCIA_NO_INICIADA)
        self.assertEqual(_evaluar(_autorizador(), fecha=date(2027, 1, 1)).motivo, Motivo.VIGENCIA_VENCIDA)

    def test_tipo_no_asignado(self):
        self.assertEqual(_evaluar(_autorizador(tipo=None)).motivo, Motivo.TIPO_NO_ASIGNADO)

    def test_vigencia_propia_del_tipo(self):
        tipo = _tipo(fecha_inicio_vigencia=date(2026, 7, 1), fecha_fin_vigencia=date(2026, 9, 30))
        self.assertEqual(_evaluar(_autorizador(tipo=tipo)).motivo, Motivo.TIPO_FUERA_DE_VIGENCIA)
        self.assertTrue(_evaluar(_autorizador(tipo=tipo), fecha=date(2026, 8, 1)))

    def test_cedula_borrada_en_usuarios_despues_del_alta(self):
        self.assertEqual(_evaluar(_autorizador(tiene_cedula=False)).motivo, Motivo.CEDULA_REQUERIDA)
        sin_exigencia = _autorizador(tiene_cedula=False, tipo=_tipo(requiere_cedula=False))
        self.assertTrue(_evaluar(sin_exigencia))

    def test_centro_no_cubierto(self):
        self.assertEqual(_evaluar(_autorizador(), centro=99).motivo, Motivo.CENTRO_NO_ASIGNADO)

    def test_cobertura_por_tipo_de_centro_y_global(self):
        por_tipo = _autorizador(tipo=_tipo(alcances=(("TIPO_CENTRO", None, "HOSPITAL"),)))
        self.assertTrue(_evaluar(por_tipo, centro=99, tipo_centro="HOSPITAL"))
        self.assertEqual(
            _evaluar(por_tipo, centro=99, tipo_centro="CLINICA").motivo, Motivo.CENTRO_NO_ASIGNADO,
        )
        global_ = _autorizador(tipo=_tipo(alcances=(("GLOBAL", None, None),)))
        self.assertEqual(_evaluar(global_, centro=99).alcance_aplicado, "GLOBAL")

    def test_gana_el_alcance_mas_especifico(self):
        tipo = _tipo(alcances=(("GLOBAL", None, None), ("TIPO_CENTRO", None, "CLINICA"), ("CENTRO", CENTRO, None)))
        self.assertEqual(_evaluar(_autorizador(tipo=tipo)).alcance_aplicado, "CENTRO")

    def test_nadie_autoriza_lo_que_el_mismo_origino(self):
        self.assertEqual(_evaluar(_autorizador(), solicitante=True).motivo, Motivo.AUTOAUTORIZACION)

    def test_cada_negativa_trae_un_mensaje_para_el_usuario(self):
        for motivo in Motivo:
            self.assertTrue(motivo.mensaje, motivo)
        decision = _evaluar(_autorizador(estatus="SUSPENDIDO"))
        self.assertFalse(decision)
        self.assertIn("suspendido", decision.mensaje.lower())
