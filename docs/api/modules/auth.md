# API Auth - Contratos

> TL;DR: Contratos oficiales de autenticacion. Backend y frontend deben cumplir estos payloads y errores.

## Problem / Context

SISEM es un sistema medico critico sobre backend Django/DRF y frontend React. Un mismatch en auth rompe sesiones, permisos y auditoria. Este documento define contratos HTTP para mantener consistencia entre clientes y backend.

**Fuente de verdad**
- `docs/api/standards.md`
- `frontend/src/infrastructure/api/types/auth.types.ts`
- `frontend/src/infrastructure/api/utils/errors.ts`

**Reglas clave**
- JWT en cookies HttpOnly (no tokens en body ni storage).
- CSRF obligatorio en mutaciones.
- Errores siguen el formato `ApiError` del estandar.
- `code` y `status` son contractuales; `message` se considera contractual para UX de auth-access (toast) y cualquier cambio requiere alinear runtime+docs+types+mocks+tests en el mismo PR.
- El contrato API documenta solo errores HTTP del backend (no errores de red del cliente).
- Gates de tipado frontend se validan por separado: `bun run typecheck:app` y `bun run typecheck:tests`.
- Alineacion docs/tipos/mocks se valida con `src/test/integration/contracts/auth-contract-alignment.spec.ts`.
- Smoke E2E se acepta solo en Docker con preflight (`bun run test:e2e:smoke`), no host-only.

Base URL
```
http://localhost:5000/api/v1
```

Headers requeridos
- Auth via cookies HttpOnly (`credentials: include` en frontend).
- Mutaciones (`POST`, `PUT`, `PATCH`, `DELETE`) requieren `X-CSRF-TOKEN`.

## Solution / Implementation

### AuthUser (entidad base)
```json
{
  "id": 1,
  "username": "jperez",
  "fullName": "Juan Perez",
  "email": "jperez@metro.cdmx.gob.mx",
  "avatarUrl": null,
  "primaryRole": "ADMIN",
  "landingRoute": "/admin",
  "roles": ["ADMIN"],
  "permissions": ["*"],
  "effectivePermissions": ["*"],
  "capabilities": {
    "admin.users.editFull": {
      "granted": true,
      "missingAllOf": [],
      "missingAnyOf": []
    }
  },
  "permissionDependenciesVersion": "v1",
  "strictCapabilityPrefixes": ["flow.recepcion.", "flow.somatometria.", "flow.visits."],
  "authRevision": "2026-03-26T10:15:30-06:00",
  "mustChangePassword": false,
  "requiresOnboarding": false,
  "alcanceCentros": { "todos": false, "centros": [{ "id": 3, "nombre": "TICOMAN" }] }
}
```

**Notas de contrato**
- `alcanceCentros`: centros sobre los que opera el usuario (ver `alcance-centro.md`). `centros` vacío y `todos = false` = sin centro asignado (no ve visitas ni citas). Es lista para soportar varios centros por usuario.
- `landingRoute` puede ser `null`.
- `avatarUrl` es opcional (`string | null`) y el runtime actual puede omitirlo.
- `roles` y `permissions` deben ser arrays (no `null`).
- `requiresOnboarding` debe venir en `/auth/me`.
- `effectivePermissions` debe ser `string[]` (en admin puede ser `[*]`).
- `capabilities` es `Record<string, { granted: boolean; missingAllOf: string[]; missingAnyOf: string[] }>`.
- `permissionDependenciesVersion` es `string` y runtime actual devuelve `"v1"`.
- `strictCapabilityPrefixes` es `string[]`.
- `authRevision` es `string` ISO 8601 y debe reflejarse tambien en header `X-Auth-Revision`.

