"""
Puente hacia el legado (diseño del 2026-10-27): el historial del sistema
anterior se busca por los identificadores del paciente. El titular ya tiene
NO_EXP; el familiar de SERMED necesita su CD_FAMILIAR del legado, que se
traduce UNA vez con el cat_familiar de la copia actual (titular + PK_NUM ->
cd_familiar) y queda registrado en cns_identificador_paciente.

Nunca se adivina: si el PK_NUM esta repetido en el legado, si dos cd_familiar
del mismo titular dan el mismo PK_NUM o si el cd_familiar ya es de otro
paciente, no se registra y se informa para revisarlo.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from apps.consulta_medica.models import ChangeLog, Patient, PatientIdentifier
from apps.consulta_medica.services import legado_archivo
from apps.consulta_medica.services.change_log_service import PROCESS_SIRES
from apps.consulta_medica.services.legacy_family_map import _int_or_none
from apps.consulta_medica.services.patient_identifier_service import IdentifierConflict, register_identifier
from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp

logger = logging.getLogger(__name__)

REGISTRADO = "REGISTRADO"
YA_TENIA = "YA_TENIA"
NO_APLICA = "NO_APLICA"
SIN_LEGADO = "SIN_LEGADO"
AMBIGUO = "AMBIGUO"
CONFLICTO = "CONFLICTO"


@dataclass
class MapaPuente:
    """(titular normalizado, PK_NUM) -> cd_familiar, solo donde no hay duda."""
    cd_por_llave: dict[tuple[str, int], int] = field(default_factory=dict)
    ambiguas: set[tuple[str, int]] = field(default_factory=set)

    @classmethod
    def desde_filas(cls, filas) -> "MapaPuente":
        """``filas``: dicts con cd_familiar, no_expf y pk_num (cat_familiar del legado)."""
        cds_por_llave: dict[tuple[str, int], set[int]] = defaultdict(set)
        for fila in filas:
            cd, pk = _int_or_none(fila.get("cd_familiar")), _int_or_none(fila.get("pk_num"))
            titular = fila.get("no_expf")
            # pk_num NULL o 0: ese familiar no tiene PK_NUM; no hay a quien unirlo.
            if cd is None or not pk or titular is None:
                continue
            cds_por_llave[(normalizar_no_exp(titular), pk)].add(cd)
        mapa = cls()
        for llave, cds in cds_por_llave.items():
            if len(cds) == 1:
                mapa.cd_por_llave[llave] = next(iter(cds))
            else:
                mapa.ambiguas.add(llave)
        return mapa

    def resolver(self, no_exp, pk_num) -> tuple[int | None, str]:
        llave = (normalizar_no_exp(no_exp), pk_num)
        if llave in self.ambiguas:
            return None, AMBIGUO
        cd = self.cd_por_llave.get(llave)
        return (cd, REGISTRADO) if cd is not None else (None, SIN_LEGADO)


def cargar_mapa(no_exp=None) -> MapaPuente:
    """cat_familiar de la copia actual; con no_exp, solo los de ese titular."""
    tabla = legado_archivo.tabla(legado_archivo.ESQUEMA_ACTUAL, "cat_familiar")
    sql = f"SELECT cd_familiar, no_expf, pk_num FROM {tabla}"
    if no_exp is None:
        return MapaPuente.desde_filas(legado_archivo.consultar(sql))
    # El titular puede venir con ceros a la izquierda en el legado: se filtra por
    # valor numerico y se normaliza al armar el mapa.
    filas = legado_archivo.consultar(
        sql + f" WHERE {legado_archivo.sin_ceros('no_expf')} = %s", [normalizar_no_exp(no_exp)],
    )
    return MapaPuente.desde_filas(filas)


def _necesita_puente(patient: Patient) -> bool:
    """Solo familiares de SERMED (pk_num > 0). El titular ya tiene NO_EXP y el
    provisional de SIRES no existe en el legado."""
    return bool(patient.pk_num) and patient.pk_num > 0


def registrar_cd_familiar(patient: Patient, mapa: MapaPuente | None = None, *, user=PROCESS_SIRES) -> str:
    """Registra el CD_FAMILIAR del legado de un familiar. Devuelve el resultado."""
    if not _necesita_puente(patient):
        return NO_APLICA
    if PatientIdentifier.objects.filter(
        patient=patient, id_type=PatientIdentifier.IdType.CD_FAMILIAR, status=PatientIdentifier.Status.ACTIVE,
    ).exists():
        return YA_TENIA
    if mapa is None:
        mapa = cargar_mapa(patient.no_exp)
    cd, resultado = mapa.resolver(patient.no_exp, patient.pk_num)
    if cd is None:
        return resultado
    try:
        register_identifier(
            patient, PatientIdentifier.IdType.CD_FAMILIAR, cd,
            reason=ChangeLog.Reason.LEGACY_BRIDGE, user=user,
        )
    except IdentifierConflict as exc:
        logger.warning("cd_familiar %s del legado ya es de otro paciente (%s): %s", cd, patient.pk, exc)
        return CONFLICTO
    return REGISTRADO


def registrar_al_abrir(patient: Patient) -> None:
    """Al abrir un familiar en SIRES. Si la copia no esta o no responde, no
    frena la atencion: lo completa la recarga nocturna."""
    if not _necesita_puente(patient) or not legado_archivo.disponible():
        return
    try:
        registrar_cd_familiar(patient)
    except legado_archivo.LegadoNoDisponible:
        logger.info("Copia del legado no disponible: el puente de %s queda para la recarga", patient.pk)
