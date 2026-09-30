-- =============================================================================
-- Limpieza de objetos HUERFANOS en las bases Postgres de SIRES (2026-09-28)
-- =============================================================================
-- Generado a partir del codigo (modelos Django + TABLAS_SYNC): la lista de
-- tablas de abajo es EXACTAMENTE lo que SIRES usa. Todo lo demas que aparezca
-- en la PARTE A no lo lee ni lo escribe ningun codigo.
--
-- ORDEN:
--   0. Aplicar primero `python manage.py migrate` (consulta_medica.0030 ya
--      elimina cns_odontogram_tooth y las columnas viejas de la historia
--      clinica; NO borrarlas a mano).
--   1. Correr la PARTE A (solo SELECT, no modifica nada) y revisar.
--   2. RESPALDO COMPLETO.
--   3. Descomentar en la PARTE B solo lo que la PARTE A confirmo.
-- =============================================================================

-- #############################################################################
-- BASE PRINCIPAL DE SIRES (DATABASES["default"], schemas sires/public)
-- #############################################################################

-- A1. Tablas que existen en la base pero NINGUN modelo de SIRES usa.
SELECT t.table_schema, t.table_name,
       (xpath('/row/c/text()', query_to_xml(
           format('SELECT count(*) AS c FROM %I.%I', t.table_schema, t.table_name),
           false, true, '')))[1]::text::bigint AS filas
FROM information_schema.tables t
WHERE t.table_schema IN ('sires', 'public')
  AND t.table_type = 'BASE TABLE'
  AND t.table_name NOT IN (
    'almacen_almacenes',
    'almacen_cat_categorias_insumo',
    'almacen_cat_insumos',
    'almacen_cat_proveedores',
    'almacen_cat_unidades_medida',
    'almacen_consumos_consulta',
    'almacen_consumos_consulta_det',
    'almacen_conteos_fisicos',
    'almacen_conteos_fisicos_det',
    'almacen_entradas_inventario',
    'almacen_entradas_inventario_det',
    'almacen_existencias',
    'almacen_kardex_movimientos',
    'almacen_lotes_insumo',
    'almacen_medicamento_insumo',
    'almacen_salidas_inventario',
    'almacen_salidas_inventario_det',
    'amb_request',
    'amb_request_schedule',
    'auditoria_eventos',
    'auth_group',
    'auth_group_permissions',
    'auth_permission',
    'auth_user',
    'auth_user_groups',
    'auth_user_user_permissions',
    'bitacora_acceso',
    'cat_areas',
    'cat_areas_clinicas',
    'cat_autorizadores',
    'cat_bajas',
    'cat_calidadlab',
    'cat_centros_atencion',
    'cat_centros_atencion_excepciones',
    'cat_centros_atencion_horarios',
    'cat_cie9_mc',
    'cat_cies',
    'cat_clasificacion_cirugia',
    'cat_consultorios',
    'cat_destino_ambulancia',
    'cat_discapacidades',
    'cat_edocivil',
    'cat_enfermedades',
    'cat_escolaridad',
    'cat_escuelas',
    'cat_especialidades',
    'cat_estado_pieza',
    'cat_estudiosmed',
    'cat_gpomedic',
    'cat_habito',
    'cat_medicamentos',
    'cat_medicos',
    'cat_modulos',
    'cat_motivo_cancelacion_cirugia',
    'cat_motivo_traslado',
    'cat_motivos_cita',
    'cat_ocupaciones',
    'cat_origencons',
    'cat_parentescos',
    'cat_pases',
    'cat_perfil_acceso_sensible',
    'cat_permisos',
    'cat_pieza_dental',
    'cat_rango_cie_sensible',
    'cat_region_corporal',
    'cat_religion',
    'cat_residencia',
    'cat_roles',
    'cat_sucursales',
    'cat_tipo_alergia',
    'cat_tipo_alta',
    'cat_tipo_cirugia',
    'cat_tipo_hospitalizacion',
    'cat_tipo_personal',
    'cat_tipo_servicio_ambulancia',
    'cat_tipo_traslado',
    'cat_tpareas',
    'cat_tpautorizacion',
    'cat_tpcitas',
    'cat_tpconsulta',
    'cat_tplicencia',
    'cat_tpsanguineo',
    'cat_turnos',
    'cat_vacunas',
    'centro_area_clinica',
    'cir_surgery',
    'cir_surgery_cancellation',
    'cir_surgery_diagnosis',
    'citas_estatus_log',
    'citas_horarios_disponibles',
    'citas_medicas',
    'citas_notificaciones',
    'cns_allergy',
    'cns_allergy_revision',
    'cns_antecedente_familiar',
    'cns_antecedente_personal',
    'cns_antecedente_quirurgico',
    'cns_bitacora_migracion',
    'cns_clinical_history',
    'cns_conflicto_migracion',
    'cns_consultation_addendum',
    'cns_exploracion_fisica',
    'cns_habito',
    'cns_legacy_consultation_diagnosis',
    'cns_legacy_consultation_record',
    'cns_medical_leave',
    'cns_nota_historica',
    'cns_odontograma',
    'cns_odontograma_pieza',
    'cns_paciente',
    'cns_paciente_origen_legado',
    'cns_paciente_revision',
    'cns_prescription_authorization',
    'cns_signos_vitales_legado',
    'cns_stomatology_history',
    'cns_stomatology_history_revision',
    'cns_study_result',
    'cns_tratamiento_dental',
    'cns_visit_consultation',
    'cns_visit_consultation_revision',
    'cns_visit_diagnosis',
    'cns_visit_prescription',
    'cns_visit_prescription_item',
    'com_anuncios',
    'contratos_oxigeno',
    'det_usuario_administrativo',
    'det_usuario_cedulas',
    'det_usuario_enfermeria',
    'det_usuario_medico',
    'det_usuarios',
    'django_admin_log',
    'django_content_type',
    'django_migrations',
    'django_session',
    'hsp_admission',
    'hsp_admission_revision',
    'portal_miembros',
    'portal_otps',
    'portal_sesiones',
    'rcp_turno_ficha_config',
    'rcp_visit_status_log',
    'rcp_visits',
    'ref_referral',
    'ref_referral_study',
    'rel_medico_centro',
    'rel_medico_cobertura',
    'rel_medico_cobertura_horario',
    'rel_medico_consultorio',
    'rel_medico_consultorio_horario',
    'rel_medico_especialidad',
    'rel_medico_excepcion',
    'rel_modulo_permisos',
    'rel_rol_permisos',
    'rel_usuario_overrides',
    'rel_usuario_roles',
    'rt_realtime_sequences',
    'smt_patient_latest_vitals',
    'smt_visit_vitals',
    'solicitudes_arco',
    'sy_sesiones_usuario',
    'sy_usuarios',
    'vac_inventario'
  )