### Mapeo AuthUser -> BD
| Campo API | Fuente BD | Notas |
| --- | --- | --- |
| `id` | `sy_usuarios.id_usuario` | PK interna |
| `username` | `sy_usuarios.usuario` | login principal |
| `fullName` | `det_usuarios.nombre_completo` | concatenado y almacenado |
| `email` | `sy_usuarios.correo` | unico |
| `avatarUrl` | derivado | campo opcional: runtime actual puede omitirlo hasta integrar fuente de avatar |
| `primaryRole` | `cat_roles.rol` | desde `rel_usuario_roles.is_primary = 1` |
| `landingRoute` | `cat_roles.landing_route` | puede ser `null` |
| `roles` | `cat_roles.rol[]` | roles activos del usuario |
| `permissions` | `cat_permisos.codigo[]` | roles + overrides, admin => `*` |
| `mustChangePassword` | `sy_usuarios.cambiar_clave` | booleano |
| `requiresOnboarding` | derivado | `cambiar_clave` o `terminos_acept = false` |
| `alcanceCentros` | `det_usuarios.id_centro_atencion` + permiso `alcance:centros:todos` | `centro_scope.alcance_contrato` |

### Ownership y boundary de datos (auth-access)

- **Dominio owner**: `auth-access` para `sy_usuarios`, `det_usuarios`, `rel_usuario_roles`, `cat_roles`, `rel_rol_permisos`, `cat_permisos`, `rel_usuario_overrides` y `auditoria_eventos` en su contexto de autenticacion/autorizacion.
- **Regla obligatoria**: no se permite SQL directo cross-domain desde otros dominios hacia estas tablas; cualquier necesidad externa debe resolverse por contrato API/evento/read-model aprobado.
- **Estado de plataforma**: una sola fuente operacional PostgreSQL con ownership/logical isolation por dominio; separacion fisica se evalua por criterios documentados.

### Reglas de permisos
- Admin se determina por `cat_roles.is_admin = true` y se responde `permissions: ["*"]`.
- Overrides activos (`rel_usuario_overrides`) se aplican despues de permisos por rol.
- Overrides expirados se ignoran.

### Auditoria (obligatoria)
Cada endpoint debe registrar en `auditoria_eventos`:
- `fch_evento`, `request_id`, `accion`, `resultado`.
- `actor_id_usuario` si hay sesion y `target_id_usuario` si aplica.
- `ip_origen`, `user_agent`, `codigo_error` en fallos.
- `meta` con contexto (endpoint, username/email enmascarado, modulo).

### Endpoints

#### POST `/auth/login`

**200 OK**
```json
{
  "user": { "...AuthUser" },
  "requiresOnboarding": false
}
```

**Errores (mensaje para toast)**
| Code | Status | Message |
| --- | --- | --- |
| `INVALID_CREDENTIALS` | 401 | Usuario o contraseña incorrectos |
| `USER_INACTIVE` | 403 | Cuenta desactivada por un administrador |
| `ACCOUNT_LOCKED` | 423 | Cuenta bloqueada por intentos fallidos |
| `ACCOUNT_EXPIRED` | 401 | Tu cuenta ha expirado. Contacta a soporte |
| `RATE_LIMIT_EXCEEDED` | 429 | Demasiadas solicitudes, espera un momento |
| `SERVICE_UNAVAILABLE` | 503 | Servicio temporalmente no disponible |
| `INTERNAL_SERVER_ERROR` | 500 | Error del servidor, intenta nuevamente |

Nota de seguridad: para evitar user enumeration, credenciales inválidas por usuario inexistente y contraseña inválida responden el mismo contrato (`INVALID_CREDENTIALS`, 401, mensaje unificado).

#### GET `/auth/me`

**200 OK**
```json
{ "...AuthUser" }
```

**Headers de respuesta**
- `X-Auth-Revision`: mismo valor que `authRevision` en payload (`string` ISO 8601).

**Errores (mensaje para toast)**
| Code | Status | Message |
| --- | --- | --- |
| `TOKEN_EXPIRED` | 401 | Tu sesión ha expirado |
| `TOKEN_INVALID` | 401 | Token inválido |
| `SESSION_EXPIRED` | 401 | Tu sesión ha expirado |
| `PERMISSION_DENIED` | 403 | No tienes permiso para esta acción |

