"""Integridad en BD del modulo de autorizaciones (F1, plan autorizadores-medicos).

Las reglas que protegen la autorizacion medica viven tambien en la base:
si el codigo falla, PostgreSQL rechaza el dato invalido.
"""
import unittest
from datetime import date

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from apps.autorizaciones.models import (
    Autorizador,
    AutorizadorAlcance,
    AutorizadorMovimiento,
    AutorizadorTipo,
    Disparador,
    TipoAutorizacion,
)

from .fabricas import (
    agregar_alcance,
    asignar_tipo,
    crear_autorizador,
    crear_centro,
    crear_usuario,
    motivo,
    tipo,
)


def _atomico(fn, *args, **kwargs):
    with transaction.atomic():
        return fn(*args, **kwargs)


class DatosInicialesTests(TestCase):
    def test_siembra_los_cuatro_tipos_de_autorizacion(self):
        claves = set(TipoAutorizacion.objects.values_list("clave", flat=True))
        self.assertEqual(claves, {"LAB", "GAB", "REC", "CNO"})

    def test_tipos_inician_en_primer_autorizador_valido_con_firma_simple(self):
        for tipo_autorizacion in TipoAutorizacion.objects.all():
            self.assertEqual(tipo_autorizacion.modalidad_predeterminada, "PRIMERO_VALIDO")
            self.assertEqual(tipo_autorizacion.aprobaciones_requeridas, 1)
            self.assertEqual(tipo_autorizacion.metodo_firma_minimo, "SIMPLE")
            self.assertEqual(tipo_autorizacion.horas_vigencia_solicitud, 72)

    def test_siembra_disparadores_del_legado_sin_el_de_costo(self):
        pares = set(Disparador.objects.values_list("tipo_autorizacion__clave", "clave"))
        self.assertEqual(pares, {
            ("REC", "MEDICAMENTO_ESPECIAL"),
            ("REC", "MEDICAMENTO_CONTROLADO"),
            ("LAB", "ESTUDIO_MARCADO"),
            ("GAB", "ESTUDIO_MARCADO"),
            ("CNO", "CANCELACION_NOTA"),
        })

    def test_motivo_otro_exige_descripcion_libre_en_cada_ambito(self):
        for ambito in ("RECHAZO", "SUSPENSION", "BAJA", "CANCELACION"):
            self.assertTrue(motivo(ambito, "OTRO").requiere_descripcion_libre)
        self.assertFalse(motivo("RECHAZO", "NO_JUSTIFICADO").requiere_descripcion_libre)


class TipoAutorizacionTests(TestCase):
    def test_primer_autorizador_valido_no_admite_varias_aprobaciones(self):
        rec = tipo("REC")
        rec.aprobaciones_requeridas = 2
        with self.assertRaises(IntegrityError):
            _atomico(rec.save)

    def test_multiple_admite_varias_aprobaciones(self):
        rec = tipo("REC")
        rec.modalidad_predeterminada = "MULTIPLE"
        rec.aprobaciones_requeridas = 2
        rec.save()

    def test_clave_activa_es_unica(self):
        with self.assertRaises(IntegrityError):
            _atomico(TipoAutorizacion.objects.create, clave="REC", nombre="Duplicado", tipo_origen="RECETA")


class DisparadorTests(TestCase):
    def test_costo_de_receta_exige_monto(self):
        with self.assertRaises(IntegrityError):
            _atomico(Disparador.objects.create, tipo_autorizacion=tipo("REC"), clave="COSTO_RECETA")

    def test_otros_disparadores_no_llevan_monto(self):
        with self.assertRaises(IntegrityError):
            _atomico(
                Disparador.objects.create,
                tipo_autorizacion=tipo("LAB"), clave="ESTUDIO_MARCADO", monto_umbral=100,
                centro_atencion=crear_centro(),
            )

    def test_costo_de_receta_con_monto_por_centro(self):
        Disparador.objects.create(
            tipo_autorizacion=tipo("REC"), clave="COSTO_RECETA", monto_umbral=1500,
            centro_atencion=crear_centro(),
        )

    def test_disparador_para_todos_los_centros_no_se_duplica(self):
        with self.assertRaises(IntegrityError):
            _atomico(Disparador.objects.create, tipo_autorizacion=tipo("LAB"), clave="ESTUDIO_MARCADO")


class AutorizadorTests(TestCase):
    def test_fin_de_vigencia_anterior_al_inicio_es_rechazado(self):
        with self.assertRaises(IntegrityError):
            _atomico(crear_autorizador, inicio=date(2026, 6, 1), fin=date(2026, 5, 31))

    def test_vigencia_de_un_solo_dia_es_valida(self):
        crear_autorizador(inicio=date(2026, 6, 1), fin=date(2026, 6, 1))

    def test_un_usuario_no_puede_tener_dos_autorizadores_vigentes(self):
        usuario = crear_usuario()
        crear_autorizador(usuario)
        with self.assertRaises(IntegrityError):
            _atomico(crear_autorizador, usuario)

    def test_tras_la_baja_el_usuario_puede_volver_a_darse_de_alta(self):
        usuario = crear_usuario()
        anterior = crear_autorizador(usuario)
        anterior.estatus = Autorizador.Estatus.INACTIVO
        anterior.motivo_estatus = motivo("BAJA", "TERMINO_DESIGNACION")
        anterior.fecha_baja = timezone.now()
        anterior.save()
        crear_autorizador(usuario)
        self.assertEqual(Autorizador.objects.filter(usuario=usuario).count(), 2)

    def test_suspender_sin_motivo_es_rechazado(self):
        with self.assertRaises(IntegrityError):
            _atomico(crear_autorizador, estatus=Autorizador.Estatus.SUSPENDIDO)

    def test_suspender_con_motivo_y_fin_de_suspension(self):
        crear_autorizador(
            estatus=Autorizador.Estatus.SUSPENDIDO,
            motivo_estatus=motivo("SUSPENSION", "LICENCIA"),
            fecha_fin_suspension=date(2026, 3, 1),
        )

    def test_fin_de_suspension_solo_aplica_a_suspendidos(self):
        with self.assertRaises(IntegrityError):
            _atomico(crear_autorizador, fecha_fin_suspension=date(2026, 3, 1))


