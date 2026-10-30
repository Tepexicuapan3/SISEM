# P-03 — Consultorio familiar (proceso nuevo de SIRES)

Estado: **implementado** en la rama `SISEM-15-07-2026` (2026-10-29). Tablas `adscripcion_*`; contrato en `docs/api/modules/adscripcion.md`.

## 1. Objetivo y alcance

Cada afiliación (`cns_paciente.id_paciente`) tiene **un consultorio familiar
vigente**: un consultorio de medicina general de la clínica que le marca su
expediente, con su turno. Sus consultas de medicina general (check-in y citas)
se proponen y se validan contra ese consultorio.

Reglas de alcance:

- **Proceso nuevo de SIRES.** No se lee, no se migra y no se consulta nada del
  SISEM viejo (`det_consultoriofam`, `det_agendafam`, `cat_consultorio`, JSP).
  El legado solo sirvió para entender la necesidad.
- **Tablas nuevas, vacías.** Todos los pacientes arrancan sin consultorio
  familiar y se les asigna conforme llegan.
- **Solo agregar.** No se agregan columnas a `cns_paciente` ni a
  `cat_consultorios`. Los cambios a código existente (check-in, citas) se
  proponen y se aplican con aprobación.
- **Fuente de la clínica del paciente: el expediente** (réplicas SERMED
  `cat_empleados` / `cat_familiar`, campo `cd_clinica`), leído en vivo con
  `recepcion/services/vigencia_service.buscar_fila_paciente`. SIRES no la copia
  ni la modifica.
- Solo **medicina general**. Especialidad y urgencias no cambian.
- Dominio dueño: **recepcion** (tablas, caso de uso, endpoints, migraciones).

## 2. Lo que se reutiliza de SIRES

| Pieza existente | Uso en P-03 |
|---|---|
| `Patient` (`cns_paciente`) | FK `id_paciente` de la asignación |
| `buscar_fila_paciente` / `fila_tiene_vigencia` | clínica (`CD_CLINICA`) y vigencia del expediente |
| `CatCentroAtencion` | centro de SIRES |
| `Consultorios` (`id_center`, `id_turn`, `is_active`) | consultorio; centro y turno salen de él |
| `RelMedicoConsultorio` (+ horarios) | médicos del consultorio (no se guardan en la asignación) |
| `CitaMedica` (`patient`, `consultorio`, `servicio_tipo`, `estatus`, `fecha_hora`) | citas futuras de medicina general |
| `cita_state_machine_usecase` + `CitaEstatusLog` + `MotivoCita` | cancelación de citas (desde el módulo de citas) |
| `DetUsuario.id_centro_atencion` | centro del operador |
| `authentication/services/audit_service.log_event` (`auditoria_eventos`) | auditoría con `datos_antes` / `datos_despues` |
| `administracion/migrations/*permisos*` + `permission_dependencies.py` | alta de permisos atómicos |
| `error_response` / `get_request_id` / `validate_csrf` | contrato de errores y seguridad |

## 3. Estructura de las tablas

Las cuatro tablas son de `recepcion` (migración `0032_adscripcion`), nacen
vacías y siguen la convención de autorizaciones: nombres en español,
`esta_activo`, `fecha_creacion`, `id_usuario_creacion` (id plano de usuario).