Nota: `TOKEN_EXPIRED`, `TOKEN_INVALID`, `SESSION_EXPIRED` y `PERMISSION_DENIED` estan validados en tests de contrato/auth API (`backend/apps/authentication/tests/test_auth_api.py`, `test_auth_contract_edges.py`).

#### GET `/auth/capabilities`

Endpoint dedicado para UI admin cuando solo necesita proyeccion de permisos/capabilities.
Mantiene compatibilidad con `/auth/me`: los campos documentados abajo son un subconjunto del `AuthUser` vigente.

Uso operativo vigente (KAN-65):
- Frontend admin in-scope (`users/roles`) consume esta proyección como fuente principal para decisiones UX de autorización.
- Ante `error/degraded` en esta proyección, el gating privilegiado en admin aplica fail-closed (`deny by default`).
- `/auth/me` continúa siendo contrato de identidad/sesión y no reemplaza la lectura de capacidades para authz UX.

**200 OK**
```json
{
  "permissions": ["expedientes:read"],
  "effectivePermissions": ["expedientes:read"],
  "capabilities": {
    "admin.users.read": {
      "granted": true,
      "missingAllOf": [],
      "missingAnyOf": []
    }
  },
  "permissionDependenciesVersion": "v1",
  "strictCapabilityPrefixes": ["flow.recepcion.", "flow.visits.", "flow.somatometria."],
  "authRevision": "2026-03-26T20:15:00-06:00"
}
```

**Errores (mensaje para toast)**
| Code | Status | Message |
| --- | --- | --- |
| `TOKEN_EXPIRED` | 401 | Tu sesión ha expirado |
| `TOKEN_INVALID` | 401 | Token inválido |
| `SESSION_EXPIRED` | 401 | Tu sesión ha expirado |
| `PERMISSION_DENIED` | 403 | No tienes permiso para esta acción |
| `INTERNAL_SERVER_ERROR` | 500 | Error del servidor, intenta nuevamente |

#### POST `/auth/logout`

**200 OK**
```json
{ "success": true }
```

**Errores (mensaje para toast)**
| Code | Status | Message |
| --- | --- | --- |
| `TOKEN_EXPIRED` | 401 | Tu sesión ha expirado |
| `TOKEN_INVALID` | 401 | Token inválido |
| `SESSION_EXPIRED` | 401 | Tu sesión ha expirado |
| `PERMISSION_DENIED` | 403 | No tienes permiso para esta acción |
| `INTERNAL_SERVER_ERROR` | 500 | Error del servidor, intenta nuevamente |

#### GET `/auth/verify`

**200 OK**
```json
{ "valid": true }
```

**Errores**
- 401/403: frontend retorna `{ "valid": false }` (sin toast).

#### POST `/auth/refresh`

**200 OK**
```json
{ "success": true }
```

**Errores (mensaje para toast)**
| Code | Status | Message |
| --- | --- | --- |
| `REFRESH_TOKEN_EXPIRED` | 401 | Tu sesión ha expirado |
| `TOKEN_INVALID` | 401 | Token inválido |
| `SESSION_EXPIRED` | 401 | Tu sesión ha expirado |
| `PERMISSION_DENIED` | 403 | No tienes permiso para esta acción |
| `INTERNAL_SERVER_ERROR` | 500 | Error del servidor, intenta nuevamente |

#### POST `/auth/request-reset-code`

**200 OK**
```json
{ "success": true }
```

**Errores (mensaje para toast)**
| Code | Status | Message |
| --- | --- | --- |
| `INVALID_EMAIL` | 400 | Email inválido |
| `VALIDATION_ERROR` | 400 | Hay errores en el formulario |
| `USER_NOT_FOUND` | 404 | Usuario no encontrado |
| `RATE_LIMIT_EXCEEDED` | 429 | Demasiadas solicitudes, espera un momento |
| `SERVICE_UNAVAILABLE` | 503 | Servicio temporalmente no disponible, intenta nuevamente más tarde |
| `INTERNAL_SERVER_ERROR` | 500 | Error del servidor, intenta nuevamente |

