# Receta — tamaño A5 y cumplimiento normativo pendiente

Estado: **A1–A4 implementadas** (2026-11-05); A5 (datos de operación) pendiente del usuario. Rama `SISEM-15-07-2026`, commits locales sin
push hasta el visto bueno. Continúa [receta-diseno-stc.md](receta-diseno-stc.md)
y [receta-flujo-impresion.md](receta-flujo-impresion.md).

> Las referencias normativas son orientativas (fuentes secundarias). **Las
> valida el responsable sanitario o jurídico del STC contra el texto vigente
> del DOF** antes de dar la receta por cumplida.

## 1. Dónde estamos

| Requisito | Norma de referencia | Estado |
|---|---|---|
| Nombre, cédula y domicilio del establecimiento de quien prescribe | RIS art. 29 | ✅ (domicilio: 4 de 5 centros lo tienen cargado) |
| Fecha y hora de emisión | RIS art. 29 | ✅ |
| Firma autógrafa | RIS art. 29 | ✅ casilla en blanco |
| Denominación genérica primero | RIS art. 31 | ✅ |
| Dosis, vía, frecuencia y duración | RIS art. 30 | ✅ obligatorias desde D8 (renglones previos: texto libre) |
| CLUES del establecimiento | NOM-024 (catálogos) | ✅ (5 de 5 centros la tienen) |
| Controlados: autorización antes de imprimir | LGS 240, 251-252 + política interna | ✅ |
| Folio único, bitácora, reimpresión marcada | NOM-024 (integridad, auditoría) | ✅ |
| Sin diagnóstico impreso | LGPDPPSO (minimización) | ✅ |
| **Tamaño A5** | decisión institucional | ✅ A5 horizontal (A1) |
| **Medicamentos que no caben en la hoja** | legibilidad | ✅ 5 por hoja + hojas de continuación "Hoja i de n" (A2) |
| Edad y sexo del paciente | práctica de prescripción (dosificación) | ✅ (A3) |
| Clave del medicamento (Compendio Nacional de Insumos) | sector público | ⚠️ D2: `Medicamentos` no tiene la columna |
| Grupo del controlado y veces que se surte | LGS 251-252 | ⏸️ D9: espera a farmacia y jurídico |
| Antibióticos (retención o sello) | Acuerdo DOF 2010 | ⏸️ D7: espera a farmacia |
| CURP | — | ⏸️ D10: decisión de privacidad |
| Firma electrónica | NOM-024 / reforma LGS | ⏸️ D11: solo si la receta deja de ser papel |
| Leyenda y mensaje del pie | aviso del usuario: `receta.leyenda`, `receta.mensaje_salud` | ✅ migración `catalogos/0046` (ver §7) |

## 2. Cambios

### A1 — Hoja A5 (obligatoria)

A5 = 148 × 210 mm (419,5 × 595,3 pt). La receta del legado es apaisada:
**A5 horizontal (595,3 × 419,5 pt)** conserva la distribución actual
reduciendo ~17 % el ancho y ~14 % el alto. Ver decisión **E1** (orientación).

- `_estilos.html`: `@page { size: A5 landscape; }` y márgenes de 5–6 mm.
- Escala de tipografía y alturas: cuerpo de 8 a 7 pt; mínimo legible 6 pt en
  etiquetas; los valores (nombre, medicamento, indicaciones) **no bajan de
  7 pt**. Folio, encabezado, sello COPIA y zona de medicamentos se
  reacomodan proporcionalmente.
- Fondo: nuevo `fondos/receta-fondo-a5.jpg` compuesto desde `MetroSTC.jpg` a
  la medida exacta de la hoja (mismo método que el de 720 × 490). El de
  720 × 490 se borra cuando A5 quede aprobada.
- Sin cambios en datos, reglas, endpoint ni bitácora.

### A2 — Medicamentos que no caben (obligatoria con A1)

`build_sheets` parte los renglones en bloques de **N por hoja** (N lo fija la
prueba visual de A1; estimado 4–5 en A5). Si hay más, se agregan hojas de
continuación con el mismo folio y la leyenda **"Hoja 1 de 2"**. ORIGINAL,
COPIA y CONTROLADO se parten igual. Así nada se desborda sobre la firma.

### A3 — Edad y sexo del paciente (recomendada)

Casillas "Edad" y "Sexo" junto a la fecha de nacimiento, desde
`patient_header` (ya se lee). Sin dato nuevo ni consulta nueva.

### A4 — Motivo real cuando no se puede imprimir (recomendada)

`usePrintDocument`: para `DOCUMENT_NOT_PRINTABLE` mostrar el `message` del
backend ("La receta tiene una autorización pendiente.") en vez del genérico.
El caso de la visita 7 mostró que el genérico no dice qué hacer.

### A5 — Datos de operación (sin código)

- Domicilios: el único centro sin domicilio es "Centro Test" (prueba). Verificar el de TAXQUEÑA (igual a Cuauhtémoc), la CLUES de ZARAGOZA (`DFSSA08895`, 10 caracteres) y "ZACATENNCO" en TICOMAN.
- ~~Cargar `receta.leyenda` y `receta.mensaje_salud`~~: resuelto por `catalogos/0046` (§7); por centro, solo si alguno difiere.
- Usuarios: centro asignado; un autorizador distinto del médico que receta.

