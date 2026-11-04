# Alcance por centro de atención

Cada usuario ve y trabaja solo la información de su centro de atención.
Primer corte: **Recepción** (fila de visitas, citas, agenda y check-in).
El expediente clínico no se restringe por centro (decisión pendiente con el
área médica).

## Conceptos

| Eje | Pregunta | Fuente |
|---|---|---|
| Permiso | ¿Qué puede hacer? | RBAC (`recepcion:citas:read`, ...) |
| Alcance | ¿Sobre qué centros? | `apps/authentication/services/centro_scope.py` |

- Hoy el alcance es el centro de adscripción del usuario
  (`det_usuarios.id_centro_atencion`). Cuando un usuario pueda tener varios
  centros cambia solo `centro_scope._centros_de`.
- **Sin centro asignado no se ve nada** (se niega por defecto).
- No se crean roles por centro.

## Permisos

| Permiso | Efecto | Asignación inicial |
|---|---|---|
| `alcance:centros:todos` | Ve y trabaja todos los centros | Ninguna (el rol administrador lo tiene por `*`) |
| `recepcion:citas:agendar_otros_centros` | Agenda y ve horarios en consultorios de otros centros. No amplía lo que ve en listas | Ninguna |

Ambos se asignan desde Administración → Roles (migración
`administracion.0020_permisos_alcance_centro`).

## Centro de cada registro

`rcp_visits.id_centro_atencion` y `citas_medicas.id_centro_atencion`
(migración `recepcion.0035`). Se fija al crear y no cambia:

1. el centro del consultorio;
2. en una cita sin consultorio, el del horario que ocupa;
3. si no hay consultorio, el centro de quien la registra.

Las filas anteriores se rellenan con el mismo criterio
(`recepcion.0036`, solo llena filas con centro vacío).

## Comportamiento de los endpoints

| Endpoint | Fuera del alcance |
|---|---|
| `GET /visits`, `GET /citas`, `GET /citas/checkin/candidatos` | No aparecen. `centroId` filtra dentro del alcance, no lo amplía |
| `GET /visits/{id}/status-log`, `PATCH /visits/{id}/status` | `404 VISIT_NOT_FOUND` |
| `GET /citas/{id}`, `PATCH /citas/{id}/estatus` | `404 CITA_NOT_FOUND` |
| `POST /citas/verificar-qr`, `/verificar-qr/confirmar`, `/checkin/confirmar-folio` | `404 CITA_NO_ENCONTRADA` |
| `GET /citas/agenda`, `GET /citas/slots` | Solo horarios de consultorios del alcance (todos con `agendar_otros_centros`) |
| `POST /visits` en consultorio de otro centro | `403 CENTRO_NO_PERMITIDO` |
| `POST /citas` en consultorio (u horario) de otro centro | `403 CENTRO_NO_PERMITIDO`, salvo `agendar_otros_centros` |
| `POST /visits` o `POST /citas` sin centro asignado | `403 CENTRO_NO_ASIGNADO` |

Un registro de otro centro responde 404 y no 403 para no revelar que existe.

`GET /visits` también lo usan enfermería y médicos: ellos también necesitan
centro asignado.

## Frontend

`/auth/me` trae `alcanceCentros` (`{ todos, centros: [{ id, nombre }] }`).
Sin centro y sin `todos`, `SinCentroAviso` (expuesto en
`domains/auth-access/contracts/navigation-auth`) explica en la agenda, fichas,
check-in QR, somatometría y consulta por qué no se ve nada. Es solo UX.

## Fuera de este corte

- Portal de Citas (el paciente agenda en cualquier centro).
- Impresión de la ficha (`apps/impresion`), que ya tenía su propio control
  por centro: pasarla a `centro_scope`.
- Número de ficha (`_calcular_num_ficha`), que se cuenta entre todos los centros.
