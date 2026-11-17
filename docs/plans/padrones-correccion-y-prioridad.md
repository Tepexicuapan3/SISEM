# Padrones — Entrega 5: corregir una inscripción y ordenar por prioridad

Estado: en curso (2026-11-17). Rama `SISEM-15-07-2026`.
Sigue a [cronicos-gestion-padron.md](cronicos-gestion-padron.md).

## Qué resuelve

| # | Hueco | Consecuencia hoy |
|---|---|---|
| C1 | No hay forma de corregir una inscripción mal capturada (CIE, fecha u observaciones) | Hay que dar de baja y volver a inscribir a mano: dos pasos, se puede quedar a medias y la baja no dice qué la sustituye |
| C2 | El listado de crónicos se ordena por fecha de inscripción | Los pacientes con control vencido quedan mezclados; la lista de trabajo no dice a quién buscar primero |

Regla: **solo agregar**. La inscripción no se edita: corregir es una baja con
motivo "Registro erróneo" más una inscripción nueva, en una sola transacción.
Sin el parámetro nuevo `order`, el listado responde igual que hoy.
No hay migración ni escritura de datos existentes.

## Diseño

### C1 — Corrección

`POST padrones/<registry>/<id>/correccion` (`clinico:padrones:write`, CSRF).

| Campo | Regla |
|---|---|
| `itemId` | Opcional; vacío = el mismo padecimiento |
| `enrolledOn` | Opcional; vacío = la misma fecha. No futura ni anterior al nacimiento |
| `notes` | Opcional; ausente = las mismas observaciones |
| `detail` | Obligatorio (qué se corrigió y por qué), queda en la baja |

| Decisión | Por qué |
|---|---|
| La inscripción original queda de baja con motivo "Registro erróneo" (catálogo existente), fecha de hoy y detalle "Corregida por la inscripción #N: …" | El historial muestra qué se capturó mal y qué lo sustituye |
| La nueva conserva paciente, centro, origen y visita | Corregir el dato no cambia de dónde salió el diagnóstico. Cambio de paciente o de centro: baja + alta normales |
| Sin cambios en `itemId`, `enrolledOn` ni `notes` → 422 | Una corrección vacía solo ensucia el historial |
| Inscripción ya dada de baja → 409; si el CIE nuevo ya está activo para el paciente → 409 y no se hace nada | La transacción revierte la baja |
| CIE restringido que el usuario no puede ver → 403 | No se corrige lo que no se ve |
| Si el motivo "Registro erróneo" no existe o está inactivo → 409 | Lo configura el administrador de catálogos |
| Concurrencia: `select_for_update` sobre la inscripción original | Dos correcciones a la vez: la segunda ve la baja y recibe 409 |
| Auditoría: evento `RegistryEnrollmentCorrected` sobre la original, con antes/después e id de la nueva | Contrato mínimo de auditoría |

Respuesta: 201 con la inscripción nueva (mismo contrato del listado).

### C2 — Orden por prioridad

Parámetro opcional `order=prioridad` (solo crónicos; en discapacidad, 422).
Orden: control vencido → sin control (con programa) → al día → sin programa →
dadas de baja. Dentro de cada grupo, el próximo control más antiguo primero y
luego la inscripción más reciente. Sin `order`, el de siempre (inscripción más
reciente).

La pantalla agrega el selector "Orden" en Crónicos, con "Prioridad de control"
por omisión.

## Tareas (TDD: pruebas primero)

1. [x] Pruebas backend (`test_correccion_prioridad.py`, 16): corrección (CIE, fecha, notas, sin cambios, ya de baja, duplicado, restringido, sin motivo, permiso, discapacidad, auditoría por API) y orden por prioridad (y 422 en discapacidad). Rojo: `correct` y `order` no existían.
2. [x] Caso de uso (`padron_usecase.correct`, `_priority_order`), serializer, vista y ruta: `apps.padrones` 91/91 con el venv (las 75 anteriores sin cambios).
3. [x] Pruebas de UI (rojo → verde): `CorrectPadronDialog.ui.test.tsx` (3) y 2 casos nuevos en `PadronesPage.ui.test.tsx`.
4. [x] Frontend: tipos, API, `useCorrectPadron`, `CorrectPadronDialog`, selector "Orden" y botón "Corregir" (no aparece en bajas ni en diagnósticos restringidos). tsc y eslint limpios.
5. [ ] Prueba manual en el navegador (usuario).

Nota: el orden usa `CASE` sobre las subconsultas del listado y `NULLS LAST`; probado en
SQLite, no con `TESTS_EN_POSTGRES=1`.