class AutorizadorTipoTests(TestCase):
    def setUp(self):
        self.autorizador = crear_autorizador()

    def test_un_tipo_activo_por_autorizador(self):
        asignar_tipo(self.autorizador, "REC")
        with self.assertRaises(IntegrityError):
            _atomico(asignar_tipo, self.autorizador, "REC")

    def test_combinaciones_distintas_de_tipos(self):
        asignar_tipo(self.autorizador, "LAB")
        asignar_tipo(self.autorizador, "GAB")
        self.assertEqual(self.autorizador.tipos.count(), 2)

    def test_retirar_un_tipo_es_baja_logica_y_permite_reasignarlo(self):
        rec = asignar_tipo(self.autorizador, "REC")
        rec.esta_activo = False
        rec.fecha_baja = timezone.now()
        rec.save()
        asignar_tipo(self.autorizador, "REC")
        self.assertEqual(AutorizadorTipo.objects.filter(autorizador=self.autorizador).count(), 2)

    def test_vigencia_del_tipo_invalida_es_rechazada(self):
        with self.assertRaises(IntegrityError):
            _atomico(
                asignar_tipo, self.autorizador, "LAB",
                fecha_inicio_vigencia=date(2026, 6, 1), fecha_fin_vigencia=date(2026, 1, 1),
            )


class AutorizadorAlcanceTests(TestCase):
    def setUp(self):
        self.autorizador_tipo = asignar_tipo(crear_autorizador(), "REC")
        self.centro = crear_centro()

    def _crear(self, **campos):
        return _atomico(
            AutorizadorAlcance.objects.create, autorizador_tipo=self.autorizador_tipo, **campos,
        )

    def test_centro_y_tipo_de_centro_a_la_vez_es_rechazado(self):
        with self.assertRaises(IntegrityError):
            self._crear(tipo_alcance="CENTRO", centro_atencion=self.centro, tipo_centro="CLINICA")

    def test_alcance_vacio_no_equivale_a_global(self):
        with self.assertRaises(IntegrityError):
            self._crear(tipo_alcance="CENTRO")
        with self.assertRaises(IntegrityError):
            self._crear(tipo_alcance="TIPO_CENTRO")

    def test_global_no_lleva_centro_ni_tipo(self):
        with self.assertRaises(IntegrityError):
            self._crear(tipo_alcance="GLOBAL", centro_atencion=self.centro)

    def test_tipo_de_centro_fuera_de_catalogo_es_rechazado(self):
        with self.assertRaises(IntegrityError):
            self._crear(tipo_alcance="TIPO_CENTRO", tipo_centro="QUIROFANO")

    def test_varios_centros_por_tipo(self):
        agregar_alcance(self.autorizador_tipo, "CENTRO", self.centro)
        agregar_alcance(self.autorizador_tipo, "CENTRO", crear_centro())
        agregar_alcance(self.autorizador_tipo, "TIPO_CENTRO", "HOSPITAL")
        self.assertEqual(self.autorizador_tipo.alcances.count(), 3)

    def test_mismo_centro_activo_no_se_repite_pero_si_tras_retirarlo(self):
        alcance = agregar_alcance(self.autorizador_tipo, "CENTRO", self.centro)
        with self.assertRaises(IntegrityError):
            self._crear(tipo_alcance="CENTRO", centro_atencion=self.centro)

        alcance.esta_activo = False
        alcance.fecha_baja = timezone.now()
        alcance.save()
        agregar_alcance(self.autorizador_tipo, "CENTRO", self.centro)

    def test_un_solo_global_activo_por_tipo(self):
        agregar_alcance(self.autorizador_tipo, "GLOBAL")
        with self.assertRaises(IntegrityError):
            self._crear(tipo_alcance="GLOBAL")


@unittest.skipUnless(connection.vendor == "postgresql", "requiere Postgres (TESTS_EN_POSTGRES=1)")
class MovimientoSoloInsercionTests(TestCase):
    def setUp(self):
        autorizador = crear_autorizador()
        self.movimiento = AutorizadorMovimiento.objects.create(
            autorizador=autorizador, tipo_movimiento="ALTA", id_usuario_responsable=autorizador.usuario_id,
        )

    def test_no_se_puede_modificar_el_historial(self):
        with self.assertRaises(Exception):
            _atomico(
                AutorizadorMovimiento.objects.filter(pk=self.movimiento.pk).update,
                descripcion_motivo="alterado",
            )

    def test_no_se_puede_borrar_el_historial(self):
        with self.assertRaises(Exception):
            _atomico(AutorizadorMovimiento.objects.filter(pk=self.movimiento.pk).delete)
