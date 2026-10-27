"""Casos de uso de administracion de autorizadores (reglas A1-A10 del plan)."""
from datetime import date
from unittest import mock

from django.test import TestCase

from apps.autorizaciones.models import (
    Autorizador,
    AutorizadorAlcance,
    AutorizadorMovimiento,
    AutorizadorTipo,
)
from apps.autorizaciones.uses_case.autorizador_use_case import (
    AutorizadorError,
    AutorizadorUseCase as UseCase,
)

from .fabricas import crear_centro, crear_usuario, motivo, tipo


def _datos(usuario, centro, **cambios):
    datos = {
        "usuarioId": usuario.id_usuario,
        "cargo": "Jefe de servicio",
        "numeroOficio": "OF-2026-001",
        "fechaInicioVigencia": date(2026, 1, 1),
        "fechaFinVigencia": date(2026, 12, 31),
        "tipos": [
            {"claveTipo": "REC", "alcance": {"centros": [centro.id], "tiposCentro": [], "global": False}},
        ],
    }
    datos.update(cambios)
    return datos


class _Base(TestCase):
    def setUp(self):
        self.actor = crear_usuario()
        self.usuario = crear_usuario()
        self.centro = crear_centro()
        self.auditoria = mock.Mock()

    def crear(self, datos=None, *, puede_otorgar_global=False, actor_id=None):
        return UseCase.crear(
            datos or _datos(self.usuario, self.centro),
            actor_id=actor_id or self.actor.id_usuario,
            puede_otorgar_global=puede_otorgar_global,
            auditoria=self.auditoria,
        )

    def assertError(self, codigo, http_status, fn, *args, **kwargs):
        with self.assertRaises(AutorizadorError) as capturado:
            fn(*args, **kwargs)
        self.assertEqual(capturado.exception.code, codigo)
        self.assertEqual(capturado.exception.http_status, http_status)
        return capturado.exception


