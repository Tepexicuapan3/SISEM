# API RBAC - Contratos

> TL;DR: Contrato oficial de RBAC (roles, permisos, usuarios, overrides) para Django/DRF. Incluye auditoria obligatoria (`auditoria_eventos`), reglas de negocio y decisiones de compatibilidad para quedar alineado con `docs/api/standards.md` y con el frontend actual.

## Problem / Context

RBAC controla autorizacion del sistema. Un mismatch entre migraciones Django, backend API y frontend rompe seguridad, UX y trazabilidad.

Esta version actualiza el contrato con los datos reales de la migracion Django para:
- auditoria (`auditoria_eventos`)
- estado de usuario (`est_bloqueado`, `fch_terminos`, `fch_baja`)
- reglas de baja logica y reactivacion por constraints unicos

**Fuente de verdad**
- `docs/api/standards.md`
- `backend/apps/catalogos/migrations/0001_initial.py`
- `backend/apps/administracion/migrations/0001_initial.py`
- `backend/apps/authentication/migrations/0001_initial.py`
- `backend/apps/authentication/migrations/0002_det_usuario.py`
- `backend/apps/authentication/repositories/user_repository.py`
- `backend/seed_e2e.py`
- `frontend/src/api/types/roles.types.ts`
- `frontend/src/api/types/permissions.types.ts`
- `frontend/src/api/types/users.types.ts`
- `frontend/src/api/resources/roles.api.ts`
- `frontend/src/api/resources/permissions.api.ts`
- `frontend/src/api/resources/users.api.ts`

Base URL
```
http://localhost:5000/api/v1
```

## Solution / Implementation

### Convenciones obligatorias

- Responses en camelCase ingles, siguiendo `docs/api/standards.md`.
- Errores con shape `ApiError` (`code`, `message`, `status`, `details?`, `requestId?`, `timestamp?`).
- Mutaciones (`POST`, `PUT`, `PATCH`, `DELETE`) requieren `X-CSRF-TOKEN`.
- Toda mutacion debe actualizar auditoria tecnica de entidad (`fch_modf`, `usr_modf`) y registrar evento en `auditoria_eventos`.
- Relaciones RBAC usan baja logica (`fch_baja`, `usr_baja`), no delete fisico.
- Permisos efectivos usan solo entidades activas (`est_activo = true`) y relaciones activas (`fch_baja is null`).

### Modelo de datos real (migraciones Django)

| Tabla | Campos clave | Constraints / Indices relevantes |
| --- | --- | --- |
| `cat_roles` | `id_rol`, `rol`, `desc_rol`, `landing_route`, `is_admin`, `es_sistema`, `est_activo`, `fch_alta/modf/baja`, `usr_alta/modf/baja` | `rol` unique |
| `cat_permisos` | `id_permiso`, `codigo`, `descripcion`, `es_sistema`, `est_activo`, `fch_alta/modf/baja`, `usr_alta/modf/baja` | `codigo` unique |
| `rel_usuario_roles` | `id_usuario_rol`, `id_usuario`, `id_rol`, `is_primary`, `fch_asignacion`, `fch_baja`, `usr_asignacion`, `usr_baja` | unique (`id_usuario`, `id_rol`), index (`id_usuario`, `is_primary`) |
| `rel_rol_permisos` | `id_rol_permiso`, `id_rol`, `id_permiso`, `fch_asignacion`, `fch_baja`, `usr_asignacion`, `usr_baja` | unique (`id_rol`, `id_permiso`) |
| `rel_usuario_overrides` | `id_override`, `id_usuario`, `id_permiso`, `efecto`, `fch_asignacion`, `fch_expira`, `fch_baja`, `usr_asignacion`, `usr_baja` | unique (`id_usuario`, `id_permiso`), `efecto in {ALLOW, DENY}` |
| `sy_usuarios` | `id_usuario`, `usuario`, `correo`, `clave_hash`, `est_activo`, `est_bloqueado`, `cambiar_clave`, `terminos_acept`, `fch_terminos`, `last_conexion`, `ip_ultima`, `fch_alta/modf/baja`, `usr_alta/modf/baja` | `usuario` unique, `correo` unique |
| `det_usuarios` | `id_usuario`, `nombre`, `paterno`, `materno`, `nombre_completo`, `id_centro_atencion` | one-to-one con `sy_usuarios`, index en `nombre_completo` |
| `auditoria_eventos` | `id_evento`, `fch_evento`, `request_id`, `accion`, `recurso_tipo`, `recurso_id`, `actor_nombre`, `target_nombre`, `ip_origen`, `user_agent`, `resultado`, `codigo_error`, `datos_antes`, `datos_despues`, `meta`, `actor_id_usuario`, `target_id_usuario`, `id_centro_atencion` | indexes: `fch_evento`, `request_id`, `accion`, (`actor_usuario`,`fch_evento`), (`target_usuario`,`fch_evento`), (`accion`,`fch_evento`) |

