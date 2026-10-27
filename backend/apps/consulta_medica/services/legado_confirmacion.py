"""
Datos del legado que un medico confirma antes de que pasen a SIRES (diseño
del 2026-10-27, paso 3). Se leen de la copia (his_clinica y his_clinicad de
todas las bases) por las llaves de la persona, y se proponen por seccion:
alergias, antecedentes personales, familiares y quirurgicos, y habitos.

Confirmar una seccion crea en SIRES lo marcado (con origen "legado" y la
referencia de la fila) y deja como descartado lo que se mostro sin marcar.
Ninguno de los dos se vuelve a proponer (cns_legado_revision). El servidor
vuelve a leer las propuestas al confirmar: nunca crea texto que mande el
cliente, solo acepta referencias de lo que el mismo propuso.

El grupo sanguineo no esta en esas tablas del legado: no se propone.
"""
from __future__ import annotations

from django.db import transaction

from apps.consulta_medica.models import (
    Allergy,
    FamilyHistory,
    Habit,
    LegacyReview,
    PersonalHistory,
    SpecialtySource,
    SurgicalHistory,
)
from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository
from apps.consulta_medica.services import legado_archivo
from apps.consulta_medica.services.legacy_history_import_service import (
    DENTAL_ALLERGY_COLUMNS,
    FAMILY_FLAG_COLUMNS,
    HABIT_FLAG_COLUMNS,
    OTHER_ALLERGY_TYPE,
    PERSONAL_FLAG_COLUMNS,
    LegacyHistoryImporter,
)
from apps.consulta_medica.services.legacy_history_parsing import (
    is_negative_allergy,
    split_allergy_items,
    split_annotations,
)
from apps.consulta_medica.services.legado_historial import _condicion, llaves_legado
from apps.consulta_medica.services.patient_link_service import records_for_key
from apps.consulta_medica.services.patient_registry_service import ORIGEN_LEGADO
from apps.recepcion.services.errors import VisitDomainError

ALERGIAS = "alergias"
PERSONALES = "antecedentes_personales"
FAMILIARES = "antecedentes_familiares"
QUIRURGICOS = "antecedentes_quirurgicos"
HABITOS = "habitos"
SECCIONES = (ALERGIAS, PERSONALES, FAMILIARES, QUIRURGICOS, HABITOS)
TITULOS = {
    ALERGIAS: "Alergias", PERSONALES: "Antecedentes personales", FAMILIARES: "Antecedentes familiares",
    QUIRURGICOS: "Antecedentes quirúrgicos", HABITOS: "Hábitos",
}
_HABITO_TEXTO = {"tabaquismo": "Tabaquismo", "alcoholismo": "Alcoholismo", "toxicomanias": "Toxicomanías"}


def _texto(valor) -> str:
    return (str(valor) if valor is not None else "").strip()


def _marcada(valor) -> bool:
    return _texto(valor).upper() == "S"


def _filas(tabla, llaves, columnas="*"):
    """Filas de esa tabla del legado para la persona, en todas las bases, la mas reciente primero."""
    filas = []
    condicion, params = _condicion(llaves, alias="a")
    for esquema in legado_archivo.esquemas_con_tabla(tabla):
        sql = (
            f"SELECT {columnas} FROM {legado_archivo.tabla(esquema, tabla)} a "
            f"WHERE {condicion} ORDER BY a.fe_hisclin DESC"
        )
        filas.extend({**fila, "_esquema": esquema} for fila in legado_archivo.consultar(sql, params))
    filas.sort(key=lambda fila: str(fila.get("fe_hisclin") or ""), reverse=True)
    return filas


def _item(seccion, fila, tabla, campo, texto, indice=None, **destino):
    ref = f"{fila['_esquema']}:{tabla}:{fila.get('no_hisclin')}:{campo}"
    if indice is not None:
        ref = f"{ref}:{indice}"
    fecha = fila.get("fe_hisclin")
    return {
        "ref": ref, "seccion": seccion, "texto": texto[:500],
        "fecha": fecha.isoformat() if hasattr(fecha, "isoformat") else (_texto(fecha) or None),
        "origen": f"{tabla} · {fila['_esquema']}", "_destino": destino,
    }


def _de_his_clinica(fila):
    for contenido, _fecha, _autor in split_annotations(fila.get("ds_alergias")):
        for indice, sustancia in enumerate(split_allergy_items(contenido)):
            if sustancia.strip() and not is_negative_allergy(sustancia):
                yield _item(ALERGIAS, fila, "his_clinica", "ds_alergias", sustancia.strip(), indice,
                            tipo=OTHER_ALLERGY_TYPE, fuente=Allergy.Source.GENERAL, original=contenido)


