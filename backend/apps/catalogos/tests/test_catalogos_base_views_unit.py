from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.catalogos.views import CatalogBaseListCreateView


class _FakeFilterResult:
    def exists(self):
        return False


class _FakeManager:
    def filter(self, **_kwargs):
        return _FakeFilterResult()


class _FakeModel:
    objects = _FakeManager()


class _InvalidWriteSerializer:
    def __init__(self, *args, **kwargs):
        self.errors = {"field": ["error"]}

    def is_valid(self):
        return False


class _FallbackWriteSerializer:
    def __init__(self, *args, **kwargs):
        self.validated_data = {"name": "x"}

    def is_valid(self):
        return True

    def save(self, **_kwargs):
        return SimpleNamespace(id_rol=12, rol="ROLE_FROM_FALLBACK")


class _InvalidPostView(CatalogBaseListCreateView):
    model = _FakeModel
    write_serializer = _InvalidWriteSerializer

    # HasCatalogPermission ahora exige `catalog` en la vista Y hace un
    # chequeo real de auth/permisos (ver apps.catalogos.permissions) -- este
    # test unitario aisla a proposito la logica de post()/serializer de la
    # capa de autorizacion (esa ya la cubre test_catalogos_authz.py), asi
    # que no requiere ningun permiso.
    def get_permissions(self):
        return []


class _FallbackPostView(CatalogBaseListCreateView):
    model = _FakeModel
    write_serializer = _FallbackWriteSerializer

    def get_permissions(self):
        return []


class CatalogBaseViewsUnitTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_post_invalid_serializer_returns_validation_error(self):
        request = self.factory.post("/catalog", {"name": ""}, format="json")
        request.user = SimpleNamespace(id_usuario=1)

        response = _InvalidPostView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_post_fallback_id_and_name_fields(self):
        request = self.factory.post("/catalog", {"name": "x"}, format="json")
        request.user = SimpleNamespace(id_usuario=1)

        response = _FallbackPostView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], 12)
        self.assertEqual(response.data["name"], "ROLE_FROM_FALLBACK")