### Mapeo API -> BD (contrato frontend)

#### RoleListItem / RoleDetail

| Campo API | Fuente BD | Notas |
| --- | --- | --- |
| `id` | `cat_roles.id_rol` | PK |
| `name` | `cat_roles.rol` | codigo del rol |
| `description` | `cat_roles.desc_rol` | descripcion visible |
| `landingRoute` | `cat_roles.landing_route` | nullable |
| `isActive` | `cat_roles.est_activo` | |
| `isSystem` | `cat_roles.es_sistema` | |
| `permissionsCount` | `rel_rol_permisos` | contar solo `fch_baja is null` |
| `usersCount` | `rel_usuario_roles` | contar solo `fch_baja is null` |
| `createdAt/By` | `cat_roles.fch_alta` / `cat_roles.usr_alta` | `UserRef` |
| `updatedAt/By` | `cat_roles.fch_modf` / `cat_roles.usr_modf` | `UserRef | null` |

#### RolePermission

| Campo API | Fuente BD | Notas |
| --- | --- | --- |
| `id` | `cat_permisos.id_permiso` | |
| `code` | `cat_permisos.codigo` | |
| `description` | `cat_permisos.descripcion` | |
| `assignedAt` | `rel_rol_permisos.fch_asignacion` | |
| `assignedBy` | `rel_rol_permisos.usr_asignacion` | `UserRef` |

#### Permission

| Campo API | Fuente BD | Notas |
| --- | --- | --- |
| `id` | `cat_permisos.id_permiso` | |
| `code` | `cat_permisos.codigo` | formato `grupo:modulo:submodulo:accion` |
| `description` | `cat_permisos.descripcion` | |
| `isSystem` | `cat_permisos.es_sistema` | |
| `dependsOn` | calculado (`get_permission_direct_dependencies`) | codigos de dependencias DIRECTAS, ordenadas; `[]` si no tiene (ej. cualquier `:read`). Ver "Dependencias de permisos" |

#### UserListItem / UserDetail

| Campo API | Fuente BD | Notas |
| --- | --- | --- |
| `id` | `sy_usuarios.id_usuario` | |
| `username` | `sy_usuarios.usuario` | |
| `fullname` | `det_usuarios.nombre_completo` | campo consumido hoy por UI RBAC |
| `fullName` | `det_usuarios.nombre_completo` | alias de compatibilidad con standards (opcional por ahora) |
| `email` | `sy_usuarios.correo` | |
| `clinic` | `det_usuarios.id_centro_atencion` | `CentroAtencionRef | null` |
| `primaryRole` | `cat_roles.rol` | rol con `rel_usuario_roles.is_primary = true` |
| `isActive` | `sy_usuarios.est_activo` | |
| `firstName` | `det_usuarios.nombre` | `UserDetail` |
| `paternalName` | `det_usuarios.paterno` | `UserDetail` |
| `maternalName` | `det_usuarios.materno` | `UserDetail` |
| `termsAccepted` | `sy_usuarios.terminos_acept` | `UserDetail` |
| `mustChangePassword` | `sy_usuarios.cambiar_clave` | `UserDetail` |
| `lastLoginAt` | `sy_usuarios.last_conexion` | `UserDetail` |
| `lastIp` | `sy_usuarios.ip_ultima` | `UserDetail` |
| `createdAt/By` | `sy_usuarios.fch_alta` / `sy_usuarios.usr_alta` | `UserRef` |
| `updatedAt/By` | `sy_usuarios.fch_modf` / `sy_usuarios.usr_modf` | `UserRef | null` |