#### POST `/auth/verify-reset-code`

**200 OK**
```json
{ "valid": true }
```

**Errores (mensaje para toast)**
| Code | Status | Message |
| --- | --- | --- |
| `CODE_EXPIRED` | 400 | El código ha expirado o fue invalidado |
| `INVALID_CODE` | 400 | Código incorrecto |
| `ACCOUNT_LOCKED` | 423 | Cuenta bloqueada por intentos fallidos |
| `SERVICE_UNAVAILABLE` | 503 | Servicio temporalmente no disponible, intenta nuevamente más tarde |
| `INTERNAL_SERVER_ERROR` | 500 | Error del servidor, intenta nuevamente |

#### POST `/auth/reset-password`

**200 OK**
```json
{
  "user": { "...AuthUser" },
  "requiresOnboarding": false
}
```

**Errores (mensaje para toast)**
| Code | Status | Message |
| --- | --- | --- |
| `VALIDATION_ERROR` | 400 | Hay errores en el formulario |
| `TOKEN_EXPIRED` | 401 | Tu sesión ha expirado |
| `TOKEN_INVALID` | 401 | Token inválido |
| `SESSION_EXPIRED` | 401 | Tu sesión ha expirado |
| `PERMISSION_DENIED` | 403 | No tienes permiso para esta acción |
| `PASSWORD_TOO_WEAK` | 400 | La contraseña es demasiado débil |
| `USER_NOT_FOUND` | 404 | Usuario no encontrado |
| `INTERNAL_SERVER_ERROR` | 500 | Error del servidor, intenta nuevamente |

#### POST `/auth/change-password`

Endpoint autenticado para cambio de contraseña self-service.

**Auth/CSRF requerido**
- Sesión activa por JWT en cookies HttpOnly.
- Header `X-CSRF-TOKEN` obligatorio.

**Request**
```json
{
  "currentPassword": "Abel_180903",
  "newPassword": "Nueva_Clave_123"
}
```

**200 OK**
```json
{ "success": true }
```

**Errores (mensaje para toast)**
| Code | Status | Message |
| --- | --- | --- |
| `VALIDATION_ERROR` | 400 | Hay errores en el formulario |
| `PASSWORD_TOO_WEAK` | 400 | La contraseña es demasiado débil |
| `INVALID_CREDENTIALS` | 401 | Usuario o contraseña incorrectos |
| `TOKEN_EXPIRED` | 401 | Tu sesión ha expirado |
| `TOKEN_INVALID` | 401 | Token inválido |
| `SESSION_EXPIRED` | 401 | Tu sesión ha expirado |
| `PERMISSION_DENIED` | 403 | No tienes permiso para esta acción |
| `INTERNAL_SERVER_ERROR` | 500 | Error del servidor, intenta nuevamente |

**Notas de regla de negocio (capa application/use-case)**
- `currentPassword` debe coincidir con el hash actual del usuario autenticado.
- `newPassword` debe ser distinta de `currentPassword`.
- `newPassword` debe pasar `validate_password` de Django.

**Auditoría obligatoria**
- `PASSWORD_CHANGE_SUCCESS` y `PASSWORD_CHANGE_FAILED` con `request_id`, actor, `ip`, `user_agent` y metadata (`endpoint`).

#### POST `/auth/complete-onboarding`

**200 OK**
```json
{
  "user": { "...AuthUser" },
  "requiresOnboarding": false
}
```

**Errores (mensaje para toast)**
| Code | Status | Message |
| --- | --- | --- |
| `VALIDATION_ERROR` | 400 | Hay errores en el formulario |
| `TERMS_NOT_ACCEPTED` | 400 | Debes aceptar los términos y condiciones |
| `PASSWORD_TOO_WEAK` | 400 | La contraseña es demasiado débil |
| `TOKEN_EXPIRED` | 401 | Tu sesión ha expirado |
| `TOKEN_INVALID` | 401 | Token inválido |
| `SESSION_EXPIRED` | 401 | Tu sesión ha expirado |
| `PERMISSION_DENIED` | 403 | No tienes permiso para esta acción |
| `ONBOARDING_FAILED` | 500 | No se pudo completar el onboarding |
| `INTERNAL_SERVER_ERROR` | 500 | Error del servidor, intenta nuevamente |

