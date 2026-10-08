-- ============================================================================
-- Verificacion de la identidad del paciente (Historia Clinica Unificada, 5.1)
-- Base PRINCIPAL de SIRES (conexion "default"). SOLO LECTURA: puros SELECT.
--
-- Uso (en el servidor TEST, desde /srv/apps/SIRES):
--   set -a; . ./.env; set +a
--   docker exec -i sisem_postgres psql -U "$AUTH_DB_USER" -d "$AUTH_DB_NAME" \
--     -f - < docs/runbooks/verificacion-identidad-5-1.sql > verificacion_ANTES.txt
-- Correrlo ANTES de cada comando y DESPUES, y comparar los archivos.
-- ============================================================================

SET search_path TO sires, public;
\pset footer off

\echo '== 1. Migraciones aplicadas (deben llegar a 0045) =='
SELECT app, name FROM django_migrations
WHERE (app = 'consulta_medica' AND name >= '0041') OR (app = 'administracion' AND name >= '0011')
ORDER BY app, name;

\echo '== 2. Totales por tabla (la correccion del paso 5 NO debe cambiarlos) =='
SELECT 'cns_paciente' AS tabla, COUNT(*) AS filas FROM cns_paciente
UNION ALL SELECT 'cns_clinical_history', COUNT(*) FROM cns_clinical_history
UNION ALL SELECT 'cns_stomatology_history', COUNT(*) FROM cns_stomatology_history
UNION ALL SELECT 'cns_allergy', COUNT(*) FROM cns_allergy
UNION ALL SELECT 'cns_legacy_consultation_record', COUNT(*) FROM cns_legacy_consultation_record
UNION ALL SELECT 'cns_antecedente_personal', COUNT(*) FROM cns_antecedente_personal
UNION ALL SELECT 'cns_antecedente_familiar', COUNT(*) FROM cns_antecedente_familiar
UNION ALL SELECT 'cns_antecedente_quirurgico', COUNT(*) FROM cns_antecedente_quirurgico
UNION ALL SELECT 'cns_habito', COUNT(*) FROM cns_habito
UNION ALL SELECT 'cns_tratamiento_dental', COUNT(*) FROM cns_tratamiento_dental
UNION ALL SELECT 'cns_nota_historica', COUNT(*) FROM cns_nota_historica
UNION ALL SELECT 'cns_signos_vitales_legado', COUNT(*) FROM cns_signos_vitales_legado
UNION ALL SELECT 'cns_odontograma', COUNT(*) FROM cns_odontograma
UNION ALL SELECT 'cns_medical_leave', COUNT(*) FROM cns_medical_leave
UNION ALL SELECT 'cns_study_result', COUNT(*) FROM cns_study_result
ORDER BY 1;

\echo '== 3. Pacientes: titulares, familiares, sin PK_NUM, uuid =='
SELECT
  COUNT(*)                                         AS pacientes,
  COUNT(*) FILTER (WHERE pk_num = 0)               AS titulares,
  COUNT(*) FILTER (WHERE pk_num > 0)               AS familiares_con_pk_num,
  COUNT(*) FILTER (WHERE pk_num IS NULL)           AS familiares_solo_cd_familiar,
  COUNT(cd_familiar)                               AS con_cd_familiar,
  COUNT(DISTINCT uuid)                             AS uuid_distintos,   -- debe ser = pacientes
  COUNT(curp)                                      AS con_curp,
  COUNT(*) FILTER (WHERE curp_origen = 'O')        AS curp_de_sermed,
  COUNT(*) FILTER (WHERE curp_origen = 'C')        AS curp_capturada
FROM cns_paciente;

\echo '== 4. Identificadores vigentes por tipo =='
SELECT tp_identificador, sw_status, COUNT(*) FROM cns_identificador_paciente
GROUP BY 1, 2 ORDER BY 1, 2;

