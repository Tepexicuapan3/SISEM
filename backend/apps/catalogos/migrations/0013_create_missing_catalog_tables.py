# Estas tablas nacieron con managed=False (nunca se creaban via migrate),
# pero son catalogos propios de SIRES (no datos del legacy SERMED), asi que
# corresponde que Django las cree y gestione normalmente.
#
# Usamos SeparateDatabaseAndState: el estado pasa a managed=True para todas,
# y la creacion fisica usa el registro real de apps (no el "apps" historico
# que recibe RunPython) para que schema_editor vea managed=True al construir
# el CREATE TABLE. Cada tabla se crea solo si todavia no existe, para no
# romper ambientes donde ya existan con datos reales.
from django.apps import apps as global_apps
from django.db import migrations

# Orden importa: las que tienen FK van al final, despues de sus tablas destino.
CATALOGOS_MODELOS_A_CREAR = [
    "areas",
    "autorizadores",
    "bajas",
    "calidadlaboral",
    "consultorios",
    "edocivil",
    "enfermedades",
    "escolaridad",
    "escuelas",
    "especialidades",
    "estudiosmed",
    "gruposdemedicamentos",
    "licencias",
    "ocupaciones",
    "origencons",
    "parentesco",
    "pases",
    "tipodecitas",
    "tiposareas",
    "tipossanguineo",
    "tpautorizacion",
    "turnos",
    "vacunas",
    "catsucursal",
    "catareaclinica",
    # FK-dependientes, deben ir despues de las tablas de arriba:
    "catcentroatencionhorario",
    "centroareaclinica",
]


def crear_tablas_faltantes(apps, schema_editor):
    tablas_existentes = set(schema_editor.connection.introspection.table_names())

    for model_name in CATALOGOS_MODELOS_A_CREAR:
        # Guard (change cancelacion-nota-cascada): este paso usa el registro
        # de apps VIVO, no el historico. El modelo "autorizadores" fue
        # eliminado del codigo (cat_autorizadores se dio de baja en 0040), asi
        # que en una BD fresca ya no existe en el registro: se salta. En
        # ambientes ya migrados esta migracion no se vuelve a ejecutar.
        try:
            model = global_apps.get_model("catalogos", model_name)
        except LookupError:
            continue
        if model._meta.db_table in tablas_existentes:
            continue
        schema_editor.create_model(model)


def revertir_noop(apps, schema_editor):
    # No se borran tablas al revertir: podrian tener datos reales cargados
    # despues de crearse. Revertir el estado (managed=False) es reversible
    # via AlterModelOptions; la parte de base de datos se deja como no-op.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0012_alter_catsucursal_options"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(name="areas", options={"managed": True}),
                migrations.AlterModelOptions(name="autorizadores", options={"managed": True}),
                migrations.AlterModelOptions(name="bajas", options={"managed": True}),
                migrations.AlterModelOptions(name="calidadlaboral", options={"managed": True}),
                migrations.AlterModelOptions(name="consultorios", options={"managed": True}),
                migrations.AlterModelOptions(name="edocivil", options={"managed": True}),
                migrations.AlterModelOptions(name="enfermedades", options={"managed": True}),
                migrations.AlterModelOptions(name="escolaridad", options={"managed": True}),
                migrations.AlterModelOptions(name="escuelas", options={"managed": True}),
                migrations.AlterModelOptions(name="especialidades", options={"managed": True}),
                migrations.AlterModelOptions(name="estudiosmed", options={"managed": True}),
                migrations.AlterModelOptions(name="gruposdemedicamentos", options={"managed": True}),
                migrations.AlterModelOptions(name="licencias", options={"managed": True}),
                migrations.AlterModelOptions(name="ocupaciones", options={"managed": True}),
                migrations.AlterModelOptions(name="origencons", options={"managed": True}),
                migrations.AlterModelOptions(name="parentesco", options={"managed": True}),
                migrations.AlterModelOptions(name="pases", options={"managed": True}),
                migrations.AlterModelOptions(name="tipodecitas", options={"managed": True}),
                migrations.AlterModelOptions(name="tiposareas", options={"managed": True}),
                migrations.AlterModelOptions(name="tipossanguineo", options={"managed": True}),
                migrations.AlterModelOptions(name="tpautorizacion", options={"managed": True}),
                migrations.AlterModelOptions(name="turnos", options={"managed": True}),
                migrations.AlterModelOptions(name="vacunas", options={"managed": True}),
                migrations.AlterModelOptions(
                    name="catsucursal",
                    options={
                        "managed": True,
                        "ordering": ["name"],
                        "verbose_name": "Sucursal",
                        "verbose_name_plural": "Sucursales",
                    },
                ),
                migrations.AlterModelOptions(
                    name="catareaclinica",
                    options={
                        "managed": True,
                        "ordering": ["name"],
                        "verbose_name": "Área Clínica",
                        "verbose_name_plural": "Áreas Clínicas",
                    },
                ),
                migrations.AlterModelOptions(
                    name="centroareaclinica",
                    options={
                        "managed": True,
                        "verbose_name": "Área Clínica por Centro",
                        "verbose_name_plural": "Áreas Clínicas por Centro",
                    },
                ),
                migrations.AlterModelOptions(
                    name="catcentroatencionhorario",
                    options={
                        "managed": True,
                        "ordering": ["center", "week_day", "shift"],
                        "verbose_name": "Horario de Centro de Atención",
                        "verbose_name_plural": "Horarios de Centros de Atención",
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(crear_tablas_faltantes, revertir_noop),
            ],
        ),
    ]
