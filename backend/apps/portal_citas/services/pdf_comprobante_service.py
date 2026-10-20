"""
apps/portal_citas/services/pdf_comprobante_service.py
=========================================================
Generación del PDF del comprobante de cita reservada desde el portal
(Fase 5), con el código QR de check-in embebido.

Se usa ``reportlab`` (Python puro) en vez de Word/``docxtpl``/``docx2pdf``
que ya usa ``apps.recepcion.services.ficha_service`` -- ese servicio
depende de Word instalado localmente vía ``pythoncom``, lo cual solo
corre en Windows con Office instalado. Este comprobante se genera desde
una tarea de Celery que corre en el contenedor ``celery-worker`` (Linux),
así que necesita una librería sin dependencias de sistema (nada de
Word/Pango/Cairo) -- ``reportlab`` dibuja el PDF directamente en Python
puro y es portable en un contenedor Linux sin instalar nada más.
"""

import functools
import io

from django.conf import settings
from django.utils import timezone

from apps.medicos.identity import display_name
from apps.portal_citas.services.comprobante_service import (
    construir_payload_qr,
    generar_qr_png,
)

# Texto de membrete institucional que identifica al área emisora del
# comprobante -- requisito de identidad institucional para un documento de
# gobierno, independiente de la marca SISEM (que es el nombre del sistema,
# no del área responsable).
TEXTO_MEMBRETE = "GERENCIA DE SALUD Y BIENESTAR SOCIAL STC METRO"


@functools.lru_cache(maxsize=4)
def _generar_marca_agua_png_bytes(logo_path_str: str, opacidad: float) -> bytes:
    """
    Genera en memoria (nunca en disco) una copia RGBA del logo con el canal
    alpha escalado a ``opacidad`` (0.0-1.0), para usarla como marca de agua
    de fondo. No modifica el archivo original en ``CITAS_LOGO_PATH``.

    ``mask="auto"`` de reportlab respeta el canal alpha del PNG que le
    pasemos, así que basta con reducir ese canal antes de dibujar -- no
    existe un parámetro de opacidad directo en ``canvas.drawImage``.

    Cacheada con ``lru_cache`` (clave: ruta + opacidad) porque el logo no
    cambia entre comprobantes -- evita reabrir/reprocesar la imagen con PIL
    en cada PDF generado por la tarea de Celery.
    """
    from PIL import Image

    with Image.open(logo_path_str) as img:
        rgba = img.convert("RGBA")
        alpha = rgba.getchannel("A")
        # Si el logo ya trae zonas transparentes (recorte del isotipo),
        # escalamos ese alpha existente en vez de pisarlo, para no volver
        # opacas zonas que el propio logo definió como transparentes.
        alpha = alpha.point(lambda px: int(px * opacidad))
        rgba.putalpha(alpha)
        buffer = io.BytesIO()
        rgba.save(buffer, format="PNG")
        return buffer.getvalue()


