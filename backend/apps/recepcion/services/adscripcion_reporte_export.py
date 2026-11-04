"""
P-03 · Excel del padrón de adscripción: hoja "Resumen" (conteos por consultorio)
y hoja "Adscritos" (una fila por persona). Solo da formato; los datos y el
alcance los decide adscripcion_reporte_usecase.
"""

import io
from datetime import datetime

import openpyxl
from openpyxl.styles import Font

TIPO = {"TITULAR": "Titular", "FAMILIAR": "Familiar"}

# (encabezado, cómo sacar el valor de la fila)
_COLUMNAS_RESUMEN = (
    ("Centro", lambda r: r["centro"]),
    ("Consultorio", lambda r: r["numero"]),
    ("Nombre", lambda r: r["consultorio"]),
    ("Turno", lambda r: r["turno"]),
    ("Titulares", lambda r: r["titulares"]),
    ("Familiares", lambda r: r["familiares"]),
    ("Total", lambda r: r["total"]),
    ("Tope", lambda r: r["capacidadMaxima"] if r["capacidadMaxima"] is not None else "Sin tope"),
    ("Médico", lambda r: ", ".join(r["medicos"]) or "Sin médico activo"),
    ("Activo", lambda r: "Sí" if r["estaActivo"] else "No"),
)

_COLUMNAS_ADSCRITOS = (
    ("Expediente", lambda r: r["noExp"]),
    ("Nombre", lambda r: r["nombre"] or "Sin nombre registrado"),
    ("Tipo", lambda r: TIPO[r["tipo"]]),
    ("Centro", lambda r: r["centro"]),
    ("Consultorio", lambda r: r["numeroConsultorio"]),
    ("Nombre del consultorio", lambda r: r["consultorio"]),
    ("Turno", lambda r: r["turno"]),
    ("Adscrito desde", lambda r: datetime.fromisoformat(r["fechaInicio"]).strftime("%d/%m/%Y")),
    ("Origen", lambda r: r["origen"]),
)


def _hoja(ws, columnas, filas):
    for col, (encabezado, _) in enumerate(columnas, start=1):
        ws.cell(row=1, column=col, value=encabezado).font = Font(bold=True)
    for fila_idx, fila in enumerate(filas, start=2):
        for col, (_, valor) in enumerate(columnas, start=1):
            ws.cell(row=fila_idx, column=col, value=valor(fila))
    ws.freeze_panes = "A2"
    for col, (encabezado, _) in enumerate(columnas, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = max(12, len(encabezado) + 4)


def construir_libro_adscripcion(resumen: list[dict], adscritos: list[dict]) -> bytes:
    libro = openpyxl.Workbook()
    hoja_resumen = libro.active
    hoja_resumen.title = "Resumen"
    _hoja(hoja_resumen, _COLUMNAS_RESUMEN, resumen)
    _hoja(libro.create_sheet("Adscritos"), _COLUMNAS_ADSCRITOS, adscritos)

    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
