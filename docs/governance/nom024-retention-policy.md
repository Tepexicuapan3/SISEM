# Política de retención de expedientes y auditoría (NOM-024-SSA3 / Ley General de Salud)

> TL;DR: SISEM debe conservar el expediente clínico un mínimo de 5 años desde el último acto
> médico, y algunos documentos de forma indefinida. Los eventos de auditoría son append-only y
> no se purgan por antigüedad. Este documento fija esas reglas explícitamente porque hoy no
> existían en ningún lado del repo.

## Problem / Context

La revisión de cumplimiento NOM-024-SSA3 encontró que SISEM no tenía ninguna política de
retención documentada, a pesar de que:

- La Ley General de Salud (art. 8 del Reglamento de la Ley General de Salud en Materia de
  Prestación de Servicios de Atención Médica) exige conservar el expediente clínico **mínimo 5
  años** contados a partir de la fecha del último acto médico registrado.
- La NOM-004-SSA3-2012 (expediente clínico) exige que ciertos documentos —consentimientos
  informados, cartas de alta voluntaria, actas de defunción— se conserven de forma indefinida o
  por plazos mayores, incluso si el resto del expediente ya cumplió los 5 años.
- NOM-024-SSA3 exige que el sistema de auditoría (ver `AuditoriaEvento`,
  `backend/apps/administracion/models/auditoria_evento.py`) sea confiable y no manipulable, lo
  que en la práctica implica que sus registros tampoco se borran por antigüedad salvo un proceso
  de archivo controlado.

Sin esta política escrita, cualquier trabajo futuro de "limpieza de datos viejos", purga
automática o migración/decomisión del legado corre el riesgo de borrar información que la ley
obliga a conservar.

## Solution / Implementation

### Retención mínima por tipo de dato

| Dato | Retención mínima | Base legal / justificación |
|---|---|---|
| Expediente clínico (consultas, notas, diagnósticos) | 5 años desde el último acto médico | Reglamento LGS en Materia de Prestación de Servicios de Atención Médica, art. 8 |
| Consentimientos informados, altas voluntarias, actas de defunción | Indefinido | NOM-004-SSA3-2012 |
| Licencias médicas / incapacidades (`dnt_licencias_medicas`) | 5 años (parte del expediente) | Mismo criterio que expediente clínico |
| Fotos de credenciales (`dnt_fotos_credenciales`) | Vigencia del empleado/familiar + 5 años tras baja | Alineado a retención del expediente administrativo asociado |
| Eventos de auditoría (`auditoria_eventos`) | No se purgan por antigüedad; solo archivo (mover a almacenamiento frío), nunca borrado | NOM-024-SSA3: trazabilidad/no repudio |
| Catálogos (CIE-10, CIE-9-MC, etc.) | Sin vencimiento; versión histórica se conserva vía `is_active`/`deleted_at`, nunca DELETE físico | Trazabilidad de qué código estaba vigente en cada consulta histórica |

### Reglas operativas

- **Nunca `DELETE` físico** sobre expediente clínico, licencias médicas o auditoría. El
  mecanismo correcto es soft-delete (`deleted_at`/`est_activo`, ya presente en `CatalogBase`,
  `backend/apps/catalogos/models/base.py`) o archivo a almacenamiento frío tras cumplir el plazo
  legal, nunca un `DELETE` que impida una auditoría o un requerimiento legal posterior.
- **La migración desde el legado (java-main) no debe usarse como excusa para "no traer todo".**
  Si una tabla legado tiene registros dentro de la ventana de retención legal (5 años hacia
  atrás desde hoy), es obligatorio migrarla o, como mínimo, mantener un respaldo verificado
  accesible (ver `docs/runbooks/legacy-backup-runbook.md`) antes de decomisionar el servidor de
  origen.
- **Decomisión de servidores legado**: solo procede después de (a) respaldo completo verificado
  (`legacy-backup-runbook.md`), (b) confirmación de que todo dato dentro de la ventana de
  retención legal ya fue migrado o el respaldo es recuperable, y (c) sign-off explícito de quien
  sea responsable de cumplimiento normativo en la institución — esto no lo puede decidir
  unilateralmente el equipo técnico.
- **Auditoría de acceso a expedientes**: dado que `AuditoriaEvento` ya captura
  `datos_antes`/`datos_despues` en operaciones críticas, cualquier lectura o cambio sobre datos
  de `cat_empleados`/`cat_familiar`/`dnt_licencias_medicas` debe pasar por un flujo que quede
  auditado — no se debe exponer un endpoint de solo-lectura sin trazabilidad para estas tablas.

## Examples

Caso concreto que motivó este documento: al corregir el gap de DDL en
`backend/storage/expedientes-ddl/002_tablas_faltantes_expediente.sql` se encontró que
`dnt_licencias_medicas` no tenía tabla destino — es decir, las licencias médicas sincronizadas
desde Oracle probablemente no se estaban persistiendo. Bajo esta política, eso no es solo un bug
técnico: es una posible violación de la obligación de conservar ese dato por 5 años. Cualquier
gap de este tipo que se detecte a futuro debe tratarse con la misma prioridad.

## References

- `backend/apps/administracion/models/auditoria_evento.py`
- `backend/storage/expedientes-ddl/001_schema.sql`, `002_tablas_faltantes_expediente.sql`
- `docs/runbooks/legacy-backup-runbook.md`
- Reglamento de la Ley General de Salud en Materia de Prestación de Servicios de Atención Médica
- NOM-004-SSA3-2012 (Expediente clínico)
- NOM-024-SSA3 (Sistemas de información de registro electrónico para la salud)
