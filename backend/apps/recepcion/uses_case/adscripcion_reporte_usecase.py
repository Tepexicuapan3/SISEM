"""
P-03 · Reporte de adscritos: cuántos derechohabientes tiene cada centro,
consultorio familiar y turno, y quiénes son.

Solo cuenta adscripciones ACTIVA. Titular es pk_num = 0; todo lo demás
(familiares, familiares sin PK_NUM, recién nacidos provisionales) es familiar.
Qué centros se ven lo decide el alcance del usuario (centro_scope): su centro,
o todos con alcance:centros:todos; sin centro no ve nada. El listado es una
lectura masiva de datos personales y queda auditado.
"""

from dataclasses import dataclass

from django.db.models import Count, Q

from apps.authentication.services.centro_scope import AlcanceCentros
from apps.catalogos.models import Consultorios
from apps.recepcion.models import AdscripcionConsultorio, AdscripcionPaciente
from apps.recepcion.services.adscripcion_evaluacion import medicos_activos
from apps.recepcion.services.adscripcion_reporte_export import construir_libro_adscripcion
from apps.recepcion.uses_case.adscripcion_usecase import AdscripcionError, Operador, _auditar

TITULAR = "TITULAR"
FAMILIAR = "FAMILIAR"
_ES_TITULAR = Q(paciente__pk_num=0)


@dataclass(frozen=True)
class FiltrosAdscritos:
    centro_id: int | None = None
    consultorio_id: int | None = None
    turno_id: int | None = None
    tipo: str | None = None
    q: str | None = None


def _filtro_centro(alcance: AlcanceCentros, centro_id: int | None, campo: str) -> Q:
    """Un centro pedido (si el alcance lo permite) o todos los del alcance."""
    if centro_id is None:
        return alcance.q(campo)
    if not alcance.permite(centro_id):
        raise AdscripcionError("CENTRO_NO_PERMITIDO", "No tienes acceso a ese centro de atención.", 403)
    return Q(**{campo: centro_id})


def _activas(alcance, centro_id):
    return AdscripcionPaciente.objects.filter(
        _filtro_centro(alcance, centro_id, "centro_id"), estatus=AdscripcionPaciente.Estatus.ACTIVA,
    )


def _nombre_persona(nombre, paterno, materno):
    return " ".join(p for p in (paterno, materno, nombre) if p)


def _medicos_por_consultorio(consultorio_ids):
    medicos = {}
    relaciones = (
        medicos_activos().filter(consultorio_id__in=consultorio_ids)
        .select_related("medico__id_usuario__detalle").order_by("id")
    )
    for rel in relaciones:
        detalle = getattr(rel.medico.id_usuario, "detalle", None)
        nombre = " ".join(p for p in (detalle.nombre, detalle.paterno, detalle.materno) if p) if detalle else ""
        lista = medicos.setdefault(rel.consultorio_id, [])
        if nombre and nombre not in lista:
            lista.append(nombre)
    return medicos


def resumen_adscripcion(*, alcance: AlcanceCentros, centro_id: int | None = None) -> dict:
    """Conteos por centro → consultorio → turno, con los consultorios familiares en cero."""
    conteos = {
        fila["consultorio_id"]: fila
        for fila in _activas(alcance, centro_id).values("consultorio_id").annotate(
            titulares=Count("id", filter=_ES_TITULAR), total=Count("id"),
        )
    }
    config = AdscripcionConsultorio.objects.select_related(
        "consultorio__id_center", "consultorio__id_turn",
    ).filter(_filtro_centro(alcance, centro_id, "consultorio__id_center_id"))
    configurados = {c.consultorio_id: c for c in config}

    # Un consultorio con adscritos que ya no está configurado igual se muestra.
    faltantes = set(conteos) - set(configurados)
    consultorios = {c.consultorio_id: c.consultorio for c in configurados.values()}
    if faltantes:
        for c in Consultorios.objects.select_related("id_center", "id_turn").filter(pk__in=faltantes):
            consultorios[c.pk] = c
    medicos = _medicos_por_consultorio(list(consultorios))

    centros = {}
    for consultorio_id, consultorio in consultorios.items():
        fila = conteos.get(consultorio_id, {"titulares": 0, "total": 0})
        cfg = configurados.get(consultorio_id)
        centro = centros.setdefault(consultorio.id_center_id, {
            "idCentroAtencion": consultorio.id_center_id,
            "centro": consultorio.id_center.name,
            "titulares": 0, "familiares": 0, "total": 0,
            "consultorios": [],
        })
        familiares = fila["total"] - fila["titulares"]
        centro["titulares"] += fila["titulares"]
        centro["familiares"] += familiares
        centro["total"] += fila["total"]
        centro["consultorios"].append({
            "consultorioId": consultorio_id,
            "consultorio": consultorio.name,
            "numero": consultorio.numero,
            "turnoId": consultorio.id_turn_id,
            "turno": consultorio.id_turn.name,
            "titulares": fila["titulares"],
            "familiares": familiares,
            "total": fila["total"],
            "capacidadMaxima": cfg.capacidad_maxima if cfg else None,
            "estaActivo": bool(cfg and cfg.esta_activo),
            "medicos": medicos.get(consultorio_id, []),
        })

    ordenados = sorted(centros.values(), key=lambda c: c["centro"])
    for centro in ordenados:
        centro["consultorios"].sort(key=lambda c: (c["numero"] or 0, c["consultorioId"]))
    return {
        "centros": ordenados,
        "totales": {
            "titulares": sum(c["titulares"] for c in ordenados),
            "familiares": sum(c["familiares"] for c in ordenados),
            "total": sum(c["total"] for c in ordenados),
        },
    }


