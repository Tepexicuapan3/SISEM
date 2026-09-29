-- ============================================================================
-- Plan de migracion de la historia clinica legacy -> SIRES
-- Documento "Historia Clinica Unificada", seccion 8.
--
-- TODAS las consultas son de SOLO LECTURA. Nada aqui modifica datos.
--   Parte A: MySQL legado (dbclinicas) -- limpieza previa, ANTES de migrar.
--   Parte B: Postgres SIRES -- revision DESPUES de cada ejecucion.
--
-- Orden de ejecucion recomendado (ventana de mantenimiento, con respaldo):
--   1. Parte A completa; resolver/aceptar lo que salga.
--   2. python manage.py migrate
--   3. python manage.py migrar_historial_clinico_legacy     --dry-run --operador <tu_usuario> ...
--   4. python manage.py migrar_historia_estomatologia_legacy --dry-run --operador <tu_usuario> ...
--   5. Los mismos dos comandos sin --dry-run.
--   6. Parte B: revisar bitacora y conflictos.
-- Los comandos son idempotentes (ref_origen): re-ejecutarlos no duplica.
--
-- Cifras de referencia medidas sobre Dump20260903.sql (2026-09-03):
--   his_clinica   3,385 filas, 0 pacientes duplicados, 0 codigos de catalogo huerfanos
--   his_clinicad 24,124 filas, 26 pacientes con mas de una historia (30 filas extra)
--   1,753 pacientes estan en ambas tablas; 389 difieren en ocupacion y
--   335 en estado civil -> quedaran en cns_conflicto_migracion.
-- ============================================================================


-- ════════════════════════════════════════════════════════════════════════════
-- PARTE A -- MySQL legado (dbclinicas)
-- ════════════════════════════════════════════════════════════════════════════

-- A1. Historias duplicadas por paciente (no_exp + tp_paciente).
--     El importador ya NO duplica antecedentes/habitos/quirurgicos (deduplica
--     por contenido); cada fila si conserva sus notas y su medicion de signos.
SELECT 'his_clinica' AS tabla, no_exp, tp_paciente, COUNT(*) AS historias,
       GROUP_CONCAT(no_hisclin ORDER BY fe_hisclin) AS folios
FROM his_clinica GROUP BY no_exp, tp_paciente HAVING COUNT(*) > 1
UNION ALL
SELECT 'his_clinicad', no_exp, tp_paciente, COUNT(*),
       GROUP_CONCAT(no_hisclin ORDER BY fe_hisclin)
FROM his_clinicad GROUP BY no_exp, tp_paciente HAVING COUNT(*) > 1
ORDER BY historias DESC;

-- A2. Filas sin expediente o con tipo de paciente no numerico (tp_paciente es
--     varchar en el legado; el comando omite esas filas, NULL cuenta como 0).
SELECT 'his_clinica' AS tabla, no_hisclin, no_exp, tp_paciente FROM his_clinica
WHERE no_exp IS NULL OR no_exp = 0 OR TRIM(tp_paciente) NOT REGEXP '^[0-9]+$'
UNION ALL
SELECT 'his_clinicad', no_hisclin, no_exp, tp_paciente FROM his_clinicad
WHERE no_exp IS NULL OR no_exp = 0 OR TRIM(tp_paciente) NOT REGEXP '^[0-9]+$';

