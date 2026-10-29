"""Generación del formato "Solicitud de servicio de oxígeno a domicilio" (.docx)
a partir de un ContratoOxigeno, usando docxtpl sobre formato_oxigeno.docx."""

import io
import os
from datetime import date

from docxtpl import DocxTemplate

from apps.administracion.services.fecha_service import calcular_edad
from apps.consulta_medica.services.paciente_entrada import llave_publica
from .models import ContratoOxigeno

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "formato_oxigeno.docx")

MESES = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
]


def _derechohabiencia_label(contrato: ContratoOxigeno) -> str:
    try:
        return ContratoOxigeno.TpDer(contrato.tp_der).label
    except ValueError:
        return contrato.tp_der


def build_context(contrato: ContratoOxigeno) -> dict:
    hoy = date.today()
    edad = calcular_edad(contrato.fecha_nacimiento)

    return {
        "dia":  str(hoy.day),
        "mes":  MESES[hoy.month - 1],
        "anio": str(hoy.year),

        "nombre_paciente":  contrato.nombre,
        "expediente":       llave_publica(contrato)[0],
        "derechohabiencia": _derechohabiencia_label(contrato),
        "edad":             edad if edad is not None else "",
        "clinica":          contrato.clinica,

        "calle":         contrato.calle,
        "num_ext":       contrato.num_ext,
        "num_int":       contrato.num_int,
        "colonia":       contrato.colonia,
        "alcaldia":      contrato.alcaldia,
        "cp":            contrato.cp,
        "entre_calle_1": contrato.entre_calle_1,
        "entre_calle_2": contrato.entre_calle_2,

        "tel_domicilio": contrato.telefono,
        "tel_oficina":   contrato.tel_oficina,
        "celular":       contrato.celular,
        "ext_tel":       contrato.ext_tel,

        "diagnostico": contrato.diagnostico,

        "hospital_azura":              contrato.hospital_azura,
        "medico_tratante":             contrato.medico_tratante,
        "especialidad":                contrato.especialidad,
        "tercer_nivel":                contrato.tercer_nivel,
        "institucion_referencia":      contrato.institucion_referencia,
        "medico_tratante_referencia":  contrato.medico_tratante_referencia,
        "tramite_subsecuente":         contrato.tramite_subsecuente,

        "num_contrato": contrato.num_contrato,
        "equipo":        contrato.servicio,
    }


def generar_formato_oxigeno(contrato: ContratoOxigeno) -> bytes:
    tpl = DocxTemplate(TEMPLATE_PATH)
    tpl.render(build_context(contrato))
    buffer = io.BytesIO()
    tpl.save(buffer)
    return buffer.getvalue()