### 3.1 `adscripcion_clinica_centro` — clínica SERMED → centro SIRES

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id_clinica_centro` | bigserial | PK | |
| `clave_clinica_sermed` | varchar(10) | NOT NULL, UNIQUE, no vacía | `cd_clinica` del expediente, con `strip()` |
| `id_centro_atencion` | bigint | NOT NULL, FK `cat_centros_atencion` (PROTECT) | |
| `esta_activo` | boolean | default `true` | |
| `fecha_creacion`, `id_usuario_creacion` | | | |
| `fecha_modificacion`, `id_usuario_modificacion` | | NULL | |

Una clave apunta a un solo centro; varias claves pueden apuntar al mismo centro.
La carga el administrador en `/admin/catalogos/consultorio-familiar`.

### 3.2 `adscripcion_consultorio` — consultorios que reciben pacientes

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id_adscripcion_consultorio` | bigserial | PK | |
| `id_consultorio` | bigint | NOT NULL, FK `cat_consultorios`, UNIQUE | |
| `esta_activo` | boolean | default `true` | `false`: deja de recibir pacientes nuevos |
| `capacidad_maxima` | integer | NULL, CHECK `> 0` | tope de adscripciones activas; NULL = sin tope |
| `fecha_creacion`, `id_usuario_creacion`, `fecha_modificacion`, `id_usuario_modificacion` | | | |

Puesta en marcha por centro sin banderas: un centro sin consultorios
configurados queda en `P03_INACTIVO` (no sugiere ni valida).

### 3.3 `adscripcion_paciente` — la adscripción del paciente (y su bitácora)

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id_adscripcion` | bigserial | PK | |
| `id_paciente` | bigint | NOT NULL, FK `cns_paciente` (PROTECT) | trabajador o derechohabiente |
| `id_centro_atencion` | bigint | NOT NULL, FK | centro al adscribir |
| `clave_clinica_sermed` | varchar(10) | NOT NULL | foto de lo que decía SERMED |
| `id_consultorio` | bigint | NOT NULL, FK `cat_consultorios` | |
| `id_turno` | bigint | NOT NULL, FK `cat_turnos` | copiado del consultorio |
| `estatus` | varchar(10) | `ACTIVA` / `CERRADA` | |
| `origen` | varchar(10) | `CHECKIN` / `CITA` / `MANUAL` | |
| `fue_sugerida` | boolean | | aceptó la sugerencia |
| `motivo_cierre` | varchar(20) | `REASIGNACION` / `CAMBIO_CLINICA` / `CONSULTORIO_INACTIVO` / `UNIFICACION` | |
| `observaciones` | varchar(255) | NULL | |
| `fecha_inicio`, `fecha_fin` | timestamptz | `fecha_fin >= fecha_inicio` | |
| `id_usuario_creacion`, `id_usuario_cierre` | bigint | | |

- Índice único parcial `adscripcion_paciente_una_activa_uq`: una `ACTIVA` por paciente.
- CHECK `adscripcion_paciente_cierre_ck`: `CERRADA` ⇔ `fecha_fin`, `id_usuario_cierre` y `motivo_cierre`.
- Índices `adscripcion_paciente_carga_idx` (consultorio, solo `ACTIVA`) y `adscripcion_paciente_hist_idx`.
- Solo PostgreSQL (`0033`): trigger `adscripcion_paciente_proteger_historial` (sin `DELETE`; una `CERRADA` no cambia; en una `ACTIVA` solo los campos de cierre) y vista `adscripcion_paciente_cambios` (bitácora con `LAG`).

### 3.4 `adscripcion_cita_afectada` — citas por reagendar

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id_cita_afectada` | bigserial | PK | |
| `id_adscripcion` | bigint | NOT NULL, FK `adscripcion_paciente` | la que provocó la cancelación |
| `id_cita_cancelada` | bigint | NOT NULL, UNIQUE, FK `citas_medicas` | |
| `id_cita_nueva` | bigint | NULL, UNIQUE, FK `citas_medicas` | la reagendada |
| `estatus` | varchar(12) | `PENDIENTE` / `REAGENDADA` / `DESCARTADA` | |
| `motivo_descarte` | varchar(255) | obligatorio si `DESCARTADA` | |
| `fecha_creacion`, `fecha_resolucion` | timestamptz | | |
| `id_usuario_creacion`, `id_usuario_resolucion` | bigint | | |

Índice `adscripcion_cita_pend_idx` (solo `PENDIENTE`). La migración `0034`
siembra el motivo de cancelación "Cambio de consultorio familiar".

## 4. Comparación clínica del expediente vs. SIRES

