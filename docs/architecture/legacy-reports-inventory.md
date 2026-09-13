# Inventario de reportes y documentos imprimibles del legado (java-main)

> TL;DR: el legado tiene dos familias distintas de "reportes" que no hay que confundir: 22
> **documentos clínicos imprimibles** por paciente/encuentro (fichas, recetas, incapacidades,
> pases) y ~57 **reportes gerenciales** sobre rangos de fecha (estadísticas, consolidados). SISEM
> hoy no tiene un módulo de reportería dedicado para ninguna de las dos. Este documento cataloga
> ambas para poder priorizar qué construir primero.

## Problem / Context

La revisión de módulos de SISEM vs. java-main identificó "reportes/estadísticas" como un hueco
completo. Antes de diseñar algo, hacía falta saber qué existía realmente en el legado — no había
ningún inventario escrito. Se revisó `usuarios/clinicam/` (JSPs) y el "switch" central de
impresión (`pdf.domain1.jsp`) en
`C:\SISEM JAVA 8\java-main\investigacion\consolidado_assets\sisem\usuarios\clinicam`.

## Solution / Implementation

### Familia 1 — Documentos clínicos imprimibles (por paciente/encuentro)

Catálogo encontrado tal cual en el comentario de `pdf.domain1.jsp` (es el "router" central de
impresión de todo el sistema — un solo JSP con un switch numérico):

| # | Documento | Estado aproximado en SISEM hoy |
|---|---|---|
| 0 | Fichas | Parcial — `recepcion/services/ficha_service.py` ya existe |
| 1 | Receta | Parcial — `farmacia` tiene código, sin confirmar si emite receta imprimible |
| 2 | Incapacidad (Prefolio) | Parcial — `consulta_medica/uses_case/medical_leave_usecase.py` genera la incapacidad, no confirmado si imprime |
| 3 | Incapacidad (Folio) | Igual que arriba |
| 4 | Notas Clínicas | Parcial — `consulta_medica` gestiona notas, imprimible no confirmado |
| 5 | Receta Complemento | Sin equivalente confirmado |
| 6 | Pase Laboratorio | Parcial — `pases` app + catálogo `Pases` existen |
| 7 | Pase Gabinete | Parcial — igual que Laboratorio |
| 8 | Pase Hospitalización | Parcial — `pases`/`recepcion` |
| 9 | Pase Especialidad | Parcial — `pases` |
| 10 | Reporte Diario | **Sin equivalente** |
| 11 | Reporte Licencias | **Sin equivalente** (agregado; el registro individual sí existe) |
| 12 | Receta Médico Transcripción | **Sin equivalente** |
| 13 | Incapacidad Transcripción (Prefolio) | **Sin equivalente** |
| 14 | Reporte SM21 | **Sin equivalente** — formato institucional específico, confirmar vigencia antes de invertir |
| 15 | Reporte Médico Especialista | **Sin equivalente** |
| 16 | Reporte Diario 2009 | Version vieja del #10 — candidato a **no migrar** |
| 17 | Alta Médica | Parcial — `recepcion` maneja estado de visita |
| 18 | Insumo | Parcial — `almacen_insumos` app existe |
| 19 | Pase Estudios Hospital | Parcial — `pases` |
| 20 | Reimpresión de incapacidad histórica | **Bloqueado**: depende de migrar primero las licencias médicas históricas del legado (ver `docs/runbooks/legacy-backup-runbook.md`) |
| 21 | Fichas Hospital | Parcial — `recepcion` |

**Nota de rigor**: la columna "Estado" es una primera pasada por nombre de app/archivo, no una
verificación línea por línea de que el documento se pueda imprimir hoy con el formato correcto.
Antes de dar cualquiera de estos por "listo" hay que confirmarlo con el módulo real.

### Familia 2 — Reportes gerenciales/administrativos (rango de fechas)

~57 JSPs bajo `usuarios/clinicam/`, agrupados por tema (tamaño de archivo como proxy de
complejidad — más grande generalmente implica más filtros/columnas):

