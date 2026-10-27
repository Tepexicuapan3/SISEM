# Runbook: el legado en tres capas (plan identidad, bloque D)

> Decisión del usuario (2026-10-23): traer **toda** la historia, la base actual
> (`dbclinicas`, 2025 en adelante) **y** las anuales archivadas (`dbclinicas2015` …
> `dbclinicas2024_a`). Sin ensuciar el modelo nuevo con las malas prácticas del legado.

| Capa | Qué | Dónde | Para qué |
|---|---|---|---|
| **1. Copia tal cual** | Cada base del legado completa, sin transformar | Base Postgres aparte `sisem_legado`, un esquema por base (`legado_actual`, `legado_2015`…) y **solo lectura** | Evidencia del original y retención legal. Es lo que se archiva a los 5 años |
| **2. Archivo de eventos** | Notas de consulta y diagnósticos CIE, curados | `cns_legacy_consultation_record`, `cns_legacy_consultation_diagnosis` (solo lectura) | Consultar la historia vieja desde SIRES |
| **3. Hechos permanentes** | Alergias, antecedentes, hábitos, grupo sanguíneo | Modelo nuevo, con origen "legado" | Lo que el médico necesita ver hoy (seguridad del paciente) |

> **Diseño vigente (2026-10-27).** El legado sigue en uso, así que no se migra en masa:
> 1. La capa 1 (`sisem_legado`) se recarga **cada noche** (la base actual; las anuales una vez).
> 2. SIRES **consulta directo** esa copia, con sus propias tablas y catálogos, por `id_persona` →
>    identificadores `NO_EXP` / `CD_FAMILIAR` del paciente (pantalla "Historial previo a SIRES").
> 3. Los hechos que importan (alergias, antecedentes, hábitos, grupo sanguíneo) pasan a SIRES
>    **cuando un médico los confirma**, por sección; lo confirmado no se vuelve a ofrecer. Las
>    alergias sin confirmar se muestran en la alerta al recetar como "del legado, sin confirmar".
>
> Las secciones "Capas 2 y 3: migrar a SIRES" de más abajo quedan **en desuso: no correrlas**.
> Se conservan como referencia hasta retirar esos comandos.

## Antes de empezar

1. **Respaldo** de la base principal de SIRES.
2. Listar las bases del legado en el servidor MySQL (solo lectura):

   ```sql
   SHOW DATABASES LIKE 'dbclinicas%';
   ```

   Anotá la lista exacta: si existe `dbclinicas2024_b` (o más particiones), entra igual.
3. Confirmar en cuáles existe `cat_familiar` (las anuales pueden no tenerla):

   ```sql
   SELECT table_schema FROM information_schema.tables
   WHERE table_name = 'cat_familiar' AND table_schema LIKE 'dbclinicas%';
   ```

   Las capas 2 y 3 traducen a los familiares **siempre** con el `cat_familiar` de la base
   actual (`--base-familiares dbclinicas`).

## Capa 1: copia tal cual con pgloader

### 1.1 Base y rol de solo lectura (una vez, en el Postgres de SIRES)

```sql
CREATE DATABASE sisem_legado;
CREATE ROLE legado_lectura NOLOGIN;
```

### 1.2 Un archivo de carga por base del legado

`legado_2015.load` (cambiá el año, las credenciales y los hosts):

```
LOAD DATABASE
  FROM      mysql://USUARIO:CLAVE@HOST_MYSQL:3306/dbclinicas2015
  INTO postgresql://USUARIO:CLAVE@HOST_POSTGRES:5432/sisem_legado

WITH create tables, create indexes, reset sequences,
     workers = 4, concurrency = 1, prefetch rows = 10000

SET MySQL PARAMETERS net_read_timeout = '600', net_write_timeout = '600'

CAST type datetime to timestamp drop default drop not null using zero-dates-to-null,
     type date drop default drop not null using zero-dates-to-null

ALTER SCHEMA 'dbclinicas2015' RENAME TO 'legado_2015';
```

Para la base actual: `.../dbclinicas` y `RENAME TO 'legado_actual'`.

```bash
docker run --rm -v "$PWD:/cfg" dimitri/pgloader:latest pgloader /cfg/legado_2015.load
```