#### UserRole

| Campo API | Fuente BD | Notas |
| --- | --- | --- |
| `id` | `cat_roles.id_rol` | |
| `name` | `cat_roles.rol` | |
| `description` | `cat_roles.desc_rol` | |
| `isPrimary` | `rel_usuario_roles.is_primary` | |
| `assignedAt` | `rel_usuario_roles.fch_asignacion` | |
| `assignedBy` | `rel_usuario_roles.usr_asignacion` | `UserRef` |

#### UserOverride

| Campo API | Fuente BD | Notas |
| --- | --- | --- |
| `id` | `rel_usuario_overrides.id_override` | |
| `permissionCode` | `cat_permisos.codigo` | |
| `permissionDescription` | `cat_permisos.descripcion` | |
| `effect` | `rel_usuario_overrides.efecto` | `ALLOW | DENY` |
| `expiresAt` | `rel_usuario_overrides.fch_expira` | nullable |
| `isExpired` | derivado | `now > fch_expira` |
| `assignedAt` | `rel_usuario_overrides.fch_asignacion` | |
| `assignedBy` | `rel_usuario_overrides.usr_asignacion` | `UserRef` |

### Campos de usuario en BD que NO forman parte del contrato RBAC actual

Estos campos existen en migracion y deben respetarse en logica backend, aunque hoy no los consume UI RBAC:

| Campo BD | Uso backend | Expuesto en contrato RBAC |
| --- | --- | --- |
| `sy_usuarios.clave_hash` | hash password | nunca |
| `sy_usuarios.est_bloqueado` | bloqueo login (`ACCOUNT_LOCKED`) | no |
| `sy_usuarios.fch_terminos` | timestamp de aceptacion terminos | no |
| `sy_usuarios.fch_baja` | cuenta expirada / baja logica (`ACCOUNT_EXPIRED`) | no |
| `sy_usuarios.usr_baja` | actor de baja logica | no |

Si luego se exponen en API RBAC, usar nombres estandar:
- `est_bloqueado -> isBlocked`
- `fch_terminos -> termsAcceptedAt`
- `fch_baja -> deletedAt`
- `usr_baja -> deletedBy`

### Reglas de serializacion para objetos de auditoria (`*By`)

- `createdBy`, `updatedBy`, `assignedBy` usan siempre `UserRef` (`{ id, name }`).
- Si FK de auditoria es `null` y el tipo frontend no acepta `null`, responder fallback `{ "id": 0, "name": "Sistema" }`.
- `name` de `UserRef` sale de `det_usuarios.nombre_completo`; fallback a `sy_usuarios.usuario` si no hay detalle.

### Resolucion de permisos efectivos (backend)

1. Tomar roles activos del usuario: `rel_usuario_roles.fch_baja is null` + `cat_roles.est_activo = true`.
2. Si existe cualquier rol con `cat_roles.is_admin = true`, responder `permissions: ["*"]`.
3. Si es admin, no aplicar overrides.
4. Si no es admin, cargar permisos de rol activos: `rel_rol_permisos.fch_baja is null` + `cat_permisos.est_activo = true`.
5. Aplicar overrides activos: `rel_usuario_overrides.fch_baja is null` y (`fch_expira is null` o `fch_expira > now`).
6. `DENY` quita permiso, `ALLOW` agrega permiso.
7. Orden final alfabetico por `codigo`.

`primaryRole` y `landingRoute`:
- Priorizar relacion `is_primary = true`.
- Si no existe primary y hay roles activos, usar el primer rol activo (orden por `id_usuario_rol`).
- Si no hay roles activos: `primaryRole = ""` y `landingRoute = null`.

### Endpoints (contrato oficial alineado con frontend)

#### Roles

| Metodo | Ruta | Request | Response | Status | Permiso |
| --- | --- | --- | --- | --- | --- |
| GET | `/roles` | `RolesListParams` | `RolesListResponse` | 200 | `admin:gestion:roles:read` |
| GET | `/roles/:id` | - | `RoleDetailResponse` | 200 | `admin:gestion:roles:read` |
| POST | `/roles` | `CreateRoleRequest` | `CreateRoleResponse` | 201 | `admin:gestion:roles:create` |
| PUT | `/roles/:id` | `UpdateRoleRequest` | `UpdateRoleResponse` | 200 | `admin:gestion:roles:update` |
| DELETE | `/roles/:id` | - | `SuccessResponse` | 200 | `admin:gestion:roles:delete` |