class CrearAutorizadorTests(_Base):
    def test_alta_crea_cabecera_tipos_alcance_historial_y_auditoria(self):
        autorizador = self.crear()

        self.assertEqual(autorizador.usuario_id, self.usuario.id_usuario)
        self.assertEqual(autorizador.estatus, "ACTIVO")
        self.assertEqual(autorizador.id_usuario_creacion, self.actor.id_usuario)
        tipo_rec = AutorizadorTipo.objects.get(autorizador=autorizador)
        self.assertEqual(tipo_rec.tipo_autorizacion.clave, "REC")
        alcance = AutorizadorAlcance.objects.get(autorizador_tipo=tipo_rec)
        self.assertEqual((alcance.tipo_alcance, alcance.centro_atencion_id), ("CENTRO", self.centro.id))
        movimiento = AutorizadorMovimiento.objects.get(autorizador=autorizador)
        self.assertEqual(movimiento.tipo_movimiento, "ALTA")
        self.assertEqual(movimiento.id_usuario_responsable, self.actor.id_usuario)
        self.auditoria.assert_called_once()
        self.assertEqual(self.auditoria.call_args.args[0], "AutorizadorCreado")

    def test_combinacion_de_tipos_y_varios_centros(self):
        otro_centro = crear_centro()
        datos = _datos(self.usuario, self.centro, tipos=[
            {"claveTipo": "LAB", "alcance": {"centros": [self.centro.id, otro_centro.id]}},
            {"claveTipo": "GAB", "alcance": {"tiposCentro": ["HOSPITAL"]}},
        ])
        autorizador = self.crear(datos)
        self.assertEqual(
            set(autorizador.tipos.values_list("tipo_autorizacion__clave", flat=True)), {"LAB", "GAB"},
        )
        self.assertEqual(AutorizadorAlcance.objects.filter(autorizador_tipo__autorizador=autorizador).count(), 3)

    def test_usuario_inexistente_o_inactivo(self):
        self.assertError("USER_INVALID", 400, self.crear, _datos(self.usuario, self.centro, usuarioId=999999))
        self.usuario.est_activo = False
        self.usuario.save()
        self.assertError("USER_INVALID", 400, self.crear)

    def test_usuario_con_autorizador_vigente(self):
        self.crear()
        self.assertError("AUTHORIZER_EXISTS", 409, self.crear)

    def test_tipo_que_exige_cedula_y_el_usuario_no_la_tiene_en_usuarios(self):
        sin_cedula = crear_usuario(con_cedula=False)
        error = self.assertError("CEDULA_REQUIRED", 400, self.crear, _datos(sin_cedula, self.centro))
        self.assertIn("Usuarios", error.message)

    def test_tipo_que_no_exige_cedula(self):
        cno = tipo("CNO")
        cno.requiere_cedula = False
        cno.save()
        sin_cedula = crear_usuario(con_cedula=False)
        self.crear(_datos(sin_cedula, self.centro, tipos=[
            {"claveTipo": "CNO", "alcance": {"centros": [self.centro.id]}},
        ]))

    def test_fin_de_vigencia_anterior_al_inicio(self):
        self.assertError("INVALID_VALIDITY", 400, self.crear, _datos(
            self.usuario, self.centro, fechaInicioVigencia=date(2026, 6, 1), fechaFinVigencia=date(2026, 5, 1),
        ))

    def test_vigencia_del_tipo_fuera_de_la_del_autorizador(self):
        self.assertError("INVALID_VALIDITY", 400, self.crear, _datos(self.usuario, self.centro, tipos=[{
            "claveTipo": "REC",
            "fechaFinVigencia": date(2027, 3, 1),
            "alcance": {"centros": [self.centro.id]},
        }]))

    def test_cada_tipo_necesita_al_menos_un_centro(self):
        self.assertError("SCOPE_REQUIRED", 400, self.crear, _datos(self.usuario, self.centro, tipos=[
            {"claveTipo": "REC", "alcance": {"centros": [], "tiposCentro": [], "global": False}},
        ]))

    def test_al_menos_un_tipo(self):
        self.assertError("VALIDATION_ERROR", 400, self.crear, _datos(self.usuario, self.centro, tipos=[]))

    def test_tipo_repetido(self):
        tipos = [{"claveTipo": "REC", "alcance": {"centros": [self.centro.id]}}] * 2
        self.assertError("VALIDATION_ERROR", 400, self.crear, _datos(self.usuario, self.centro, tipos=tipos))

    def test_tipo_o_centro_inexistente(self):
        self.assertError("VALIDATION_ERROR", 400, self.crear, _datos(self.usuario, self.centro, tipos=[
            {"claveTipo": "XYZ", "alcance": {"centros": [self.centro.id]}},
        ]))
        self.assertError("VALIDATION_ERROR", 400, self.crear, _datos(self.usuario, self.centro, tipos=[
            {"claveTipo": "REC", "alcance": {"centros": [999999]}},
        ]))

    def test_global_exige_permiso(self):
        datos = _datos(self.usuario, self.centro, tipos=[{"claveTipo": "REC", "alcance": {"global": True}}])
        self.assertError("GLOBAL_PERMISSION_REQUIRED", 403, self.crear, datos)
        self.assertFalse(Autorizador.objects.exists())
        self.crear(datos, puede_otorgar_global=True)

    def test_nadie_administra_su_propio_registro(self):
        self.assertError("SELF_ADMIN_NOT_ALLOWED", 403, self.crear, actor_id=self.usuario.id_usuario)

    def test_si_falla_la_auditoria_no_se_guarda_nada(self):
        self.auditoria.side_effect = RuntimeError("auditoria caida")
        with self.assertRaises(RuntimeError):
            self.crear()
        self.assertFalse(Autorizador.objects.exists())
        self.assertFalse(AutorizadorMovimiento.objects.exists())


