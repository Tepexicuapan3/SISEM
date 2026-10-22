# Runbook: auditoría de la actualización de expedientes desde SERMED

> Change `auditoria-sync-expedientes` (2026-10-21). El botón **Actualizar** de
> Administración → Expedientes ahora deja rastro completo (quién, cuándo, desde
> dónde, resultado y antes/después de cada fila de la réplica), exige su propio
> permiso y aplica las 6 tablas en una sola transacción.

## Qué cambia

| Pieza | Antes | Ahora |
|---|---|---|
| Quién actualizó | No se guardaba | `bitacora_sync_expediente` (usuario, login, IP, user agent, request id, origen) |
| Antes/después de la réplica | Se sobrescribía/borraba sin rastro | `bitacora_replica_sermed` (A/M/B, solo columnas que cambiaron; fotos como hash) |
| Usuario en `cns_bitacora_cambios` | Siempre `SYNC_SERMED` | El id del usuario que apretó el botón (comandos siguen con `SYNC_SERMED`) |
| `cns_paciente.usr_modf` | Vacío | Usuario que trajo el cambio |
| Consultar / buscar expediente | Sin registro | `bitacora_acceso` (acción `ver`, recursos `expediente_sermed` y `expediente_sermed_busqueda`) |
| Permiso del botón | `admin:gestion:expedientes:read` | `admin:gestion:expedientes:update` |
| Transacción | Commit por bloque; errores se tragaban | Todo o nada por expediente |
| Concurrencia | Dos actualizaciones podían pisarse | Advisory lock por `no_exp` → `409 SYNC_EN_CURSO` |
| Respuesta | Siempre 200 | `200` OK/PARCIAL, `409` ocupado, `502` error (nada aplicado) |
| Bitácoras | "No se edita" solo por convención | Trigger Postgres rechaza UPDATE/DELETE/TRUNCATE |
| Tabla faltante en la réplica | Warning silencioso, "OK" sin guardar | Error: el expediente no se actualiza |
| Contraseñas de BD en `settings.py` | `112233` por defecto | Sin valor por defecto; con `DEBUG=False` el arranque falla si faltan |

Migraciones: `administracion 0013, 0014, 0015` y `consulta_medica 0055`.

## Antes de desplegar (obligatorio)

1. **Variables de entorno del servidor.** El `.env` del backend debe definir
   `POSTGRES_PASSWORD` y `EXPEDIENTES_PASSWORD` (y `ORACLE_HOST`). Si alguna
   faltaba y se usaba el valor del código, con `DEBUG=False` el backend **no
   arranca** (`ImproperlyConfigured: Faltan variables de entorno obligatorias`).
2. **Las 6 tablas existen en la base `expedientes`.** Si falta alguna, ahora
   toda actualización termina en `ERROR` en vez de "OK" silencioso:

   ```sql
   -- En la base expedientes (solo lectura)
   SELECT t FROM unnest(ARRAY['cat_empleados','cat_empleados_sis','cat_familiar',
          'cat_familiar2','dnt_licencias_medicas','dnt_fotos_credenciales']) AS t
   WHERE to_regclass(t) IS NULL;   -- debe devolver 0 filas
   ```

   Si devuelve filas, aplicar `backend/storage/expedientes-ddl/002_tablas_faltantes_expediente.sql`.
3. **Respaldo** de la base principal antes de `up -d` (el arranque corre `migrate`).

## Después de desplegar

```sql
-- Triggers de inmutabilidad (base principal): deben salir 10 filas.
-- Se consulta pg_trigger: information_schema.triggers NO muestra los de TRUNCATE.
SELECT tgrelid::regclass AS tabla, tgname
FROM pg_trigger
WHERE tgname LIKE '%\_inmutable' OR tgname LIKE '%\_sin\_truncate'
ORDER BY 1, 2;

-- Prueba de fuego: DEBE fallar con "es una bitacora" (SQL state 42501)
DELETE FROM bitacora_sync_expediente WHERE id = (SELECT max(id) FROM bitacora_sync_expediente);

-- Roles que recibieron el permiso nuevo (los que ya tenían lectura)
SELECT r.rol
FROM rel_rol_permisos rp
JOIN cat_roles r ON r.id_rol = rp.id_rol
JOIN cat_permisos p ON p.id_permiso = rp.id_permiso
WHERE p.codigo = 'admin:gestion:expedientes:update' AND rp.fch_baja IS NULL;
```

**Decisión institucional pendiente:** la migración 0015 da `update` a todos los
roles que hoy tienen `read`, para no quitarle el botón a nadie. Calidad /
Capital Humano deben definir qué roles solo consultan y retirarles `update`
desde Administración → Roles.

## Consultas de auditoría

```sql
-- ¿Quién actualizó el expediente 40041 y con qué resultado?
SELECT id, fecha_inicio, fecha_fin, cd_usuario, origen, ip_origen, resultado, errores
FROM bitacora_sync_expediente WHERE no_exp = '40041' ORDER BY fecha_inicio DESC;

-- ¿Qué cambió en la réplica en esa actualización?
SELECT tabla, llave, accion, valor_anterior, valor_nuevo
FROM bitacora_replica_sermed WHERE id_sync = <id> ORDER BY id;

-- ¿Estaba vigente el familiar 88731 en una fecha? (historia de fec_vig)
SELECT b.fecha_hora, s.cd_usuario, b.accion,
       b.valor_anterior ->> 'fec_vig' AS antes, b.valor_nuevo ->> 'fec_vig' AS despues
FROM bitacora_replica_sermed b JOIN bitacora_sync_expediente s ON s.id = b.id_sync
WHERE b.tabla = 'cat_familiar' AND b.llave = 'pk_num|88731' ORDER BY b.fecha_hora;

-- Actualizaciones que se quedaron EN_CURSO (proceso muerto a la mitad)
SELECT * FROM bitacora_sync_expediente
WHERE resultado = 'EN_CURSO' AND fecha_inicio < now() - interval '1 hour';
```

> La historia de la réplica empieza con el despliegue: lo anterior no se puede
> reconstruir.

## Pendiente: inspeccionar Oracle (punto 10)

`dnt_licencias_medicas` tiene solo 3 columnas y `cat_empleados_sis` /
`cat_familiar2` tienen columnas **supuestas**. Desde el contenedor del backend
(solo SELECT a Oracle):

```bash
python manage.py inspeccionar_oracle \
  --tabla DNT_LICENCIAS_MEDICAS --tabla CAT_EMPLEADOS_SIS --tabla CAT_FAMILIAR2 \
  --output /tmp/oracle_tablas_sync.json
```

Con ese resultado se amplía el DDL (solo columnas que Oracle tiene: una
columna que Oracle no tiene rompe el sync).

## Reversa

- Código: revertir el commit. Las tablas nuevas quedan (son evidencia).
- Triggers: `python manage.py migrate consulta_medica 0054` y
  `python manage.py migrate administracion 0013` los quitan.
- Para una corrección controlada de una bitácora (con acta):
  `ALTER TABLE <tabla> DISABLE TRIGGER <tabla>_inmutable;` … `ENABLE TRIGGER`.
