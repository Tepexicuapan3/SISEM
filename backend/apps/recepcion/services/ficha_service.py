"""
Generación de la Ficha de Consulta en PDF.
Usa docxtpl para renderizar la plantilla Word y docx2pdf para convertir.
"""

import logging
import os
import tempfile
from datetime import date, datetime

from apps.consulta_medica.services.paciente_entrada import llave_publica

logger = logging.getLogger(__name__)

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "Ficha cita medica.docx"
)


def _get_nombre_components(no_exp: str, pk_num: int) -> dict:
    """
    Consulta SERMED para obtener apellidos, nombre, edad y fecha de nacimiento.
    """
    try:
        from apps.administracion.use_cases.expedientes.buscar_expediente import buscar_expediente
        resultado  = buscar_expediente(no_exp)
        empleados  = resultado.get("empleados", [])
        familiares = resultado.get("familiares", [])

        if pk_num == 0 and empleados:
            emp = empleados[0]
            return {
                "a_paterno":       emp.get("DS_PATERNO", ""),
                "a_materno":       emp.get("DS_MATERNO", ""),
                "nombre_paciente": emp.get("DS_NOMBRE", ""),
                "edad":            str(emp.get("EDAD", "")) if emp.get("EDAD") is not None else "",
                "fecha_nac":       str(emp["FE_NAC"]) if emp.get("FE_NAC") else "",
            }

        if pk_num > 0:
            fam = next((f for f in familiares if f.get("PK_NUM") == pk_num), None)
            if fam:
                return {
                    "a_paterno":       fam.get("DS_PATERNO", ""),
                    "a_materno":       fam.get("DS_MATERNO", ""),
                    "nombre_paciente": fam.get("DS_NOMBRE", ""),
                    "edad":            str(fam.get("EDAD", "")) if fam.get("EDAD") is not None else "",
                    "fecha_nac":       str(fam["FE_NAC"]) if fam.get("FE_NAC") else "",
                }
    except Exception:
        logger.exception("Error consultando expediente %s para ficha", no_exp)

    # Plan identidad, bloque C2: quien no esta en SERMED (recien nacido
    # provisional, familiar del legado) se toma de su registro en SIRES.
    from apps.consulta_medica.services.patient_link_service import find_patient_by_record_key

    paciente = find_patient_by_record_key(no_exp, pk_num)
    if paciente is not None and (paciente.first_name or paciente.paternal_surname):
        nacimiento = paciente.birth_date
        edad = ""
        if nacimiento:
            hoy = date.today()
            edad = str(hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)))
        return {
            "a_paterno": paciente.paternal_surname or "",
            "a_materno": paciente.maternal_surname or "",
            "nombre_paciente": paciente.first_name or "",
            "edad": edad,
            "fecha_nac": str(nacimiento) if nacimiento else "",
        }
    return {"a_paterno": "", "a_materno": "", "nombre_paciente": "", "edad": "", "fecha_nac": ""}


def _get_cita_datetime(visit):
    """Retorna el datetime local de la cita vinculada, o None."""
    from django.utils import timezone as tz
    if visit.appointment_id:
        try:
            from apps.recepcion.models import CitaMedica
            cita = CitaMedica.objects.filter(folio=visit.appointment_id).first()
            if cita:
                return tz.localtime(cita.fecha_hora)
        except Exception:
            pass
    return None


def _get_hora_cierre(visit) -> str:
    """Hora en que la visita fue cerrada (status → cerrada)."""
    from django.utils import timezone as tz
    from apps.recepcion.models import VisitStatusLog
    log = VisitStatusLog.objects.filter(
        visit=visit, to_status="cerrada"
    ).order_by("changed_at").last()
    if log:
        return tz.localtime(log.changed_at).strftime("%H:%M")
    return ""


def _get_fecha_cierre(visit) -> str:
    from django.utils import timezone as tz
    from apps.recepcion.models import VisitStatusLog
    log = VisitStatusLog.objects.filter(
        visit=visit, to_status="cerrada"
    ).order_by("changed_at").last()
    if log:
        return tz.localtime(log.changed_at).strftime("%d/%m/%Y")
    return ""


def _get_hora_consulta(visit) -> str:
    from django.utils import timezone as tz
    from apps.recepcion.services.hora_consulta_resolver import resolve_hora_consulta

    cita_dt = _get_cita_datetime(visit)
    fch_alta_local = tz.localtime(visit.fch_alta) if visit.fch_alta else None
    return resolve_hora_consulta(visit.hora_consulta, cita_dt, fch_alta_local)