Servicio de solo lectura `evaluar_consultorio_familiar(id_paciente)`. Se ejecuta
en vivo en check-in, al agendar una cita de medicina general y en la pantalla de
consultorio familiar.

1. Lee la fila del expediente (`buscar_fila_paciente`) → `CD_CLINICA` y vigencia.
2. Traduce `CD_CLINICA` con `adscripcion_clinica_centro` → centro SIRES.
3. Lee la asignación `ACTIVA` y el estado de su consultorio.
4. Devuelve un estado (el primero que aplique, en este orden):

| Estado | Condición | Comportamiento |
|---|---|---|
| `SIN_DATO_EXPEDIENTE` | sin fila, sin `CD_CLINICA` o SERMED no responde | no bloquea, no asigna (regla actual de SIRES) |
| `NO_VIGENTE` | expediente no vigente | no asigna (la vigencia ya bloquea la cita) |
| `CLINICA_SIN_CENTRO` | `CD_CLINICA` sin equivalencia activa | no asigna; aviso para el administrador de catálogos |
| `P03_INACTIVO` | el centro no tiene consultorios configurados | no sugiere ni valida |
| `SIN_ASIGNAR` | no hay asignación activa | sugiere consultorio; el operador confirma |
| `NO_COINCIDE` | el centro de la asignación ≠ el centro actual del expediente | advertencia con las citas del consultorio anterior; al confirmar se cancelan, se reasigna en la clínica nueva (`CAMBIO_CLINICA`) y quedan por reagendar |
| `CONSULTORIO_INACTIVO` | consultorio dado de baja o su config `activo = false` | mismo proceso de advertencia que `NO_COINCIDE` (`CONSULTORIO_INACTIVO`) |
| `VIGENTE` | todo coincide | propone su consultorio y sus médicos |

`VIGENTE` también avisa (sin bloquear) si el consultorio no tiene ningún médico
activo hoy en `RelMedicoConsultorio`.

## 5. Funcionamiento

Este funcionamiento sigue el diagrama de flujo de la usuaria (2026-10-29):
paciente → ¿tiene centro, consultorio y turno? → no: asignar con sugerencias →
sí: ¿centro = SERMED? → sí: cita en recepción; no: advertencia, cancelar citas
del consultorio anterior, asignar con sugerencias y reagendar.

**Criterios de sugerencia de turno y consultorio**, en orden: (1) centro
equivalente a la clínica de SERMED; (2) consultorio familiar configurado y
activo; (3) con al menos un médico activo en `RelMedicoConsultorio`; (4) bajo
su `capacidad_max`; (5) del turno que pida el paciente, si pide uno; (6) menor
número de pacientes activos y, si empatan, menor número de consultorio. Las
opciones se agrupan por turno.

### 5.1 Primera asignación (check-in o cita de medicina general)

1. Recepción abre al paciente y el estado sale `SIN_ASIGNAR`.
2. El backend arma las opciones por turno con los criterios de arriba, con sus
   médicos y su carga.
3. **Sugerencia:** turno y consultorio según los criterios.
4. La pantalla muestra la sugerencia y la lista. El operador **confirma o elige
   otro**. Nunca se asigna en silencio.
5. Se guarda (`origen = CHECKIN` o `CITA`, `fue_sugerida` según el caso) y el
   check-in o la cita sigue normal.

### 5.2 Operación diaria (`VIGENTE`)

- En check-in y citas de medicina general el consultorio y sus médicos vienen
  propuestos.
- Si el operador elige **otro** consultorio de medicina general, el backend
  responde `409 CONSULTORIO_FAMILIAR_DIFERENTE`. Puede seguir solo si tiene el
  permiso `recepcion:consultorio_familiar:excepcion` y manda un motivo. Queda
  auditado como `CONSULTORIO_FAMILIAR_EXCEPCION`. La asignación **no** cambia.

### 5.3 Reasignación manual (pantalla "Consultorio familiar")