class ActualizarAutorizadorTests(_Base):
    def setUp(self):
        super().setUp()
        self.autorizador = self.crear()
        self.auditoria.reset_mock()

    def actualizar(self, **cambios):
        datos = {
            "cargo": "Subdirector",
            "numeroOficio": "OF-2026-002",
            "tipos": [{"claveTipo": "REC", "alcance": {"centros": [self.centro.id]}}],
            "version": self.autorizador.version,
        }
        datos.update(cambios)
        return UseCase.actualizar(
            self.autorizador.id_autorizador, datos,
            actor_id=self.actor.id_usuario, puede_otorgar_global=False, auditoria=self.auditoria,
        )

    def test_version_desactualizada(self):
        self.assertError("STALE_VERSION", 409, self.actualizar, version=self.autorizador.version + 5)

    def test_edicion_incrementa_version_y_registra_historial(self):
        actualizado = self.actualizar()
        self.assertEqual(actualizado.version, self.autorizador.version + 1)
        self.assertEqual(actualizado.cargo, "Subdirector")
        self.assertEqual(actualizado.id_usuario_modificacion, self.actor.id_usuario)
        self.assertTrue(
            AutorizadorMovimiento.objects.filter(autorizador=actualizado, tipo_movimiento="EDICION").exists()
        )
        self.assertEqual(self.auditoria.call_args.args[0], "AutorizadorActualizado")

    def test_retirar_un_centro_es_baja_logica_y_conserva_el_registro(self):
        otro = crear_centro()
        self.actualizar(tipos=[{"claveTipo": "REC", "alcance": {"centros": [otro.id]}}])

        retirado = AutorizadorAlcance.objects.get(centro_atencion=self.centro)
        self.assertFalse(retirado.esta_activo)
        self.assertIsNotNone(retirado.fecha_baja)
        self.assertTrue(AutorizadorAlcance.objects.get(centro_atencion=otro).esta_activo)
        tipos_mov = set(
            AutorizadorMovimiento.objects.filter(autorizador=self.autorizador)
            .values_list("tipo_movimiento", flat=True)
        )
        self.assertTrue({"ALTA_CENTRO", "BAJA_CENTRO"} <= tipos_mov)

    def test_agregar_y_retirar_tipos(self):
        self.actualizar(tipos=[{"claveTipo": "LAB", "alcance": {"centros": [self.centro.id]}}])

        rec = AutorizadorTipo.objects.get(autorizador=self.autorizador, tipo_autorizacion__clave="REC")
        self.assertFalse(rec.esta_activo)
        self.assertFalse(rec.alcances.filter(esta_activo=True).exists())
        self.assertTrue(
            AutorizadorTipo.objects.filter(
                autorizador=self.autorizador, tipo_autorizacion__clave="LAB", esta_activo=True,
            ).exists()
        )
        tipos_mov = set(
            AutorizadorMovimiento.objects.filter(autorizador=self.autorizador)
            .values_list("tipo_movimiento", flat=True)
        )
        self.assertTrue({"ALTA_TIPO", "BAJA_TIPO"} <= tipos_mov)

    def test_inexistente(self):
        with self.assertRaises(AutorizadorError) as capturado:
            UseCase.actualizar(
                999999, {"tipos": [], "version": 1},
                actor_id=self.actor.id_usuario, puede_otorgar_global=False, auditoria=self.auditoria,
            )
        self.assertEqual(capturado.exception.http_status, 404)


