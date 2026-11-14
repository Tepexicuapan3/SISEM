# API Adscripción a consultorio familiar (P-03) - Contratos

> TL;DR: cada persona del expediente (trabajador de `cat_empleados` o derechohabiente de `cat_familiar`) queda adscrita a un consultorio de medicina general dentro de la clínica que le marca SERMED. Proceso nuevo de SIRES: tablas `adscripcion_*` que nacen vacías, sin leer ni migrar datos del SISEM legado.

Base URL:

```txt
/api/v1/adscripcion
```

## Convenciones

- Auth por cookies JWT HttpOnly; mutaciones (`POST`, `PATCH`) con `X-CSRF-TOKEN`.
- Payloads en `camelCase`. Errores con shape `ApiError` (`code`, `message`, `status`, `details?`, `requestId?`).
- Las reglas viven en `backend/apps/recepcion/services/adscripcion_evaluacion.py` (evaluación y sugerencia, solo lectura) y `backend/apps/recepcion/uses_case/adscripcion_usecase.py` / `adscripcion_config_usecase.py` (escrituras, transacción, auditoría). Las vistas (`views/adscripcion_views.py`) solo validan transporte y mapean.
- Comunicación cross-domain: lectura por contrato de la réplica SERMED (`vigencia_service.buscar_expediente`, alias de BD `expedientes`); las citas se cancelan con `CitasRepository` del mismo módulo de recepción.

## Permisos atómicos

| Permiso | Para qué | Depende de |
| --- | --- | --- |
| `recepcion:consultorio_familiar:read` | Ver estado, opciones, historial y citas por reagendar | — |
| `recepcion:consultorio_familiar:write` | Asignar o reasignar, reagendar, descartar | `read` |
| `recepcion:consultorio_familiar:excepcion` | Atender en un consultorio distinto al familiar (con motivo) | `read` |
| `recepcion:consultorio_familiar:todos_centros` | Operar pacientes de otro centro | `write` |
| `admin:catalogos:consultorio_familiar:config` | Equivalencias de clínica y consultorios familiares | `admin:catalogos:centros_atencion:read`, `admin:catalogos:consultorios:read` |
| `admin:reportes:adscripcion:read` | Reporte de adscritos por centro, consultorio y turno | — |

Sin `todos_centros`, quien opera solo actúa sobre pacientes cuyo centro SERMED es su centro (`DetUsuario`): si no, `403 CENTRO_NO_PERMITIDO`.

## Estados de la evaluación

`VIGENTE`, `SIN_ADSCRIPCION`, `NO_COINCIDE` (el centro SERMED cambió), `CONSULTORIO_INACTIVO`, `CLINICA_SIN_CENTRO` (falta equivalencia), `P03_INACTIVO` (el centro no tiene consultorios familiares), `NO_VIGENTE`, `SIN_DATO_EXPEDIENTE`. Requieren reasignar: `SIN_ADSCRIPCION`, `NO_COINCIDE`, `CONSULTORIO_INACTIVO`.

La búsqueda del expediente (`GET /api/v1/visits/patient-lookup`) agrega `adscripcion: AdscripcionResumen | null` a cada miembro, sin volver a consultar SERMED. Los recién nacidos provisionales usan la clínica del titular, leída en vivo.

`AdscripcionResumen`: `estado`, `requiereReasignar`, `claveClinicaSermed`, `idCentroSermed`, `centroSermed` (nombre del centro que SERMED le marca hoy), `idAdscripcion`, `idConsultorio`, `consultorio`, `numeroConsultorio`, `turno`, `idCentroAdscripcion`, `centroAdscripcion` (nombre del centro de su consultorio actual), `sinMedicoActivo` y `citasFuturas`. Con los nombres, recepción ve a qué clínica pertenece la persona y, en `NO_COINCIDE`, de cuál a cuál la cambió Capital Humano.

## Endpoints de recepción

| Método | Ruta | Permiso | Request | Response | Status |
| --- | --- | --- | --- | --- | --- |
| GET | `/pacientes/:idPaciente` | read | — | `AdscripcionPacienteResponse` | 200 |
| GET | `/opciones` | read | `?idPaciente&turnoId?` | `OpcionesAdscripcionResponse` | 200 |
| POST | `/previsualizar` | read | `{ idPaciente, consultorioId }` | `PrevisualizarAdscripcionResponse` (no escribe) | 200 |
| POST | `` (raíz) | write | `AdscribirRequest` | `AdscribirResponse` | 201, o 200 con `sinCambios: true` |
| GET | `/pacientes/:idPaciente/historial` | read | — | `{ items: Adscripcion[] }` | 200 |
| GET | `/citas-por-reagendar` | read | `?idPaciente?&centroId?` (sin filtros: las del centro de quien opera) | `{ items: CitaAfectada[] }` | 200 |
| POST | `/citas-por-reagendar/:id/descartar` | write | `{ motivo }` | `CitaAfectada` | 200 |