-- A3. Codigos de catalogo sin descripcion en el legado (quedarian NULL).
SELECT 'his_clinica.cd_ocupacion' AS columna, a.cd_ocupacion AS codigo, COUNT(*) AS filas
FROM his_clinica a LEFT JOIN cat_ocupacion b ON a.cd_ocupacion = b.cd_ocupacion
WHERE a.cd_ocupacion IS NOT NULL AND a.cd_ocupacion <> 0 AND b.cd_ocupacion IS NULL GROUP BY a.cd_ocupacion
UNION ALL
SELECT 'his_clinica.cd_escolaridad', a.cd_escolaridad, COUNT(*)
FROM his_clinica a LEFT JOIN cat_escolaridad b ON a.cd_escolaridad = b.cd_escolaridad
WHERE a.cd_escolaridad IS NOT NULL AND a.cd_escolaridad <> 0 AND b.cd_escolaridad IS NULL GROUP BY a.cd_escolaridad
UNION ALL
SELECT 'his_clinica.cd_edocivil', a.cd_edocivil, COUNT(*)
FROM his_clinica a LEFT JOIN cat_edocivil b ON a.cd_edocivil = b.cd_edocivil
WHERE a.cd_edocivil IS NOT NULL AND a.cd_edocivil <> 0 AND b.cd_edocivil IS NULL GROUP BY a.cd_edocivil
UNION ALL
SELECT 'his_clinica.cd_religion', a.cd_religion, COUNT(*)
FROM his_clinica a LEFT JOIN cat_religion b ON a.cd_religion = b.cd_religion
WHERE a.cd_religion IS NOT NULL AND a.cd_religion <> 0 AND b.cd_religion IS NULL GROUP BY a.cd_religion
UNION ALL
SELECT 'his_clinica.cd_residencia', a.cd_residencia, COUNT(*)
FROM his_clinica a LEFT JOIN cat_residencia b ON a.cd_residencia = b.cd_residencia
WHERE a.cd_residencia IS NOT NULL AND a.cd_residencia <> 0 AND b.cd_residencia IS NULL GROUP BY a.cd_residencia
UNION ALL
SELECT 'his_clinicad.cd_ocupacion', a.cd_ocupacion, COUNT(*)
FROM his_clinicad a LEFT JOIN cat_ocupacion b ON a.cd_ocupacion = b.cd_ocupacion
WHERE a.cd_ocupacion IS NOT NULL AND a.cd_ocupacion <> 0 AND b.cd_ocupacion IS NULL GROUP BY a.cd_ocupacion
UNION ALL
SELECT 'his_clinicad.cd_edocivil', a.cd_edocivil, COUNT(*)
FROM his_clinicad a LEFT JOIN cat_edocivil b ON a.cd_edocivil = b.cd_edocivil
WHERE a.cd_edocivil IS NOT NULL AND a.cd_edocivil <> 0 AND b.cd_edocivil IS NULL GROUP BY a.cd_edocivil;

