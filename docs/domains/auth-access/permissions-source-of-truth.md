# auth-access - Permissions Source of Truth (KAN-49)

> TL;DR: este slice de KAN-49 consolida la evaluacion de permisos efectivos/capabilities en backend como fuente canonica y fuerza `deny by default` en consumo frontend cuando la proyeccion backend existe, acotado al flujo critico de recepcion.

## 1) Alcance del slice KAN-49

Incluye solo el minimo runtime obligatorio para cerrar la primera porcion de KAN-49:

- Backend: punto unico de evaluacion de capabilities (`authorization_service`) reutilizado por el flujo critico de recepcion.
- Frontend: gating UX de flujo critico consumiendo capabilities del contrato backend canonico sin fallback inseguro.
- Testing: evidencia de `deny by default`, `allow` con permiso efectivo y prueba de punto unico de cambio.

Fuera de alcance en este slice:

- Reescritura total de todos los checks historicos de permisos.
- Migracion completa de todos los feature modules a `requiredCapability` puro.
- Migracion completa de todos los flujos clinicos/realtime pendientes a capability enforcement runtime.

## 2) Contrato canonico de permisos (backend -> frontend)

### 2.1 Payload canonico en `AuthUser`

Campos relevantes:

- `permissions: string[]` -> permisos otorgados directos (role + overrides).
- `effectivePermissions: string[]` -> permisos realmente efectivos luego de dependencias.
- `capabilities: Record<string, { granted: boolean; missingAllOf: string[]; missingAnyOf: string[] }>` -> evaluacion canonica por capacidad.
- `permissionDependenciesVersion: string` -> version del motor de proyeccion (`v1` en este slice).
- `strictCapabilityPrefixes: string[]` -> prefijos de capability en modo estricto para frontend transicional.

Proyeccion dedicada KAN-64:

- `GET /api/v1/auth/capabilities` expone el subconjunto de `AuthUser` necesario para UI admin (`permissions`, `effectivePermissions`, `capabilities`, `permissionDependenciesVersion`, `strictCapabilityPrefixes`, `authRevision`) sin romper compatibilidad con `GET /api/v1/auth/me`.

### 2.2 Semantica

- Backend es source of truth de autorizacion.
- Si falta capability o requisito en backend, el resultado es `granted: false` (`deny by default`).
- Frontend usa capabilities solo para UX gating; no decide seguridad real.

### 2.3 Modo transicional KAN-49 (compat strategy)

Para evitar regresion en modulos no migrados y mantener backend como source of truth en el alcance migrado:

- `strictCapabilityPrefixes` define los ambitos en modo estricto (`deny by default` si capability no viene en `capabilities`).
- En este slice de KAN-49 los prefijos estrictos activos son:
  - `flow.recepcion.`
  - `flow.visits.`
- `flow.somatometria.` pasa a modo estricto en KAN-57 para cerrar fallback inseguro en el flujo clinico pendiente.
- Para capabilities fuera de esos prefijos, frontend puede aplicar fallback legacy temporal (si se provee `fallbackRequirement`) para preservar UX en modulos no migrados.
- Este fallback NO reemplaza seguridad backend: cualquier accion real sigue validando permisos/capabilities en backend.

### 2.4 Errores esperados en flujos protegidos

Contrato de error standard (`error_response`):

- `code`
- `message`
- `status`
- `timestamp`
- `requestId` (si aplica)

Codigos observables en este slice para autorizacion:

- `ROLE_NOT_ALLOWED` (dominio operativo/flujo critico)
- `PERMISSION_DENIED` (CSRF o acceso denegado por capa de seguridad)

## 3) Legacy -> Target (slice incremental)

