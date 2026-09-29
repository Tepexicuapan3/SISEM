"""
Siembra de los catalogos de la historia clinica unificada. Idempotente
(update_or_create por clave): correrla dos veces no duplica. Los datos
viven inline a proposito -- una migracion no debe depender de codigo de la
app que puede cambiar despues.
"""
from django.db import migrations

HABITOS = (
    ("tabaquismo", "Tabaquismo"),
    ("alcoholismo", "Alcoholismo"),
    ("toxicomanias", "Toxicomanías"),
    ("actividad_fisica", "Actividad física"),
    ("alimentacion", "Alimentación"),
    ("otro", "Otro"),
)

REGIONES = (
    ("cabeza", "Cabeza", 1),
    ("cuello", "Cuello", 2),
    ("torax", "Tórax", 3),
    ("abdomen", "Abdomen", 4),
    ("genitales", "Genitales", 5),
    ("miembros", "Miembros", 6),
    ("otra", "Otra", 7),
)

# Mismos `code` que la vieja `OdontogramTooth.Condition` (contrato del
# frontend). Componente CPOD: C cariado, P perdido, O obturado.
ESTADOS_PIEZA = (
    ("healthy", "Sano", None),
    ("caries", "Caries", "C"),
    ("filled", "Obturado", "O"),
    ("crown", "Corona", "O"),
    ("missing", "Ausente", "P"),
    ("extraction_needed", "Extracción indicada", "P"),
    ("root_canal", "Endodoncia", "O"),
    ("sealant", "Sellante", None),
    ("fracture", "Fracturado", None),
    ("implant", "Implante", "P"),
)

_POSICION = {
    1: "incisivo central", 2: "incisivo lateral", 3: "canino",
    4: "primer premolar", 5: "segundo premolar",
    6: "primer molar", 7: "segundo molar", 8: "tercer molar",
}
_POSICION_TEMPORAL = {
    1: "incisivo central", 2: "incisivo lateral", 3: "canino",
    4: "primer molar", 5: "segundo molar",
}
_CUADRANTE = {
    1: "superior derecho", 2: "superior izquierdo",
    3: "inferior izquierdo", 4: "inferior derecho",
    5: "superior derecho", 6: "superior izquierdo",
    7: "inferior izquierdo", 8: "inferior derecho",
}


def _piezas():
    for cuadrante in range(1, 5):
        for pos in range(1, 9):
            yield f"{cuadrante}{pos}", f"{_POSICION[pos]} {_CUADRANTE[cuadrante]}", "P", cuadrante
    for cuadrante in range(5, 9):
        for pos in range(1, 6):
            yield (
                f"{cuadrante}{pos}",
                f"{_POSICION_TEMPORAL[pos]} temporal {_CUADRANTE[cuadrante]}",
                "T",
                cuadrante,
            )


def seed(apps, schema_editor):
    CatHabito = apps.get_model("catalogos", "CatHabito")
    CatRegionCorporal = apps.get_model("catalogos", "CatRegionCorporal")
    CatEstadoPieza = apps.get_model("catalogos", "CatEstadoPieza")
    CatPiezaDental = apps.get_model("catalogos", "CatPiezaDental")

    for code, name in HABITOS:
        CatHabito.objects.update_or_create(code=code, defaults={"name": name})
    for code, name, order in REGIONES:
        CatRegionCorporal.objects.update_or_create(code=code, defaults={"name": name, "order": order})
    for code, name, dmft in ESTADOS_PIEZA:
        CatEstadoPieza.objects.update_or_create(
            code=code, defaults={"name": name, "dmft_component": dmft},
        )
    for fdi, name, dentition, quadrant in _piezas():
        CatPiezaDental.objects.update_or_create(
            fdi=fdi, defaults={"name": name, "dentition": dentition, "quadrant": quadrant},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalogos", "0031_catalogos_historia_clinica"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
