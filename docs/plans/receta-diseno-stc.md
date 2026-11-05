# Receta médica — diseño del formato STC

Estado: **F0–F3 implementadas** en `SISEM-15-07-2026` (2026-11-04), commit
local **sin push** hasta el visto bueno tras probarlo. Pendiente: F4 (ajuste
con la imagen reconstruida, que trae Liberation Sans) y F5 (decisiones D1–D7).

## 1. Objetivo y alcance

Que el PDF de la receta que genera SIRES se vea como el formato en papel del
STC (`Receta.pdf` de referencia): hoja de 720 × 490 pt horizontal, fondo con el
logo del Metro, casillas de formulario, microtexto de seguridad y sello
"COPIA" en la segunda hoja.

Reglas de alcance:

- **Solo presentación y armado de datos de la receta.** No cambian las reglas
  de imprimibilidad (consulta cerrada, nota no cancelada, autorización), ni el
  endpoint, ni el permiso `documentos.receta.imprimir`, ni la bitácora.
- **Mismo motor.** WeasyPrint vía `apps/impresion/engine.render_pdf`; el
  registry sigue con una sola clave `receta`.
- **Sin legado en ejecución.** El `.jrxml` y el PDF de referencia solo sirven
  para copiar el diseño. No se replican los tokens cifrados del pie
  (`JcHGdrLlsSg= & …`) ni se leen tablas del SISEM viejo.
- **Datos que no existen hoy se imprimen como casilla vacía** hasta que se
  decida su origen (sección 8). No se inventan.
- Dominio dueño: **consulta_medica** (builder y plantillas). `impresion` solo
  aporta el motor, la hoja de estilo base y los recursos estáticos.

## 2. Lo que se reutiliza

| Pieza existente | Uso |
|---|---|
| `apps/impresion/engine.render_pdf` | render HTML → PDF |
| `apps/impresion/services/safe_fetcher.py` | solo carga recursos de `static/impresion/` |
| `apps/impresion/services/barcode.code128_data_uri` | código de barras del folio |
| `apps/impresion/static/impresion/css/base.css` | fuente Liberation Sans (métrica de Arial) y pie de impresión |
| `print_document_usecase` | ya agrega `printed_at`, `institution_name`, `logo_uri`, `watermarks`, `copy_number` |
| `consulta_medica/impresion/receta.py` | `build_receta_context` y `build_sheets` (se extienden) |
| `impresion/services/patient_header.get_patient_header` | apellidos separados y `birth_date` |
| `CatCentroAtencion` | `address`, `neighborhood`, `municipality`, `postal_code`, `city`, `state` |
| `get_param("receta.leyenda")` | nota al pie |

## 3. Estructura de plantillas

La plantilla única `consulta_medica/impresion/receta.html` se divide en hojas
y bloques. La hoja que usa cada página la decide el builder (`build_sheets`),
no la plantilla.

```
backend/apps/consulta_medica/templates/consulta_medica/impresion/receta/
├── documento.html        ← la que apunta el registry; recorre sheets
├── _estilos.html         ← @page y CSS del formato
├── bloques/
│   ├── _encabezado.html  (fecha de impresión, código de barras, folio, FN, tipo)
│   ├── _datos.html       (unidad, dirección, Día/Mes/Año, paciente, expediente)
│   ├── _medicamentos.html (zona de alto fijo + microtexto)
│   ├── _indicaciones.html
│   └── _firma.html       (médico, D.G.P., clave, leyenda, mensaje)
└── hojas/
    ├── normal.html       (ORIGINAL y COPIA; transcripción la comparte por ahora)
    └── controlado.html   (sin indicaciones generales)

backend/apps/impresion/static/impresion/fondos/receta-fondo.jpg
```

- `receta-fondo.jpg`: generado a partir de `MetroSTC.jpg` (carta vertical,
  816 × 1062 px) a la medida exacta de la receta, 1500 × 1021 px a 150 dpi
  (= 720 × 490 pt), con la M grande a la derecha. Se usa con
  `background: url("fondos/receta-fondo.jpg") no-repeat 0 0 / 720pt 490pt`.
