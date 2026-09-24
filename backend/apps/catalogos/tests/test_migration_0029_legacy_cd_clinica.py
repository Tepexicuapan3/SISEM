from django.db import connection
from django.test import TestCase

from apps.catalogos.models import CatCentroAtencion


class Migration0029LegacyCdClinicaTests(TestCase):
    """`CatCentroAtencion` es managed=False (ver models/centros_atencion.py):
    un `AddField` normal solo actualiza el estado de Django SIN emitir el
    ALTER TABLE. Esta prueba atrapa exactamente ese no-op silencioso --
    confirma que `cd_clinica_legado` existe FÍSICAMENTE en la tabla
    (introspección), no solo en el modelo de Django. Corre en sqlite
    (`manage.py test`), mismo motor que usa la migración 0029 en su rama
    portable de `_column_exists`.
    """

    def test_column_exists_physically_after_migrations(self):
        with connection.cursor() as cursor:
            columns = {
                col.name
                for col in connection.introspection.get_table_description(
                    cursor, "cat_centros_atencion"
                )
            }
        self.assertIn("cd_clinica_legado", columns)

    def test_field_is_usable_via_the_orm(self):
        centro = CatCentroAtencion.objects.create(
            name="Clínica de prueba",
            code="TESTCLUES01",
            center_type=CatCentroAtencion.TipoCentro.CLINICA,
            legacy_cd_clinica=5,
        )
        centro.refresh_from_db()
        self.assertEqual(centro.legacy_cd_clinica, 5)
