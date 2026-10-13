"""Cobertura de `CatMedico` (campos personales + CheckConstraint, R3) y de los
helpers de `apps.medicos.identity` (R4): display_name / nombre_partes /
cedula_profesional / annotate_display_name en los dos modos (con y sin
usuario), sin excepción por usuario ausente y con número de queries
constante."""

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from apps.authentication.models import DetUsuario, DetUsuarioCedula, SyUsuario
from apps.medicos import identity
from apps.medicos.models import CatMedico


def _usuario(username, *, con_detalle=True, nombre="Ana", paterno="Pérez", materno="Gómez"):
    user = SyUsuario.objects.create(
        usuario=username,
        correo=f"{username}@example.com",
        clave_hash=make_password("x"),
        est_activo=True,
    )
    if con_detalle:
        DetUsuario.objects.create(id_usuario=user, nombre=nombre, paterno=paterno, materno=materno)
    return user


def _cargar(medico_id):
    """Recarga el médico con el select_related/prefetch estándar de identity."""
    qs = identity.with_identity(CatMedico.objects.filter(id=medico_id))
    return qs.prefetch_related(*identity.IDENTITY_PREFETCH).get()


class CatMedicoConstraintTests(TestCase):
    def test_sin_usuario_acepta_datos_personales(self):
        medico = CatMedico.objects.create(
            nombre="Juan", paterno="López", materno="Ramírez", cedula_profesional="12345678"
        )
        medico.refresh_from_db()
        self.assertEqual(medico.nombre, "Juan")
        self.assertEqual(medico.cedula_profesional, "12345678")

    def test_cedula_acepta_30_caracteres(self):
        medico = CatMedico.objects.create(nombre="Juan", cedula_profesional="9" * 30)
        medico.refresh_from_db()
        self.assertEqual(len(medico.cedula_profesional), 30)

    def test_con_usuario_rechaza_datos_personales(self):
        user = _usuario("dr_constraint")
        for campo in ("nombre", "paterno", "materno", "cedula_profesional"):
            with self.subTest(campo=campo):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    CatMedico.objects.create(id_usuario=user, **{campo: "x"})
        for campo, valor in (("id_escuela_id", 1), ("sexo", "M"), ("fecha_nac", "1975-03-15")):
            with self.subTest(campo=campo):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    CatMedico.objects.create(id_usuario=user, **{campo: valor})

    def test_con_usuario_sin_datos_personales_ok(self):
        user = _usuario("dr_limpio")
        self.assertIsNotNone(CatMedico.objects.create(id_usuario=user).pk)


class DisplayNameTests(TestCase):
    def test_con_usuario_usa_detalle(self):
        user = _usuario("dr_det")
        medico = CatMedico.objects.create(id_usuario=user)
        self.assertEqual(identity.display_name(_cargar(medico.id)), "Ana Pérez Gómez")

    def test_con_usuario_sin_detalle_usa_username(self):
        user = _usuario("dr_sin_det", con_detalle=False)
        medico = CatMedico.objects.create(id_usuario=user)
        self.assertEqual(identity.display_name(_cargar(medico.id)), "dr_sin_det")

    def test_sin_usuario_compone_nombre_paterno_materno(self):
        medico = CatMedico.objects.create(nombre="Juan", paterno="López", materno="Ramírez")
        self.assertEqual(identity.display_name(_cargar(medico.id)), "Juan López Ramírez")

    def test_sin_usuario_con_partes_faltantes_no_deja_espacios_sobrantes(self):
        medico = CatMedico.objects.create(nombre="Juan", paterno="López")
        self.assertEqual(identity.display_name(_cargar(medico.id)), "Juan López")

    def test_sin_usuario_sin_datos_devuelve_placeholder_sin_excepcion(self):
        medico = CatMedico.objects.create()
        self.assertEqual(identity.display_name(_cargar(medico.id)), f"Médico #{medico.id}")


class NombrePartesTests(TestCase):
    def test_con_usuario(self):
        medico = CatMedico.objects.create(id_usuario=_usuario("dr_partes"))
        partes = identity.nombre_partes(_cargar(medico.id))
        self.assertEqual((partes.nombre, partes.paterno, partes.materno), ("Ana", "Pérez", "Gómez"))

    def test_sin_usuario(self):
        medico = CatMedico.objects.create(nombre="Juan", paterno="López")
        partes = identity.nombre_partes(_cargar(medico.id))
        self.assertEqual((partes.nombre, partes.paterno, partes.materno), ("Juan", "López", None))

    def test_usuario_sin_detalle_devuelve_vacio(self):
        medico = CatMedico.objects.create(id_usuario=_usuario("dr_partes_sd", con_detalle=False))
        partes = identity.nombre_partes(_cargar(medico.id))
        self.assertEqual((partes.nombre, partes.paterno, partes.materno), (None, None, None))