#### Permisos de rol

| Metodo | Ruta | Request | Response | Status | Permiso |
| --- | --- | --- | --- | --- | --- |
| POST | `/permissions/assign` | `AssignPermissionsRequest` | `AssignPermissionsResponse` | 200 | `admin:gestion:roles:update` |
| DELETE | `/permissions/roles/:roleId/permissions/:permissionId` | - | `RevokePermissionsResponse` | 200 | `admin:gestion:roles:update` |

#### Catalogo de permisos

| Metodo | Ruta | Request | Response | Status | Permiso |
| --- | --- | --- | --- | --- | --- |
| GET | `/permissions` | - | `PermissionCatalogResponse` | 200 | `admin:gestion:permisos:read` |

#### Usuarios (core)

| Metodo | Ruta | Request | Response | Status | Permiso |
| --- | --- | --- | --- | --- | --- |
| GET | `/users` | `UsersListParams` | `UsersListResponse` | 200 | `admin:gestion:usuarios:read` |
| GET | `/users/:id` | - | `UserDetailResponse` | 200 | `admin:gestion:usuarios:read` |
| POST | `/users` | `CreateUserRequest` | `CreateUserResponse` | 201 | `admin:gestion:usuarios:create` |
| PATCH | `/users/:id` | `UpdateUserRequest` | `UpdateUserResponse` | 200 | `admin:gestion:usuarios:update` |
| PATCH | `/users/:id/activate` | - | `UserStatusResponse` | 200 | `admin:gestion:usuarios:update` |
| PATCH | `/users/:id/deactivate` | - | `UserStatusResponse` | 200 | `admin:gestion:usuarios:update` |

##### Contrato de falla de envio de credenciales (`POST /users`)

El comportamiento de `POST /users` ante fallo de `send_user_credentials_email(...)` es **dual** y esta gobernado por `ALLOW_USER_CREATE_WITHOUT_EMAIL`:

| Flag `ALLOW_USER_CREATE_WITHOUT_EMAIL` | HTTP | Persistencia usuario | Shape de respuesta |
| --- | --- | --- | --- |
| `false` (strict mode) | `500` | rollback (no queda usuario creado) | `ApiError` con `code=EMAIL_DELIVERY_FAILED`, `message`, `status`, `timestamp`, `requestId?`, `details?` |
| `true` (tolerant mode) | `201` | commit (usuario creado disponible para lecturas) | `CreateUserResponse` con `id`, `username`, `credentialsEmailSent=false` |

Error esperado en strict mode:

```json
{
  "code": "EMAIL_DELIVERY_FAILED",
  "message": "No se pudo enviar el correo de credenciales. El usuario no fue creado.",
  "status": 500,
  "timestamp": "2026-04-13T18:00:00Z",
  "requestId": "kan-73-strict-mode"
}
```

##### UsersListParams

Filtros soportados en `GET /users`:

- `status`: `active | inactive | pending`
  - `pending` = usuario con `terminos_acept = false` **o** `cambiar_clave = true`.

#### Usuarios - roles

| Metodo | Ruta | Request | Response | Status | Permiso |
| --- | --- | --- | --- | --- | --- |
| POST | `/users/:id/roles` | `AssignRolesRequest` | `AssignRolesResponse` | 201 | `admin:gestion:usuarios:update` |
| PUT | `/users/:id/roles/primary` | `SetPrimaryRoleRequest` | `SetPrimaryRoleResponse` | 200 | `admin:gestion:usuarios:update` |
| DELETE | `/users/:id/roles/:roleId` | - | `RevokeRoleResponse` | 200 | `admin:gestion:usuarios:update` |

#### Usuarios - overrides

| Metodo | Ruta | Request | Response | Status | Permiso |
| --- | --- | --- | --- | --- | --- |
| POST | `/users/:id/overrides` | `AddUserOverrideRequest` | `AddUserOverrideResponse` | 200 | `admin:gestion:usuarios:update` |
| DELETE | `/users/:id/overrides/:code` | - | `RemoveUserOverrideResponse` | 200 | `admin:gestion:usuarios:update` |

