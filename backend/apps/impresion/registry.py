"""
apps/impresion/registry.py
==============================
Registro central de documentos imprimibles. Cada modulo aporta un builder
(funcion pura y de solo lectura, referenciada por dotted path y cargada de
forma perezosa) y una plantilla Django; el endpoint generico despacha por
``documento``.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from apps.consulta_medica.services.record_access_audit_service import RecordSection
from apps.impresion.errors import PrintError


@dataclass(frozen=True)
class DocumentSpec:
    key: str  # "ficha" | "receta" | "nota"
    template: str
    # dotted path: fn(resource_id, actor, *, permissions, roles) -> PrintContext
    builder: str
    capability: str  # clave de CAPABILITY_REQUIREMENTS
    section: str  # RecordSection para BitacoraAcceso
    watermark_on_reprint: bool = True
    # Ruta de un renderer alternativo fn(print_context, actor) -> bytes
    # (solo la ficha: FICHA_ENGINE=docx). None = sin camino alterno.
    legacy_renderer: Optional[str] = None


@dataclass
class PrintContext:
    """Resultado de un builder. ``context`` alimenta la plantilla; el resto
    es metadata para guardas, bitacora y headers de respuesta."""

    context: dict
    no_exp: Optional[str]
    pk_num: Optional[int]
    folio: str
    filename: str
    is_cancelled: bool = False
    center_id: Optional[int] = None  # centro de atencion del documento
    legacy_cd_clinica: Optional[int] = None  # logo por centro
    source: Any = field(default=None, repr=False)  # objeto origen (p. ej. Visit)


REGISTRY = {
    "ficha": DocumentSpec(
        key="ficha",
        template="recepcion/impresion/ficha.html",
        builder="apps.recepcion.impresion.ficha.build_ficha_context",
        capability="documentos.ficha.imprimir",
        section=RecordSection.FICHA,
        watermark_on_reprint=False,  # R2.3: se registra pero sin marca de agua
        legacy_renderer="apps.recepcion.impresion.ficha.render_ficha_docx",
    ),
    "receta": DocumentSpec(
        key="receta",
        template="consulta_medica/impresion/receta.html",
        builder="apps.consulta_medica.impresion.receta.build_receta_context",
        capability="documentos.receta.imprimir",
        section=RecordSection.RECETA,
    ),
    "nota": DocumentSpec(
        key="nota",
        template="consulta_medica/impresion/nota.html",
        builder="apps.consulta_medica.impresion.nota.build_nota_context",
        capability="documentos.nota.imprimir",
        section=RecordSection.NOTA,
    ),
}


def get_spec(documento):
    spec = REGISTRY.get(documento)
    if spec is None:
        raise PrintError(
            code="DOCUMENT_TYPE_NOT_FOUND",
            message="Tipo de documento no soportado.",
            status_code=404,
        )
    return spec