| Estado | Legacy | Target KAN-49 slice |
|---|---|---|
| Resolucion de permisos/capabilities | Dependencias y checks dispersos entre use cases + fallback frontend | Servicio backend central (`backend/apps/authentication/services/authorization_service.py`) + consumo canonico en frontend |
| Autorizacion de flujo critico recepcion | Bypass por role string (`RECEPCION`) | Evaluacion por capability canonica (`flow.recepcion.queue.write`, `flow.visits.queue.read`) |
| Autorizacion de flujo critico somatometria | Bypass historico por role string (`SOMATOMETRIA`) | Enforcement por capability canonica (`flow.somatometria.capture`) en backend |
| UX fallback | Fallback local aunque backend tenga proyeccion | Modo hibrido: `deny by default` solo para prefijos estrictos KAN-49 + fallback legacy temporal en capabilities no migradas |

## 4) AC KAN-49 -> evidencia

| AC KAN-49 | Evidencia |
|---|---|
| 1) Acciones protegidas autorizadas desde backend (sin logica dispersa) | `backend/apps/authentication/services/authorization_service.py`, `backend/apps/recepcion/uses_case/visit_queue_usecase.py` |
| 2) Frontend consume contrato canonico | `frontend/src/domains/auth-access/hooks/usePermissionDependencies.ts` (sin fallback inseguro con proyeccion backend), `frontend/src/test/unit/auth/usePermissionDependencies.test.ts` |
| 3) Regla critica con punto unico de cambio + prueba | `backend/apps/authentication/tests/test_authorization_service.py::test_single_change_point_updates_runtime_behavior` |
| 4) Continuidad runtime fuera de KAN-49 (KAN-57) | `backend/apps/somatometria/uses_case/capture_vitals_usecase.py`, `backend/apps/somatometria/tests/test_vitals_contract_api.py` |

## 5) Riesgos y limites del slice

Riesgos residuales:

- Existen todavia checks heredados fuera de este flujo critico que no migraron al servicio central.
- Realtime `visits.stream` y otros flujos no migrados todavia pueden requerir barrido adicional de capability gates en tickets siguientes.
- `ROLE_NOT_ALLOWED` se mantiene como codigo de error de dominio para compatibilidad de contrato, aunque la decision ya es por capability.

Limites:

- No hay deprecacion total de helpers legacy de dependencia local en frontend.
- No se completo el barrido global de todas las rutas protegidas en backend/apps.

## 6) Recomendaciones inmediatas (KAN-57 / KAN-52)

- KAN-57: continuar barrido de checks remanentes por role string en use cases fuera del slice clinico/realtime ya migrado.
- KAN-52: amarrar decision de autorizacion con evento de auditoria estandarizado por capability evaluada + `requestId/contextId`.

## 7) Delta aplicado en KAN-57 (endurecimiento runtime)

- Se agrega `flow.somatometria.` a `strictCapabilityPrefixes` para forzar `deny by default` tambien en ese flujo.
- `capture_vitals_usecase` elimina bypass por role string y usa capability centralizada (`flow.somatometria.capture`) via `authorization_service`.
- `visits.stream` en realtime migra de allow-list por roles/permisos ad-hoc a capability gate unica (`flow.visits.queue.read`).

## 8) Separacion de alcance con KAN-50

- KAN-50 queda reservado para estrategia de datos RBAC (`managed=False`) en `rbac-db-ownership-migration-strategy.md`.
- Este documento mantiene alcance runtime del slice KAN-49 y su continuidad en KAN-57.

## 9) Delta aplicado en KAN-65 (frontend admin capability-first)

- KAN-65 consolida el consumo frontend admin de `GET /api/v1/auth/capabilities` como source of truth UX para gating de rutas/acciones in-scope (`users/roles`).
- `GET /api/v1/auth/me` se mantiene para identidad/sesión; no reemplaza la proyección de capacidades para decisiones UX de autorización en admin.
- En estados `loading/error/degraded` de capacidades, el flujo admin in-scope aplica `deny by default` (fail-closed) para acciones privilegiadas.
- La sincronía de cache `session + capabilities` (login/logout/refresh/auth-revision) reduce drift temporal entre identidad y autorización UX.