**Notas de ruta/compatibilidad**
- En frontend, la ruta real para asignar permisos es `POST /permissions/assign` (no `/roles/:id/permissions`).
- `AssignPermissionsRequest` acepta `roleId`/`role_id` y `permissionIds`/`permission_ids` por compatibilidad legacy.
- `RemoveUserOverride` usa `:code` (`permissionCode`) en la ruta, no `overrideId`.

### Auditoria obligatoria RBAC (`auditoria_eventos`)

Cada endpoint RBAC debe registrar evento de auditoria.

Campos minimos obligatorios:
- `request_id`: usar `X-Request-ID`; si no llega, generar UUID para no perder trazabilidad.
- `accion`: codigo de accion de la matriz RBAC.
- `recurso_tipo`: `role`, `permission`, `user`, `user_role`, `user_override`.
- `recurso_id`: id del recurso principal cuando aplique.
- `resultado`: `SUCCESS` o `FAIL`.
- `codigo_error`: solo en fail.
- `actor_id_usuario` y `actor_nombre`: usuario autenticado que ejecuta.
- `target_id_usuario` y `target_nombre`: cuando se opera sobre un usuario objetivo.
- `ip_origen`, `user_agent`.
- `meta`: al menos `{ "module": "rbac", "endpoint": "...", "method": "..." }`.

Para mutaciones (`POST`, `PUT`, `PATCH`, `DELETE`):
- `datos_antes`: snapshot parcial antes del cambio (sin secretos).
- `datos_despues`: snapshot parcial despues del cambio.

Matriz de `accion` recomendada:

| Endpoint | `accion` | `recurso_tipo` | `recurso_id` | `target_id_usuario` |
| --- | --- | --- | --- | --- |
| GET `/roles` | `RBAC_ROLE_LIST` | `role` | `null` | `null` |
| GET `/roles/:id` | `RBAC_ROLE_DETAIL` | `role` | `:id` | `null` |
| POST `/roles` | `RBAC_ROLE_CREATE` | `role` | `newRoleId` | `null` |
| PUT `/roles/:id` | `RBAC_ROLE_UPDATE` | `role` | `:id` | `null` |
| DELETE `/roles/:id` | `RBAC_ROLE_DELETE` | `role` | `:id` | `null` |
| GET `/permissions` | `RBAC_PERMISSION_LIST` | `permission` | `null` | `null` |
| POST `/permissions/assign` | `RBAC_ROLE_PERMISSIONS_ASSIGN` | `role` | `roleId` | `null` |
| DELETE `/permissions/roles/:roleId/permissions/:permissionId` | `RBAC_ROLE_PERMISSION_REVOKE` | `role` | `:roleId` | `null` |
| GET `/users` | `RBAC_USER_LIST` | `user` | `null` | `null` |
| GET `/users/:id` | `RBAC_USER_DETAIL` | `user` | `:id` | `:id` |
| POST `/users` | `RBAC_USER_CREATE` | `user` | `newUserId` | `newUserId` |
| PATCH `/users/:id` | `RBAC_USER_UPDATE` | `user` | `:id` | `:id` |
| PATCH `/users/:id/activate` | `RBAC_USER_ACTIVATE` | `user` | `:id` | `:id` |
| PATCH `/users/:id/deactivate` | `RBAC_USER_DEACTIVATE` | `user` | `:id` | `:id` |
| POST `/users/:id/roles` | `RBAC_USER_ROLES_ASSIGN` | `user_role` | `:id` | `:id` |
| PUT `/users/:id/roles/primary` | `RBAC_USER_ROLE_PRIMARY_SET` | `user_role` | `:id` | `:id` |
| DELETE `/users/:id/roles/:roleId` | `RBAC_USER_ROLE_REVOKE` | `user_role` | `:id` | `:id` |
| POST `/users/:id/overrides` | `RBAC_USER_OVERRIDE_UPSERT` | `user_override` | `:id` | `:id` |
| DELETE `/users/:id/overrides/:code` | `RBAC_USER_OVERRIDE_REMOVE` | `user_override` | `:id` | `:id` |

### Reglas de negocio y edge cases

