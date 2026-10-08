"""
Caso de uso: Actualizar / sincronizar un expediente desde Oracle → PostgreSQL.

Orquesta la sincronización de las 6 tablas relacionadas con un expediente,
equivalente al endpoint ``expediente_accion`` → acción ``actualizar`` del Flask original.
"""

import logging

from ...services.sync_service import sincronizar_tabla, obtener_conexion_oracle

logger = logging.getLogger(__name__)

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


def actualizar_expediente(expediente: str) -> dict:
    """
    Sincroniza todas las tablas de un expediente desde Oracle a PostgreSQL.

    Args:
        expediente: Número de expediente a sincronizar.

    Returns:
        Dict con resultado por tabla::

            {
              "cat_empleados": {"insertados": 0, "eliminados": 0, "actualizados": 1},
              ...
              "errores": []
            }
    """
    resultado: dict = {tabla: {} for tabla in TABLAS_SYNC}
    resultado['errores'] = []
    oracle_conn = None

    try:
        oracle_conn = obtener_conexion_oracle()
        logger.info("Conexión Oracle establecida para expediente %s", expediente)

        for tabla, (llaves, fec_act, no_exp) in TABLAS_SYNC.items():
            try:
                conteos = sincronizar_tabla(
                    oracle_conn=oracle_conn,
                    tabla=tabla,
                    llaves_primarias=llaves,
                    fec_actualizacion=fec_act,
                    no_exp=no_exp,
                    expediente=expediente,
                )
                resultado[tabla] = conteos
            except Exception as exc:
                msg = f"Error en tabla {tabla}: {exc}"
                logger.error(msg)
                resultado['errores'].append(msg)

    except Exception as exc:
        msg = f"Error al conectar con Oracle: {exc}"
        logger.error(msg)
        resultado['errores'].append(msg)

    finally:
        if oracle_conn:
            try:
                oracle_conn.close()
                logger.info("Conexión Oracle cerrada.")
            except Exception:
                pass

    # Historia clinica unificada 5.1, paso 6: con la replica al dia, los
    # pacientes de SIRES de este expediente toman nombre, fecha de nacimiento,
    # sexo y CURP de SERMED. Un error aqui no invalida la actualizacion.
    try:
        from apps.consulta_medica.services.sermed_sync_service import sync_no_exp

        sync = sync_no_exp(expediente)
        resultado['pacientes'] = sync.counts
    except Exception as exc:
        msg = f"Error al sincronizar pacientes con SERMED: {exc}"
        logger.error(msg)
        resultado['errores'].append(msg)

    return resultado