### Asignación por familia

Es el flujo recomendado: asigna a todo el núcleo en un solo paso.

| Método | Ruta | Permiso | Request | Response | Status |
| --- | --- | --- | --- | --- | --- |
| GET | `/familia` | read | `?noExp&turnoId?` | `FamiliaAdscripcionResponse` (**no escribe**, no registra pacientes) | 200 |
| POST | `/familia` | write | `AdscribirFamiliaRequest` | `{ resultados: [{ pkNum, idPaciente, sinCambios, adscripcion, citasCanceladas }] }` | 201 |

**`GET /familia`**

- Se busca el expediente con los miembros de baja incluidos, para mostrarlos en gris.
- `idCentroAtencion` es el centro SERMED de la familia: el del titular o, si no lo trae, el del primer miembro que lo tenga.
- Cada miembro trae:
  - `estado`, `elegible` y `razon`, que puede ser `NO_VIGENTE`, `SIN_DATO_EXPEDIENTE`, `CLINICA_SIN_CENTRO`, `P03_INACTIVO` u `OTRA_CLINICA`;
  - `preseleccionado`: es `false` si ya está en su consultorio, y solo se mueve si recepción lo marca;
  - `idAdscripcionActual` e `idConsultorioActual`;
  - `citasACancelarPorConsultorio`, con forma `{ "<consultorioId>": Cita[] }` y una entrada por cada opción.
- `opciones` sigue las mismas reglas que `/opciones`. S0 es el consultorio donde ya está alguien del expediente.
- Si no hay opciones, `motivoSinOpciones` dice por qué: `SIN_CONSULTORIOS`, `SIN_MEDICO` o `TODOS_LLENOS`.
- `familiaSeparada` vale `true` cuando el consultorio donde ya está la familia no se puede ofrecer.

Ejemplo de `POST /api/v1/adscripcion/familia`:

```json
{
  "noExp": "3498",
  "asignaciones": [
    { "pkNum": 0, "consultorioId": 42, "idAdscripcionEsperada": null, "citasACancelar": [], "fueSugerida": true },
    { "pkNum": 1, "consultorioId": 42, "idAdscripcionEsperada": 9, "citasACancelar": [501], "fueSugerida": true }
  ],
  "motivoCancelacionId": 31,
  "origen": "CHECKIN"
}
```

**`POST /familia`**, en **una sola transacción**, procesa a cada miembro en el orden recibido:

1. Lo registra como paciente si todavía no lo es, por la puerta central (`paciente_de_llave`: verifica en SERMED y no duplica). Un recién nacido provisional ya existe y no se crea.
2. Lo asigna con las mismas validaciones que `POST /adscripcion`.

Cada asignación ve a las anteriores del lote, así que la **capacidad cuenta a todo el núcleo**. Si un miembro falla, **no queda nada escrito**: ni pacientes, ni adscripciones, ni citas canceladas. El error trae `details.pkNum` del miembro que falló, y el rechazo se audita como `FAIL`.

El `pkNum` es el de SERMED (0 = titular) o el `cd_provisional` del recién nacido. Si un miembro se repite en `asignaciones`, responde `422 VALIDATION_ERROR`.

Sugerencias (`/opciones`): primero el consultorio de la familia (mismo `no_exp`, S0), luego menor carga, luego número. La carga cuenta adscripciones `ACTIVA` y excluye provisionales ya vinculados (`sw_status = B`).

Ejemplo `POST /api/v1/adscripcion`:

```json
{
  "idPaciente": 77,
  "consultorioId": 42,
  "idAdscripcionEsperada": 9,
  "citasACancelar": [501],
  "motivoCancelacionId": 31,
  "origen": "CITA",
  "fueSugerida": true,
  "observaciones": null
}
```

`idAdscripcionEsperada` y `citasACancelar` son la foto que vio el usuario en `/previsualizar`: si cambiaron entre medio, `409 ADSCRIPCION_MODIFICADA` o `409 CITAS_MODIFICADAS` (con `details.citas`). Las citas futuras de medicina general fuera del consultorio nuevo se cancelan en la misma transacción y quedan en `adscripcion_cita_afectada` como `PENDIENTE`.