1. Se busca el expediente; aparecen sus afiliaciones con estado, consultorio,
   turno, médicos y antigüedad de la asignación.
2. El operador elige turno → consultorio (solo del centro del expediente).
3. **Vista previa** (no escribe): actual vs. nuevo, y citas futuras de medicina
   general (`agendada` / `confirmada`, `fecha_hora >= ahora`).
4. Si hay citas futuras (medicina general, `agendada`/`confirmada`, a futuro)
   → **advertencia**: cuántas, fecha, médico y consultorio, y motivo obligatorio.
5. Al confirmar, en una transacción: se cancelan con
   `CitasRepository.update_estatus` (libera horario y escribe `CitaEstatusLog`),
   se cierra la activa (`REASIGNACION`), se crea la nueva y cada cita queda en
   `adscripcion_cita_afectada` como `PENDIENTE`.
6. Mismo consultorio que el actual → no escribe nada (respuesta `200`,
   `sinCambios: true`).

### 5.4 Centro distinto al de SERMED (`NO_COINCIDE`)

- La asignación vieja deja de usarse para agendar en cuanto el expediente cambia.
- Advertencia con las citas del consultorio anterior; el operador puede cancelar
  la operación sin cambios.
- Si confirma, elige turno y consultorio sugeridos en la clínica nueva. Al
  guardar se cancelan las citas, la vieja se cierra con `CAMBIO_CLINICA` y se
  crea la nueva (misma transacción que 5.3).

### 5.4 bis Reagendar en el nuevo consultorio

- Al terminar la reasignación se abre "Citas por reagendar".
- Cada cita se reagenda con `POST /citas` enviando `idCitaAfectada`; en la misma
  transacción pasa a `REAGENDADA` con `id_cita_nueva`.
- Si ya no se necesita, se marca `DESCARTADA` con motivo.
- Las pendientes se ven en la ficha del paciente y en una bandeja por centro.

### 5.5 Unificación de afiliaciones (cuando exista)

SIRES hoy no unifica afiliaciones. Cuando exista: si las dos tienen asignación
activa, la de la afiliación absorbida se cierra con `UNIFICACION` y queda la de
la sobreviviente.

## 6. Reglas de seguridad, concurrencia y auditoría

**Permisos atómicos nuevos** (alta por migración de datos en `administracion`
+ `permission_dependencies.py`):

| Permiso | Para |
|---|---|
| `recepcion:consultorio_familiar:read` | ver asignación, opciones e historial |
| `recepcion:consultorio_familiar:write` | asignar y reasignar |
| `recepcion:consultorio_familiar:excepcion` | atender en otro consultorio con motivo |
| `recepcion:consultorio_familiar:todos_centros` | operar pacientes de otro centro (perfil central) |
| `catalogos:consultorio_familiar:config` | equivalencias de clínica y configuración de consultorios |

**Centro del operador:** con `write`, solo se asignan pacientes cuyo centro (del
expediente) es el `DetUsuario.id_centro_atencion` del operador, salvo
`todos_centros`. Operador sin centro → solo con `todos_centros`.

**Confirmación atómica** (`transaction.atomic` en el caso de uso):

1. Revalida todo: vigencia, equivalencia de clínica, consultorio configurado y
   activo, centro del operador, citas futuras.
2. Concurrencia sin bloquear tablas de otros dominios:
   - Reasignación: `SELECT ... FOR UPDATE` sobre la fila `ACTIVA` del paciente y
     comparación con `idAdscripcionEsperada` que vio el operador → si cambió,
     `409 ADSCRIPCION_MODIFICADA`.
   - Primera asignación: el UNIQUE parcial; un `IntegrityError` se traduce a
     `409 ADSCRIPCION_MODIFICADA`.
   - Capacidad: `SELECT ... FOR UPDATE` sobre la fila de
     `adscripcion_consultorio` antes de contar → `409 CONSULTORIO_LLENO`.