\echo '== 5. Titulares sin identificador NO_EXP (despues del paso 4 debe dar 0) =='
SELECT COUNT(*) AS titulares_sin_no_exp
FROM cns_paciente p
WHERE p.pk_num = 0
  AND NOT EXISTS (
    SELECT 1 FROM cns_identificador_paciente i
    WHERE i.id_paciente = p.id_paciente AND i.tp_identificador = 'NO_EXP' AND i.sw_status = 'A'
  );

\echo '== 6. Filas SIN id_paciente por tabla (paso 7: tabla en 0 = lista para NOT NULL) =='
SELECT 'cns_allergy' AS tabla, COUNT(*) AS sin_paciente FROM cns_allergy WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_legacy_consultation_record', COUNT(*) FROM cns_legacy_consultation_record WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_antecedente_personal', COUNT(*) FROM cns_antecedente_personal WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_antecedente_familiar', COUNT(*) FROM cns_antecedente_familiar WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_antecedente_quirurgico', COUNT(*) FROM cns_antecedente_quirurgico WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_habito', COUNT(*) FROM cns_habito WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_tratamiento_dental', COUNT(*) FROM cns_tratamiento_dental WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_nota_historica', COUNT(*) FROM cns_nota_historica WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_signos_vitales_legado', COUNT(*) FROM cns_signos_vitales_legado WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_odontograma', COUNT(*) FROM cns_odontograma WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_stomatology_history', COUNT(*) FROM cns_stomatology_history WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_medical_leave', COUNT(*) FROM cns_medical_leave WHERE id_paciente IS NULL
UNION ALL SELECT 'cns_study_result', COUNT(*) FROM cns_study_result WHERE id_paciente IS NULL
ORDER BY 2 DESC, 1;

\echo '== 7. Coherencia: filas vinculadas a un paciente con OTRA llave (debe dar 0 antes de fusiones) =='
SELECT 'cns_allergy' AS tabla, COUNT(*) AS llave_distinta
FROM cns_allergy t JOIN cns_paciente p ON p.id_paciente = t.id_paciente
WHERE t.no_exp <> p.no_exp OR (p.pk_num IS NOT NULL AND t.pk_num <> p.pk_num)
   OR (p.pk_num IS NULL AND t.pk_num <> p.cd_familiar)
UNION ALL
SELECT 'cns_legacy_consultation_record', COUNT(*)
FROM cns_legacy_consultation_record t JOIN cns_paciente p ON p.id_paciente = t.id_paciente
WHERE t.no_exp <> p.no_exp OR (p.pk_num IS NOT NULL AND t.pk_num <> p.pk_num)
   OR (p.pk_num IS NULL AND t.pk_num <> p.cd_familiar);

\echo '== 8. CURP repetidas en cns_paciente (candidatos a fusion) =='
SELECT COUNT(*) AS curp_repetidas FROM (
  SELECT curp FROM cns_paciente WHERE curp IS NOT NULL GROUP BY curp HAVING COUNT(*) > 1
) x;

\echo '== 9. Bitacora de cambios por motivo =='
SELECT motivo, accion, COUNT(*) FROM cns_bitacora_cambios GROUP BY 1, 2 ORDER BY 1, 2;

\echo '== 10. Ultimas ejecuciones de comandos (cns_bitacora_migracion) =='
SELECT id_ejecucion, comando, sw_simulacion, estatus, fch_inicio, LEFT(resumen, 200) AS resumen
FROM cns_bitacora_migracion ORDER BY id_ejecucion DESC LIMIT 10;

\echo '== 11. Sincronizacion con SERMED (paso 6) =='
SELECT
  COUNT(*)                                          AS pacientes,
  COUNT(ds_nombre)                                  AS con_nombre_de_sermed,
  COUNT(fe_nacimiento)                              AS con_fecha_nacimiento,
  COUNT(*) FILTER (WHERE curp_origen = 'O')         AS curp_de_sermed,
  (SELECT COUNT(*) FROM cns_paciente_sermed)        AS con_estado_sermed,
  (SELECT COUNT(*) FROM cns_paciente_sermed WHERE NOT sw_en_sermed) AS ya_no_estan_en_sermed
FROM cns_paciente;