Nota: errores de red/timeout (por ejemplo `NETWORK_ERROR` y `TIMEOUT_ERROR`) pertenecen a la capa cliente y no forman parte del contrato HTTP del backend.

### Catalogo de codigos runtime actuales (legacy estables)

Los codigos `code` del backend auth-access se mantienen **legacy y estables** por compatibilidad. No se migran en este slice a otra taxonomia.

### Politica de taxonomia de errores (canon runtime + alias documental)

- **Canonico hoy:** los codigos legacy emitidos por backend (`TOKEN_INVALID`, `PERMISSION_DENIED`, etc.) son la fuente de verdad operativa y los que el cliente debe procesar.
- **Alias `AUTH_XXX`:** se documentan solo como referencia de gobernanza/normalizacion. **No** implican cambio de runtime ni reemplazan los codigos legacy en respuestas HTTP actuales.
- En caso de conflicto, prevalece el codigo legacy runtime hasta que exista decision explicita de migracion y rollout backward-compatible.

| Legacy runtime code | AUTH alias (doc-only) | Uso |
| --- | --- | --- |
| `INVALID_CREDENTIALS` | `AUTH_001` | Referencia documental, no emitido por runtime |
| `USER_NOT_FOUND` | `AUTH_002` | Referencia documental, no emitido por runtime |
| `USER_INACTIVE` | `AUTH_003` | Referencia documental, no emitido por runtime |
| `ACCOUNT_LOCKED` | `AUTH_004` | Referencia documental, no emitido por runtime |
| `ACCOUNT_EXPIRED` | `AUTH_005` | Referencia documental, no emitido por runtime |
| `RATE_LIMIT_EXCEEDED` | `AUTH_006` | Referencia documental, no emitido por runtime |
| `SERVICE_UNAVAILABLE` | `AUTH_007` | Referencia documental, no emitido por runtime |
| `TOKEN_EXPIRED` | `AUTH_008` | Referencia documental, no emitido por runtime |
| `REFRESH_TOKEN_EXPIRED` | `AUTH_009` | Referencia documental, no emitido por runtime |
| `TOKEN_INVALID` | `AUTH_010` | Referencia documental, no emitido por runtime |
| `SESSION_EXPIRED` | `AUTH_011` | Referencia documental, no emitido por runtime |
| `PERMISSION_DENIED` | `AUTH_012` | Referencia documental, no emitido por runtime |
| `INVALID_EMAIL` | `AUTH_013` | Referencia documental, no emitido por runtime |
| `VALIDATION_ERROR` | `AUTH_014` | Referencia documental, no emitido por runtime |
| `CODE_EXPIRED` | `AUTH_015` | Referencia documental, no emitido por runtime |
| `INVALID_CODE` | `AUTH_016` | Referencia documental, no emitido por runtime |
| `PASSWORD_TOO_WEAK` | `AUTH_017` | Referencia documental, no emitido por runtime |
| `TERMS_NOT_ACCEPTED` | `AUTH_018` | Referencia documental, no emitido por runtime |
| `ONBOARDING_FAILED` | `AUTH_019` | Referencia documental, no emitido por runtime |
| `INTERNAL_SERVER_ERROR` | `AUTH_020` | Referencia documental, no emitido por runtime |