3. Cierra la anterior, inserta la nueva y audita en la misma transacción.

**Auditoría** (`log_event`, `resource_type = "consultorio_familiar"`):
`CONSULTORIO_FAMILIAR_ASIGNAR`, `..._REASIGNAR`, `..._EXCEPCION`,
`..._CONFIG` y `..._EQUIVALENCIA`. Con `datos_antes` / `datos_despues`,
`request_id`, IP y user agent. Los intentos rechazados también se registran como
`FAIL` con su código.

## 7. API (`/api/v1/adscripcion`)

Contrato completo (rutas, payloads, permisos, errores y auditoría):
[`docs/api/modules/adscripcion.md`](../api/modules/adscripcion.md).

## 8. Enganches en código existente (con aprobación)

| Dónde | Cambio |
|---|---|
| `visit_queue_usecase.create_visit` | en medicina general, valida contra el consultorio familiar (§5.2) |
| `citas_views.CitasListCreateView.post` | misma validación |
| `visit_queue_usecase.lookup_patient` | agrega `consultorioFamiliar` por miembro, en una sola consulta (sin N+1) |
| Portal de citas (fase posterior) | en medicina general, propone primero el consultorio familiar; sin asignación no restringe |
| `follow_up_usecase` P-12 (fase posterior) | podrá proponer el médico del consultorio familiar |

## 9. Frontend

**Dónde opera (definido por la usuaria, 2026-10-29):** Recepción > Agenda >
"Generar ficha de consulta" (`RecepcionQuickCheckinDialog`). Ahí recepción ya
busca el expediente y ve la vigencia del trabajador y su núcleo familiar
(`GET /visits/patient-lookup` → `lookup_patient`). En esa búsqueda se muestran
el estado P-03 de cada persona y las advertencias, y desde ahí se asigna el
consultorio y se cancelan las citas. No hace falta pantalla aparte ni acceso a
Administración > Expedientes.

- `lookup_patient` agrega `consultorioFamiliar` por miembro (estado, consultorio,
  turno, centro, número de citas futuras MG), en una consulta por familia.
- `features/recepcion/modules/consultorio-familiar/`: etiqueta de estado, aviso,
  panel "Revisar y reasignar" (comparación → turno y consultorio → advertencia de
  citas → confirmar → seguir con la ficha), historial y "Citas por reagendar".
  Se incrustan en `RecepcionQuickCheckinDialog`.
- Miembro sin `idPaciente`: se abre con `visitsAPI.openPatient` (el mismo paso
  que ya usa el diálogo) antes de asignar.
- La preselección de centro usa la tabla puente, no `cdClinica == centro.id`
  (hoy el diálogo compara así en las líneas 226 y 339).
- "Citas por reagendar" reutiliza `SlotCalendar` y `citasAPI.create`
  (`POST /citas`, hoy sin uso en la UI de recepción); contador en `BandejaView`.
- Fase posterior: columna de solo lectura en Administración > Expedientes.
- `features/admin/modules/catalogos/consultorio-familiar/`: equivalencias de
  clínica y configuración de consultorios con su carga actual.
- Los permisos en el front solo muestran u ocultan; el backend decide.

## 10. Plan de entrega (TDD: Red → Green → Refactor)