class CedulaProfesionalTests(TestCase):
    def test_sin_usuario_usa_campo_propio(self):
        medico = CatMedico.objects.create(nombre="Juan", cedula_profesional="ABC123")
        self.assertEqual(identity.cedula_profesional(_cargar(medico.id)), "ABC123")

    def test_sin_usuario_sin_cedula_es_none(self):
        medico = CatMedico.objects.create(nombre="Juan")
        self.assertIsNone(identity.cedula_profesional(_cargar(medico.id)))

    def test_usuario_sin_cedulas_es_none(self):
        medico = CatMedico.objects.create(id_usuario=_usuario("dr_sin_ced"))
        self.assertIsNone(identity.cedula_profesional(_cargar(medico.id)))

    def test_usuario_prefiere_la_principal(self):
        user = _usuario("dr_ced")
        DetUsuarioCedula.objects.create(id_usuario=user, numero="111", tipo="PROFESIONAL", es_principal=False, orden=1)
        DetUsuarioCedula.objects.create(id_usuario=user, numero="222", tipo="ESPECIALIDAD", es_principal=True, orden=2)
        medico = CatMedico.objects.create(id_usuario=user)
        self.assertEqual(identity.cedula_profesional(_cargar(medico.id)), "222")

    def test_usuario_sin_principal_usa_profesional(self):
        user = _usuario("dr_ced_prof")
        DetUsuarioCedula.objects.create(id_usuario=user, numero="333", tipo="ESPECIALIDAD", es_principal=False, orden=1)
        DetUsuarioCedula.objects.create(id_usuario=user, numero="444", tipo="PROFESIONAL", es_principal=False, orden=2)
        medico = CatMedico.objects.create(id_usuario=user)
        self.assertEqual(identity.cedula_profesional(_cargar(medico.id)), "444")


class AnnotateDisplayNameTests(TestCase):
    def test_ordena_con_y_sin_usuario(self):
        CatMedico.objects.create(id_usuario=_usuario("dr_z", nombre="Zacarías", paterno="Zepeda", materno=None))
        sin_a = CatMedico.objects.create(nombre="Alberto", paterno="Aguilar")
        sin_m = CatMedico.objects.create(nombre="Mario", paterno="Morales", materno="Mora")
        CatMedico.objects.create(id_usuario=_usuario("dr_sin_det_x", con_detalle=False))

        qs = identity.annotate_display_name(CatMedico.objects.all()).order_by("medico_nombre", "id")
        nombres = [m.medico_nombre for m in qs]

        self.assertIn("Alberto Aguilar", nombres)
        self.assertIn("Mario Morales Mora", nombres)
        self.assertIn("dr_sin_det_x", nombres)
        self.assertEqual(len(nombres), 4)
        # Orden estable: los sin usuario quedan intercalados, no al final.
        ids = [m.id for m in qs]
        self.assertLess(ids.index(sin_a.id), ids.index(sin_m.id))

    def test_prefijo_sobre_relacion(self):
        from apps.medicos.models import RelMedicoEspecialidad

        medico = CatMedico.objects.create(nombre="Juan", paterno="López")
        qs = identity.annotate_display_name(
            RelMedicoEspecialidad.objects.filter(medico=medico), prefix="medico__", alias="nombre_x"
        )
        self.assertEqual(qs.count(), 0)  # compila la expresión sin error


class IdentityQueryCountTests(TestCase):
    def _armar(self, n):
        medicos = []
        for i in range(n):
            if i % 2:
                user = _usuario(f"dr_q_{n}_{i}")
                DetUsuarioCedula.objects.create(id_usuario=user, numero=f"C{i}", tipo="PROFESIONAL", es_principal=True, orden=1)
                medicos.append(CatMedico.objects.create(id_usuario=user))
            else:
                medicos.append(CatMedico.objects.create(nombre=f"N{i}", paterno="P", cedula_profesional=f"S{i}"))
        return [m.id for m in medicos]

    def _leer(self, ids):
        qs = identity.with_identity(CatMedico.objects.filter(id__in=ids)).prefetch_related(
            *identity.IDENTITY_PREFETCH
        )
        for m in qs:
            identity.display_name(m)
            identity.nombre_partes(m)
            identity.cedula_profesional(m)

    def test_numero_de_queries_constante(self):
        uno = self._armar(1)
        with self.assertNumQueries(1):
            self._leer(uno)  # sin usuario: sin prefetch porque id_usuario es NULL

        cinco = self._armar(5)
        # select_related + 1 prefetch de cédulas, sin importar N.
        with self.assertNumQueries(2):
            self._leer(cinco)


class Migracion0011ReversibleTests(TransactionTestCase):
    """S3.3: 0011 aplica y revierte (`migrate medicos 0010`) sin error."""

    def test_revierte_a_0010_y_vuelve_a_aplicar(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("medicos", "0010_add_legacy_cd_medico")])
        columnas = {c.name for c in connection.introspection.get_table_description(
            connection.cursor(), "cat_medicos")}
        self.assertIn("nombre_display", columnas)
        self.assertIn("legacy_cd_medico", columnas)
        self.assertNotIn("cedula_profesional", columnas)

        executor = MigrationExecutor(connection)
        executor.migrate([("medicos", "0011_catmedico_no_medico_identity")])
        columnas = {c.name for c in connection.introspection.get_table_description(
            connection.cursor(), "cat_medicos")}
        self.assertNotIn("nombre_display", columnas)
        self.assertNotIn("legacy_cd_medico", columnas)
        self.assertIn("cedula_profesional", columnas)