## Enganches en endpoints existentes

| Endpoint | Campo nuevo | Comportamiento |
| --- | --- | --- |
| `POST /api/v1/visits` (ficha) | `excepcionConsultorioFamiliar?` | Medicina general en consultorio distinto al familiar → `409 CONSULTORIO_FAMILIAR_DIFERENTE`; con motivo y permiso `excepcion` pasa y se audita `ADSCRIPCION_EXCEPCION` |
| `POST /api/v1/citas` | `idPaciente?`, `idCitaAfectada?`, `excepcionConsultorioFamiliar?` | Misma validación; con `idCitaAfectada` la cita nueva queda ligada y la afectada pasa a `REAGENDADA` (misma transacción; tiene que ser en el consultorio de la adscripción activa) |
| Confirmar check-in por folio y por QR | `excepcionConsultorioFamiliar?` | Misma validación sobre la cita; las respuestas agregan `idPaciente` |

Regla de clínica (`WRONG_CLINIC` en `POST /api/v1/citas`, `CLINICA_NO_CORRESPONDE` y filtros del portal de citas): `CD_CLINICA` de SERMED se traduce al centro de SIRES con la equivalencia activa de `adscripcion_clinica_centro`. Sin equivalencia se compara con el id del centro (comportamiento anterior a P-03). Sin dato de clínica no se bloquea. Aplica a todos los usuarios, admin incluido, sin excepción. Fuente única: `apps/recepcion/services/clinica_paciente_service.py`. El mensaje de `WRONG_CLINIC` nombra el centro del paciente y el del consultorio (o la clave de SERMED si no tiene equivalencia), con `details`: `idCentroPaciente`, `centroPaciente` y `claveClinicaSermed`.

`details` de `CONSULTORIO_FAMILIAR_DIFERENTE`: `estado`, `idAdscripcion`, `idConsultorioFamiliar`, `idConsultorioSolicitado`, `idCentroSermed`.

## Configuración (admin)

| Método | Ruta | Request | Response | Status |
| --- | --- | --- | --- | --- |
| GET | `/config/clinicas` | — | `{ items: EquivalenciaClinica[] }` | 200 |
| POST | `/config/clinicas` | `{ claveClinicaSermed, idCentroAtencion }` (la clave debe existir en `cat_clinicas` de SERMED; el front la elige de `GET /clinicas`) | `EquivalenciaClinica` | 201 |
| PATCH | `/config/clinicas/:id` | `{ idCentroAtencion?, estaActivo? }` | `EquivalenciaClinica` | 200 |
| GET | `/config/consultorios` | `?centroId?` | `{ items: ConsultorioFamiliar[] }` (con `carga`) | 200 |
| POST | `/config/consultorios` | `{ consultorioId, capacidadMaxima? }` | `ConsultorioFamiliar` | 201 |
| PATCH | `/config/consultorios/:id` | `{ capacidadMaxima?, estaActivo? }` | `ConsultorioFamiliar` | 200 |

Pantalla: `/admin/catalogos/consultorio-familiar`.

## Reporte de adscritos (admin)

Solo lectura, permiso `admin:reportes:adscripcion:read`. Cuenta adscripciones `ACTIVA`; titular es `pk_num = 0` y todo lo demás (familiares, familiares sin PK_NUM, recién nacidos provisionales) es familiar.

Los centros que se ven los decide el alcance del usuario (`centro_scope.alcance_de`), no `todos_centros`: su centro, o todos con `alcance:centros:todos`. Sin centro asignado no ve nada. Pedir un `centroId` fuera del alcance → `403 CENTRO_NO_PERMITIDO`.

| Método | Ruta | Request | Response | Status |
| --- | --- | --- | --- | --- |
| GET | `/reporte/resumen` | `?centroId?` | `ResumenAdscripcionResponse` | 200 |
| GET | `/reporte/adscritos` | `?centroId?&consultorioId?&turnoId?&tipo?&q?&page?&pageSize?` | `AdscritosResponse` (paginado) | 200 |
| GET | `/reporte/adscritos?export=xlsx` | mismos filtros (sin paginar) | Excel con hojas `Resumen` y `Adscritos` | 200 |

