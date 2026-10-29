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

## Atajo vigente (2026-10-29): leer el espejo MySQL del legado

Ya existe un **espejo MySQL del legado** (mismas bases `dbclinicas`, `dbclinicas2015`…, sin
transformar) que mantiene otra persona. Mientras no se arme la copia en Postgres, SIRES lo lee
**directo**, con PyMySQL (Django 6 no acepta MySQL anteriores a 8.0.11). Los pasos 3 a 7 y 11 de
abajo no hacen falta con este atajo.

En el `.env` del servidor (sin `LEGADO_NAME`):

```
LEGADO_MOTOR=mysql
LEGACY_MYSQL_HOST=ip_del_espejo
LEGACY_MYSQL_PORT=3306
LEGACY_MYSQL_USER=usuario_de_solo_select
LEGACY_MYSQL_PASSWORD=...
LEGACY_MYSQL_DATABASE=dbclinicas
```

- `LEGACY_MYSQL_DATABASE` es la base **actual**; las anuales se encuentran solas por prefijo
  (`dbclinicas2015` → `legado_2015`).
- Protección: el usuario tiene que tener **solo `SELECT`**; además la sesión abre con
  `SET SESSION TRANSACTION READ ONLY` y el código rechaza cualquier SQL que no sea `SELECT`.
- Verificación desde el servidor:
  `docker compose exec backend python manage.py shell -c "from apps.consulta_medica.services import legado_archivo as l; print(l.esquemas_con_tabla('his_notas'))"`
  tiene que listar `legado_actual` y las anuales.

**Pasar después a una copia en Postgres** (la carga o la actualiza un tercero, sin recarga
nocturna de nuestro lado): se cambian solo variables. Si la copia conserva los nombres
originales (`dbclinicas`, `dbclinicas2015`… como esquemas, lo que deja pgloader sin el
`ALTER SCHEMA … RENAME`), en el `.env` se quita `LEGADO_MOTOR=mysql` y se ponen
`LEGADO_NAME`, `LEGADO_USER`, `LEGADO_PASSWORD`, `LEGADO_HOST`, `LEGADO_PORT` y
`LEGADO_ESQUEMA_ACTUAL=dbclinicas`. Si se renombraron a `legado_*`, sin `LEGADO_ESQUEMA_ACTUAL`.
Lo que los médicos ya confirmaron sigue valiendo: SIRES guarda el origen con los nombres
lógicos (`legado_2015:…`), no con el físico.

## Paso a paso (seguir en este orden)

Todo lo que toca el legado es **solo lectura**. Marcá cada paso al terminarlo.

- [ ] **1. Desplegar el código** (bloques L1 a L5, incluye la migración `0063`):
      `git pull` → `docker compose up -d --build backend frontend` →
      `docker compose exec backend python manage.py migrate consulta_medica` → `docker compose restart proxy`.
      Sin `LEGADO_*` en el `.env` no cambia nada visible.
- [ ] **2. Preparar:** respaldo de SIRES; host, puerto y usuario **de solo lectura** del MySQL del
      legado; lista de bases (`SHOW DATABASES LIKE 'dbclinicas%';`); red de Docker de `auth-db`
      (`docker network ls`, p. ej. `sires_default`).
- [ ] **3. Base y usuarios** en el Postgres de SIRES: secciones 1.1 y 1.5 (`CREATE DATABASE
      sisem_legado`, rol `legado_lectura`, usuario `sires_legado`).
- [ ] **4. Copiar cada base con pgloader:** sección 1.2. Un `.load` por base; la actual se renombra
      a `legado_actual`. Para que pgloader encuentre `auth-db`, agregar la red:
      `docker run --rm --network sires_default -v "$PWD:/cfg" dimitri/pgloader:latest pgloader /cfg/legado_2015.load`.
      El resumen final tiene que dar `errors = 0`.
- [ ] **5. Verificar conteos** MySQL contra Postgres: sección 1.3 (`his_notas`, `det_hisnotcie`,
      `his_clinica`, `his_clinicad`).
- [ ] **6. Permisos de solo lectura** por esquema: sección 1.4.
- [ ] **7. Índices** por esquema: sección 1.6.
- [ ] **8. Conectar SIRES:** variables `LEGADO_*` de la sección 1.5 en el `.env`,
      `docker compose up -d backend`, `docker compose restart proxy` y la verificación
      `SHOW transaction_read_only` → `('on',)`.
- [ ] **9. Puente de los familiares que ya existen:**
      `docker compose exec backend python manage.py registrar_llaves_legado --dry-run` y después sin
      `--dry-run`. Los **dudosos** que liste se revisan a mano (nunca se adivinan).
- [ ] **10. Probar en pantalla** (expediente → pestaña Historial):
      "Historial previo a SIRES" muestra notas de todas las bases con médico, clínica y diagnósticos;
      "Datos del sistema anterior por revisar" ofrece alergias, antecedentes y hábitos para confirmar;
      al recetar un medicamento que choca con una alergia del legado sin confirmar aparece la
      advertencia "del sistema anterior, sin confirmar".
- [ ] **11. Recarga nocturna** de `legado_actual`: sección 1.7 (cron). Después del intercambio de
      esquemas, correr también `registrar_llaves_legado`. Las anuales no se recargan.

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
docker run --rm --network sires_default -v "$PWD:/cfg" dimitri/pgloader:latest pgloader /cfg/legado_2015.load
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
-- SIRES compara el expediente sin ceros a la izquierda: el índice es sobre esa expresión.
CREATE INDEX IF NOT EXISTS ix_notas_paciente   ON legado_2015.his_notas    ((ltrim(CAST(no_exp AS text), '0')), tp_paciente);
CREATE INDEX IF NOT EXISTS ix_hisnotcie_nota   ON legado_2015.det_hisnotcie ((CAST(cd_snota AS text)));
CREATE INDEX IF NOT EXISTS ix_hisclin_paciente ON legado_2015.his_clinica  ((ltrim(CAST(no_exp AS text), '0')), tp_paciente);  -- si existe
CREATE INDEX IF NOT EXISTS ix_hisclind_pac     ON legado_2015.his_clinicad ((ltrim(CAST(no_exp AS text), '0')), tp_paciente);  -- si existe
CREATE INDEX IF NOT EXISTS ix_familiar_tit     ON legado_2015.cat_familiar ((ltrim(CAST(no_expf AS text), '0')));           -- si existe
ANALYZE;
```

Los catálogos que usa la pantalla (`cat_medicos`, `cat_clinicas`, `cat_cie10`) se leen **siempre de
`legado_actual`**: las anuales pueden no tenerlos.

### 1.7 Recarga nocturna de la base actual

Las anuales no cambian: se cargan una vez. La actual (`dbclinicas`) se recarga cada noche en un
esquema nuevo y se intercambia al final, así la pantalla nunca ve una carga a medias.

`legado_actual.load` igual que 1.2, pero con `ALTER SCHEMA 'dbclinicas' RENAME TO 'legado_actual_nuevo'`.

```bash
# cron del servidor, 02:30 todos los días (ajustar la red: docker network ls)
docker run --rm --network sires_default -v "$PWD:/cfg" dimitri/pgloader:latest pgloader /cfg/legado_actual.load && \
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
docker compose exec -T backend python manage.py registrar_llaves_legado
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
