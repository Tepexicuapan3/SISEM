"""
Historial previo a SIRES leido directo de la copia del legado (diseño del
2026-10-27). Se guarda por id_paciente y se lee por id_persona: de la persona
salen todas sus afiliaciones y de cada una sus llaves del legado
(identificadores NO_EXP del titular y CD_FAMILIAR del familiar, ver
legado_llaves). El legado tiene una base por año: primero se cuentan las
notas de la persona en cada base (una sola consulta) y despues se leen las
notas de UNA base, la que elige el medico, con medico, clinica, servicio,
diagnosticos y medicamentos de los catalogos de la base actual (las anuales
pueden no tenerlos).
"""
from __future__ import annotations

from apps.consulta_medica.models import PatientIdentifier
from apps.consulta_medica.services import legado_archivo
from apps.consulta_medica.services.patient_link_service import records_for_key
from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp

MAX_NOTAS = 200
ACTUAL = legado_archivo.ESQUEMA_ACTUAL
# Cruces con catalogos: en MySQL sin CAST, para que use el indice del catalogo.
C = legado_archivo.clave


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
        params.extend([legado_archivo.valor_expediente(no_exp), tp])
    return "(" + " OR ".join(partes) + ")", params


def _texto(valor):
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _fecha(valor):
    """El legado guarda '0000-00-00' como "sin fecha"; el driver lo deja como texto."""
    if not valor or str(valor).startswith("0000"):
        return None
    return valor


def _nombre_medico(fila):
    partes = [_texto(fila.get(c)) for c in ("med_paterno", "med_materno", "med_nombre")]
    nombre = " ".join(p for p in partes if p)
    return nombre or None


def bases_con_notas(llaves) -> list[dict]:
    """Bases donde la persona tiene notas, con cuantas y de que fechas, en el
    orden de esquemas_con_tabla (la actual primero). Una sola consulta: cada
    parte usa el indice del expediente."""
    esquemas = legado_archivo.esquemas_con_tabla("his_notas")
    if not esquemas:
        return []
    condicion, params_llaves = _condicion(llaves)
    partes, params = [], []
    for esquema in esquemas:
        partes.append(
            "SELECT %s AS esquema, count(*) AS total, min(n.fe_nota) AS desde, max(n.fe_nota) AS hasta "
            f"FROM {legado_archivo.tabla(esquema, 'his_notas')} n WHERE {condicion}"
        )
        params.extend([esquema, *params_llaves])
    filas = {f["esquema"]: f for f in legado_archivo.consultar(" UNION ALL ".join(partes), params)}
    resultado = []
    for esquema in esquemas:
        fila = filas.get(esquema)
        if fila and int(fila["total"] or 0):
            resultado.append({"sourceDb": esquema, "total": int(fila["total"]),
                              "from": _fecha(fila["desde"]), "to": _fecha(fila["hasta"])})
    return resultado


def _notas_de_esquema(esquema, llaves):
    condicion, params = _condicion(llaves)
    notas = legado_archivo.tabla(esquema, "his_notas")
    medicos = legado_archivo.tabla(ACTUAL, "cat_medicos")
    clinicas = legado_archivo.tabla(ACTUAL, "cat_clinicas")
    cie = legado_archivo.tabla(ACTUAL, "cat_cie10")
    servicios = legado_archivo.tabla(ACTUAL, "cat_servicios")
    tipos = legado_archivo.tabla(ACTUAL, "cat_tpconsulta")
    especialidades = legado_archivo.tabla(ACTUAL, "cat_especialidad")
    sql = f"""
        SELECT n.cd_snota, n.cd_clinica, n.fe_nota, n.hh_nota, n.cd_medico,
               n.ds_sintomas, n.ds_objetivo, n.ds_analisis, n.ds_plan, n.ds_diagnostico,
               n.sw_complemento, n.sw_status, n.sw_incapacidad, n.sw_laboratorio, n.sw_gabinete, n.fe_cita, n.cd_servicio, n.tp_consulta, n.cd_especialidad,
               n.no_peso, n.no_estatura, n.no_ta, n.no_pulso, n.no_temp, n.no_resp, n.no_imc, n.no_gluc,
               m.ds_paterno AS med_paterno, m.ds_materno AS med_materno, m.ds_nombre AS med_nombre,
               c.ds_clinica, x.cd_cie, x.ds_cie, s.ds_servicio, t.ds_tpconsulta, e.ds_especialidad
        FROM {notas} n
        LEFT JOIN {medicos} m ON {C('m.no_medico')} = {C('n.cd_medico')}
        LEFT JOIN {clinicas} c ON {C('c.cd_clinica')} = {C('n.cd_clinica')}
        LEFT JOIN {cie} x ON {C('x.no_cie')} = {C('n.no_cie')}
        LEFT JOIN {servicios} s ON {C('s.cd_servicio')} = {C('n.cd_servicio')}
        LEFT JOIN {tipos} t ON {C('t.tp_consulta')} = {C('n.tp_consulta')}
        LEFT JOIN {especialidades} e ON {C('e.cd_especialidad')} = {C('n.cd_especialidad')}
        WHERE {condicion}
        ORDER BY n.fe_nota DESC, n.hh_nota DESC
        LIMIT {MAX_NOTAS}
    """
    return legado_archivo.consultar(sql, params)