- `resumen`: `{ centros: [{ idCentroAtencion, centro, titulares, familiares, total, consultorios: [{ consultorioId, consultorio, numero, turnoId, turno, titulares, familiares, total, capacidadMaxima, estaActivo, medicos }] }], totales }`. Incluye los consultorios familiares en cero y los que tienen adscritos aunque ya no estén configurados (`estaActivo: false`). `medicos` son los de `RelMedicoConsultorio` vigentes hoy.
- `adscritos`: `tipo` es `TITULAR` o `FAMILIAR`; `q` busca en nombre y expediente; `pageSize` máximo 100 (default 20). Cada consulta se audita como `ADSCRIPCION_REPORTE_LISTAR` con los filtros, el alcance y el total en `meta`; el resumen (solo conteos) no se audita. La exportación trae todas las filas que cumplen los filtros y se audita como `ADSCRIPCION_REPORTE_EXPORTAR`.

Pantalla: `/admin/reportes/adscripcion` (Reportes y Analítica Operativa → Padrón de adscripción).

## Errores

| Código | Status | Cuándo |
| --- | --- | --- |
| `VALIDATION_ERROR` | 422 | Payload inválido |
| `PERMISSION_DENIED` | 403 | Falta el permiso atómico |
| `CENTRO_NO_PERMITIDO` | 403 | Paciente de otro centro sin `todos_centros` |
| `EXCEPCION_NO_PERMITIDA` | 403 | Pide excepción sin el permiso |
| `PACIENTE_NO_ENCONTRADO` | 404 | — |
| `PACIENTE_NO_VIGENTE` | 409 | Sin vigencia en SERMED |
| `CONSULTORIO_NO_ELEGIBLE` | 422 | No es familiar activo del centro SERMED del paciente |
| `CONSULTORIO_LLENO` | 409 | Llegó a `capacidadMaxima` |
| `MOTIVO_REQUERIDO` | 422 | Cancela citas sin motivo / descarta sin motivo |
| `ORIGEN_INVALIDO` | 422 | — |
| `ADSCRIPCION_MODIFICADA` / `CITAS_MODIFICADAS` | 409 | Concurrencia (ver arriba) |
| `CONSULTORIO_FAMILIAR_DIFERENTE` | 409 | Ficha/cita/check-in fuera del consultorio familiar |
| `CITA_AFECTADA_NO_ENCONTRADA` | 404 | — |
| `CITA_AFECTADA_RESUELTA` | 409 | Ya reagendada o descartada |
| `CITA_DE_OTRO_PACIENTE` | 422 | La cita nueva no es del paciente |
| `CITA_YA_USADA` | 409 | La cita nueva ya reagenda otra |
| `CLAVE_REQUERIDA` / `CAPACIDAD_INVALIDA` | 422 | Configuración |
| `CLAVE_NO_EXISTE_SERMED` | 422 | La clave no está en `cat_clinicas` de SERMED |
| `CATALOGO_SERMED_NO_DISPONIBLE` | 503 | La réplica de SERMED no respondió; no se guarda la equivalencia |
| `CLAVE_DUPLICADA` / `CONSULTORIO_YA_CONFIGURADO` | 409 | Configuración |
| `CENTRO_NO_ENCONTRADO` / `EQUIVALENCIA_NO_ENCONTRADA` / `CONSULTORIO_NO_ENCONTRADO` / `CONFIGURACION_NO_ENCONTRADA` | 404 | Configuración |

## Auditoría

`log_event` con `actor`, `timestamp`, `action`, `resource`, `result`, `requestId`, `ip`, `userAgent` y, en mutaciones, `beforeState`/`afterState`. Acciones: `ADSCRIPCION_ASIGNAR`, `ADSCRIPCION_REASIGNAR`, `ADSCRIPCION_EXCEPCION`, `ADSCRIPCION_REAGENDAR`, `ADSCRIPCION_DESCARTAR_CITA`, `ADSCRIPCION_EQUIVALENCIA`, `ADSCRIPCION_CONSULTORIO`, `ADSCRIPCION_REPORTE_LISTAR` y `ADSCRIPCION_REPORTE_EXPORTAR` (lectura masiva). Los rechazos de negocio se auditan con `FAIL` fuera de la transacción.

## Datos y concurrencia

- `adscripcion_paciente`: una sola `ACTIVA` por paciente (índice único parcial). En PostgreSQL un trigger impide `DELETE` y cambios a una `CERRADA`; la vista `adscripcion_paciente_cambios` (con `LAG`) es la bitácora de cambios de clínica y consultorio.
- Asignar bloquea la adscripción activa y las citas a cancelar (`SELECT ... FOR UPDATE`) dentro de `transaction.atomic()`; no se bloquean tablas de otros dominios.
