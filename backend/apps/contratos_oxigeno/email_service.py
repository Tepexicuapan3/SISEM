"""Servicio de email para notificaciones de contratos de oxígeno."""

from datetime import date

from django.core.mail import EmailMessage
from django.conf import settings

from apps.consulta_medica.services.paciente_entrada import llave_publica


# ── Template HTML ─────────────────────────────────────────────────────────────

def _status_color(dias_faltan):
    if dias_faltan is None:
        return "#6b7280"
    if dias_faltan < 0:
        return "#dc2626"
    if dias_faltan <= 15:
        return "#d97706"
    return "#16a34a"


def _status_label(dias_faltan):
    if dias_faltan is None:
        return "Sin fecha"
    if dias_faltan < 0:
        return f"Vencido hace {abs(dias_faltan)} días"
    if dias_faltan <= 15:
        return f"Vence en {dias_faltan} días"
    return f"{dias_faltan} días"


def build_vencimiento_html(contratos, cuerpo_intro: str = "") -> str:
    filas = ""
    for c in contratos:
        color = _status_color(c.dias_faltan)
        label = _status_label(c.dias_faltan)
        fecha = c.fecha_renovar.strftime("%d/%m/%Y") if c.fecha_renovar else "—"
        filas += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-family:monospace;font-weight:600;color:#1d4ed8">{c.num_contrato}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb">{c.nombre}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-family:monospace;color:#6b7280">{llave_publica(c)[0]}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb">{c.servicio}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-family:monospace">{fecha}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-weight:600;color:{color}">{label}</td>
        </tr>"""

    intro_html = f"<p style='margin:0 0 16px;color:#374151'>{cuerpo_intro}</p>" if cuerpo_intro else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <div style="max-width:760px;margin:32px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)">
    <!-- Header -->
    <div style="background:#1e40af;padding:24px 32px">
      <p style="margin:0;color:#bfdbfe;font-size:12px;text-transform:uppercase;letter-spacing:.08em">Sistema de Información en Salud</p>
      <h1 style="margin:4px 0 0;color:#ffffff;font-size:20px;font-weight:700">Aviso de vencimiento de contratos</h1>
    </div>
    <!-- Body -->
    <div style="padding:24px 32px">
      {intro_html}
      <p style="margin:0 0 4px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:#9ca3af">
        Contratos incluidos en este aviso
      </p>
      <table style="width:100%;border-collapse:collapse;margin-top:8px">
        <thead>
          <tr style="background:#f3f4f6">
            <th style="padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;color:#6b7280">N° Contrato</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;color:#6b7280">Paciente</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;color:#6b7280">Expediente</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;color:#6b7280">Servicio</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;color:#6b7280">Fecha límite</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;color:#6b7280">Estado</th>
          </tr>
        </thead>
        <tbody>{filas}</tbody>
      </table>
    </div>
    <!-- Footer -->
    <div style="padding:16px 32px;border-top:1px solid #e5e7eb;background:#f9fafb">
      <p style="margin:0;font-size:11px;color:#9ca3af">
        Generado el {date.today().strftime('%d/%m/%Y')} · {settings.DEFAULT_FROM_EMAIL}
      </p>
    </div>
  </div>
</body>
</html>"""


# ── Envío ─────────────────────────────────────────────────────────────────────

def enviar_notificacion(
    destinatarios: list[str],
    asunto: str,
    cuerpo_html: str,
    adjuntos: list[tuple] | None = None,
) -> dict:
    """
    Envía un email HTML a múltiples destinatarios.
    adjuntos: lista de (nombre, contenido_bytes, mimetype)
    Retorna {'enviados': n, 'fallidos': 0} o lanza Exception.
    """
    msg = EmailMessage(
        subject=asunto,
        body=cuerpo_html,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios,
    )
    msg.content_subtype = "html"

    if adjuntos:
        for nombre, contenido, mimetype in adjuntos:
            msg.attach(nombre, contenido, mimetype)

    msg.send(fail_silently=False)
    return {"enviados": len(destinatarios), "fallidos": 0}
