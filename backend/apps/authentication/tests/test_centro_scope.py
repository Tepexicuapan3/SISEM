"""
Alcance por centro de atención: sobre qué centros opera cada usuario.

Hoy sale del centro de adscripción (det_usuarios.id_centro_atencion). Sin
centro no se ve nada; con el permiso alcance:centros:todos (o `*`, el
administrador) se ven todos.
"""

from django.test import TestCase

from apps.authentication.models import DetUsuario, SyUsuario
from apps.authentication.services.centro_scope import (
    PERMISO_TODOS_CENTROS,
    alcance_de,
    centro_principal,
)
from apps.catalogos.models import CatCentroAtencion
from apps.recepcion.models import Visit


class CentroScopeTests(TestCase):
    def setUp(self):
        self.ticoman = CatCentroAtencion.objects.create(
            name="TICOMAN", code="CT-T", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        self.cuauhtemoc = CatCentroAtencion.objects.create(
            name="CUAUHTEMOC", code="CT-C", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )

    def _usuario(self, nombre, centro):
        user = SyUsuario.objects.create(usuario=nombre, correo=f"{nombre}@example.com", clave_hash="x", est_activo=True)
        DetUsuario.objects.create(id_usuario=user, nombre=nombre, id_centro_atencion=centro)
        return user

    def test_usuario_con_centro_solo_tiene_su_centro(self):
        alcance = alcance_de(self._usuario("rcp.ticoman", self.ticoman), [])

        self.assertFalse(alcance.todos)
        self.assertEqual(alcance.centros, frozenset({self.ticoman.pk}))
        self.assertTrue(alcance.permite(self.ticoman.pk))
        self.assertFalse(alcance.permite(self.cuauhtemoc.pk))
        self.assertFalse(alcance.permite(None))

    def test_usuario_sin_centro_no_tiene_ninguno(self):
        alcance = alcance_de(self._usuario("rcp.sin.centro", None), [])

        self.assertEqual(alcance.centros, frozenset())
        self.assertFalse(alcance.permite(self.ticoman.pk))

    def test_permiso_todos_los_centros(self):
        alcance = alcance_de(self._usuario("supervision", None), [PERMISO_TODOS_CENTROS])

        self.assertTrue(alcance.todos)
        self.assertTrue(alcance.permite(self.cuauhtemoc.pk))
        self.assertTrue(alcance.permite(None))

    def test_administrador_ve_todos(self):
        self.assertTrue(alcance_de(self._usuario("admin.test", self.ticoman), ["*"]).todos)

    def test_filtro_sin_centros_no_devuelve_filas(self):
        alcance = alcance_de(self._usuario("rcp.vacio", None), [])

        self.assertFalse(Visit.objects.filter(alcance.q("centro_id")).exists())
        self.assertEqual(list(Visit.objects.filter(alcance.q("centro_id"))), [])

    def test_el_usuario_de_sesion_trae_su_alcance(self):
        from apps.authentication.repositories.user_repository import UserRepository

        con_centro = UserRepository.build_auth_user(self._usuario("rcp.sesion", self.ticoman))
        sin_centro = UserRepository.build_auth_user(self._usuario("rcp.sesion.vacia", None))

        self.assertEqual(
            con_centro["alcanceCentros"],
            {"todos": False, "centros": [{"id": self.ticoman.pk, "nombre": "TICOMAN"}]},
        )
        self.assertEqual(sin_centro["alcanceCentros"], {"todos": False, "centros": []})

    def test_centro_principal(self):
        user = self._usuario("rcp.principal", self.ticoman)

        self.assertEqual(centro_principal(user.pk), self.ticoman.pk)
        self.assertIsNone(centro_principal(None))
        self.assertIsNone(centro_principal(self._usuario("rcp.nada", None).pk))