1. `rel_usuario_roles`, `rel_rol_permisos` y `rel_usuario_overrides` tienen unique constraints con baja logica.
   - Si la relacion existe con `fch_baja` no nulo, reactivar fila (set `fch_baja = null`) en vez de insertar otra.
2. Un usuario no puede quedar sin roles activos (`CANNOT_REMOVE_LAST_ROLE`).
3. Debe existir un unico rol primario por usuario activo.
   - `setPrimary` limpia otros `is_primary` en la misma transaccion.
   - Si se revoca rol primario, promover otro rol activo en la misma transaccion.
4. `es_sistema = true` en roles/permisos implica solo lectura.
   - update de rol de sistema: `ROLE_SYSTEM_PROTECTED` (403).
   - delete de rol de sistema: `CANNOT_DELETE_SYSTEM_ROLE` (403).
5. `is_admin = true` retorna `permissions: ["*"]` y anula overrides.
6. Overrides expirados o con `fch_baja` no impactan permisos.
7. Override es idempotente por usuario+permiso (upsert: actualiza `efecto` y `fch_expira`).
8. Asignacion bulk de permisos debe ser transaccional y tratar la lista recibida como set final.
9. No permitir baja logica de rol con usuarios activos asignados (`ROLE_HAS_USERS`).
10. Dependencias de permisos:
   - Si se asigna `:create/:update/:delete`, garantizar `:read` del mismo recurso.
   - Si se intenta revocar `:read` y quedan permisos de escritura del mismo recurso, rechazar (`PERMISSION_DEPENDENCY`).
   - `GET /permissions` (ambos serializers, legacy y S1) incluye `dependsOn` por permiso: dependencias directas (explicitas + `X:read` inferido para acciones `create|update|delete|manage|assign|revoke`). Es un campo aditivo; no es el cierre transitivo. Las excepciones sin `:read` en catalogo (`recepcion:fichas:*:create`) no lo infieren.
   - `POST /permissions/assign` (`ensure_read_dependencies`): el backend agrega al set pedido el cierre transitivo de dependencias (`get_permission_dependency_closure`) de cada permiso activo pedido. Ejemplo: asignar solo `X:update` deja el rol con `X:update` y `X:read`; asignar `admin:gestion:usuarios:update` agrega tambien `admin:gestion:roles:read`, `admin:gestion:permisos:read` y `admin:gestion:usuarios:read`. Los codigos de dependencia que no existen (o estan inactivos) en el catalogo se ignoran sin error. Idempotente.
   - Las dependencias agregadas pasan por la misma validacion de alcance que los permisos pedidos: si el actor (sin `*`) no posee alguna, responde `403 PERMISSION_GRANT_NOT_ALLOWED` y no se persiste nada.
   - El frontend (tab "Permisos por modulo") usa `dependsOn` para auto-marcar dependencias y cascadear al desmarcar; la fuente de verdad del cierre sigue siendo el backend.
11. `CreateUser` debe dejar onboarding forzado:
    - `cambiar_clave = true`
    - `terminos_acept = false`
    - `fch_terminos = null`
    - response incluye `credentialsEmailSent` (`true` cuando envio OK, `false` cuando se tolera falla por flag).
12. `PATCH /users/:id/activate|deactivate` solo cambia `est_activo`.
   - No usar `fch_baja` para activar/desactivar normal.
   - `fch_baja` queda reservado para expiracion/baja de cuenta.

### Codigos de error RBAC (ademas del estandar global)

Estos codigos adicionales ya son consumidos por frontend RBAC:

| Code | HTTP sugerido | Caso |
| --- | --- | --- |
| `ROLE_EXISTS` | 409 | nombre de rol duplicado |
| `ROLE_SYSTEM_PROTECTED` | 403 | intento de modificar rol de sistema |
| `ROLE_HAS_USERS` | 400 | intento de eliminar rol con usuarios activos |
| `PERMISSION_DEPENDENCY` | 400 | violacion de dependencia `read`/escritura |
| `PERMISSION_GRANT_NOT_ALLOWED` | 403 | el actor intenta asignar (o, por cierre de dependencias, implicar) permisos que no posee |

### Seed E2E relevante (`backend/seed_e2e.py`)

