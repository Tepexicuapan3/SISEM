# Runbook: Respaldo del sistema legado (java-main) antes de migrar o decomisionar

> TL;DR: antes de tocar, mover o apagar cualquier servidor del stack legado, se saca un respaldo
> completo (schema + datos) de cada base. Sin esto, cualquier trabajo de migración corre con
> riesgo de pérdida irreversible.

## Problem / Context

El sistema legado (`java-main`, Glassfish 4) no es una sola aplicación: son al menos 5 apps
independientes corriendo bajo el mismo servidor, cada una con su propia base de datos:

| App legado | Carpeta en `java-main` | Contenido probable |
|---|---|---|
| `sisem` / `dbclinicas` | `investigacion/consolidado/sisem`, `consolidado_assets/sisem` | Clínica: consultas, agenda, pases, incapacidades, farmacia, catálogos |
| `sides` | `investigacion/consolidado/sides` | Módulo aparte, sin mapear todavía |
| `fotosys` | `investigacion/consolidado/fotosys` | Fotos/credenciales (binarios) |
| `nominad` | `investigacion/consolidado/nominad` | Nómina/RH (relacionado con Oracle SERMED/NOMINAP) |
| `ws_stc` | `investigacion/consolidado/ws_stc` | Web services |

Se confirmó que existe un dump de **rutinas** de MySQL 8.0 para `dbclinicas`
(`investigacion/procedures/dbclinicas_procedures.sql`, host origen `10.15.15.61`), pero **no hay
ningún dump con `CREATE TABLE`** de ninguna de las 5 bases en el árbol del repo. Si esos
servidores se apagan sin respaldo previo, el esquema y los datos reales se pierden sin forma de
recuperarlos desde este repositorio.

## Solution / Implementation

### Antes de cualquier cambio en el legado

Para **cada** base (`dbclinicas`/`sisem`, `sides`, `fotosys`, `nominad`, `ws_stc` — confirmar
nombre real de cada schema en el servidor):

```bash
# Respaldo completo (schema + datos + rutinas/triggers/procedures)
mysqldump \
  --host=<HOST_LEGADO> \
  --port=3306 \
  --user=<USUARIO_LECTURA> \
  --password \
  --routines --triggers --events \
  --single-transaction \
  --set-gtid-purged=OFF \
  <NOMBRE_BASE> > backup_<NOMBRE_BASE>_$(date +%Y%m%d).sql
```

Notas:
- `--single-transaction` evita bloquear tablas InnoDB mientras se usa el sistema en producción.
- `--routines --triggers --events` es obligatorio: ya sabemos que `dbclinicas` tiene lógica de
  negocio en stored procedures (`sp_rep_master`, `sp_status_exp`, `sp_freceta`, etc.) que no está
  replicada en ningún otro lado.
- Si alguna base es Oracle (verificar; `nominad` podría vivir en el mismo Oracle que
  `SERMED`/`NOMINAP` referenciado en `backend/config/settings.py`), usar `expdp` (Data Pump) en
  vez de `mysqldump`, coordinando con quien administre esa instancia.
- Guardar el respaldo fuera del propio servidor legado (no en el mismo disco) — si el objetivo es
  apagar esa máquina, un backup local no sirve de nada.

### Verificación del respaldo

```bash
# Confirmar que el dump no está vacío y que trae CREATE TABLE
grep -c "^CREATE TABLE" backup_<NOMBRE_BASE>_*.sql
grep -c "^INSERT INTO" backup_<NOMBRE_BASE>_*.sql
```

Si `CREATE TABLE` da 0, el dump falló silenciosamente (permisos insuficientes, conexión cortada a
medias) — no continuar hasta corregirlo.

### Inventario posterior al respaldo

Una vez que exista un respaldo seguro, usar el comando de inspección
`inspeccionar_legado_mysql` (`backend/apps/authentication/management/commands/inspeccionar_legado_mysql.py`)
contra el servidor real (o restaurando el dump en un MySQL de prueba) para generar el inventario
de tablas/columnas/conteos que sirve de base a las migraciones por dominio.

## Examples

Orden recomendado si se van a respaldar las 5 bases en una sola sesión:

```bash
for db in dbclinicas sides fotosys nominad ws_stc; do
  mysqldump --host=<HOST_LEGADO> --user=<USUARIO_LECTURA> --password \
    --routines --triggers --events --single-transaction --set-gtid-purged=OFF \
    "$db" > "backup_${db}_$(date +%Y%m%d).sql"
done
```

## References

- `docs/governance/nom024-retention-policy.md` — define qué datos NO se pueden perder al
  decomisionar el legado (retención legal mínima) y el criterio de sign-off antes de apagar un
  servidor.
- `investigacion/procedures/dbclinicas_procedures.sql` (en `C:\SISEM JAVA 8\java-main`) — único
  artefacto de esquema legado disponible hoy (solo rutinas, sin `CREATE TABLE`).
- `backend/apps/authentication/management/commands/migrar_usuarios_legacy.py` — patrón de
  conexión `LEGACY_MYSQL_*` a reutilizar en cualquier script de inspección/migración.
- `backend/apps/authentication/management/commands/inspeccionar_legado_mysql.py` — comando de
  inventario (solo lectura) que consume este respaldo/servidor.