def _get_fecha_consulta(visit) -> str:
    from django.utils import timezone as tz

    # 1. Fecha explícita elegida por el recepcionista al hacer check-in
    if visit.fecha_consulta:
        return visit.fecha_consulta.strftime("%d/%m/%Y")
    # 2. Cita médica vinculada → fecha de la cita
    cita_dt = _get_cita_datetime(visit)
    if cita_dt:
        return cita_dt.strftime("%d/%m/%Y")
    # 3. Fallback: fecha del check-in
    if visit.fch_alta:
        return tz.localtime(visit.fch_alta).strftime("%d/%m/%Y")
    return ""


def _get_vitals(visit):
    try:
        return visit.vital_signs
    except Exception:
        return None


def _get_nombre_doctor(visit) -> str:
    if not visit.doctor_id:
        return ""
    try:
        from apps.authentication.models import DetUsuario
        det = DetUsuario.objects.filter(id_usuario_id=visit.doctor_id).first()
        return det.nombre_completo if det else ""
    except Exception:
        return ""


def _get_turno_context(visit) -> dict:
    """
    Usa num_ficha y turno_nombre guardados al crear la visita.
    Usa try/except para tolerar que las columnas aún no existan en la BD.
    """
    try:
        num_ficha    = visit.num_ficha
        turno_nombre = visit.turno_nombre or ""
    except Exception:
        num_ficha    = None
        turno_nombre = ""

    return {
        "num_ficha":   str(num_ficha) if num_ficha else str(visit.id_visit),
        "folio_ficha": visit.folio,
        "turno":       turno_nombre,
    }


def build_context(visit, usuario_nombre: str = "", nombre: dict | None = None) -> dict:
    """``nombre`` permite inyectar los datos del paciente ya resueltos (motor
    WeasyPrint, via patient_header); si es None se consulta SERMED (docx)."""
    from django.utils import timezone as tz

    if nombre is None:
        nombre = _get_nombre_components(llave_publica(visit)[0] or "", llave_publica(visit)[1])
    vitals  = _get_vitals(visit)
    # Usar hora local (Mexico_City) para día/mes/año de la ficha
    fecha   = tz.localtime(visit.fch_alta) if visit.fch_alta else datetime.now()

    consultorio     = ""
    centro_atencion = ""
    if visit.consultorio:
        consultorio = str(visit.consultorio.numero)
        try:
            if visit.consultorio.id_center:
                centro_atencion = visit.consultorio.id_center.name
        except Exception:
            pass

    ta = ""
    sistolica   = ""
    diastolica  = ""
    if vitals and vitals.blood_pressure_systolic and vitals.blood_pressure_diastolic:
        sistolica  = str(vitals.blood_pressure_systolic)
        diastolica = str(vitals.blood_pressure_diastolic)
        ta = f"{sistolica}/{diastolica}"

    return {
        "a_paterno":             nombre["a_paterno"],
        "a_materno":             nombre["a_materno"],
        "nombre_paciente":       nombre["nombre_paciente"] or visit.nombre_paciente or "",
        "nombre_doctor":         _get_nombre_doctor(visit),
        "usuario_recepcion":     usuario_nombre,
        "edad":                  nombre.get("edad", ""),
        "fecnac":                nombre.get("fecha_nac", ""),
        "expediente":            llave_publica(visit)[0] or "",
        "folio_ficha":           visit.folio,
        # Turno y número secuencial de ficha
        **_get_turno_context(visit),
        "consultorio":           consultorio,
        "centro_atencion":       centro_atencion,   # sin acento
        "centro_atención":       centro_atencion,   # con acento (como está en el Word)
        "hora_consulta":         _get_hora_consulta(visit),
        "fecha_consulta":        _get_fecha_consulta(visit),
        "hora_registro":         tz.localtime(visit.fch_alta).strftime("%H:%M") if visit.fch_alta else "",
        "fecha_registro":        tz.localtime(visit.fch_alta).strftime("%d/%m/%Y") if visit.fch_alta else "",
        "hora_cierre":           _get_hora_cierre(visit),
        "fecha_cierre":          _get_fecha_cierre(visit),
        "anio":                  str(fecha.year),
        "mes":                   str(fecha.month).zfill(2),
        "dia":                   str(fecha.day).zfill(2),
        "peso":                    str(vitals.weight_kg)                   if vitals else "",
        "talla":                   str(vitals.height_cm)                   if vitals else "",
        "temperatura":             str(vitals.temperature_c)               if vitals and vitals.temperature_c          else "",
        "t":                       {"a": ta},
        "tension_arterial":        ta,
        "sistolica":               sistolica,
        "diastolica":              diastolica,
        "frecuencia_cardiaca":     str(vitals.heart_rate_bpm)              if vitals and vitals.heart_rate_bpm         else "",
        "frecuencia_respiratoria": str(vitals.respiratory_rate_bpm)        if vitals and vitals.respiratory_rate_bpm   else "",
        "saturacion_oxigeno":      str(vitals.oxygen_saturation_pct)       if vitals and vitals.oxygen_saturation_pct  else "",
        "cintura":                 str(vitals.waist_circumference_cm)      if vitals and vitals.waist_circumference_cm else "",
        "imc":                     str(vitals.bmi)                         if vitals else "",
        "glucosa_capilar":         str(vitals.glucosa_capilar_mgdl)        if vitals and vitals.glucosa_capilar_mgdl   else "",
        "notas_vitales":           vitals.notes or ""                      if vitals else "",
    }