Datos utiles para pruebas de contrato:
- Password default: `Sisem_123456`.
- Usuario multirol: `usuario_multirol` (CLINICO + RECEPCION + FARMACIA).
- Usuarios de estado: `usuario_inactivo*`, `usuario_bloqueado*`, `usuario_onboarding*`, `usuario_cambiar_clave*`.

Brechas actuales del seed frente a frontend RBAC:
- faltan permisos: `admin:gestion:roles:create`, `admin:gestion:roles:update`, `admin:gestion:roles:delete`.
- faltan permisos: `admin:gestion:usuarios:create`, `admin:gestion:usuarios:update`.
- falta permiso: `admin:gestion:permisos:read`.

### Decision de compatibilidad standards vs frontend (`fullname`)

`docs/api/standards.md` define `fullName`, pero el frontend RBAC hoy tipa y consume `fullname`.

Decision de contrato para no romper:
1. Backend RBAC debe responder `fullname` (obligatorio hoy).
2. Backend RBAC puede responder tambien `fullName` como alias de migracion.
3. `sortBy` en listados de usuarios debe aceptar ambos (`fullname` y `fullName`) durante la transicion.

## Examples

**Crear usuario**
```json
{
  "username": "auditor1",
  "firstName": "Ana",
  "paternalName": "Lopez",
  "maternalName": "Garcia",
  "email": "ana.lopez@sisem.local",
  "clinicId": 1,
  "primaryRoleId": 6
}
```

**Response create user (201)**
```json
{
  "id": 120,
  "username": "auditor1",
  "credentialsEmailSent": true
}
```

**Detalle de usuario (compat frontend + standards)**
```json
{
  "user": {
    "id": 12,
    "username": "recepcion",
    "fullname": "Recepcion Demo",
    "fullName": "Recepcion Demo",
    "email": "recepcion@sisem.local",
    "clinic": { "id": 1, "name": "Centro de Atencion Local" },
    "primaryRole": "RECEPCION",
    "isActive": true,
    "firstName": "Recepcion",
    "paternalName": "Demo",
    "maternalName": "",
    "termsAccepted": true,
    "mustChangePassword": false,
    "lastLoginAt": null,
    "lastIp": null,
    "createdAt": "2026-02-04T12:00:00Z",
    "createdBy": { "id": 1, "name": "Admin Sistema" },
    "updatedAt": null,
    "updatedBy": null
  },
  "roles": [
    {
      "id": 7,
      "name": "RECEPCION",
      "description": "Recepcion",
      "isPrimary": true,
      "assignedAt": "2026-02-04T12:00:00Z",
      "assignedBy": { "id": 1, "name": "Admin Sistema" }
    }
  ],
  "overrides": []
}
```

**Registro de auditoria RBAC (ejemplo insert en `auditoria_eventos`)**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "accion": "RBAC_USER_UPDATE",
  "recurso_tipo": "user",
  "recurso_id": 12,
  "resultado": "SUCCESS",
  "actor_id_usuario": 1,
  "actor_nombre": "Admin Sistema",
  "target_id_usuario": 12,
  "target_nombre": "Recepcion Demo",
  "ip_origen": "10.10.0.25",
  "user_agent": "Mozilla/5.0",
  "datos_antes": { "email": "old@sisem.local" },
  "datos_despues": { "email": "new@sisem.local" },
  "meta": {
    "module": "rbac",
    "endpoint": "/users/12",
    "method": "PATCH"
  }
}
```

## References

- `docs/api/standards.md`
- `backend/apps/catalogos/migrations/0001_initial.py`
- `backend/apps/administracion/migrations/0001_initial.py`
- `backend/apps/authentication/migrations/0001_initial.py`
- `backend/apps/authentication/migrations/0002_det_usuario.py`
- `backend/apps/authentication/repositories/user_repository.py`
- `backend/seed_e2e.py`
- `frontend/src/api/types/roles.types.ts`
- `frontend/src/api/types/permissions.types.ts`
- `frontend/src/api/types/users.types.ts`
- `frontend/src/api/resources/roles.api.ts`
- `frontend/src/api/resources/permissions.api.ts`
- `frontend/src/api/resources/users.api.ts`
- `frontend/src/domains/auth-access/adapters/rbac/roles/roles.feedback.ts`
- `frontend/src/domains/auth-access/adapters/rbac/users/users.feedback.ts`