## 10) Alta de un módulo o catálogo nuevo (checklist obligatorio)

### 10.1 Por qué importa: `admin.` también es estricto

Además de los prefijos que manda el backend (`strictCapabilityPrefixes`), el frontend agrega por código `admin.` como prefijo estricto (`KAN49_STRICT_CAPABILITY_PREFIXES` en `frontend/src/domains/auth-access/hooks/usePermissionDependencies.ts`). Consecuencia:

- Si una pantalla llama `hasCapability("admin.catalogs.foo.read", ...)` y esa key **no existe** en `CAPABILITY_REQUIREMENTS`, el backend no la proyecta y `hasCapability` devuelve `false`.
- El `fallbackRequirement` (segundo argumento) **se ignora** en prefijos estrictos.
- Tener `permissions: ["*"]` **no alcanza**: `resolve_capabilities` solo concede `*` sobre las keys registradas.
- Resultado: la pantalla queda bloqueada para TODOS, incluido admin ("No tienes acceso para consultar este catálogo"). Asignar el permiso al rol no lo arregla.

Caso real (2026-10-14): los 8 catálogos de cirugías/ambulancias (`cie9mc`, `tiposcirugia`, `clasificacionescirugia`, `motivoscancelacioncirugia`, `motivostraslado`, `tipostraslado`, `tiposservicioambulancia`, `destinosambulancia`), `admin.arco.write` y `admin.users.clinicsCatalog.read` estaban usados en el frontend sin registrar en el backend.

### 10.2 Pasos

Para cada módulo/catálogo nuevo con permiso `<area>:<modulo>:<recurso>:<accion>` (ej. `admin:catalogos:destinos_ambulancia:read`):

1. **Permiso en BD** — agregar `(codigo, descripcion)` al seed que corresponda:
   - Catálogo con CRUD: `backend/apps/administracion/management/seeds/catalogos_crud_permissions_seed.py` (read/create/update/delete).
   - Resto de módulos: `backend/apps/administracion/management/seeds/navigation_permissions_seed.py` (nueva "tanda" al final).
   - Ambos comandos corren en `backend/start-docker.sh` y asignan los códigos `admin:catalogos:*` a los roles con `is_admin=True`.
2. **Capability en backend** — registrar cada key que use el frontend en `CAPABILITY_REQUIREMENTS` (`backend/apps/authentication/services/permission_dependencies.py`):
   ```python
   "admin.catalogs.destinosambulancia.read": {"allOf": ["admin:catalogos:destinos_ambulancia:read"]},
   ```
   La key tiene que coincidir **carácter por carácter** con la del frontend (camelCase, guiones o todo junto: lo que use la página).
3. **Consumo en frontend** — `usePermissionDependencies().hasCapability(key, { allOf: [permiso] })` en la página/diálogo; queries con `enabled: canRead`.
4. **Navegación** — nodo en `navigation_seed.py` con el mismo permiso, ruta con `ProtectedRoute requiredPermission`, regenerar `menu-destinations.generated.ts` y agregar el label en `menu-destinations.labels.ts`.
5. **Verificar** — `python manage.py test apps.authentication.tests.test_capability_registry_sync` (ver 10.3) y entrar con el usuario admin **después de re-loguear** (las capabilities vienen en la sesión).

### 10.3 Guardrail automático

`backend/apps/authentication/tests/test_capability_registry_sync.py` escanea los literales `admin.*` en `frontend/src` (sin tests) y falla si alguno no está en `CAPABILITY_REQUIREMENTS`, indicando archivo y línea. Corre en el job `backend` de CI (`python manage.py test`). Se salta solo si `frontend/src` no existe (contenedor solo backend).

Para otros prefijos estrictos (`flow.*`) el test todavía no aplica: si se agrega un prefijo estricto nuevo, extender el regex del test.
