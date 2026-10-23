"""
apps/impresion/services/patient_header.py
=============================================
Encabezado de paciente compartido por ficha/receta/nota (solo lectura).

Cadena de resolucion (R2.1 S3): ``cns_paciente`` (tabla propia de SIRES) ->
SERMED ``buscar_expediente`` (solo SELECT sobre replicas) -> nombre
capturado en la visita. Nunca escribe en SERMED ni en tablas clinicas.
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)

SOURCE_PATIENT = "cns_paciente"
SOURCE_SERMED = "sermed"
SOURCE_VISIT = "visit"


def _age(birth_date, today=None):
    if not birth_date:
        return ""
    today = today or date.today()
    years = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return str(max(years, 0))


def _empty(no_exp, pk_num):
    return {
        "no_exp": no_exp or "",
        "pk_num": pk_num,
        "paternal_surname": "",
        "maternal_surname": "",
        "first_name": "",
        "full_name": "",
        "age": "",
        "birth_date": "",
        "sex": "",
        "source": None,
    }


def _full_name(first, paternal, maternal):
    return " ".join(p.strip() for p in (first, paternal, maternal) if p and p.strip())


def _from_patient(no_exp, pk_num):
    from apps.consulta_medica.services.patient_link_service import find_patient_by_record_key

    # Por llave de registro: tambien encuentra al familiar del legado y al
    # recien nacido provisional, que viajan con su cd_familiar como pk_num.
    patient = find_patient_by_record_key(no_exp, pk_num)
    if patient is None or not (patient.first_name or patient.paternal_surname):
        return None
    header = _empty(no_exp, pk_num)
    header.update(
        paternal_surname=patient.paternal_surname or "",
        maternal_surname=patient.maternal_surname or "",
        first_name=patient.first_name or "",
        full_name=_full_name(patient.first_name, patient.paternal_surname, patient.maternal_surname),
        age=_age(patient.birth_date),
        birth_date=patient.birth_date.strftime("%d/%m/%Y") if patient.birth_date else "",
        sex=patient.sex or "",
        source=SOURCE_PATIENT,
    )
    return header


def _default_sermed_lookup(no_exp):
    from apps.administracion.use_cases.expedientes.buscar_expediente import buscar_expediente

    return buscar_expediente(no_exp, incluir_fotos=False)


def _from_sermed(no_exp, pk_num, lookup):
    try:
        result = lookup(no_exp) or {}
    except Exception:
        logger.exception("SERMED no disponible resolviendo paciente %s", no_exp)
        return None
    row = None
    if pk_num == 0:
        empleados = result.get("empleados") or []
        row = empleados[0] if empleados else None
    else:
        row = next((f for f in (result.get("familiares") or []) if f.get("PK_NUM") == pk_num), None)
    if not row:
        return None
    paterno, materno, nombre = row.get("DS_PATERNO") or "", row.get("DS_MATERNO") or "", row.get("DS_NOMBRE") or ""
    if not (nombre or paterno):
        return None
    fe_nac = row.get("FE_NAC")
    header = _empty(no_exp, pk_num)
    header.update(
        paternal_surname=paterno,
        maternal_surname=materno,
        first_name=nombre,
        full_name=_full_name(nombre, paterno, materno),
        age=str(row["EDAD"]) if row.get("EDAD") is not None else "",
        birth_date=fe_nac.strftime("%d/%m/%Y") if hasattr(fe_nac, "strftime") else (str(fe_nac) if fe_nac else ""),
        source=SOURCE_SERMED,
    )
    return header


def get_patient_header(no_exp, pk_num, visit_name="", *, sermed_lookup=None):
    """Devuelve el dict de encabezado; ``source`` es None si no se resolvio nada."""
    pk_num = pk_num or 0
    header = _from_patient(no_exp, pk_num) if no_exp else None
    if header is None and no_exp:
        header = _from_sermed(no_exp, pk_num, sermed_lookup or _default_sermed_lookup)
    if header is None:
        header = _empty(no_exp, pk_num)
        if visit_name and visit_name.strip():
            header.update(full_name=visit_name.strip(), first_name=visit_name.strip(), source=SOURCE_VISIT)
    return header
