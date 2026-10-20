"""Cobertura de `CatMedico` (id_usuario obligatorio, OneToOne PROTECT) y de los
helpers de `apps.medicos.identity`: display_name / nombre_partes /
cedula_profesional / annotate_display_name, siempre desde el usuario, sin
excepción por detalle ausente y con número de queries constante."""

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
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


class CatMedicoUsuarioObligatorioTests(TestCase):
    def test_sin_usuario_se_rechaza(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CatMedico.objects.create()

    def test_con_usuario_ok(self):
        user = _usuario("dr_limpio")
        self.assertIsNotNone(CatMedico.objects.create(id_usuario=user).pk)

    def test_un_usuario_un_solo_medico(self):
        user = _usuario("dr_unico")
        CatMedico.objects.create(id_usuario=user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CatMedico.objects.create(id_usuario=user)

    def test_borrar_usuario_medico_esta_protegido(self):
        user = _usuario("dr_protegido")
        CatMedico.objects.create(id_usuario=user)
        with self.assertRaises(ProtectedError):
            user.delete()
        self.assertTrue(SyUsuario.objects.filter(pk=user.pk).exists())

    def test_sin_campos_personales_propios(self):
        campos = {f.name for f in CatMedico._meta.get_fields()}
        for campo in ("nombre", "paterno", "materno", "cedula_profesional", "id_escuela", "sexo", "fecha_nac"):
            self.assertNotIn(campo, campos)


class DisplayNameTests(TestCase):
    def test_con_detalle_usa_nombre_completo(self):
        user = _usuario("dr_det")
        medico = CatMedico.objects.create(id_usuario=user)
        self.assertEqual(identity.display_name(_cargar(medico.id)), "Ana Pérez Gómez")

    def test_usuario_sin_detalle_usa_username(self):
        user = _usuario("dr_sin_det", con_detalle=False)
        medico = CatMedico.objects.create(id_usuario=user)
        self.assertEqual(identity.display_name(_cargar(medico.id)), "dr_sin_det")


class NombrePartesTests(TestCase):
    def test_con_usuario(self):
        medico = CatMedico.objects.create(id_usuario=_usuario("dr_partes"))
        partes = identity.nombre_partes(_cargar(medico.id))
        self.assertEqual((partes.nombre, partes.paterno, partes.materno), ("Ana", "Pérez", "Gómez"))

    def test_usuario_sin_detalle_devuelve_vacio(self):
        medico = CatMedico.objects.create(id_usuario=_usuario("dr_partes_sd", con_detalle=False))
        partes = identity.nombre_partes(_cargar(medico.id))
        self.assertEqual((partes.nombre, partes.paterno, partes.materno), (None, None, None))


class CedulaProfesionalTests(TestCase):
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
    def test_ordena_por_nombre_del_usuario_con_fallback_a_username(self):
        CatMedico.objects.create(id_usuario=_usuario("dr_z", nombre="Zacarías", paterno="Zepeda", materno=None))
        CatMedico.objects.create(id_usuario=_usuario("dr_a", nombre="Alberto", paterno="Aguilar", materno=None))
        CatMedico.objects.create(id_usuario=_usuario("dr_sin_det_x", con_detalle=False))

        qs = identity.annotate_display_name(CatMedico.objects.all()).order_by("medico_nombre", "id")
        nombres = [m.medico_nombre for m in qs]

        self.assertEqual(nombres, ["Alberto Aguilar", "Zacarías Zepeda", "dr_sin_det_x"])

    def test_prefijo_sobre_relacion(self):
        from apps.medicos.models import RelMedicoEspecialidad

        medico = CatMedico.objects.create(id_usuario=_usuario("dr_prefijo"))
        qs = identity.annotate_display_name(
            RelMedicoEspecialidad.objects.filter(medico=medico), prefix="medico__", alias="nombre_x"
        )
        self.assertEqual(qs.count(), 0)  # compila la expresión sin error


class IdentityQueryCountTests(TestCase):
    def _armar(self, n):
        medicos = []
        for i in range(n):
            user = _usuario(f"dr_q_{n}_{i}")
            DetUsuarioCedula.objects.create(id_usuario=user, numero=f"C{i}", tipo="PROFESIONAL", es_principal=True, orden=1)
            medicos.append(CatMedico.objects.create(id_usuario=user))
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
        # select_related + 1 prefetch de cédulas, sin importar N.
        with self.assertNumQueries(2):
            self._leer(uno)

        cinco = self._armar(5)
        with self.assertNumQueries(2):
            self._leer(cinco)


def _hojas():
    """Nodos hoja del grafo de migraciones (estado actual del código)."""
    return MigrationExecutor(connection).loader.graph.leaf_nodes()


class Migracion0011ReversibleTests(TransactionTestCase):
    """S3.3: 0011 aplica y revierte (`migrate medicos 0010`) sin error."""

    def tearDown(self):
        # Deja la BD en el estado final para no contaminar otras suites.
        MigrationExecutor(connection).migrate(_hojas())

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


class Migracion0017PrecheckTests(TransactionTestCase):
    """0017 aborta con mensaje claro si hay médicos sin usuario."""

    def tearDown(self):
        MigrationExecutor(connection).migrate(_hojas())

    def test_aborta_si_hay_medicos_sin_usuario(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("medicos", "0016_delete_medicoimportjob")])
        apps_0016 = executor.loader.project_state(
            [("medicos", "0016_delete_medicoimportjob")]
        ).apps
        CatMedicoHist = apps_0016.get_model("medicos", "CatMedico")
        CatMedicoHist.objects.create(nombre="Sin", paterno="Usuario")

        executor = MigrationExecutor(connection)
        with self.assertRaisesMessage(RuntimeError, "Hay 1 médicos sin usuario"):
            executor.migrate([("medicos", "0017_catmedico_usuario_obligatorio")])

        # Vaciado el catálogo, la migración aplica.
        CatMedicoHist.objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate([("medicos", "0017_catmedico_usuario_obligatorio")])
        columnas = {c.name for c in connection.introspection.get_table_description(
            connection.cursor(), "cat_medicos")}
        self.assertNotIn("nombre", columnas)
        self.assertNotIn("cedula_profesional", columnas)