| # | Bloque | Contenido | Commit |
|---|---|---|---|
| 0 | Preparación | ticket Jira; rama nueva desde `main` | — |
| 1 | Tests (rojo) | ver §11 | `test(recepcion): add P-03 consultorio familiar specs` |
| 2 | Modelos | 3 tablas + migración (solo `CreateModel`) | `feat(recepcion): add consultorio familiar tables` |
| 3 | Dominio | `evaluar_consultorio_familiar`, sugerencia por carga | `feat(recepcion): evaluate patient consultorio familiar` |
| 4 | Caso de uso | asignar/reasignar atómico, concurrencia, auditoría | `feat(recepcion): assign consultorio familiar` |
| 5 | API + permisos | endpoints, migración de permisos (**escritura de datos: OK previo**) | `feat(recepcion): expose consultorio familiar API` |
| 6 | Enganches | check-in, citas, `lookup_patient` (**con aprobación**) | `feat(recepcion): enforce consultorio familiar on general medicine` |
| 7 | Front admin | equivalencias y configuración | `feat(catalogos): manage consultorio familiar settings` |
| 8 | Front recepción | pantalla P-03 y tarjeta en check-in/citas | `feat(recepcion): add consultorio familiar screen` |
| 9 | Docs | `docs/api/modules/recepcion`, `docs/domains/` | `docs(recepcion): document P-03 consultorio familiar` |
| 10 | Fases posteriores | portal, P-12, reportes de carga y `NO_COINCIDE` | — |

Commits convencionales, sin atribución, solo con rutas propias
(`git commit -- <rutas>`). Tests en Docker.

## 11. Casos de prueba (se escriben primero)

Evaluación (§4):

- Cada estado de la tabla, incluido el orden de prioridad.
- SERMED caído → `SIN_DATO_EXPEDIENTE`, no bloquea.
- Expediente que cambia de clínica → `NO_COINCIDE`.

Sugerencia:

- Menor carga gana; desempate por número de consultorio.
- Excluye otros centros, consultorios inactivos, sin config y llenos.

Asignación:

- Primera asignación crea `ACTIVA` con la foto `cd_clinica_expediente`.
- Reasignación cierra la anterior con motivo y usuario; historial intacto.
- Mismo consultorio → sin escrituras.
- Citas futuras MG → `CITAS_FUTURAS_PENDIENTES`; citas pasadas o de especialidad no bloquean.
- Dos primeras asignaciones simultáneas → una gana, la otra `409`.
- `idAdscripcionEsperada` desactualizado → `409`.
- Capacidad al límite con dos operadores → `CONSULTORIO_LLENO` para uno.
- Falla a mitad (auditoría que lanza) → nada escrito.

Seguridad:

- Sin permiso → `403`; sin CSRF → `403`.
- Operador de otro centro → `CENTRO_NO_PERMITIDO`, salvo `todos_centros`.
- Excepción en check-in sin permiso o sin motivo → `409`; con ambos → pasa y se audita.

Auditoría: cada operación deja su evento con antes/después; los rechazos, como `FAIL`.

## 12. Decisiones tomadas por defecto (revisables)

| # | Decisión | Por defecto | Alternativa |
|---|---|---|---|
| 1 | Primera asignación | sugerida y confirmada por el operador | automática silenciosa |
| 2 | Citas futuras al reasignar | **fijado por el diagrama de la usuaria:** advertencia y cancelación en la misma operación, con motivo "Cambio de consultorio familiar" (alta en `MotivoCita`, requiere OK); quedan por reagendar | bloquear y cancelar desde Citas |
| 3 | Otro consultorio en check-in/cita | `409` salvo permiso de excepción + motivo | bloquear siempre |
| 4 | Quién reasigna | permiso `write` + mismo centro del operador; `todos_centros` para perfil central | solo permiso |
| 5 | Regla de sugerencia | menor carga del centro (y turno, si se indica) | sin sugerencia |
| 6 | Dónde opera | **definido:** búsqueda de expediente en Recepción > Agenda > Generar ficha de consulta | pantalla aparte |
| 7 | Recién nacidos provisionales | **definido (reemplaza "heredar la clínica del titular"):** fuera de P-03. Si `cns_paciente.cd_provisional` no es nulo, el estado es `RECIEN_NACIDO_PROVISIONAL`: no se asigna, no se avisa, no se bloquea y no se lee SERMED. No se toca `newborn_service` ni su vinculación. Entran a P-03 cuando la vinculación actual los registra con `pk_num` y `cd_clinica` | heredar la clínica del titular (descartado: obligaría a tocar la vinculación para cerrar la asignación provisional) |
