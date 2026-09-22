# Domain Map (Phase 1 + base Phase 2)

> TL;DR: SISEM mantiene runtime actual, pero el delivery se organiza por dominios con ownership explicito para backend, frontend, DB y docs bajo estrategia `DB por dominio` con PostgreSQL como target.

## Problem / Context

El repo crecio por modulos y features, con riesgo de colisiones cuando varios equipos trabajan en paralelo y con sobrecarga de datos en aumento.

## Solution / Implementation

### Dominios operativos iniciales

| Dominio | Backend actual | Frontend actual | Data ownership (PostgreSQL target) | Estado migracion |
|---|---|---|---|---|
| Auth & Access | `backend/apps/authentication`, `backend/apps/core` | `frontend/src/features/auth`, `frontend/src/features/admin` + `frontend/src/domains/auth-access` | Schema/logical ownership dedicado por dominio (TO-BE detallado en `docs/domains/auth-access/db-domain-to-be-map.md`) | Hybrid |
| Recepcion | `backend/apps/recepcion` | `frontend/src/features/recepcion` | Schema/logical ownership dedicado por dominio | Piloto recomendado |
| Somatometria | `backend/apps/somatometria` | `frontend/src/features/somatometria` | Schema/logical ownership dedicado por dominio | Piloto recomendado |
| Consulta Medica | `backend/apps/consulta_medica` | `frontend/src/features/consulta-medica`, `frontend/src/features/consultas`, `frontend/src/features/autorizacion-recetas` (Autorizadores: Recetas) | Schema/logical ownership dedicado por dominio | Legacy activo |
| Catalogos | `backend/apps/catalogos`, `backend/apps/opciones` | `frontend/src/features/catalogos` | Schema/logical ownership dedicado por dominio | Legacy activo |
| Movimientos/Pases | `backend/apps/movimientos`, `backend/apps/pases` | `frontend/src/features/operativo` | Schema/logical ownership dedicado por dominio | Legacy activo |
| Farmacia | `backend/apps/farmacia` (modelo `VacInventario` -- inventario de vacunas, CRUD completo + permisos `farmacia:vacunas:*`, migraciones `0001`/`0002` ya aplicadas) | (sin modulo dedicado estable -- backend real, sin pagina propia) | Schema/logical ownership dedicado por dominio | Piloto en progreso (backend) |
| Realtime | `backend/apps/realtime` | `frontend/src/realtime` | Read-model/event stream, sin tablas cross-domain directas | Shared capability |

### Ownership minimo por dominio

Cada dominio debe tener ownership explicito para:

- backend (API, use cases, repos)
- frontend (UI, hooks, state)
- DB en PostgreSQL (schemas/tablas/migraciones/indices)
- docs (playbook, contracts, ADR/RFC)
- Cada area debe declarar owner primario y secundario para continuidad operativa y review.

### Reglas de datos entre dominios

- No acceso directo cross-domain a tablas o schemas.
- El intercambio se hace por API, eventos o read-models.
- El owner del dominio define retencion, archivo y observabilidad de su data.

## Examples

Formato sugerido para ticket de ownership:

```text
Dominio: Recepcion
Owner backend (primary/secondary): @backend-owner-a / @backend-owner-b
Owner frontend (primary/secondary): @frontend-owner-a / @frontend-owner-b
Owner DB (primary/secondary): @db-owner-a / @db-owner-b
Owner docs (primary/secondary): @docs-owner-a / @docs-owner-b
```

## References

- `docs/architecture/context-map.md`
- `docs/architecture/dependency-rules.md`
- `docs/architecture/db-ownership-migration-policy.md`
- `docs/guides/domain-dor-dod.md`