| Code | Status HTTP observado |
| --- | --- |
| `INVALID_CREDENTIALS` | 401 |
| `USER_NOT_FOUND` | 404 |
| `USER_INACTIVE` | 403 |
| `ACCOUNT_LOCKED` | 423 |
| `ACCOUNT_EXPIRED` | 401 |
| `RATE_LIMIT_EXCEEDED` | 429 |
| `SERVICE_UNAVAILABLE` | 503 |
| `TOKEN_EXPIRED` | 401 |
| `REFRESH_TOKEN_EXPIRED` | 401 |
| `TOKEN_INVALID` | 401 |
| `SESSION_EXPIRED` | 401 |
| `PERMISSION_DENIED` | 403 |
| `INVALID_EMAIL` | 400 |
| `VALIDATION_ERROR` | 400 |
| `CODE_EXPIRED` | 400 |
| `INVALID_CODE` | 400 |
| `PASSWORD_TOO_WEAK` | 400 |
| `TERMS_NOT_ACCEPTED` | 400 |
| `ONBOARDING_FAILED` | 500 |
| `INTERNAL_SERVER_ERROR` | 500 |

### Resolution guidance (cliente)

Acciones recomendadas para clientes al recibir errores auth-access. Esta guia es operacional y no cambia el contrato runtime actual.

| Code | Resolution guidance (que debe hacer el cliente) |
| --- | --- |
| `INVALID_CREDENTIALS` | Mostrar mensaje de credenciales invalidas y permitir reintento inmediato sin invalidar estado local. |
| `USER_NOT_FOUND` | Mostrar error contextual, evitar enumeracion de usuarios en UI publica y ofrecer canal de soporte si aplica. |
| `USER_INACTIVE` | Bloquear reintentos automaticos y dirigir a contacto con administrador/soporte. |
| `ACCOUNT_LOCKED` | Bloquear login temporalmente, mostrar tiempo de espera (si existe) y sugerir recuperacion de cuenta. |
| `ACCOUNT_EXPIRED` | Cerrar flujo actual y redirigir a soporte/mesa de ayuda para reactivacion. |
| `RATE_LIMIT_EXCEEDED` | Aplicar backoff en cliente, deshabilitar boton temporalmente y reintentar luego del cooldown. |
| `SERVICE_UNAVAILABLE` | Mostrar estado transitorio, no borrar sesion local por defecto y habilitar retry manual. |
| `TOKEN_EXPIRED` | Intentar refresh una vez si corresponde; si falla, limpiar sesion local y redirigir a login. |
| `REFRESH_TOKEN_EXPIRED` | Limpiar sesion local y redirigir a login solicitando autenticacion nuevamente. |
| `TOKEN_INVALID` | Limpiar sesion local inmediatamente y redirigir a login (token no recuperable). |
| `SESSION_EXPIRED` | Limpiar sesion local y redirigir a login con mensaje de sesion expirada. |
| `PERMISSION_DENIED` | Mantener sesion, ocultar/inhabilitar accion no autorizada y mostrar feedback de permisos insuficientes. |
| `INVALID_EMAIL` | Marcar campo email, mostrar validacion inline y no enviar reintentos hasta correccion. |
| `VALIDATION_ERROR` | Mostrar errores de formulario por campo y mantener inputs para correccion del usuario. |
| `CODE_EXPIRED` | Pedir nuevo codigo de recuperacion y reiniciar contador/flujo OTP. |
| `INVALID_CODE` | Permitir reintento controlado de OTP y advertir intentos restantes si aplica. |
| `PASSWORD_TOO_WEAK` | Mostrar criterios de password en UI y bloquear submit hasta cumplir politicas. |
| `TERMS_NOT_ACCEPTED` | Bloquear onboarding hasta aceptar terminos; conservar contexto del formulario. |
| `ONBOARDING_FAILED` | Mantener datos ingresados cuando sea seguro, mostrar error general y permitir reintento/manual support fallback. |
| `INTERNAL_SERVER_ERROR` | Mostrar mensaje generico, registrar `requestId` si viene en payload y habilitar reintento manual. |

### Backend checklist por endpoint (BD + auditoria)