def _de_his_clinicad(fila):
    for columna, tipo in DENTAL_ALLERGY_COLUMNS.items():
        texto = _texto(fila.get(columna))
        if texto and not is_negative_allergy(texto):
            yield _item(ALERGIAS, fila, "his_clinicad", columna, texto,
                        tipo=tipo, fuente=Allergy.Source.STOMATOLOGY, original=texto)
    for columna, (categoria, etiqueta) in PERSONAL_FLAG_COLUMNS.items():
        if _marcada(fila.get(columna)):
            yield _item(PERSONALES, fila, "his_clinicad", columna, etiqueta, categoria=categoria)
    for columna, (categoria, etiqueta) in FAMILY_FLAG_COLUMNS.items():
        if _marcada(fila.get(columna)):
            yield _item(FAMILIARES, fila, "his_clinicad", columna, etiqueta, categoria=categoria)
    if _texto(fila.get("ds_muerte")):
        yield _item(FAMILIARES, fila, "his_clinicad", "ds_muerte",
                    f"Familiar finado: {_texto(fila.get('ds_muerte'))}", finado=_texto(fila.get("ds_muerte")))
    if _texto(fila.get("ds_antquir")):
        yield _item(QUIRURGICOS, fila, "his_clinicad", "ds_antquir", _texto(fila.get("ds_antquir")))
    for columna, codigo in HABIT_FLAG_COLUMNS.items():
        if _marcada(fila.get(columna)):
            yield _item(HABITOS, fila, "his_clinicad", columna, _HABITO_TEXTO.get(codigo, codigo), habito=codigo)
    for columna, codigo, etiqueta in (("ds_habitos", "otro", "Otros hábitos"),
                                      ("ds_alimentos", "alimentacion", "Alimentación")):
        if _texto(fila.get(columna)):
            yield _item(HABITOS, fila, "his_clinicad", columna, f"{etiqueta}: {_texto(fila.get(columna))}",
                        habito=codigo, notas=_texto(fila.get(columna)))


def _propuestas_crudas(no_exp, pk_num) -> list[dict]:
    llaves = llaves_legado(no_exp, pk_num)
    if not llaves:
        return []
    items = []
    for fila in _filas("his_clinica", llaves, "a.no_hisclin, a.fe_hisclin, a.ds_alergias"):
        items.extend(_de_his_clinica(fila))
    for fila in _filas("his_clinicad", llaves):
        items.extend(_de_his_clinicad(fila))
    return items


def _ya_revisado(registros) -> tuple[set[str], set[tuple[str, str]]]:
    """Referencias revisadas y (seccion, texto): el mismo dato repetido en otra
    fila del legado tampoco vuelve a proponerse."""
    filas = LegacyReview.objects.filter(patient__in=registros).values_list("legacy_ref", "section", "text")
    return {ref for ref, _, _ in filas}, {(seccion, texto.lower()) for _, seccion, texto in filas}


def _alergias_existentes(registros) -> set[str]:
    return {s.lower() for s in Allergy.objects.filter(patient__in=registros).values_list("substance", flat=True)}


def propuestas(no_exp, pk_num) -> list[dict]:
    """Secciones con lo pendiente de revisar (sin lo ya confirmado, descartado o
    capturado en SIRES; sin repetidos entre filas: gana la mas reciente).
    Lanza LegadoNoDisponible si la copia no esta o no responde."""
    registros = records_for_key(no_exp, pk_num)
    revisados, textos_revisados = _ya_revisado(registros)
    alergias = _alergias_existentes(registros)
    vistos, por_seccion = set(textos_revisados), {s: [] for s in SECCIONES}
    for item in _propuestas_crudas(no_exp, pk_num):
        clave = (item["seccion"], item["texto"].lower())
        if item["ref"] in revisados or clave in vistos:
            continue
        if item["seccion"] == ALERGIAS and item["texto"].lower() in alergias:
            continue
        vistos.add(clave)
        por_seccion[item["seccion"]].append({k: v for k, v in item.items() if not k.startswith("_")})
    return [{"seccion": s, "titulo": TITULOS[s], "items": por_seccion[s]} for s in SECCIONES if por_seccion[s]]