def _folios(notas):
    folios = sorted({str(n["cd_snota"]) for n in notas})
    return folios, ", ".join(["%s"] * len(folios))


def _diagnosticos(esquema, notas) -> dict[tuple, list[dict]]:
    """Diagnosticos CIE-10 de esas notas: (cd_clinica, cd_snota) -> [{codigo, descripcion}].
    det_hisnotcie.cd_cie es el numero interno del catalogo (cat_cie10.no_cie), no la clave."""
    if not notas:
        return {}
    detalle = legado_archivo.tabla(esquema, "det_hisnotcie")
    cie = legado_archivo.tabla(ACTUAL, "cat_cie10")
    folios, marcas = _folios(notas)
    filas = legado_archivo.consultar(
        f"""
        SELECT d.cd_snota, d.cd_clinica, x.cd_cie, x.ds_cie
        FROM {detalle} d
        LEFT JOIN {cie} x ON {C('x.no_cie')} = {C('d.cd_cie')}
        WHERE {C('d.cd_snota')} IN ({marcas}) AND d.sw_status = 'A'
        ORDER BY d.cd_detcie
        """,
        folios,
    )
    resultado: dict[tuple, list[dict]] = {}
    for fila in filas:
        llave = (str(fila["cd_clinica"]), str(fila["cd_snota"]))
        resultado.setdefault(llave, []).append({"codigo": _texto(fila["cd_cie"]), "descripcion": _texto(fila["ds_cie"])})
    return resultado


def _medicamentos(esquema, notas) -> dict[str, list[dict]]:
    """Medicamentos recetados en esas notas: cd_snota -> [medicamento]. det_receta
    solo tiene indice por cd_snota, por eso se llega a ella desde las notas."""
    if not notas:
        return {}
    receta = legado_archivo.tabla(esquema, "det_receta")
    catalogo = legado_archivo.tabla(ACTUAL, "cat_medicamentos")
    folios, marcas = _folios(notas)
    filas = legado_archivo.consultar(
        f"""
        SELECT r.cd_snota, r.no_medic, r.no_cantidad, r.ds_indicaciones, r.fe_surtida, r.sw_status,
               med.ds_medic, med.ds_activo
        FROM {receta} r
        LEFT JOIN {catalogo} med ON {C('med.no_medic')} = {C('r.no_medic')}
        WHERE {C('r.cd_snota')} IN ({marcas})
        ORDER BY r.cd_receta
        """,
        folios,
    )
    resultado: dict[str, list[dict]] = {}
    for fila in filas:
        resultado.setdefault(str(fila["cd_snota"]), []).append({
            "name": _texto(fila["ds_medic"]) or f"Medicamento {fila['no_medic']}",
            "activeIngredient": _texto(fila["ds_activo"]),
            "quantity": fila["no_cantidad"],
            "instructions": _texto(fila["ds_indicaciones"]),
            "dispensedOn": _fecha(fila["fe_surtida"]),
            "cancelled": (_texto(fila["sw_status"]) or "A") != "A",
        })
    return resultado