class EstatusYVigenciaTests(_Base):
    def setUp(self):
        super().setUp()
        self.autorizador = self.crear()

    def _version(self):
        self.autorizador.refresh_from_db()
        return self.autorizador.version

    def suspender(self, **datos):
        base = {"motivoId": motivo("SUSPENSION", "LICENCIA").id_motivo, "version": self._version()}
        base.update(datos)
        return UseCase.suspender(
            self.autorizador.id_autorizador, base, actor_id=self.actor.id_usuario, auditoria=self.auditoria,
        )

    def test_suspender_exige_motivo_de_suspension(self):
        self.assertError("REASON_REQUIRED", 400, self.suspender, motivoId=None)
        self.assertError(
            "VALIDATION_ERROR", 400, self.suspender, motivoId=motivo("BAJA", "BAJA_LABORAL").id_motivo,
        )

    def test_motivo_otro_exige_descripcion(self):
        otro = motivo("SUSPENSION", "OTRO").id_motivo
        self.assertError("REASON_REQUIRED", 400, self.suspender, motivoId=otro)
        self.suspender(motivoId=otro, descripcionMotivo="Comisión sindical")

    def test_suspender_y_reactivar(self):
        suspendido = self.suspender(fechaFinSuspension=date(2026, 3, 1))
        self.assertEqual(suspendido.estatus, "SUSPENDIDO")
        self.assertEqual(suspendido.fecha_fin_suspension, date(2026, 3, 1))

        reactivado = UseCase.reactivar(
            self.autorizador.id_autorizador, {"version": self._version()},
            actor_id=self.actor.id_usuario, auditoria=self.auditoria,
        )
        self.assertEqual(reactivado.estatus, "ACTIVO")
        self.assertIsNone(reactivado.motivo_estatus_id)
        self.assertIsNone(reactivado.fecha_fin_suspension)
        tipos_mov = list(
            AutorizadorMovimiento.objects.filter(autorizador=self.autorizador)
            .order_by("id_movimiento").values_list("tipo_movimiento", flat=True)
        )
        self.assertEqual(tipos_mov, ["ALTA", "SUSPENSION", "REACTIVACION"])

    def test_solo_se_reactiva_un_suspendido(self):
        self.assertError(
            "INVALID_STATUS_TRANSITION", 409, UseCase.reactivar,
            self.autorizador.id_autorizador, {"version": self._version()},
            actor_id=self.actor.id_usuario, auditoria=self.auditoria,
        )

    def test_baja_es_terminal(self):
        dado_de_baja = UseCase.dar_de_baja(
            self.autorizador.id_autorizador,
            {"motivoId": motivo("BAJA", "BAJA_LABORAL").id_motivo, "version": self._version()},
            actor_id=self.actor.id_usuario, auditoria=self.auditoria,
        )
        self.assertEqual(dado_de_baja.estatus, "INACTIVO")
        self.assertFalse(dado_de_baja.esta_activo)
        self.assertIsNotNone(dado_de_baja.fecha_baja)
        self.assertEqual(dado_de_baja.id_usuario_baja, self.actor.id_usuario)

        self.assertError("AUTHORIZER_INACTIVE", 409, self.suspender)
        self.assertError(
            "AUTHORIZER_INACTIVE", 409, UseCase.renovar,
            self.autorizador.id_autorizador,
            {"fechaFinVigencia": date(2027, 12, 31), "version": self._version()},
            actor_id=self.actor.id_usuario, auditoria=self.auditoria,
        )

    def test_tras_la_baja_puede_volver_a_darse_de_alta(self):
        UseCase.dar_de_baja(
            self.autorizador.id_autorizador,
            {"motivoId": motivo("BAJA", "TERMINO_DESIGNACION").id_motivo, "version": self._version()},
            actor_id=self.actor.id_usuario, auditoria=self.auditoria,
        )
        self.crear()
        self.assertEqual(Autorizador.objects.filter(usuario=self.usuario).count(), 2)

    def test_renovar_solo_amplia_y_conserva_historial(self):
        self.assertError(
            "INVALID_VALIDITY", 400, UseCase.renovar,
            self.autorizador.id_autorizador,
            {"fechaFinVigencia": date(2026, 6, 30), "version": self._version()},
            actor_id=self.actor.id_usuario, auditoria=self.auditoria,
        )
        renovado = UseCase.renovar(
            self.autorizador.id_autorizador,
            {"fechaFinVigencia": date(2027, 12, 31), "version": self._version()},
            actor_id=self.actor.id_usuario, auditoria=self.auditoria,
        )
        self.assertEqual(renovado.fecha_fin_vigencia, date(2027, 12, 31))
        movimiento = AutorizadorMovimiento.objects.get(autorizador=renovado, tipo_movimiento="RENOVACION")
        self.assertEqual(movimiento.datos_anteriores["fechaFinVigencia"], "2026-12-31")
        self.assertEqual(movimiento.datos_nuevos["fechaFinVigencia"], "2027-12-31")