def _adscrito(a):
    p = a.paciente
    return {
        "idAdscripcion": a.id,
        "idPaciente": p.pk,
        "noExp": p.no_exp,
        "nombre": _nombre_persona(p.first_name, p.paternal_surname, p.maternal_surname),
        "tipo": TITULAR if p.pk_num == 0 else FAMILIAR,
        "idCentroAtencion": a.centro_id,
        "centro": a.centro.name,
        "consultorioId": a.consultorio_id,
        "consultorio": a.consultorio.name,
        "numeroConsultorio": a.consultorio.numero,
        "turnoId": a.turno_id,
        "turno": a.turno.name,
        "origen": a.origen,
        "fechaInicio": a.fecha_inicio.isoformat(),
    }


def _consulta_adscritos(alcance: AlcanceCentros, filtros: FiltrosAdscritos):
    """Adscritos activos con los filtros de pantalla (los mismos para listar y exportar)."""
    qs = _activas(alcance, filtros.centro_id).select_related("paciente", "centro", "consultorio", "turno")
    if filtros.consultorio_id:
        qs = qs.filter(consultorio_id=filtros.consultorio_id)
    if filtros.turno_id:
        qs = qs.filter(turno_id=filtros.turno_id)
    if filtros.tipo == TITULAR:
        qs = qs.filter(_ES_TITULAR)
    elif filtros.tipo == FAMILIAR:
        qs = qs.exclude(_ES_TITULAR)
    texto = (filtros.q or "").strip()
    if texto:
        qs = qs.filter(
            Q(paciente__no_exp__icontains=texto)
            | Q(paciente__first_name__icontains=texto)
            | Q(paciente__paternal_surname__icontains=texto)
            | Q(paciente__maternal_surname__icontains=texto)
        )
    return qs.order_by(
        "centro__name", "consultorio__numero", "paciente__paternal_surname",
        "paciente__maternal_surname", "paciente__first_name", "id",
    )


def _auditar_lectura(request, operador, alcance, filtros, accion, total, **extra):
    _auditar(
        request, operador, accion, "SUCCESS",
        meta={
            "filtros": {
                "centroId": filtros.centro_id,
                "todosLosCentros": alcance.todos,
                "centrosDelAlcance": sorted(alcance.centros),
                "consultorioId": filtros.consultorio_id,
                "turnoId": filtros.turno_id,
                "tipo": filtros.tipo,
                "q": (filtros.q or "").strip() or None,
            },
            "total": total,
            **extra,
        },
    )


def listar_adscritos(
    *, operador: Operador, alcance: AlcanceCentros, filtros: FiltrosAdscritos, page: int, page_size: int, request,
) -> dict:
    """Detalle paginado de adscritos activos. Audita quién consultó y con qué filtros."""
    qs = _consulta_adscritos(alcance, filtros)
    total = qs.count()
    total_pages = (total + page_size - 1) // page_size
    inicio = (page - 1) * page_size
    items = [_adscrito(a) for a in qs[inicio:inicio + page_size]]

    _auditar_lectura(
        request, operador, alcance, filtros, "ADSCRIPCION_REPORTE_LISTAR", total, page=page, pageSize=page_size,
    )
    return {"items": items, "page": page, "pageSize": page_size, "total": total, "totalPages": total_pages}


def exportar_adscritos(*, operador: Operador, alcance: AlcanceCentros, filtros: FiltrosAdscritos, request) -> bytes:
    """Excel con el resumen y TODOS los adscritos que cumplen los filtros (sin paginar). Se audita."""
    items = [_adscrito(a) for a in _consulta_adscritos(alcance, filtros)]
    resumen = [
        {**cons, "centro": centro["centro"]}
        for centro in resumen_adscripcion(alcance=alcance, centro_id=filtros.centro_id)["centros"]
        for cons in centro["consultorios"]
        if (not filtros.consultorio_id or cons["consultorioId"] == filtros.consultorio_id)
        and (not filtros.turno_id or cons["turnoId"] == filtros.turno_id)
    ]
    contenido = construir_libro_adscripcion(resumen, items)
    _auditar_lectura(request, operador, alcance, filtros, "ADSCRIPCION_REPORTE_EXPORTAR", len(items))
    return contenido