def _dias(valor):
    """ds_dias es texto ('3', '07'): numero si se puede, el texto tal cual si no."""
    texto = _texto(valor)
    return int(texto) if texto and texto.isdigit() else texto


def _incapacidades(esquema, notas) -> dict[str, list[dict]]:
    """Dias de incapacidad de esas notas: cd_snota -> [{days, cancelled}]. Solo
    las notas marcadas con sw_incapacidad = 'S'; det_licencia no tiene indice
    por cd_snota, pero es chica (unas 25 mil filas en la base actual). El resto
    de la incapacidad se ve en su propia seccion."""
    folios, marcas = _folios([n for n in notas if _texto(n.get("sw_incapacidad")) == "S"])
    if not folios:
        return {}
    licencias = legado_archivo.tabla(esquema, "det_licencia")
    filas = legado_archivo.consultar(
        f"""
        SELECT l.cd_snota, l.ds_dias, l.sw_status
        FROM {licencias} l
        WHERE {C('l.cd_snota')} IN ({marcas})
        ORDER BY l.cd_licencia
        """,
        folios,
    )
    resultado: dict[str, list[dict]] = {}
    for fila in filas:
        resultado.setdefault(str(fila["cd_snota"]), []).append({
            "days": _dias(fila["ds_dias"]),
            "cancelled": (_texto(fila["sw_status"]) or "A") != "A",
        })
    return resultado


# Pases con estudios: (tabla de detalle, columna del estudio, marca en la nota, tipo).
# Las dos apuntan a cat_estudios.cd_estudios ("RX ARTICULACION RODILLA (2 PROYECCIONES)").
_PASES_CON_ESTUDIOS = (
    ("det_pasgab", "cd_estudiog", "sw_gabinete", "GABINETE"),
    ("det_paslab", "cd_estudiol", "sw_laboratorio", "LABORATORIO"),
)


def _estudios(esquema, notas, con_tabla) -> dict[str, list[dict]]:
    """Estudios de los pases de gabinete y laboratorio de esas notas:
    cd_snota -> [{type, name, note, cancelled}]; note es lo que anoto el medico
    en el estudio ("AP Y LATERAL CON INTERPRETACION"). Solo las notas con la marca del
    pase; las tablas de detalle no tienen indice por cd_snota."""
    catalogo = legado_archivo.tabla(ACTUAL, "cat_estudios")
    resultado: dict[str, list[dict]] = {}
    for detalle, columna, marca, tipo in _PASES_CON_ESTUDIOS:
        if detalle not in con_tabla:
            continue
        folios, marcas = _folios([n for n in notas if _texto(n.get(marca)) == "S"])
        if not folios:
            continue
        filas = legado_archivo.consultar(
            f"""
            SELECT d.cd_snota, d.{columna} AS cd_estudio, d.sw_status, d.ds_complemento, e.ds_estudios
            FROM {legado_archivo.tabla(esquema, detalle)} d
            LEFT JOIN {catalogo} e ON {C('e.cd_estudios')} = {C(f'd.{columna}')}
            WHERE {C('d.cd_snota')} IN ({marcas})
            ORDER BY d.cd_estudio
            """,
            folios,
        )
        for fila in filas:
            resultado.setdefault(str(fila["cd_snota"]), []).append({
                "type": tipo,
                "name": _texto(fila["ds_estudios"]) or f"Estudio {fila['cd_estudio']}",
                "note": _texto(fila["ds_complemento"]),
                "cancelled": (_texto(fila["sw_status"]) or "A") != "A",
            })
    return resultado