ORDER BY filas DESC, t.table_name;

-- A2. Verificacion post-migrate: estas columnas/tablas ya NO deben existir
--     (las elimina consulta_medica.0030). Si aparecen, el migrate no corrio.
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema IN ('sires', 'public')
  AND (
    (table_name = 'cns_clinical_history' AND column_name IN (
        'antecedentes','padecimiento_actual','organos_aparatos_sistemas',
        'exploracion_cabeza','exploracion_cuello','exploracion_torax',
        'exploracion_abdomen','exploracion_genitales','exploracion_miembros',
        'manejo_diagnostico','manejo_terapeutico','alergias'))
    OR (table_name = 'cns_stomatology_history' AND column_name LIKE 'alergia_%')
    OR table_name = 'cns_odontogram_tooth'
    -- consulta_medica.0033: la ficha del paciente paso a cns_paciente.
    OR (table_name = 'cns_clinical_history' AND column_name IN (
        'curp','sexo','id_ocupacion','id_escolaridad','id_edocivil',
        'id_religion','id_residencia','telefono'))
    OR (table_name = 'cns_allergy' AND column_name = 'categoria')
    OR table_name = 'cns_clinical_history_revision'
  );

-- A3. Tablas de Django que SIRES no usa (auth_* estandar: SIRES autentica con
--     sy_usuarios). Se listan en A1 solo si NO estan en la lista de arriba;
--     auth_user/auth_group SI estan porque django.contrib.auth sigue instalado.

-- #############################################################################
-- BASE "expedientes" (DATABASES["expedientes"], replica de Oracle)
-- #############################################################################

-- A4. Tablas que no son parte del sync ni de ningun modelo.
SELECT t.table_schema, t.table_name
FROM information_schema.tables t
WHERE t.table_schema = 'public'
  AND t.table_type = 'BASE TABLE'
  AND t.table_name NOT IN (
    'cat_clinicas',
    'cat_empleados',
    'cat_empleados_sis',
    'cat_familiar',
    'cat_familiar2',
    'dnt_fotos_credenciales',
    'dnt_licencias_medicas'
  )
ORDER BY t.table_name;

-- A5. Columna `curp` en tablas REPLICADAS de Oracle (DDL 002 viejo). El CURP
--     ahora vive en cns_paciente (base principal). Si la columna
--     existe aqui, sync_service.py la busca en Oracle (descubre columnas por
--     information_schema) y rompe el sync donde Oracle no la tiene.
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name = 'curp'
  AND table_name IN ('cat_empleados', 'cat_familiar', 'cat_empleados_sis', 'cat_familiar2');

-- A6. Si A5 encontro columnas: confirmar que estan VACIAS antes de borrar.
-- SELECT count(curp) FROM cat_empleados;
-- SELECT count(curp) FROM cat_familiar;
-- SELECT count(curp) FROM cat_empleados_sis;
-- SELECT count(curp) FROM cat_familiar2;

-- =============================================================================
-- PARTE B -- LIMPIEZA (descomentar SOLO lo confirmado en la PARTE A, con respaldo)
-- =============================================================================

-- B1. (base principal) Por cada tabla de A1 que se confirme sin uso:
-- DROP TABLE sires.<tabla>;

-- B2. (base expedientes) Columnas curp huerfanas (solo si A6 = 0 filas con dato):
-- ALTER TABLE cat_empleados     DROP COLUMN IF EXISTS curp;
-- ALTER TABLE cat_familiar      DROP COLUMN IF EXISTS curp;
-- ALTER TABLE cat_empleados_sis DROP COLUMN IF EXISTS curp;
-- ALTER TABLE cat_familiar2     DROP COLUMN IF EXISTS curp;

-- B3. (base expedientes) Por cada tabla de A4 que se confirme sin uso:
-- DROP TABLE public.<tabla>;
