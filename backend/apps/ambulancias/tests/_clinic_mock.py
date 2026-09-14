"""
CatClinica vive en la base de datos "expedientes" (ver
routers.ExpedientesRouter) y es managed=False (tabla replicada de Oracle,
nunca creada por una migracion) -- no existe forma de crear una fila real
en el test runner (settings.py ni siquiera define el alias "expedientes"
cuando corre `manage.py test`). Se simula con un mock en vez de un fixture
real, igual que se haria con cualquier dependencia externa no disponible en
tests.
"""
from unittest.mock import MagicMock, patch


class FakeClinicQuerySet:
    def __init__(self, clinic_id, name):
        self._clinic_id = clinic_id
        self._name = name

    def exists(self):
        return True

    def only(self, *args, **kwargs):
        return self

    def first(self):
        clinic = MagicMock()
        clinic.cd_clinica = self._clinic_id
        clinic.ds_clinica = self._name
        return clinic


def mock_clinic(test_case, clinic_id="7", name="Clinica Central"):
    """Parchea CatClinica.objects.filter(pk=clinic_id) en uses_case y
    repository para simular una clinica existente sin tocar la BD real."""
    queryset = FakeClinicQuerySet(clinic_id, name)
    patcher = patch(
        "apps.administracion.models.CatClinica.objects.filter",
        return_value=queryset,
    )
    patcher.start()
    test_case.addCleanup(patcher.stop)
    return clinic_id
