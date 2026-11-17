# API Catalogos - Contratos

> TL;DR: Contratos REST del dominio Catalogos para SISEM (backend Django/DRF + frontend React), alineados con `docs/api/standards.md` y el modelo operativo domain-first.

## Scope

- Este modulo cubre catalogos funcionales (por ejemplo `areas`, `care-centers`).
- RBAC (`roles`, `permissions`, `users`) se documenta en `docs/api/modules/rbac.md`.
- Auth se documenta en `docs/api/modules/auth.md`.

Base URL:

```txt
/api/v1
```

## Convenciones obligatorias

- Recursos REST con sustantivos y metodos HTTP semanticos.
- Payloads para frontend en `camelCase`.
- Errores con shape `ApiError`: `code`, `message`, `status`, opcional `details`, opcional `requestId`.
- Mutaciones (`POST`, `PUT`, `PATCH`, `DELETE`) con `X-CSRF-TOKEN`.
- Auth por cookies JWT HttpOnly (`credentials: include` en clientes web).

## Estructura comun (catalogos CRUD)

| Metodo | Ruta | Request | Response | Status |
| --- | --- | --- | --- | --- |
| GET | `/<catalogo>` | `ListParams` | `ListResponse<T>` | 200 |
| GET | `/<catalogo>/:id` | - | `DetailResponse` | 200 |
| POST | `/<catalogo>` | `CreateRequest` | `CreateResponse` | 201 |
| PUT | `/<catalogo>/:id` | `UpdateRequest` | `UpdateResponse` | 200 |
| DELETE | `/<catalogo>/:id` | - | `SuccessResponse` | 200 |

Notas:

- `ListResponse<T>` usa `{ items, page, pageSize, total, totalPages }`.
- `DetailResponse` envuelve la entidad en clave singular (`area`, `careCenter`, etc.).
- `CreateResponse` devuelve al menos `{ id, name }`.
- `DELETE` es baja logica cuando aplique en backend.

## Catalogo: Centros de Atencion

| Metodo | Ruta | Request | Response | Status | Permiso |
| --- | --- | --- | --- | --- | --- |
| GET | `/care-centers` | `CentrosAtencionListParams` | `CentrosAtencionListResponse` | 200 | `admin:catalogos:centros_atencion:read` |
| GET | `/care-centers/:id` | - | `CentroAtencionDetailResponse` | 200 | `admin:catalogos:centros_atencion:read` |
| POST | `/care-centers` | `CreateCentroAtencionRequest` | `CreateCentroAtencionResponse` | 201 | `admin:catalogos:centros_atencion:create` |
| PUT | `/care-centers/:id` | `UpdateCentroAtencionRequest` | `UpdateCentroAtencionResponse` | 200 | `admin:catalogos:centros_atencion:update` |
| DELETE | `/care-centers/:id` | - | `DeleteCentroAtencionResponse` | 200 | `admin:catalogos:centros_atencion:delete` |

Tipos frontend relacionados:

- `frontend/src/api/types/catalogos/centros-atencion.types.ts`

## Catalogo: Areas

| Metodo | Ruta | Request | Response | Status | Permiso |
| --- | --- | --- | --- | --- | --- |
| GET | `/areas` | `AreasListParams` | `AreasListResponse` | 200 | `admin:catalogos:areas:read` |
| GET | `/areas/:id` | - | `AreaDetailResponse` | 200 | `admin:catalogos:areas:read` |
| POST | `/areas` | `CreateAreaRequest` | `CreateAreaResponse` | 201 | `admin:catalogos:areas:create` |
| PUT | `/areas/:id` | `UpdateAreaRequest` | `UpdateAreaResponse` | 200 | `admin:catalogos:areas:update` |
| DELETE | `/areas/:id` | - | `DeleteAreaResponse` | 200 | `admin:catalogos:areas:delete` |

Tipos frontend relacionados:

- `frontend/src/api/types/catalogos/areas.types.ts`

## Catalogo: CIE (diagnosticos CIE-10)

| Metodo | Ruta | Request | Response | Status | Permiso |
| --- | --- | --- | --- | --- | --- |
| GET | `/cies/` | `CiesListParams` | `CiesListResponse` | 200 | `admin:catalogos:cies:read` |
| POST | `/cies/upload/` | multipart `file` + `version` | vista previa por fila (no guarda) | 200 | `admin:catalogos:cies:create` |
| POST | `/cies/confirm/` | `{ rows }` de la vista previa | `{ inserted }` | 200 | `admin:catalogos:cies:create` |

- `GET /cies/` usa la estructura comun paginada; cada item es `{ code, name, version, isActive }`
  (la PK es `code`, no hay `id`).
- `search` busca en el servidor por clave o descripcion; la clave se guarda sin punto
  (formato DGIS) y se encuentra escrita con o sin el: `E11.9` = `E119`.
- Filtros extra: `version` (exacto, ej. `CIE-10`), `isActive`. `sortBy`: `code`, `name`, `version`, `isActive`.

Tipos frontend relacionados:

- `frontend/src/infrastructure/api/resources/catalogos/cies.api.ts`

## Errores esperados

Ademas de errores globales (`401`, `403`, `500`), catalogos puede responder:

- `400` con `VALIDATION_ERROR`.
- `404` con codigo `*_NOT_FOUND`.
- `409` con codigo `*_EXISTS`.

Ejemplo:

```json
{
  "code": "AREAS_EXISTS",
  "message": "Area already exists",
  "status": 409,
  "details": { "name": ["Duplicado"] },
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Referencias

- `docs/api/standards.md`
- `docs/api/modules/rbac.md`
- `docs/api/modules/auth.md`
- `docs/architecture/domain-map.md`
- `docs/architecture/dependency-rules.md`
- `docs/architecture/db-ownership-migration-policy.md`