def _word_convert_worker(abs_docx: str, abs_pdf: str, error_holder: list) -> None:
    """
    Corre en un thread dedicado con su propio CoInitialize.
    Daphne usa async — COM de Word requiere un STA thread propio.
    """
    import pythoncom
    import win32com.client

    WD_FORMAT_PDF       = 17
    WD_ORIENT_LANDSCAPE = 1
    A5_W = 595   # 210 mm en puntos
    A5_H = 420   # 148 mm en puntos

    pythoncom.CoInitialize()
    word = None
    wdoc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        wdoc = word.Documents.Open(abs_docx)
        wdoc.PageSetup.Orientation = WD_ORIENT_LANDSCAPE
        wdoc.PageSetup.PageWidth   = A5_W
        wdoc.PageSetup.PageHeight  = A5_H
        wdoc.SaveAs2(abs_pdf, FileFormat=WD_FORMAT_PDF)
    except Exception as exc:
        error_holder.append(exc)
    finally:
        if wdoc is not None:
            try:
                wdoc.Close(SaveChanges=False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _docx_to_pdf_half_letter(docx_path: str, pdf_path: str) -> None:
    """Lanza la conversión Word→PDF en un thread STA dedicado."""
    import threading

    abs_docx = os.path.abspath(docx_path).replace("/", "\\")
    abs_pdf  = os.path.abspath(pdf_path).replace("/", "\\")

    errors: list = []
    t = threading.Thread(target=_word_convert_worker, args=(abs_docx, abs_pdf, errors))
    t.start()
    t.join(timeout=60)

    if t.is_alive():
        raise TimeoutError("Word tardó demasiado en generar el PDF.")
    if errors:
        raise errors[0]


def _crop_pdf_to_content(pdf_path: str) -> None:
    """
    Recorta el PDF al área con contenido real, eliminando el espacio en blanco inferior.
    Usa pikepdf para leer el bounding box real del contenido y ajustar la página.
    """
    import pikepdf

    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]

        # Coordenadas del mediabox original [x0, y0, x1, y1]
        mb     = page.mediabox
        x0     = float(mb[0])
        y0     = float(mb[1])
        x1     = float(mb[2])
        page_h = float(mb[3])

        # Obtener bounding box real del contenido
        content_y_min = page_h  # irá bajando al recorrer objetos
        for operands, operator in pikepdf.parse_content_stream(page):
            op = str(operator)
            # "Td", "TD", "Tm" son operadores de posicionamiento de texto
            if op in ("Td", "TD") and len(operands) >= 2:
                y = float(operands[1])
                if y < content_y_min:
                    content_y_min = y
            elif op == "Tm" and len(operands) >= 6:
                y = float(operands[5])
                if y < content_y_min:
                    content_y_min = y
            # "re" es rectángulo (tablas/bordes)
            elif op == "re" and len(operands) >= 4:
                y      = float(operands[1])
                height = float(operands[3])
                bottom = y + min(height, 0)
                if bottom < content_y_min:
                    content_y_min = bottom

        # Margen inferior de 10 pt para no cortar bordes
        crop_y0 = max(x0, content_y_min - 10)

        from decimal import Decimal as D
        new_box = pikepdf.Array([
            pikepdf.Real(D(str(round(x0,     2)))),
            pikepdf.Real(D(str(round(crop_y0, 2)))),
            pikepdf.Real(D(str(round(x1,     2)))),
            pikepdf.Real(D(str(round(page_h,  2)))),
        ])
        page.mediabox = new_box
        page.cropbox  = new_box

        pdf.save(pdf_path)


def generate_ficha_pdf(visit, usuario_nombre: str = "") -> bytes:
    """
    Renderiza la plantilla Word con los datos de la visita y devuelve el PDF
    recortado al contenido real sin espacio en blanco.
    Requiere: docxtpl, pywin32, pikepdf, Microsoft Word instalado en el servidor.
    """
    from docxtpl import DocxTemplate

    context = build_context(visit, usuario_nombre=usuario_nombre)

    doc = DocxTemplate(TEMPLATE_PATH)
    doc.render(context)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        docx_out = os.path.join(tmpdir, f"ficha_{visit.id_visit}.docx")
        pdf_out  = os.path.join(tmpdir, f"ficha_{visit.id_visit}.pdf")

        doc.save(docx_out)
        _docx_to_pdf_half_letter(docx_out, pdf_out)
        _crop_pdf_to_content(pdf_out)

        with open(pdf_out, "rb") as f:
            return f.read()
