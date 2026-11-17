# Crónicos — Entrega 4: el padrón como lista de trabajo

Estado: en curso (2026-11-17). Rama `SISEM-15-07-2026`.
Sigue a [cronicos-alta-padron.md](cronicos-alta-padron.md). Sale de la revisión
funcional de crónicos del 2026-11-17 (hallazgos A1, B4, B6 y 13).

## Qué resuelve

| # | Hueco | Consecuencia hoy |
|---|---|---|
| A1 | "Registrar control" aparece con la consulta sin iniciar o ya cerrada | El médico captura valores y recibe un 409; pierde lo escrito |
| B4 | Nadie ve a los pacientes con control vencido | "Control vencido" solo aparece si el paciente vuelve a consulta |
| B6 | El listado solo filtra por expediente y estado | No hay "mis diabéticos", ni búsqueda por nombre |
| 13 | El origen del diagnóstico se guarda pero no se ve | Sin trazabilidad visible |

Regla: **solo agregar**. Sin los filtros nuevos, el listado responde lo mismo
que hoy; los campos nuevos del contrato son opcionales para quien no los lea.
No hay migración ni escritura de datos.

## Diseño

| Pieza | Decisión | Qué NO cambia |
|---|---|---|
| Panel de control | Campo nuevo `visitInConsultation`. La pantalla solo muestra la captura si es `true`; si no, explica "Inicia la consulta para registrar el control" | `canRegister`, el POST y su 409 |
| Programa en el listado | Cada inscripción de crónicos trae `program` (o `null`) con la regla de prefijos existente. Un CIE redactado no muestra programa | Las filas y su orden |
| Último control | `lastControl`: fecha, estado, próximo control y `overdue` del último control del paciente **en ese programa** | El registro del control |
| Filtros nuevos (opcionales) | `program=<clave>`, `control=vencido\|al_dia\|sin_control`, `search=<nombre>` (todas las palabras, en nombre y apellidos) | `noExp`, `pkNum`, `centerId`, `status`, la paginación |
| Catálogo de programas | `GET padrones/cronicos/programas` (activos, con `clinico:padrones:read`) para el selector | — |
| Pantalla | Selectores Programa y Control, búsqueda por nombre, columnas Programa, Control y Origen (solo en Crónicos) | Pestaña Discapacidad, alta y baja |

### Situación del control (`control`)

| Valor | Cuándo |
|---|---|
| `vencido` | El último control del programa tiene `próximo control` anterior a hoy |
| `al_dia` | El último control tiene `próximo control` hoy o después |
| `sin_control` | El CIE pertenece a un programa y nunca se registró control |

Un CIE fuera de los programas no entra en ningún valor de este filtro.
`program` y `control` solo existen en Crónicos: en Discapacidad dan 422.

## Fuera de esta entrega (pendiente de decisión)

- **A3 — alcance por centro del listado.** Hoy quien tiene
  `clinico:padrones:read` ve todas las clínicas. Restringirlo cambia quién ve
  qué: lo decide la Gerencia. PROPUESTA: solo su centro por omisión y un permiso
  `clinico:padrones:todos_centros` para jefatura y nivel central.
- **A2 — usuario sin centro** al inscribir (selector de centro o exigir centro).

## Tareas (TDD: pruebas primero)

1. [x] Pruebas backend (`test_gestion_padron.py`, 11): programa y último control en el contrato, filtros `program`/`control`/`search`, 422 en discapacidad, catálogo de programas, `visitInConsultation`. Rojo: 10 fallan, "sin filtros no cambia" pasa.
2. [x] Caso de uso, vista y ruta: `apps.padrones` 69/69 con el venv (las 58 anteriores sin cambios). El programa y el último control salen de subconsultas en la misma consulta del listado (sin N+1).
3. [x] Pruebas de UI (rojo → verde): `PadronesPage.ui.test.tsx` (4) y un caso nuevo en `ChronicControlPanel.ui.test.tsx`.
4. [x] Frontend: tipos, API, hooks, panel y listado. El panel se vuelve a pedir al cambiar el estado de la visita (llave con el estado), así que aparece la captura al iniciar la consulta. Sin `visitInConsultation` (respuesta anterior) se comporta como antes. tsc y eslint limpios.
   De paso: `test/unit/padrones/padrones.test.ts` fallaba desde la entrega 3 (el esquema exige `pkNum`); se corrigió la prueba y se agregó el caso "sin persona no hay alta".
5. [ ] Prueba manual en el navegador (usuario).

Nota: el filtro por programa usa `LIKE` con el prefijo; en SQLite está probado. En
PostgreSQL es el mismo SQL estándar, pero no se corrió con `TESTS_EN_POSTGRES=1`
(no hay Docker en desarrollo).
