"""
Historial previo a SIRES leido directo de la copia del legado (diseño del
2026-10-27). Se guarda por id_paciente y se lee por id_persona: de la persona
salen todas sus afiliaciones y de cada una sus llaves del legado
(identificadores NO_EXP del titular y CD_FAMILIAR del familiar, ver
legado_llaves). Con esas llaves se buscan las notas en TODAS las bases
(legado_actual y las anuales), con medico, clinica y diagnosticos de los
catalogos de la base actual (las anuales pueden no tenerlos).
"""
from __future__ import annotations

from apps.consulta_medica.models import PatientIdentifier
from apps.consulta_medica.services import legado_archivo
from apps.consulta_medica.services.patient_link_service import records_for_key
from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp

MAX_NOTAS = 200
ACTUAL = legado_archivo.ESQUEMA_ACTUAL
T = legado_archivo.texto


def llaves_legado(no_exp, pk_num) -> list[tuple[str, int]]:
    """(no_exp, tp_paciente) con las que el legado conoce a la persona."""
    registros = records_for_key(no_exp, pk_num)
    llaves = set()
    identificadores = PatientIdentifier.objects.filter(
        patient__in=registros, status=PatientIdentifier.Status.ACTIVE,
        id_type__in=(PatientIdentifier.IdType.NO_EXP, PatientIdentifier.IdType.CD_FAMILIAR),
    ).select_related("patient")
    for identificador in identificadores:
        if identificador.id_type == PatientIdentifier.IdType.NO_EXP:
            llaves.add((normalizar_no_exp(identificador.value), 0))
        else:
            # En el legado el familiar es (expediente del titular, tp_paciente = cd_familiar).
            llaves.add((normalizar_no_exp(identificador.patient.no_exp), int(identificador.value)))
    return sorted(llaves)


def _condicion(llaves, alias="n") -> tuple[str, list]:
    partes, params = [], []
    for no_exp, tp in llaves:
        partes.append(f"({legado_archivo.sin_ceros(f'{alias}.no_exp')} = %s AND {alias}.tp_paciente = %s)")
        params.extend([no_exp, tp])
    return "(" + " OR ".join(partes) + ")", params


def _texto(valor):
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _nombre_medico(fila):
    partes = [_texto(fila.get(c)) for c in ("med_paterno", "med_materno", "med_nombre")]
    nombre = " ".join(p for p in partes if p)
    return nombre or None


def _notas_de_esquema(esquema, llaves):
    condicion, params = _condicion(llaves)
    notas = legado_archivo.tabla(esquema, "his_notas")
    medicos = legado_archivo.tabla(ACTUAL, "cat_medicos")
    clinicas = legado_archivo.tabla(ACTUAL, "cat_clinicas")
    cie = legado_archivo.tabla(ACTUAL, "cat_cie10")
    sql = f"""
        SELECT n.cd_snota, n.cd_clinica, n.fe_nota, n.hh_nota, n.cd_medico,
               n.ds_sintomas, n.ds_objetivo, n.ds_analisis, n.ds_plan, n.ds_diagnostico,
               n.sw_complemento, n.sw_status,
               n.no_peso, n.no_estatura, n.no_ta, n.no_pulso, n.no_temp, n.no_resp, n.no_imc, n.no_gluc,
               m.ds_paterno AS med_paterno, m.ds_materno AS med_materno, m.ds_nombre AS med_nombre,
               c.ds_clinica, x.cd_cie, x.ds_cie
        FROM {notas} n
        LEFT JOIN {medicos} m ON {T('m.no_medico')} = {T('n.cd_medico')}
        LEFT JOIN {clinicas} c ON {T('c.cd_clinica')} = {T('n.cd_clinica')}
        LEFT JOIN {cie} x ON {T('x.no_cie')} = {T('n.no_cie')}
        WHERE {condicion}
        ORDER BY n.fe_nota DESC, n.hh_nota DESC
        LIMIT {MAX_NOTAS}
    """
    return legado_archivo.consultar(sql, params)


def _contar_en_esquema(esquema, llaves) -> int:
    condicion, params = _condicion(llaves)
    filas = legado_archivo.consultar(
        f"SELECT count(*) AS total FROM {legado_archivo.tabla(esquema, 'his_notas')} n WHERE {condicion}", params,
    )
    return int(filas[0]["total"]) if filas else 0