def _contrato(esquema, nota, diagnosticos, medicamentos, incapacidades=None, estudios=None) -> dict:
    llave = (str(nota["cd_clinica"]), str(nota["cd_snota"]))
    principal = None
    if nota.get("cd_cie") or nota.get("ds_cie"):
        principal = {"codigo": _texto(nota.get("cd_cie")), "descripcion": _texto(nota.get("ds_cie"))}
    # cd_especialidad 0 es " SIN ESPECIALIDAD" en el catalogo: no aporta nada.
    especialidad = _texto(nota.get("ds_especialidad")) if nota.get("cd_especialidad") else None
    return {
        "id": f"{esquema}:{llave[0]}:{llave[1]}",
        "legacyFolio": llave[1],
        "sourceDb": esquema,
        "date": nota["fe_nota"],
        "time": _texto(nota.get("hh_nota")),
        "doctorName": _nombre_medico(nota),
        "clinicName": _texto(nota.get("ds_clinica")),
        "serviceName": _texto(nota.get("ds_servicio")),
        "consultationType": _texto(nota.get("ds_tpconsulta")),
        "specialtyName": especialidad,
        "subjective": _texto(nota.get("ds_sintomas")),
        "objective": _texto(nota.get("ds_objetivo")),
        "assessment": _texto(nota.get("ds_analisis")),
        "plan": _texto(nota.get("ds_plan")),
        "diagnosticImpression": _texto(nota.get("ds_diagnostico")),
        "primaryCie": principal,
        "diagnoses": diagnosticos.get(llave, []),
        "medications": medicamentos.get(llave[1], []),
        "sickLeaves": (incapacidades or {}).get(llave[1], []),
        "referralStudies": (estudios or {}).get(llave[1], []),
        # fe_cita es la proxima cita que dejo el medico (casi siempre vacia).
        "nextAppointment": _fecha(nota.get("fe_cita")),
        "addendumLegacy": _texto(nota.get("sw_complemento")),
        "statusLegacy": _texto(nota.get("sw_status")),
        "weightLegacy": _texto(nota.get("no_peso")),
        "heightLegacy": _texto(nota.get("no_estatura")),
        "bloodPressureLegacy": _texto(nota.get("no_ta")),
        "pulseLegacy": _texto(nota.get("no_pulso")),
        "temperatureLegacy": _texto(nota.get("no_temp")),
        "respirationLegacy": _texto(nota.get("no_resp")),
        "bmiLegacy": _texto(nota.get("no_imc")),
        "glucoseLegacy": _texto(nota.get("no_gluc")),
    }


def _vacio(base=None, bases=None) -> dict:
    payload = {"items": [], "total": 0, "totalCount": 0, "base": base}
    if bases is not None:
        payload["bases"] = bases
    return payload


def historial(no_exp, pk_num, base=None) -> dict:
    """Notas del legado de la persona en UNA base, las mas recientes primero.

    Sin `base`: devuelve tambien `bases` (donde tiene notas) y las notas de la
    primera. Con `base`: solo las notas de esa base (la lista ya la tiene la
    pantalla). Lanza LegadoNoDisponible si la copia no esta o no responde."""
    llaves = llaves_legado(no_exp, pk_num)
    if not llaves:
        return _vacio(bases=[] if base is None else None)

    bases = None
    if base is None:
        bases = bases_con_notas(llaves)
        if not bases:
            return _vacio(bases=[])
        base = bases[0]["sourceDb"]
    elif base not in legado_archivo.esquemas_con_tabla("his_notas"):
        return _vacio(base=base)

    notas = _notas_de_esquema(base, llaves)
    diagnosticos = _diagnosticos(base, notas) if base in legado_archivo.esquemas_con_tabla("det_hisnotcie") else {}
    medicamentos = _medicamentos(base, notas) if base in legado_archivo.esquemas_con_tabla("det_receta") else {}
    incapacidades = (_incapacidades(base, notas)
                     if base in legado_archivo.esquemas_con_tabla("det_licencia") else {})
    con_tabla = {detalle for detalle, *_ in _PASES_CON_ESTUDIOS
                 if base in legado_archivo.esquemas_con_tabla(detalle)}
    estudios = _estudios(base, notas, con_tabla)
    items = [_contrato(base, nota, diagnosticos, medicamentos, incapacidades, estudios) for nota in notas]
    if bases is not None:
        total = bases[0]["total"]
    else:
        total = _contar_en_esquema(base, llaves) if len(notas) >= MAX_NOTAS else len(notas)
    payload = {"items": items, "total": len(items), "totalCount": total, "base": base}
    if bases is not None:
        payload["bases"] = bases
    return payload


def _contar_en_esquema(esquema, llaves) -> int:
    condicion, params = _condicion(llaves)
    filas = legado_archivo.consultar(
        f"SELECT count(*) AS total FROM {legado_archivo.tabla(esquema, 'his_notas')} n WHERE {condicion}", params,
    )
    return int(filas[0]["total"]) if filas else 0