### Esperan a las áreas (no se implementan en este plan)

D2 clave del medicamento (columna + carga del Compendio), D7 antibióticos,
D9 grupo del controlado, D10 CURP, D11 firma electrónica. Siguen en
`receta-diseno-stc.md` §8.

## 3. Entrega (TDD: Red → Green → Refactor)

| Fase | Tests primero | Código | Commit |
|---|---|---|---|
| A2 | `build_sheets`: 12 renglones con N=5 → 3 hojas por tipo, "Hoja i de n", mismo folio; CONTROLADO solo con controlados y partida igual | `receta.py`, `_encabezado.html` | 1 |
| A1 | la plantilla declara `A5 landscape`; el fondo A5 existe y lo carga `safe_fetcher`; render real de 1, N y N+1 renglones sin páginas de más | `_estilos.html`, fondo A5 | 1 |
| A3 | contexto con `age`/`sex`; plantilla los muestra; vacío si no hay dato | `receta.py`, `_datos.html` | 1 |
| A4 | `usePrintDocument`: 409 `DOCUMENT_NOT_PRINTABLE` con `message` → muestra el `message` | `usePrintDocument.ts` | 1 |

Validación: backend en Docker (`apps.impresion`, receta, flujo de punta a
punta); frontend en contenedor de Node; **prueba visual en Windows y en
Docker** (Arial en desarrollo, Liberation en servidor) imprimiendo en papel A5
real antes del visto bueno.

## 4. Decisiones para arrancar

| # | Decisión | Recomendación |
|---|---|---|
| E1 | Orientación A5: horizontal (como el legado) o vertical | **Horizontal**: mismo diseño, solo más chico |
| E2 | ¿Se imprimen edad y sexo (A3)? | **Sí**: son datos de dosificación, ya se leen |
| E3 | Hojas de continuación (A2) o limitar medicamentos por receta | **Continuación**: no limita al médico |

## 5. Riesgos

| Riesgo | Mitigación |
|---|---|
| Letra demasiado chica en A5 | Mínimos de 6 pt en etiquetas y 7 pt en valores; prueba impresa en papel real |
| Impresoras configuradas en carta escalan el PDF | El PDF declara A5; en la impresora: bandeja A5 o "tamaño real" (sin "ajustar a página") |
| El fondo del Metro pierde nitidez | Se recompone a 150 dpi a la medida A5 desde el original |

## 6. Decisiones y evidencia (2026-11-05)

Decisiones del usuario: **E1 horizontal**, **E2 sí** (edad y sexo), **E3 hojas
de continuación**.

| Fase | Rojo | Verde | Commit |
|---|---|---|---|
| A2 | `ImportError ROWS_PER_SHEET`; 3 de plantilla | 54 OK (receta + flujo) | `c2e858f0` |
| A1 | 3 (A5 en la plantilla, fondo A5, proporción) | 53 OK; vista previa en Windows: 6 medicamentos → ORIGINAL 1-2, COPIA 1-2, CONTROLADO | `5481d11a` |
| A3 | `Edad` ausente | 56 OK; vista previa con nombre largo sin cortes | `b563989f` |
| A4 | 1 (motivo del backend) | 85 OK frontend; `tsc` sin errores | `55f52ade` |

Cierre: 144 tests backend OK (`apps.impresion`, receta, flujo, D8, historial).

- `ROWS_PER_SHEET = 5`: en la vista previa sobran ~40 pt al pie; se deja ese
  margen para la impresión en papel real antes de subirlo a 6.
- El fondo de 720 × 490 (`fondos/receta-fondo.jpg`) queda sin uso; se borra
  con el visto bueno del A5 impreso.
- Pendiente: prueba en **papel A5 real** con la impresora en "tamaño real" y
  la imagen del servidor (Liberation Sans).

## 7. Catálogos y pie de la receta (2026-11-10)

Revisión de solo lectura de la base de desarrollo:

| Catálogo | Hallazgo |
|---|---|
| `cat_medicamentos` | 1 registro de prueba; **no hay comando de carga**. La lista oficial la entrega farmacia junto con D2 (clave) y D9 (grupo) |
| Insumos, almacenes, mapeo medicamento → insumo | Vacíos: no afectan la impresión; sí la dispensación |
| Vías de administración | 13 opciones fijas en el código: correcto |
| Parámetros del pie | `receta.leyenda` tenía el mensaje de salud (0043) y `receta.mensaje_salud` no estaba definido |

`catalogos/0046_receta_leyenda_mensaje_salud`: define `receta.mensaje_salud`
("CUIDA TU PESO, ALIMENTATE SANAMENTE") y pone en `receta.leyenda` la nota de
surtido de la receta del legado (texto verificado en `Receta.pdf`). La leyenda
solo se corrige si conserva el valor sembrado; reversible. Rojo: 6 fallas en
`test_parametros`; verde: 150 OK (parámetros, impresión, receta).