-- A4. Descripciones del legado que NO existen por nombre en los catalogos de
--     SISEM: las reporta el propio comando al final ("Sin match en catalogo
--     SISEM ..."). Correr el --dry-run y dar de alta/homologar antes del real.

-- A5. Vista previa de conflictos his_clinica vs his_clinicad (ocupacion y
--     estado civil). Regla que aplicara la migracion: gana el fe_hisclin mas
--     reciente; empate o sin fecha -> se conserva el primero; lo editado en
--     SIRES nunca se pisa. Todo queda en cns_conflicto_migracion.
SELECT g.no_exp, g.tp_paciente,
       g.fe_hisclin AS fecha_general, og.ds_ocupacion AS ocupacion_general, eg.ds_edocivil AS edocivil_general,
       d.fe_hisclin AS fecha_dental,  od.ds_ocupacion AS ocupacion_dental,  ed.ds_edocivil AS edocivil_dental,
       CASE WHEN d.fe_hisclin > g.fe_hisclin THEN 'dental' ELSE 'general' END AS ganaria
FROM his_clinica g
JOIN his_clinicad d ON d.no_exp = g.no_exp AND d.tp_paciente = g.tp_paciente
LEFT JOIN cat_ocupacion og ON og.cd_ocupacion = g.cd_ocupacion
LEFT JOIN cat_ocupacion od ON od.cd_ocupacion = d.cd_ocupacion
LEFT JOIN cat_edocivil  eg ON eg.cd_edocivil  = g.cd_edocivil
LEFT JOIN cat_edocivil  ed ON ed.cd_edocivil  = d.cd_edocivil
WHERE (g.cd_ocupacion <> 0 AND d.cd_ocupacion <> 0 AND g.cd_ocupacion <> d.cd_ocupacion)
   OR (g.cd_edocivil  <> 0 AND d.cd_edocivil  <> 0 AND g.cd_edocivil  <> d.cd_edocivil)
ORDER BY g.no_exp, g.tp_paciente;

-- A6. Signos vitales con relleno ("0", ".", "..") -- quedaran NULL en
--     cns_signos_vitales_legado (el texto original se conserva en
--     ds_texto_original). Solo informativo.
SELECT 'his_clinica' AS tabla,
       SUM(no_peso IN ('0', '.', '..')) AS peso_relleno,
       SUM(no_ta   IN ('0', '.', '..')) AS ta_relleno,
       SUM(no_ta NOT LIKE '%/%' AND no_ta <> '') AS ta_sin_diagonal
FROM his_clinica
UNION ALL
SELECT 'his_clinicad',
       SUM(no_peso IN ('0', '.', '..')), SUM(no_ta IN ('0', '.', '..')),
       SUM(no_ta NOT LIKE '%/%' AND no_ta <> '')
FROM his_clinicad;


-- ════════════════════════════════════════════════════════════════════════════
-- PARTE B -- Postgres SIRES (despues de cada ejecucion)
-- ════════════════════════════════════════════════════════════════════════════

-- B1. Bitacora de ejecucion: quien corrio que, cuando y como termino.
--     estatus: E en curso (si queda asi, el proceso murio sin cerrar), O terminada, F fallida.
SELECT id_ejecucion, comando, operador, equipo, sw_simulacion, estatus,
       filas_leidas, fch_inicio, fch_fin, resumen
FROM cns_bitacora_migracion
ORDER BY fch_inicio DESC;

-- B2. Conflictos por ejecucion y tipo de resolucion.
--     ganador: L legado mas reciente aplicado, P se conservo el legado previo,
--              S se conservo lo editado en SIRES.
SELECT c.id_ejecucion, c.campo, c.ganador, COUNT(*) AS conflictos
FROM cns_conflicto_migracion c
GROUP BY c.id_ejecucion, c.campo, c.ganador
ORDER BY c.id_ejecucion DESC, c.campo, c.ganador;

-- B3. Detalle para revision humana (ocupacion / estado civil con nombre).
SELECT c.no_exp, c.tp_paciente, c.campo, c.ganador, c.ref_origen, c.fe_origen,
       c.valor_conservado, c.valor_descartado,
       COALESCE(ok.ocupacion, ek.edocivil) AS conservado,
       COALESCE(od.ocupacion, ed.edocivil) AS descartado
FROM cns_conflicto_migracion c
LEFT JOIN cat_ocupaciones ok ON c.campo = 'occupation_id'     AND ok.id_ocupacion::text = c.valor_conservado
LEFT JOIN cat_ocupaciones od ON c.campo = 'occupation_id'     AND od.id_ocupacion::text = c.valor_descartado
LEFT JOIN cat_edocivil    ek ON c.campo = 'marital_status_id' AND ek.id_edocivil::text  = c.valor_conservado
LEFT JOIN cat_edocivil    ed ON c.campo = 'marital_status_id' AND ed.id_edocivil::text  = c.valor_descartado
ORDER BY c.no_exp, c.tp_paciente, c.campo;

-- B4. Signos vitales legado: cuantos valores quedaron NULL por no ser plausibles.
SELECT especialidad, COUNT(*) AS filas,
       COUNT(no_peso) AS con_peso, COUNT(no_talla) AS con_talla,
       COUNT(no_ta_sistolica) AS con_ta, COUNT(no_imc) AS con_imc
FROM cns_signos_vitales_legado
GROUP BY especialidad;
