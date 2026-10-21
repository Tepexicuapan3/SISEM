"""
Caso de uso: Actualizar / sincronizar un expediente desde Oracle → PostgreSQL.

Orquesta la sincronización de las 6 tablas relacionadas con un expediente,
equivalente al endpoint ``expediente_accion`` → acción ``actualizar`` del Flask original.

Controles (change auditoria-sync-expedientes, nivel expediente clínico):
  - Bitácora: ``bitacora_sync_expediente`` registra quién, desde dónde,
    cuándo y con qué resultado; ``bitacora_replica_sermed`` el antes/después
    de cada fila de la réplica. Sin bitácora no se escribe nada.
  - Candado: dos actualizaciones del mismo expediente no corren a la vez.
  - Todo o nada: las 6 tablas en una sola transacción de la réplica.
  - Resultado explícito: OK, PARCIAL (réplica al día, pacientes de SIRES
    no), ERROR (no se aplicó nada) u OCUPADO.
"""

import logging

from django.db import transaction

from apps.administracion.models import BitacoraSyncExpediente
from apps.administracion.services import sync_audit_service

from ...services.sync_service import candado_expediente, obtener_conexion_oracle, sincronizar_tabla

logger = logging.getLogger(__name__)

Resultado = BitacoraSyncExpediente.Resultado
Origen = BitacoraSyncExpediente.Origen

# Tablas que se sincronizan y sus metadatos.
# Formato: tabla → (llaves_primarias, columna_fecha_actualizacion, columna_no_expediente)
# Nota: nombres en minúsculas para compatibilidad con PostgreSQL (case-sensitive con comillas)
TABLAS_SYNC: dict[str, tuple[list[str], str, str]] = {
    "cat_empleados":         (["no_exp"],                       "fec_ult_actualizacion", "no_exp"),
    "cat_empleados_sis":     (["no_exp"],                       "fec_ult_actualizacion", "no_exp"),
    "cat_familiar":          (["pk_num"],                       "fec_ult_actualizacion", "no_expf"),
    "cat_familiar2":         (["pk_num"],                       "fec_ult_actualizacion", "no_expf"),
    "dnt_licencias_medicas": (["no_folio"],                     "fec_ult_actualizacion", "no_exp"),
    "dnt_fotos_credenciales":(["id_empleado", "id_clave_foto"], "fec_actualizacion",     "id_empleado"),
}


def _transaccion_replica():
    """Una transacción en la conexión de la réplica (en tests no existe: se reemplaza)."""
    return transaction.atomic(using="expedientes")


def _sincronizar_replica(expediente: str, registro, resultado: dict) -> bool:
    """Oracle → réplica en una sola transacción. True si se confirmó."""
    cambios: list = []
    oracle_conn = None
    try:
        oracle_conn = obtener_conexion_oracle()
        logger.info("Conexión Oracle establecida para expediente %s", expediente)

        with _transaccion_replica():
            for tabla, (llaves, fec_act, no_exp) in TABLAS_SYNC.items():
                try:
                    resultado["tablas"][tabla] = sincronizar_tabla(
                        oracle_conn=oracle_conn,
                        tabla=tabla,
                        llaves_primarias=llaves,
                        fec_actualizacion=fec_act,
                        no_exp=no_exp,
                        expediente=expediente,
                        cambios=cambios,
                    )
                except Exception as exc:
                    raise RuntimeError(f"Error en tabla {tabla}: {exc}") from exc
            # Antes de confirmar la réplica: si la bitácora no se puede
            # guardar, la excepción revierte las 6 tablas.
            resultado["cambios_registrados"] = sync_audit_service.registrar_cambios_replica(
                registro, cambios,
            )
        return True
    except Exception as exc:
        msg = f"{exc} (no se aplicó ningún cambio en la réplica)"
        logger.error("Expediente %s: %s", expediente, msg)
        resultado["errores"].append(msg)
        resultado["tablas"] = {tabla: {} for tabla in TABLAS_SYNC}
        return False
    finally:
        if oracle_conn:
            try:
                oracle_conn.close()
                logger.info("Conexión Oracle cerrada.")
            except Exception:
                pass


def _sincronizar_pacientes(expediente: str, usuario, resultado: dict) -> bool:
    """
    Historia clinica unificada 5.1, paso 6: con la replica al dia, los
    pacientes de SIRES de este expediente toman nombre, fecha de nacimiento,
    sexo y CURP de SERMED. Cada paciente se aplica en su propia transaccion.
    """
    try:
        from apps.consulta_medica.services.change_log_service import PROCESS_SERMED_SYNC
        from apps.consulta_medica.services.sermed_sync_service import sync_no_exp

        sync = sync_no_exp(expediente, user=usuario or PROCESS_SERMED_SYNC)
        resultado["pacientes"] = sync.counts
        return True
    except Exception as exc:
        msg = f"Error al sincronizar pacientes con SERMED: {exc}"
        logger.error(msg)
        resultado["errores"].append(msg)
        return False


def actualizar_expediente(
    expediente: str,
    *,
    usuario=None,
    origen: str = Origen.COMANDO,
    request=None,
) -> dict:
    """
    Sincroniza todas las tablas de un expediente desde Oracle a PostgreSQL
    y después sus pacientes de SIRES.

    Args:
        expediente: Número de expediente a sincronizar.
        usuario: SyUsuario que la pidió (None para comandos y tareas).
        origen: BOTON, COMANDO o AUTOMATICO.
        request: request HTTP, para IP, user agent y request id.

    Returns:
        Dict::

            {
              "estado": "OK" | "PARCIAL" | "ERROR" | "OCUPADO",
              "id_sync": 123,
              "tablas": {"cat_empleados": {"insertados": 0, "eliminados": 0, "actualizados": 1}, ...},
              "cambios_registrados": 1,
              "pacientes": {"procesados": 2, ...},
              "errores": []
            }
    """
    expediente = str(expediente).strip()
    # Sin bitácora no hay actualización: si esto falla, la excepción sube.
    registro = sync_audit_service.abrir(expediente, origen=origen, usuario=usuario, request=request)

    resultado: dict = {
        "estado": Resultado.EN_CURSO,
        "id_sync": registro.pk,
        "tablas": {tabla: {} for tabla in TABLAS_SYNC},
        "errores": [],
    }

    try:
        with candado_expediente(expediente) as adquirido:
            if not adquirido:
                resultado["errores"].append(
                    f"El expediente {expediente} ya se está actualizando en otra sesión. "
                    "Espera a que termine y vuelve a intentar."
                )
                estado = Resultado.OCUPADO
            elif not _sincronizar_replica(expediente, registro, resultado):
                estado = Resultado.ERROR
            elif not _sincronizar_pacientes(expediente, usuario, resultado):
                estado = Resultado.PARCIAL
            else:
                estado = Resultado.OK
    except Exception as exc:
        # Falla inesperada (p. ej. el candado): queda registrada igual.
        logger.exception("Falla inesperada al actualizar el expediente %s", expediente)
        resultado["errores"].append(f"Falla inesperada: {exc}")
        estado = Resultado.ERROR

    resultado["estado"] = estado
    conteos = {"tablas": resultado["tablas"]}
    for clave in ("cambios_registrados", "pacientes"):
        if clave in resultado:
            conteos[clave] = resultado[clave]
    sync_audit_service.cerrar(registro, resultado=estado, conteos=conteos, errores=resultado["errores"])
    return resultado
