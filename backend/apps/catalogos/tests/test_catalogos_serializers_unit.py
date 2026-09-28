from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.catalogos.serializers import (AutorizadoresDetailSerializer,
                                        PermisosDetailSerializer,
                                        RolesDetailSerializer,
                                        build_catalog_ref,
                                        build_user_ref)

# `_build_user_ref`/`_build_catalog_ref` dejaron de ser metodos de instancia
# de CatalogDetailSerializer -- ahora son funciones de MODULO
# (`build_user_ref`/`build_catalog_ref` en apps.catalogos.serializers),
# reusadas tambien fuera de serializers (ej. _HorarioReadMixin.get_center).
# Estos tests se actualizaron para reflejar eso.


class CatalogSerializersUnitTests(SimpleTestCase):
    def test_build_user_ref_when_repository_returns_none(self):
        with patch("apps.catalogos.serializers.UserRepository.get_by_id", return_value=None):
            value = build_user_ref(99)

        self.assertEqual(value, {"id": 99, "name": ""})

    def test_build_user_ref_for_profile_object_with_empty_name_uses_username(self):
        sy_user = SimpleNamespace(id_usuario=77, usuario="fallback_user")
        det_like = SimpleNamespace(nombre="", paterno="", materno="", id_usuario=sy_user)

        with patch("apps.catalogos.serializers.UserRepository.get_by_id", return_value=det_like):
            value = build_user_ref(77)

        self.assertEqual(value, {"id": 77, "name": "fallback_user"})

    def test_build_user_ref_for_syusuario_without_profile_uses_username(self):
        user = SimpleNamespace(id_usuario=55, usuario="plain_user", detalle=None)

        with patch("apps.catalogos.serializers.UserRepository.get_by_id", return_value=user):
            value = build_user_ref(55)

        self.assertEqual(value, {"id": 55, "name": "plain_user"})

    def test_autorizadores_build_catalog_ref_helper(self):
        class FakeQuerySet:
            def __init__(self, item):
                self.item = item

            def filter(self, **_kwargs):
                return self

            def only(self, *_args):
                return self

            def first(self):
                return self.item

        none_ref = build_catalog_ref(None, FakeQuerySet(None))
        found_ref = build_catalog_ref(10, FakeQuerySet(SimpleNamespace(name="Item")))
        missing_ref = build_catalog_ref(11, FakeQuerySet(None))

        self.assertIsNone(none_ref)
        self.assertEqual(found_ref, {"id": 10, "name": "Item"})
        self.assertEqual(missing_ref, {"id": 11, "name": ""})

    def test_autorizadores_field_getters_delegate_to_helpers(self):
        serializer = AutorizadoresDetailSerializer()
        obj = SimpleNamespace(center_id=1, authorization_type_id=2, user_id=3)

        with patch(
            "apps.catalogos.serializers.build_catalog_ref",
            side_effect=[{"id": 1, "name": "C"}, {"id": 2, "name": "T"}],
        ):
            center = serializer.get_center(obj)
            authorization_type = serializer.get_authorizationType(obj)

        with patch(
            "apps.catalogos.serializers.build_user_ref", return_value={"id": 3, "name": "U"},
        ):
            user = serializer.get_user(obj)

        self.assertEqual(center, {"id": 1, "name": "C"})
        self.assertEqual(authorization_type, {"id": 2, "name": "T"})
        self.assertEqual(user, {"id": 3, "name": "U"})

    def test_permisos_and_roles_detail_created_updated_by_helpers(self):
        perm_serializer = PermisosDetailSerializer()
        role_serializer = RolesDetailSerializer()
        obj = SimpleNamespace(created_by_id=10, updated_by_id=11)

        with patch(
            "apps.catalogos.serializers.build_user_ref",
            side_effect=[{"id": 10, "name": "A"}, {"id": 11, "name": "B"}],
        ):
            perm_created = perm_serializer.get_createdBy(obj)
            perm_updated = perm_serializer.get_updatedBy(obj)

        with patch(
            "apps.catalogos.serializers.build_user_ref",
            side_effect=[{"id": 10, "name": "A"}, {"id": 11, "name": "B"}],
        ):
            role_created = role_serializer.get_createdBy(obj)
            role_updated = role_serializer.get_updatedBy(obj)

        self.assertEqual(perm_created, {"id": 10, "name": "A"})
        self.assertEqual(perm_updated, {"id": 11, "name": "B"})
        self.assertEqual(role_created, {"id": 10, "name": "A"})
        self.assertEqual(role_updated, {"id": 11, "name": "B"})