pgloader convierte los tipos y el encoding latin1 del legado. Revisá su resumen final: la
columna `errors` tiene que dar 0.

### 1.3 Verificar conteos (por base)

```sql
-- MySQL
SELECT COUNT(*) FROM dbclinicas2015.his_notas;
SELECT COUNT(*) FROM dbclinicas2015.det_hisnotcie;
-- Postgres (sisem_legado)
SELECT COUNT(*) FROM legado_2015.his_notas;
SELECT COUNT(*) FROM legado_2015.det_hisnotcie;
```

Tienen que coincidir exactamente.

### 1.4 Dejarla de solo lectura (por esquema)

```sql
GRANT CONNECT ON DATABASE sisem_legado TO legado_lectura;
GRANT USAGE ON SCHEMA legado_2015 TO legado_lectura;
GRANT SELECT ON ALL TABLES IN SCHEMA legado_2015 TO legado_lectura;
REVOKE CREATE ON SCHEMA legado_2015 FROM PUBLIC;
```

Quien consulte la copia usa un usuario con el rol `legado_lectura`, nunca el de la aplicación.

### 1.5 Usuario de SIRES para la copia (una vez)

```sql
CREATE ROLE sires_legado LOGIN PASSWORD 'CLAVE_LARGA' IN ROLE legado_lectura;
```

En el `.env` del backend (no hay que tocar nada más; sin `LEGADO_NAME` la pantalla dice
"no disponible" y el sistema arranca igual):

```
LEGADO_NAME=sisem_legado
LEGADO_USER=sires_legado
LEGADO_PASSWORD=CLAVE_LARGA
LEGADO_HOST=auth-db
LEGADO_PORT=5432
```

Además del rol, la conexión de SIRES abre con `default_transaction_read_only=on`: aunque el
usuario tuviera permisos de más, la sesión no puede escribir. Verificación:

```bash
docker compose exec backend python manage.py shell -c \
  "from django.db import connections; c=connections['legado'].cursor(); c.execute('SHOW transaction_read_only'); print(c.fetchone())"
```

Tiene que imprimir `('on',)`.

### 1.6 Índices (después de cada carga, por esquema)

pgloader copia los índices del MySQL, que no siempre alcanzan para buscar por paciente:

```sql
CREATE INDEX IF NOT EXISTS ix_notas_paciente   ON legado_2015.his_notas (no_exp, tp_paciente);
CREATE INDEX IF NOT EXISTS ix_hisnotcie_nota   ON legado_2015.det_hisnotcie (cd_snota);
CREATE INDEX IF NOT EXISTS ix_hisclin_paciente ON legado_2015.his_clinica (no_exp, tp_paciente);   -- si existe
CREATE INDEX IF NOT EXISTS ix_hisclind_pac     ON legado_2015.his_clinicad (no_exp, tp_paciente);  -- si existe
CREATE INDEX IF NOT EXISTS ix_familiar_tit     ON legado_2015.cat_familiar (no_expf);              -- si existe
CREATE INDEX IF NOT EXISTS ix_familiar_pk      ON legado_2015.cat_familiar (pk_num);               -- si existe
ANALYZE;
```

### 1.7 Recarga nocturna de la base actual

Las anuales no cambian: se cargan una vez. La actual (`dbclinicas`) se recarga cada noche en un
esquema nuevo y se intercambia al final, así la pantalla nunca ve una carga a medias.

`legado_actual.load` igual que 1.2, pero con `ALTER SCHEMA 'dbclinicas' RENAME TO 'legado_actual_nuevo'`.

```bash
# cron del servidor, 02:30 todos los días
docker run --rm -v "$PWD:/cfg" dimitri/pgloader:latest pgloader /cfg/legado_actual.load && \
docker compose exec -T auth-db sh -c 'psql -U "$POSTGRES_USER" -d sisem_legado -v ON_ERROR_STOP=1' <<'SQL'
-- índices de 1.6 sobre legado_actual_nuevo, y después:
BEGIN;
DROP SCHEMA IF EXISTS legado_actual_viejo CASCADE;
ALTER SCHEMA legado_actual RENAME TO legado_actual_viejo;
ALTER SCHEMA legado_actual_nuevo RENAME TO legado_actual;
GRANT USAGE ON SCHEMA legado_actual TO legado_lectura;
GRANT SELECT ON ALL TABLES IN SCHEMA legado_actual TO legado_lectura;
COMMIT;
SQL
```