def generar_pdf_comprobante(cita, miembro_objetivo) -> bytes:
    """
    Genera el PDF del comprobante en memoria y devuelve sus bytes.

    ``cita``: instancia de ``apps.recepcion.models.CitaMedica`` ya
    reservada, con ``medico__id_usuario__detalle`` y ``consultorio``
    precargados (select_related) para no disparar queries extra acá.
    ``miembro_objetivo``: ``PortalMiembro`` del paciente de la cita --
    se imprime su ``nombre_visible``, nunca ``no_exp``/``pk_num`` (dato
    interno de identificación que no debe quedar impreso en un
    comprobante que el paciente se lleva).

    Diseño (Fase 5, rediseño "Citas en Línea"): letterhead con los dos
    logos "unidos" (SISEM + Portal, mismo compuesto que el header del
    correo OTP -- ver ``services/email_service.py``) como marca de agua Y
    como lockup de encabezado, folio destacado en una píldora de color de
    marca, campos agrupados en una tarjeta con fondo sutil, y el QR dentro
    de su propia tarjeta con instrucciones -- mismo lenguaje visual
    (tarjetas redondeadas, naranja institucional, tipografía con
    jerarquía) que ya usa el resto del portal.
    """
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    # Paleta institucional SISEM (frontend/src/shared/styles/theme.css),
    # reutilizada acá para que el comprobante impreso quede consistente con
    # la identidad visual del portal.
    COLOR_NARANJA_MARCA = HexColor("#fe5000")
    COLOR_TEXTO = HexColor("#111827")  # --text-body
    COLOR_TEXTO_MUTED = HexColor("#64748b")  # --text-muted
    COLOR_BORDE = HexColor("#e2e8f0")  # --border-hairline
    COLOR_FONDO_SUAVE = HexColor("#f8fafc")  # --bg-subtle
    COLOR_BLANCO = HexColor("#ffffff")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    margen_marco = 12 * mm
    logo_path = getattr(
        settings, "CITAS_COMPROBANTE_WATERMARK_PATH", None
    ) or getattr(settings, "CITAS_LOGO_PATH", None)

    # Marca de agua: se dibuja PRIMERO -- en el canvas de reportlab no hay
    # z-index, el orden de dibujo ES el orden de apilado visual, así que
    # todo lo que se dibuje después queda por encima. A diferencia de la
    # v1 (un solo logo grande centrado, que solo cubría una franja angosta
    # del medio de la página), acá se REPITE en mosaico -- al tresbolillo
    # (filas alternadas desfasadas, como un papel tapiz) -- para que
    # abarque TODO el marco naranja, de punta a punta, no solo el centro.
    # Recortada (``clipPath``) al interior del marco para que ningún
    # azulejo se dibuje por fuera del borde. Al 5% de opacidad -- más baja
    # que el 7% de la v1 porque acá se repite muchas veces y la suma visual
    # de varios azulejos pesa más que un solo logo grande.
    if logo_path and logo_path.exists():
        try:
            marca_agua_bytes = _generar_marca_agua_png_bytes(str(logo_path), 0.05)
            marca_agua_reader = ImageReader(io.BytesIO(marca_agua_bytes))
            wm_ratio = marca_agua_reader.getSize()[1] / marca_agua_reader.getSize()[0]
            wm_w = 58 * mm
            wm_h = wm_w * wm_ratio
            paso_x = wm_w * 1.55
            paso_y = wm_h * 2.9

            c.saveState()
            marco_interior = c.beginPath()
            marco_interior.rect(
                margen_marco,
                margen_marco,
                width - 2 * margen_marco,
                height - 2 * margen_marco,
            )
            c.clipPath(marco_interior, stroke=0, fill=0)

            fila = 0
            y_azulejo = margen_marco - wm_h
            while y_azulejo < height - margen_marco + wm_h:
                desfase_x = (paso_x / 2) if fila % 2 else 0
                x_azulejo = margen_marco - wm_w + desfase_x
                while x_azulejo < width - margen_marco + wm_w:
                    c.drawImage(
                        marca_agua_reader,
                        x_azulejo,
                        y_azulejo,
                        width=wm_w,
                        height=wm_h,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                    x_azulejo += paso_x
                y_azulejo += paso_y
                fila += 1

            c.restoreState()
        except Exception:
            # La marca de agua es cosmética: nunca debe romper la
            # generación del PDF.
            pass

    # Marco fino alrededor de la página, con margen de aire respecto del
    # borde físico del papel (no es una franja: es solo el contorno).
    c.setStrokeColor(COLOR_NARANJA_MARCA)
    c.setLineWidth(0.75)
    c.rect(
        margen_marco,
        margen_marco,
        width - 2 * margen_marco,
        height - 2 * margen_marco,
        fill=0,
        stroke=1,
    )

    y = height - margen_marco - 9 * mm

    # Letterhead: el mismo lockup de "logos unidos" del header de correo,
    # esta vez a tamaño de encabezado (no de marca de agua) -- es lo que le
    # da identidad de "Portal de Citas en Línea" al documento en vez de ser
    # un formulario genérico con un isotipo de fondo.
    if logo_path and logo_path.exists():
        try:
            header_reader = ImageReader(str(logo_path))
            header_w = 46 * mm
            header_h = header_w * (header_reader.getSize()[1] / header_reader.getSize()[0])
            c.drawImage(
                header_reader,
                (width - header_w) / 2,
                y - header_h,
                width=header_w,
                height=header_h,
                preserveAspectRatio=True,
                mask="auto",
            )
            y -= header_h + 4 * mm
        except Exception:
            pass

    # Eyebrow de marca: mismo patrón que "Integrado con SISEM" del portal
    # web (label chico, mayúsculas, tracking amplio, color de marca).
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(COLOR_NARANJA_MARCA)
    _draw_tracked_centered(c, width / 2, y, "CITAS EN LÍNEA", tracking=1.6)
    y -= 5 * mm

    # Membrete institucional: identifica al área emisora, requisito de
    # identidad para un documento de gobierno, con jerarquía visual menor
    # (fuente chica, gris neutro) para no competir con el título.
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(COLOR_TEXTO_MUTED)
    c.drawCentredString(width / 2, y, TEXTO_MEMBRETE)
    y -= 4 * mm
    c.setStrokeColor(COLOR_NARANJA_MARCA)
    c.setLineWidth(0.4)
    c.line(35 * mm, y, width - 35 * mm, y)
    y -= 11 * mm

    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(COLOR_TEXTO)
    c.drawCentredString(width / 2, y, "Comprobante de cita médica")
    y -= 5.5 * mm
    c.setFont("Helvetica-Oblique", 9.5)
    c.setFillColor(COLOR_TEXTO_MUTED)
    c.drawCentredString(width / 2, y, "Conserva este comprobante hasta el día de tu cita")
    y -= 9 * mm

    # Píldora de folio: el dato que el paciente más va a necesitar (en
    # recepción, o si llama por teléfono) sale de la tabla de campos y se
    # destaca solo, en el color de marca -- mismo criterio que un badge de
    # estatus en la UI del portal.
    folio_texto = f"FOLIO   {cita.folio}"
    c.setFont("Helvetica-Bold", 13)
    folio_ancho_texto = c.stringWidth(folio_texto, "Helvetica-Bold", 13)
    folio_pill_w = folio_ancho_texto + 16 * mm
    folio_pill_h = 10 * mm
    folio_pill_x = (width - folio_pill_w) / 2
    c.setFillColor(COLOR_NARANJA_MARCA)
    c.setFillAlpha(0.92)  # deja asomar la marca de agua incluso bajo la píldora
    c.roundRect(folio_pill_x, y - folio_pill_h, folio_pill_w, folio_pill_h, 5 * mm, stroke=0, fill=1)
    c.setFillAlpha(1)
    c.setFillColor(COLOR_BLANCO)
    c.drawCentredString(width / 2, y - folio_pill_h + 3.3 * mm, folio_texto)
    y -= folio_pill_h + 8 * mm

    # display_name no revienta aunque el usuario no tenga detalle.
    nombre_medico = display_name(cita.medico)

    campos = [
        ("Paciente", miembro_objetivo.nombre_visible),
        ("Fecha", timezone.localtime(cita.fecha_hora).strftime("%d/%m/%Y")),
        ("Hora", timezone.localtime(cita.fecha_hora).strftime("%H:%M")),
        ("Consultorio", cita.consultorio.name if cita.consultorio else "Por asignar"),
        ("Médico", f"Dr(a). {nombre_medico}"),
        ("Tipo de servicio", cita.get_servicio_tipo_display()),
    ]

    # Tarjeta de campos: fondo sutil + borde fino redondeado, mismo
    # lenguaje visual que las tarjetas "glass" del portal web (sin blur acá,
    # claro -- es un PDF estático).
    fila_h = 8.4 * mm
    card_pad = 6 * mm
    card_w = width - 40 * mm
    card_x = 20 * mm
    card_h = fila_h * len(campos) + card_pad * 2
    card_top = y
    c.setFillColor(COLOR_FONDO_SUAVE)
    c.setFillAlpha(0.9)  # deja asomar la marca de agua bajo la tarjeta de campos
    c.setStrokeColor(COLOR_BORDE)
    c.setLineWidth(0.6)
    c.roundRect(card_x, card_top - card_h, card_w, card_h, 3 * mm, stroke=1, fill=1)
    c.setFillAlpha(1)

    fila_y = card_top - card_pad - 5.5 * mm
    for etiqueta, valor in campos:
        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColor(COLOR_TEXTO_MUTED)
        c.drawString(card_x + 8 * mm, fila_y, etiqueta.upper())
        c.setFont("Helvetica", 11)
        c.setFillColor(COLOR_TEXTO)
        c.drawRightString(card_x + card_w - 8 * mm, fila_y, str(valor))
        fila_y -= fila_h
    y = card_top - card_h - 9 * mm

    # Tarjeta del QR: mismo criterio (tarjeta redondeada con borde), con la
    # etiqueta e instrucciones DENTRO de la tarjeta en vez de sueltas en la
    # página -- agrupa visualmente "esto es lo que hay que escanear".
    payload = construir_payload_qr(cita.folio)
    qr_png = generar_qr_png(payload)
    qr_reader = ImageReader(io.BytesIO(qr_png))
    qr_size = 40 * mm
    qr_card_w = 100 * mm
    qr_card_x = (width - qr_card_w) / 2
    qr_card_pad_top = 8 * mm
    qr_label_h = 5 * mm
    qr_caption_h = 11 * mm
    qr_card_pad_bottom = 7 * mm
    qr_card_h = qr_card_pad_top + qr_label_h + qr_size + qr_caption_h + qr_card_pad_bottom
    qr_card_top = y

    c.setFillColor(COLOR_BLANCO)
    c.setFillAlpha(0.92)  # deja asomar la marca de agua bajo la tarjeta del QR
    c.setStrokeColor(COLOR_NARANJA_MARCA)
    c.setLineWidth(0.9)
    c.roundRect(qr_card_x, qr_card_top - qr_card_h, qr_card_w, qr_card_h, 4 * mm, stroke=1, fill=1)
    c.setFillAlpha(1)

    label_y = qr_card_top - qr_card_pad_top
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(COLOR_TEXTO_MUTED)
    _draw_tracked_centered(c, width / 2, label_y, "ESCANEA PARA CHECK-IN", tracking=1.1)

    qr_y = label_y - qr_label_h - qr_size
    c.drawImage(qr_reader, (width - qr_size) / 2, qr_y, width=qr_size, height=qr_size)

    caption_y = qr_y - 6 * mm
    c.setFont("Helvetica", 8.5)
    c.setFillColor(COLOR_TEXTO_MUTED)
    c.drawCentredString(
        width / 2, caption_y, "Presenta este código QR en recepción el día de tu cita."
    )
    c.drawCentredString(
        width / 2, caption_y - 4 * mm, "Es tu comprobante de check-in — no lo compartas."
    )

    # Pie de página: línea + texto pequeño, fijo cerca del borde inferior
    # del marco (no forma parte del flujo de contenido de arriba).
    footer_y = margen_marco + 9 * mm
    c.setStrokeColor(COLOR_BORDE)
    c.setLineWidth(0.5)
    c.line(35 * mm, footer_y + 5 * mm, width - 35 * mm, footer_y + 5 * mm)
    c.setFont("Helvetica", 7.5)
    c.setFillColor(COLOR_TEXTO_MUTED)
    c.drawCentredString(
        width / 2, footer_y, "Generado automáticamente por el Portal de Citas en Línea — SISEM STC Metro"
    )

    c.showPage()
    c.save()
    return buffer.getvalue()


def _draw_tracked_centered(c, x_center: float, y: float, texto: str, tracking: float) -> None:
    """
    ``drawCentredString`` no soporta letter-spacing (tracking) -- reportlab
    no tiene esa opción nativa para texto centrado. Mide el ancho total
    (glyphs + tracking entre cada par de caracteres) y dibuja carácter por
    carácter para lograr el efecto "eyebrow" (mayúsculas espaciadas) que ya
    usa la UI del portal (ej. "Integrado con SISEM").
    """
    from reportlab.lib.units import mm

    font_name, font_size = c._fontname, c._fontsize
    ancho_total = c.stringWidth(texto, font_name, font_size) + tracking * mm * max(len(texto) - 1, 0)
    x = x_center - ancho_total / 2
    for char in texto:
        c.drawString(x, y, char)
        x += c.stringWidth(char, font_name, font_size) + tracking * mm