def _diagnosticos(esquema, notas) -> dict[tuple, list[dict]]:
    """Diagnosticos CIE-10 de esas notas: (cd_clinica, cd_snota) -> [{codigo, descripcion}]."""
    if not notas:
        return {}
    detalle = legado_archivo.tabla(esquema, "det_hisnotcie")
    cie = legado_archivo.tabla(ACTUAL, "cat_cie10")
    folios = sorted({str(n["cd_snota"]) for n in notas})
    marcas = ", ".join(["%s"] * len(folios))
    filas = legado_archivo.consultar(
        f"""
        SELECT d.cd_snota, d.cd_clinica, x.cd_cie, x.ds_cie
        FROM {detalle} d
        LEFT JOIN {cie} x ON {T('x.no_cie')} = {T('d.cd_cie')}
        WHERE {T('d.cd_snota')} IN ({marcas}) AND d.sw_status = 'A'
        ORDER BY d.cd_detcie
        """,
        folios,
    )
    resultado: dict[tuple, list[dict]] = {}
    for fila in filas:
        llave = (str(fila["cd_clinica"]), str(fila["cd_snota"]))
        resultado.setdefault(llave, []).append({"codigo": _texto(fila["cd_cie"]), "descripcion": _texto(fila["ds_cie"])})
    return resultado


def _contrato(esquema, nota, diagnosticos) -> dict:
    llave = (str(nota["cd_clinica"]), str(nota["cd_snota"]))
    principal = None
    if nota.get("cd_cie") or nota.get("ds_cie"):
        principal = {"codigo": _texto(nota.get("cd_cie")), "descripcion": _texto(nota.get("ds_cie"))}
    return {
        "id": f"{esquema}:{llave[0]}:{llave[1]}",
        "legacyFolio": llave[1],
        "sourceDb": esquema,
        "date": nota["fe_nota"],
        "time": _texto(nota.get("hh_nota")),
        "doctorName": _nombre_medico(nota),
        "clinicName": _texto(nota.get("ds_clinica")),
        "subjective": _texto(nota.get("ds_sintomas")),
        "objective": _texto(nota.get("ds_objetivo")),
        "assessment": _texto(nota.get("ds_analisis")),
        "plan": _texto(nota.get("ds_plan")),
        "diagnosticImpression": _texto(nota.get("ds_diagnostico")),
        "primaryCie": principal,
        "diagnoses": diagnosticos.get(llave, []),
        "addendumLegacy": _texto(nota.get("sw_complemento")),
        "statusLegacy": _texto(nota.get("sw_status")),
        "weightLegacy": _texto(nota.get("no_peso")),
        "heightLegacy": _texto(nota.get("no_estatura")),
        "bloodPressureLegacy": _texto(nota.get("no_ta")),
        "pulseLegacy": _texto(nota.get("no_pulso")),
        "temperatureLegacy": _texto(nota.get("no_temp")),
    }


def historial(no_exp, pk_num) -> dict:
    """Notas del legado de la persona, de todas las bases, las mas recientes primero.
    Lanza LegadoNoDisponible si la copia no esta o no responde."""
    llaves = llaves_legado(no_exp, pk_num)
    if not llaves:
        return {"items": [], "total": 0, "totalCount": 0}
    items, total = [], 0
    con_diagnosticos = set(legado_archivo.esquemas_con_tabla("det_hisnotcie"))
    for esquema in legado_archivo.esquemas_con_tabla("his_notas"):
        notas = _notas_de_esquema(esquema, llaves)
        if not notas:
            continue
        total += _contar_en_esquema(esquema, llaves) if len(notas) >= MAX_NOTAS else len(notas)
        diagnosticos = _diagnosticos(esquema, notas) if esquema in con_diagnosticos else {}
        items.extend(_contrato(esquema, nota, diagnosticos) for nota in notas)
    items.sort(key=lambda item: (str(item["date"]), item["time"] or ""), reverse=True)
    items = items[:MAX_NOTAS]
    return {"items": items, "total": len(items), "totalCount": total}
