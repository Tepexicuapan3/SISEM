"""F8: migracion de designaciones viejas (cat_designacion_autorizador) al modulo nuevo.

Mapeo de tipos: 01->REC, 03->LAB, 04->GAB, CN->CNO. Sin fe_fin vence al año
del inicio. GLOBAL sin fe_fin no se migra (hoy no habilita: no se amplian permisos).
"""
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.administracion.models.auditoria_evento import AuditoriaEvento
from apps.autorizaciones.models import Autorizador, AutorizadorMovimiento, AutorizadorTipo
from apps.autorizaciones.uses_case.migracion_designaciones_use_case import (
    Estado,
    migrar_designaciones,
)
from apps.catalogos.tests.designacion_factories import get_tipo, make_center, make_designation

from .fabricas import crear_autorizador, crear_usuario

HOY = date(2026, 10, 28)


def _sin_auditoria(*_args, **_kwargs):
    return None


def _migrar(aplicar=True, auditoria=_sin_auditoria):
    return migrar_designaciones(aplicar=aplicar, hoy=HOY, auditoria=auditoria)


def _por_designacion(reporte):
    return {r.id_designacion: r for r in reporte.resultados}


class MigracionDesignacionesTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        self.clinica = make_center()

    def test_cancelacion_de_nota_pasa_a_cno_con_su_centro_y_origen(self):
        designacion = make_designation(
            self.usuario, get_tipo("CN"), start=date(2026, 1, 1), end=date(2027, 6, 30),
            scopes=[("CENTRO", self.clinica)], position="Director",
        )

        reporte = _migrar()

        resultado = _por_designacion(reporte)[designacion.id]
        self.assertEqual(resultado.estado, Estado.MIGRADA)
        self.assertEqual(resultado.clave_nueva, "CNO")
        autorizador = Autorizador.objects.get(usuario=self.usuario)
        self.assertEqual(autorizador.cargo, "Director")
        self.assertEqual(autorizador.fecha_inicio_vigencia, date(2026, 1, 1))
        self.assertEqual(autorizador.fecha_fin_vigencia, date(2027, 6, 30))
        autorizador_tipo = AutorizadorTipo.objects.get(autorizador=autorizador)
        self.assertEqual(autorizador_tipo.tipo_autorizacion.clave, "CNO")
        self.assertEqual(autorizador_tipo.id_designacion_origen, designacion.id)
        alcance = autorizador_tipo.alcances.get()
        self.assertEqual((alcance.tipo_alcance, alcance.centro_atencion_id), ("CENTRO", self.clinica.id))
        self.assertTrue(
            AutorizadorMovimiento.objects.filter(autorizador=autorizador, tipo_movimiento="ALTA").exists()
        )

    def test_varias_designaciones_del_mismo_usuario_quedan_en_un_autorizador(self):
        receta = make_designation(
            self.usuario, get_tipo("01"), start=date(2026, 3, 1), end=date(2026, 12, 31),
            scopes=[("TIPO_CENTRO", "CLINICA"), ("TIPO_CENTRO", "HOSPITAL")],
        )
        laboratorio = make_designation(
            self.usuario, get_tipo("03"), start=date(2026, 1, 1), end=date(2027, 3, 31),
            scopes=[("CENTRO", self.clinica)],
        )
        gabinete = make_designation(
            self.usuario, get_tipo("04"), start=date(2026, 2, 1), end=date(2026, 11, 30),
            scopes=[("CENTRO", self.clinica)],
        )

        reporte = _migrar()

        resultados = _por_designacion(reporte)
        self.assertEqual(
            {resultados[d.id].clave_nueva for d in (receta, laboratorio, gabinete)}, {"REC", "LAB", "GAB"}
        )
        autorizador = Autorizador.objects.get(usuario=self.usuario)
        self.assertEqual(autorizador.fecha_inicio_vigencia, date(2026, 1, 1))
        self.assertEqual(autorizador.fecha_fin_vigencia, date(2027, 3, 31))
        tipos = {t.tipo_autorizacion.clave: t for t in autorizador.tipos.all()}
        self.assertEqual(set(tipos), {"REC", "LAB", "GAB"})
        self.assertEqual(tipos["REC"].fecha_inicio_vigencia, date(2026, 3, 1))
        self.assertEqual(tipos["GAB"].fecha_fin_vigencia, date(2026, 11, 30))
        self.assertEqual(
            sorted(a.tipo_centro for a in tipos["REC"].alcances.all()), ["CLINICA", "HOSPITAL"]
        )

    def test_sin_fecha_de_fin_vence_al_año_del_inicio(self):
        make_designation(
            self.usuario, get_tipo("CN"), start=date(2026, 10, 15), end=None,
            scopes=[("TIPO_CENTRO", "CLINICA")],
        )

        _migrar()

        autorizador = Autorizador.objects.get(usuario=self.usuario)
        self.assertEqual(autorizador.fecha_fin_vigencia, date(2027, 10, 15))

    def test_inicio_29_de_febrero_vence_el_28(self):
        make_designation(
            self.usuario, get_tipo("CN"), start=date(2028, 2, 29), end=None,
            scopes=[("CENTRO", self.clinica)],
        )

        _migrar()

        self.assertEqual(
            Autorizador.objects.get(usuario=self.usuario).fecha_fin_vigencia, date(2029, 2, 28)
        )

    def test_tipo_sin_equivalente_no_se_migra(self):
        designacion = make_designation(
            self.usuario, get_tipo("02"), end=date(2027, 1, 1), scopes=[("CENTRO", self.clinica)],
        )

        resultado = _por_designacion(_migrar())[designacion.id]

        self.assertEqual(resultado.estado, Estado.OMITIDA)
        self.assertEqual(resultado.motivo, "TIPO_SIN_EQUIVALENTE")
        self.assertFalse(Autorizador.objects.filter(usuario=self.usuario).exists())

    def test_global_sin_fecha_de_fin_no_se_migra_porque_hoy_no_habilita(self):
        designacion = make_designation(
            self.usuario, get_tipo("CN"), end=None, scopes=[("GLOBAL", None)],
        )

        resultado = _por_designacion(_migrar())[designacion.id]

        self.assertEqual(resultado.estado, Estado.OMITIDA)
        self.assertEqual(resultado.motivo, "GLOBAL_SIN_FECHA_FIN")
        self.assertFalse(Autorizador.objects.filter(usuario=self.usuario).exists())

    def test_designacion_vencida_no_se_migra(self):
        designacion = make_designation(
            self.usuario, get_tipo("CN"), start=date(2025, 1, 1), end=date(2026, 1, 1),
            scopes=[("CENTRO", self.clinica)],
        )

        resultado = _por_designacion(_migrar())[designacion.id]

        self.assertEqual((resultado.estado, resultado.motivo), (Estado.OMITIDA, "VENCIDA"))

    def test_designacion_sin_alcance_activo_no_se_migra(self):
        designacion = make_designation(self.usuario, get_tipo("CN"), end=date(2027, 1, 1))

        resultado = _por_designacion(_migrar())[designacion.id]

        self.assertEqual((resultado.estado, resultado.motivo), (Estado.OMITIDA, "SIN_ALCANCE"))

    def test_designacion_dada_de_baja_se_ignora(self):
        designacion = make_designation(
            self.usuario, get_tipo("CN"), end=date(2027, 1, 1), scopes=[("CENTRO", self.clinica)],
            is_active=False,
        )

        reporte = _migrar()

        self.assertNotIn(designacion.id, _por_designacion(reporte))
        self.assertFalse(Autorizador.objects.filter(usuario=self.usuario).exists())

    def test_usuario_sin_cedula_queda_omitido_con_el_motivo_de_la_regla(self):
        sin_cedula = crear_usuario(con_cedula=False)
        designacion = make_designation(
            sin_cedula, get_tipo("CN"), end=date(2027, 1, 1), scopes=[("CENTRO", self.clinica)],
        )

        resultado = _por_designacion(_migrar())[designacion.id]

        self.assertEqual((resultado.estado, resultado.motivo), (Estado.OMITIDA, "CEDULA_REQUIRED"))
        self.assertFalse(Autorizador.objects.filter(usuario=sin_cedula).exists())

    def test_un_usuario_que_falla_no_impide_migrar_a_los_demas(self):
        sin_cedula = crear_usuario(con_cedula=False)
        make_designation(sin_cedula, get_tipo("CN"), end=date(2027, 1, 1), scopes=[("CENTRO", self.clinica)])
        make_designation(self.usuario, get_tipo("CN"), end=date(2027, 1, 1), scopes=[("CENTRO", self.clinica)])

        reporte = _migrar()

        self.assertEqual(reporte.total(Estado.MIGRADA), 1)
        self.assertTrue(Autorizador.objects.filter(usuario=self.usuario).exists())

    def test_usuario_ya_registrado_en_el_modulo_nuevo_no_se_toca(self):
        existente = crear_autorizador(self.usuario)
        designacion = make_designation(
            self.usuario, get_tipo("CN"), end=date(2027, 1, 1), scopes=[("CENTRO", self.clinica)],
        )

        resultado = _por_designacion(_migrar())[designacion.id]

        self.assertEqual((resultado.estado, resultado.motivo), (Estado.OMITIDA, "AUTORIZADOR_YA_REGISTRADO"))
        self.assertEqual(Autorizador.objects.get(usuario=self.usuario).pk, existente.pk)
        self.assertFalse(AutorizadorTipo.objects.filter(autorizador=existente).exists())

    def test_correr_dos_veces_no_duplica(self):
        designacion = make_designation(
            self.usuario, get_tipo("CN"), end=date(2027, 1, 1), scopes=[("CENTRO", self.clinica)],
        )
        _migrar()

        resultado = _por_designacion(_migrar())[designacion.id]

        self.assertEqual(resultado.estado, Estado.YA_MIGRADA)
        self.assertEqual(Autorizador.objects.filter(usuario=self.usuario).count(), 1)

    def test_vista_previa_reporta_lo_mismo_sin_escribir(self):
        designacion = make_designation(
            self.usuario, get_tipo("CN"), end=date(2027, 1, 1), scopes=[("CENTRO", self.clinica)],
        )

        reporte = _migrar(aplicar=False)

        self.assertEqual(_por_designacion(reporte)[designacion.id].estado, Estado.MIGRADA)
        self.assertFalse(reporte.aplicado)
        self.assertFalse(Autorizador.objects.exists())

    def test_cada_alta_se_audita(self):
        make_designation(self.usuario, get_tipo("CN"), end=date(2027, 1, 1), scopes=[("CENTRO", self.clinica)])
        eventos = []

        _migrar(auditoria=lambda accion, id_recurso, antes, despues: eventos.append((accion, id_recurso)))

        autorizador = Autorizador.objects.get(usuario=self.usuario)
        self.assertEqual(eventos, [("AutorizadorMigrado", autorizador.pk)])


class ComandoMigrarDesignacionesTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario()
        make_designation(
            self.usuario, get_tipo("CN"), end=date(2027, 1, 1), scopes=[("CENTRO", make_center())],
        )

    def test_sin_aplicar_es_vista_previa(self):
        salida = StringIO()

        call_command("migrar_designaciones", stdout=salida)

        self.assertFalse(Autorizador.objects.exists())
        self.assertIn("VISTA PREVIA", salida.getvalue())
        self.assertIn("MIGRADA", salida.getvalue())

    def test_aplicar_escribe_y_deja_evento_de_auditoria(self):
        salida = StringIO()

        call_command("migrar_designaciones", "--aplicar", stdout=salida)

        autorizador = Autorizador.objects.get(usuario=self.usuario)
        evento = AuditoriaEvento.objects.get(accion="AutorizadorMigrado")
        self.assertEqual(evento.recurso_tipo, "autorizador")
        self.assertEqual(evento.recurso_id, autorizador.pk)
        self.assertEqual(evento.meta["module"], "autorizaciones")
        self.assertIn("APLICADO", salida.getvalue())