Si pgloader falla, el `&&` evita el intercambio: queda la copia de la noche anterior. La primera
vez no existe `legado_actual`: renombrar directo `legado_actual_nuevo` a `legado_actual`.
`legado_actual_viejo` queda un día como respaldo inmediato.

## Capas 2 y 3: migrar a SIRES, base por base (EN DESUSO, ver diseño vigente)

Los comandos leen del MySQL del legado mientras exista (lo que se ejecuta es solo SELECT
sobre el legado). **Orden de las bases: de la más vieja a la más nueva.** Por cada base,
primero el simulacro (`--dry-run`) y después el real:

```bash
DB=dbclinicas2015            # repetir para cada base, la actual al final
OPS="--database $DB --base-familiares dbclinicas"

# Capa 2: eventos (las notas antes que sus diagnósticos)
docker compose exec backend python manage.py migrar_notas_clinicas_legacy  $OPS --dry-run
docker compose exec backend python manage.py migrar_notas_clinicas_legacy  $OPS
docker compose exec backend python manage.py migrar_diagnosticos_cie_legacy --database $DB --dry-run
docker compose exec backend python manage.py migrar_diagnosticos_cie_legacy --database $DB

# Capa 3: hechos permanentes (gana el fe_hisclin más reciente; los conflictos quedan registrados)
docker compose exec backend python manage.py migrar_historial_clinico_legacy      $OPS --operador TU_USUARIO --dry-run
docker compose exec backend python manage.py migrar_historial_clinico_legacy      $OPS --operador TU_USUARIO
docker compose exec backend python manage.py migrar_historia_estomatologia_legacy $OPS --operador TU_USUARIO --dry-run
docker compose exec backend python manage.py migrar_historia_estomatologia_legacy $OPS --operador TU_USUARIO
```

Si una base anual no tiene `his_clinica`/`his_clinicad` (solo notas), los comandos de la capa
3 fallan al no encontrar la tabla: se omiten para esa base.

### Lo que protege cada comando (bloque D)

| | Regla |
|---|---|
| Notas | El folio (`CC25-1`) incluye el año y es único. Si llega el **mismo folio desde otra base** (p. ej. `2024_a` y `2024_b` con consecutivos reiniciados), **no se sobrescribe**: sale en el reporte como conflicto. Cada nota guarda su `db_origen` |
| Diagnósticos | `cd_detcie` se reinicia en cada base: la llave es **(base de origen, `cd_detcie`)**. El 5 de 2016 y el 5 de 2025 conviven |
| Filas ya importadas sin origen | Se **adoptan** en la siguiente corrida de su base (no se duplican) |
| Familiares | Se traducen con el `cat_familiar` de la base actual (`--base-familiares`) |

### Al terminar todas las bases

```bash
docker compose exec backend python manage.py corregir_llave_familiares_legacy --base-familiares dbclinicas --dry-run
docker compose exec backend python manage.py vincular_id_paciente --dry-run
docker compose exec backend python manage.py vincular_id_paciente
```

Verificación (base principal, solo lectura):

```sql
SELECT db_origen, count(*) FROM cns_legacy_consultation_record GROUP BY db_origen ORDER BY 1;
SELECT db_origen, count(*) FROM cns_legacy_consultation_diagnosis GROUP BY db_origen ORDER BY 1;
```

Cada base tiene que aparecer con un conteo igual a su `his_notas` / `det_hisnotcie` menos los
conflictos reportados.

## Retención

- La capa 1 (`sisem_legado`) y las capas 2 y 3 son expediente clínico: **mínimo 5 años desde
  el último acto médico**, y **nunca DELETE físico** (`docs/governance/nom024-retention-policy.md`).
- Pasado el plazo, la capa 1 se **archiva** por esquema (`pg_dump -n legado_2015`), se verifica
  la restauración y recién entonces se retira de la base viva, con el visto bueno de quien sea
  responsable de cumplimiento.
- El servidor MySQL del legado solo se apaga después de: capa 1 completa y verificada, capas 2 y
  3 migradas, y respaldo del MySQL (`legacy-backup-runbook.md`).