def alergias_sin_confirmar(no_exp, pk_num) -> list[dict]:
    """Alergias del legado que nadie confirmo ni descarto todavia (para la
    alerta al recetar). Si la copia no esta o no responde, ninguna: la alerta
    es apoyo y nunca frena la receta."""
    if not legado_archivo.disponible():
        return []
    try:
        secciones = propuestas(no_exp, pk_num)
    except legado_archivo.LegadoNoDisponible:
        return []
    return next((s["items"] for s in secciones if s["seccion"] == ALERGIAS), [])


def _crear(importador, item, base, user_id):
    """Crea el dato en SIRES. Devuelve (tabla, id) o (None, None) si ya existia."""
    destino, seccion = item["_destino"], item["seccion"]
    if seccion == ALERGIAS:
        antes = Allergy.objects.filter(no_exp=base["no_exp"], pk_num=base["pk_num"]).count()
        importador.allergy(no_exp=base["no_exp"], pk_num=base["pk_num"], substance=item["texto"],
                           allergy_type_id=destino["tipo"], source=destino["fuente"],
                           original_text=destino["original"])
        if Allergy.objects.filter(no_exp=base["no_exp"], pk_num=base["pk_num"]).count() == antes:
            return None, None
        alergia = Allergy.objects.filter(no_exp=base["no_exp"], pk_num=base["pk_num"]).latest("id_allergy")
        Allergy.objects.filter(pk=alergia.pk).update(created_by_id=user_id)
        return Allergy._meta.db_table, alergia.pk
    if seccion == PERSONALES:
        creado = importador.record(PersonalHistory, base, cie_id=importador.cie_code(destino["categoria"]),
                                   description=item["texto"])
    elif seccion == FAMILIARES and "finado" in destino:
        creado = importador.record(FamilyHistory, base, is_deceased=True, cause_of_death=destino["finado"][:255],
                                   description="Familiar finado")
    elif seccion == FAMILIARES:
        creado = importador.record(FamilyHistory, base, cie_id=importador.cie_code(destino["categoria"]),
                                   description=item["texto"])
    elif seccion == QUIRURGICOS:
        creado = importador.record(SurgicalHistory, base, procedure=item["texto"][:500])
    else:
        campos = {"habit_id": importador._habits[destino["habito"]]}
        if destino.get("notas"):
            campos["notes"] = destino["notas"]
        creado = importador.record(Habit, base, **campos)
    if creado is None:
        return None, None
    type(creado).objects.filter(pk=creado.pk).update(created_by_id=user_id)
    return creado._meta.db_table, creado.pk


def confirmar(no_exp, pk_num, seccion, aceptar, *, user_id=None) -> dict:
    """Crea lo marcado de la seccion y descarta lo demas que se propuso.
    `aceptar`: referencias (ref) de los items marcados."""
    if seccion not in SECCIONES:
        raise VisitDomainError("SECCION_INVALIDA", "Esa sección del legado no existe.", 422)
    pendientes = next((s["items"] for s in propuestas(no_exp, pk_num) if s["seccion"] == seccion), [])
    if not pendientes:
        return {"confirmados": 0, "descartados": 0}
    refs_propuestas = {item["ref"] for item in pendientes}
    desconocidas = set(aceptar) - refs_propuestas
    if desconocidas:
        raise VisitDomainError(
            "LEGADO_CAMBIO", "Los datos del legado cambiaron mientras revisabas. Volvé a abrir la sección.", 409,
            details={"refs": sorted(desconocidas)},
        )
    completos = {item["ref"]: item for item in _propuestas_crudas(no_exp, pk_num) if item["ref"] in refs_propuestas}
    paciente, _ = PatientRepository.get_or_create(no_exp, pk_num, created_by_id=user_id, origen=ORIGEN_LEGADO)
    base = {"no_exp": paciente.no_exp, "pk_num": pk_num, "source": SpecialtySource.LEGACY}
    importador = LegacyHistoryImporter()
    confirmados = descartados = 0
    with transaction.atomic():
        for ref, item in completos.items():
            if ref in aceptar:
                tabla, creado = _crear(importador, item, {**base, "legacy_ref": ref[:60]}, user_id)
                decision, confirmados = LegacyReview.Decision.CONFIRMED, confirmados + 1
            else:
                tabla, creado = None, None
                decision, descartados = LegacyReview.Decision.REJECTED, descartados + 1
            LegacyReview.objects.create(
                patient=paciente, section=seccion, legacy_ref=ref, text=item["texto"], decision=decision,
                created_table=tabla, created_id=creado, created_by_id=user_id,
            )
    return {"confirmados": confirmados, "descartados": descartados}