- `MetroSTC.jpg` y `Receta.pdf` no se suben al repo.
- La regla "la hoja de controlado no lleva indicaciones generales" deja de ser
  un `if` en el HTML: es la composición de `hojas/controlado.html`.

## 4. Cambios en el builder (`receta.py`)

| Clave nueva en el contexto | Origen | Forma |
|---|---|---|
| `sheets[].template` | `build_sheets(rows, prescription_type)` | ruta de `hojas/*.html` |
| `sheets[].stamp` | `build_sheets` | `"COPIA"` solo en la copia |
| `issued` | `fmt_date(created_at)` | `{"d", "m", "y"}` |
| `birth` | `header["birth_date"]` | `{"d", "m", "y"}`; vacío si no hay fecha |
| `center_address` | `CatCentroAtencion` | `{"line1", "line2"}` sin partes vacías |
| `barcode_uri` | `code128_data_uri(folio)` | `""` si no hay folio |
| `microtext` | constante del módulo | texto decorativo |
| `beneficiary_type`, `doctor_key`, `items[].code` | pendiente (D2–D4) | `""` |
| `health_message` | `get_param("receta.mensaje_salud")` (D5) | `""` por defecto |

Las funciones nuevas (`_date_boxes`, `_center_address`) son puras.

## 5. Plan de entrega (TDD: Red → Green → Refactor)

Rama nueva `feat/receta-diseno-stc` desde `SISEM-15-07-2026` (no desde `main`:
`main` está 314 commits atrás y no tiene el módulo `impresion` ni el builder de
la receta), en un worktree aparte para no cambiar la rama de la carpeta que
comparten otras sesiones. Un commit por fase.

| Fase | Contenido | Resultado visible |
|---|---|---|
| F0 | Rama; `receta-fondo.jpg` en `static/impresion/fondos/` | ninguno |
| F1 | **Reorganización sin cambio visual**: tests de `build_sheets` con plantilla por hoja → división en `documento.html` + `hojas/` + `bloques/`; registry apunta a `receta/documento.html`; se borra `receta.html` | PDF idéntico al actual |
| F2 | **Datos disponibles**: tests de `_date_boxes`, `_center_address`, `barcode_uri`, `stamp` → builder | ninguno (la plantilla aún no los usa) |
| F3 | **Diseño STC**: `_estilos.html` y bloques con el formato; fondo; sello COPIA; casillas vacías para lo pendiente | PDF con el formato STC |
| F4 | **Ajuste visual en Docker** contra `Receta.pdf` (anchos, alto de la zona de medicamentos, posición del sello y del fondo) + actualización de docs | PDF final |
| F5 | (cuando se decidan D2–D5) cada dato pendiente entra con su test y su fuente | casillas llenas |

Comando para revisar el PDF en F3–F4 (contexto falso, sin consulta real):

```bash
docker compose up -d backend
docker compose exec backend python manage.py shell -c "from apps.impresion.engine import render_pdf; ..."
docker compose cp backend:/tmp/receta.pdf ./receta-preview.pdf
```

## 6. Casos de prueba (se escriben primero)

`backend/apps/consulta_medica/tests/test_print_receta_nota.py`

`RecetaSheetsTests`
- sin controlados → `ORIGINAL`, `COPIA` (firma nueva con `prescription_type`).
- con controlados → agrega `CONTROLADO` solo con esos renglones.
- `ORIGINAL` y `COPIA` usan `hojas/normal.html`; `CONTROLADO` usa `hojas/controlado.html`.
- transcripción usa `hojas/normal.html` mientras no tenga hoja propia.
- solo la `COPIA` lleva `stamp = "COPIA"`.
- todas las plantillas de hoja existen (`get_template`).