| Grupo | Archivos representativos | Tamaño máx. | Prioridad sugerida |
|---|---|---|---|
| Consulta médica / clínica | `body-repconsulta`, `body-repconsultamed`, `body-repclinica*`, `body-repmedica`, `body-repnotas`, `body-repcie`, `body-estcie`, `body-repcroni`, `body-repfrecuencia` | 33.8 KB (`body-repexp`) | **Alta** — `consulta_medica` ya tiene los datos base |
| Pases / hospitalización | `body-repases*`, `body-repingresados`, `body-rephospital*`, `rep-medshospital`, `body-repaltapaciente` | 22.8 KB | **Alta** — `pases`/`recepcion` ya existen |
| Farmacia / insumos | `rep-farmacia` (+4 variantes), `rep-insumos(-ant)`, `body-repins` | 29.3 KB | Media — depende de madurar `farmacia` (hoy "Discovery") |
| Incapacidades | `body-repincap*`, `rep-incap`, `rep-incap2` | 17.3 KB | Media — el dato vive parcialmente, falta el agregado |
| Medicina del trabajo ("medikos") | `body-repmedikos*`, `rep-medikos` | 20 KB | Baja — confirmar si sigue vigente ese concepto |
| Cirugías | `body-repcirugias*`, `rep-cirugias` | 18.3 KB | **Bloqueada** — el módulo de cirugías no existe todavía en SISEM |
| Discapacidad | `rep-discapacidad` | 9 KB | Baja |
| Transcripción | `rep-transcriptor`, `body-reptrans` | 19.1 KB | Baja |
| Estadísticas/gráficas generales | `body-graficas` (84 KB), `body-graficas2` (71 KB), `body-estadist`, `gengrafica(_online)` | 84.4 KB | Media — son los más grandes/complejos, mejor después de tener los reportes tabulares base |
| Exportación genérica | `body-repexp`, `dataexcel`, `nexcel`, `body-presrep`, `body-reportes`, `body-reportesmed` | 33.8 KB | N/A — es mecanismo, no reporte (ver abajo) |

### Mecanismo técnico del legado (para no copiarlo tal cual)

- **Excel**: `dataexcel.jsp`/`nexcel.jsp` no generan un `.xlsx` real — ponen
  `contentType="application/vnd.ms-excel"` sobre una tabla HTML y dejan que Excel la "adivine".
  Funciona pero es fragil (formato, tipos de dato, celdas fusionadas se pierden). SISEM ya usa
  `openpyxl` para el import de catálogos (`catalog_import_service.py`) — mejor generar `.xlsx`
  reales con la misma librería en vez de replicar el truco.
- **PDF**: pasa por `Resources/FCExporter_PDF.jsp` (componente de terceros, "Infosoft Global",
  2009). No hay equivalente moderno instalado; para PDFs reales en Django, evaluar
  `weasyprint`/`reportlab` cuando se llegue a esa fase.
- Casi todos los reportes tabulares son JSP con SQL embebido directo y un formulario de rango de
  fechas (`fe_reg1`/`fe_reg2`) — no hay lógica de negocio reutilizable que valga la pena portar
  literalmente; el valor está en saber **qué columnas/filtros** mostraba cada uno, no en el código.

## Examples

Los stored procedures ya identificados en
`investigacion/procedures/dbclinicas_procedures.sql` (`sp_rep_master`, `sp_rep_master_aux`,
`sp_rep_pivote`, `sp_vw_pacientes`, `sp_vw_medicos`, `sp_vw_pases`, `sp_citas_todos`,
`sp_status_exp`) muy probablemente respaldan varios de estos reportes — son la pista más directa
de qué columnas/joins esperaba el negocio antes de rediseñar el reporte desde cero.

## Recomendación de siguiente paso

Empezar por **Familia 2 → Consulta médica/clínica** y **Pases/hospitalización**: son los grupos
de mayor prioridad porque el dato ya existe en SISEM (`consulta_medica`, `pases`, `recepcion`) —
es "solo" construir la capa de reporte (filtros + tabla + export `.xlsx`), sin esperar a otro
módulo. Cirugías queda bloqueado hasta que exista el módulo; farmacia/insumos e incapacidades
conviene esperar a que esas apps maduren un poco más para no reportar sobre un modelo de datos
que todavía va a cambiar.

## References

- `C:\SISEM JAVA 8\java-main\investigacion\consolidado_assets\sisem\usuarios\clinicam\pdf.domain1.jsp`
- `C:\SISEM JAVA 8\java-main\investigacion\procedures\dbclinicas_procedures.sql`
- `backend/apps/catalogos/services/catalog_import_service.py` (uso existente de `openpyxl`)
- `docs/architecture/domain-map.md`