#### POST `/auth/login`
- Lee BD: `sy_usuarios`, `det_usuarios`, `rel_usuario_roles`, `cat_roles`, `rel_rol_permisos`, `cat_permisos`, `rel_usuario_overrides`.
- Escribe BD: `sy_usuarios.last_conexion`, `sy_usuarios.ip_ultima`, `sy_usuarios.fch_modf`, `sy_usuarios.usr_modf`.
- Auditoria: `LOGIN_SUCCESS` o `LOGIN_FAILED` con `codigo_error` si falla.

#### GET `/auth/me`
- Lee BD: mismas tablas de permisos/roles que login.
- Escribe BD: no aplica.
- Auditoria: `SESSION_VALIDATE` (success/fail).

#### GET `/auth/capabilities`
- Lee BD: mismas tablas de permisos/roles que `/auth/me` (misma proyeccion backend).
- Escribe BD: no aplica.
- Auditoria: `CAPABILITIES_READ` (success/fail).

#### POST `/auth/logout`
- Lee BD: no aplica.
- Escribe BD: no aplica.
- Auditoria: `LOGOUT`.

#### GET `/auth/verify`
- Lee BD: no aplica.
- Escribe BD: no aplica.
- Auditoria: `TOKEN_VERIFY` (opcional).

#### POST `/auth/refresh`
- Lee BD: no aplica (token via cookies).
- Escribe BD: no aplica.
- Auditoria: `TOKEN_REFRESH` (success/fail).

#### POST `/auth/request-reset-code`
- Lee BD: `sy_usuarios` por `correo`.
- Escribe BD: no aplica (OTP vive en Redis).
- Auditoria: `RESET_CODE_REQUESTED` (success/fail).

#### POST `/auth/verify-reset-code`
- Lee BD: `sy_usuarios` por `correo` (solo para auditoria).
- Escribe BD: no aplica (OTP vive en Redis).
- Auditoria: `RESET_CODE_VERIFIED` o `RESET_CODE_FAILED`.

#### POST `/auth/reset-password`
- Lee BD: `sy_usuarios` por token temporal.
- Escribe BD: `sy_usuarios.clave_hash`, `sy_usuarios.cambiar_clave = false`, `sy_usuarios.fch_modf`, `sy_usuarios.usr_modf`.
- Escribe BD (si devuelve sesion): `sy_usuarios.last_conexion`, `sy_usuarios.ip_ultima`.
- Auditoria: `PASSWORD_RESET_SUCCESS` o `PASSWORD_RESET_FAILED`.

#### POST `/auth/complete-onboarding`
- Lee BD: `sy_usuarios` por token temporal.
- Escribe BD: `sy_usuarios.clave_hash`, `sy_usuarios.cambiar_clave = false`, `sy_usuarios.terminos_acept = true`, `sy_usuarios.fch_terminos`.
- Escribe BD (si devuelve sesion): `sy_usuarios.last_conexion`, `sy_usuarios.ip_ultima`.
- Auditoria: `ONBOARDING_COMPLETED` o `ONBOARDING_FAILED`.

## Examples

**Login OK (200)**
```json
{
  "user": {
    "id": 1,
    "username": "jperez",
    "fullName": "Juan Perez",
    "email": "jperez@metro.cdmx.gob.mx",
    "primaryRole": "ADMIN",
    "landingRoute": "/admin",
    "roles": ["ADMIN"],
    "permissions": ["*"],
    "mustChangePassword": false,
    "requiresOnboarding": false
  },
  "requiresOnboarding": false
}
```

**Auditoria login (insert en `auditoria_eventos`)**
```json
{
  "accion": "LOGIN_SUCCESS",
  "resultado": "SUCCESS",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "actor_id_usuario": 1,
  "target_id_usuario": 1,
  "ip_origen": "192.168.1.10",
  "user_agent": "Mozilla/5.0",
  "meta": {
    "endpoint": "/auth/login"
  }
}
```

## References
- `docs/api/standards.md`
- `frontend/src/infrastructure/api/types/auth.types.ts`
- `frontend/src/infrastructure/api/utils/errors.ts`
- `frontend/src/infrastructure/api/resources/auth.api.ts`