`RecetaContextHelpersTests`
- `_date_boxes("07/07/1959")` → `{"d": "07", "m": "07", "y": "1959"}`.
- `_date_boxes("")` y formatos inválidos → casillas vacías.
- `_center_address` omite partes vacías; `None` → líneas vacías.

`RecetaBuilderTests`
- el contexto trae `issued`, `birth`, `center_address`, `barcode_uri`.
- `test_template_renders_sheets` sigue pasando con `receta/documento.html`.
- la hoja de controlado no imprime "Indicaciones generales"; la normal sí (si D1 las mantiene).
- el HTML de la `COPIA` contiene el sello; el `ORIGINAL` no.

Los tests ya existentes de imprimibilidad (404/409, autorización, permiso,
marca de agua por reimpresión) no cambian y deben seguir pasando.

## 7. Seguridad y auditoría

Sin cambios: el permiso, la bitácora de impresión (`PrintLog`), la marca de
agua de reimpresión y el `safe_fetcher` quedan igual. El fondo se carga como
recurso local de `static/impresion/`; no se agrega ningún origen externo.

## 8. Decisiones pendientes

| # | Decisión | Por defecto mientras tanto |
|---|---|---|
| D1 | ¿Las indicaciones generales siguen en la receta? (el formato STC no las tiene) | Se mantienen, debajo de los medicamentos |
| D2 | Clave del medicamento (`7500771166133`): `Medicamentos` no tiene ese campo. Requiere columna nueva en catálogos (otro ticket) | Casilla vacía |
| D3 | Tipo de derechohabiente ("TRABAJADOR"): no viene en `patient_header` | Casilla vacía |
| D4 | Clave del médico (`37533`) y médico/institución de transcripción | Casilla vacía; firma con el médico que atendió |
| D5 | Mensaje de salud ("CUIDA TU PESO…"): ¿parámetro `receta.mensaje_salud` por centro? | Vacío |
| D6 | "Servicio": ¿nombre del consultorio o especialidad? | Nombre del consultorio |
| D7 | Hoja de antibiótico | Fuera, como hoy (decisión 2026-10-16) |
| D8 | Vía, frecuencia y duración estructuradas (RIS art. 30) | **Resuelta 2026-11-05**: columnas `via`, `frecuencia`, `duracion` en `cns_visit_prescription_item` (migración aditiva `0068`), obligatorias para cada medicamento nuevo en `add_prescription_item`; los renglones previos quedan nulos y se imprimen como antes. Ver `receta-flujo-impresion.md` §9 |
| D9 | Grupo del controlado (estupefaciente / psicotrópico II, III, IV; LGS arts. 240, 251, 252). `Medicamentos` solo tiene `is_controlled`. Con farmacia y jurídico: veces que se surte y **bloqueo** de los que van en recetario especial COFEPRIS | Hoja CONTROLADO genérica |
| D10 | ¿CURP del paciente impresa? Identifica sin ambigüedad pero expone más datos personales (LGPDPPSO) | No se imprime |
| D11 | Firma electrónica (NOM-024 / reforma LGS de receta electrónica): solo si la receta deja de ser papel | Firma autógrafa |

## 9. Ajustes normativos aplicados (2026-11-05)

Con datos que ya existen, sin migraciones ni cambios de endpoint. **A validar
por el responsable sanitario / jurídico contra el texto vigente del DOF.**

| Requisito | Norma | Cambio |
|---|---|---|
| Hora de emisión | RIS art. 29 | `issued_time` (de `created_at`) junto a la fecha en el encabezado; la hora del pie es la de impresión |
| Firma autógrafa | RIS art. 29 | Casilla "Nombre y Firma del Médico" queda en blanco |
| Denominación genérica | RIS art. 31 | `_drug_label`: genérico en negrita arriba; nombre de catálogo (con concentración) y presentación abajo. Sin genérico, va el nombre |
| Identificación del establecimiento | NOM-024 (catálogo CLUES) | `clues` = `CatCentroAtencion.code`; se oculta si está vacío |
