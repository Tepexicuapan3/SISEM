# RFC Cross-Domain Template

> Usar este template cuando un cambio impacta multiples dominios, ownership de datos o contratos compartidos.

## Metadata

- RFC ID:
- Fecha:
- Autor:
- Dominios impactados:
- Cambio SDD-Orchestrator relacionado:
- Estado: Draft | Review | Approved | Rejected

## Problem / Context

Describe el problema y por que NO se puede resolver dentro de un solo dominio.

## Current State

- Contexto actual por dominio
- Dependencias existentes
- Riesgos detectados

## Proposed Change

- Cambio propuesto
- Contratos/API/DB impactados
- Estrategia de compatibilidad (`legacy`/`hybrid`/`domain-first`)
- Estrategia de datos por dominio (`DB por dominio` + PostgreSQL target)
- Regla de integracion entre dominios (API/eventos/read-models; sin SQL directo cross-domain)

## Alternatives Considered

1. Opcion A (pros/cons)
2. Opcion B (pros/cons)

## Rollout Plan

1. Fase 1
2. Fase 2
3. Fase 3

## Validation

- Testing requerido
- Observabilidad/metricas de exito
- Criterio de rollback

## Data Overload Controls (if applies)

- Particionado
- Indices
- Retencion/archivo
- Read-models/reporting
- Observabilidad DB

## Risks and Mitigations

- Riesgo 1 -> Mitigacion
- Riesgo 2 -> Mitigacion

## Approval Checklist

- [ ] Owners de dominios impactados aprobaron
- [ ] Owner de DB aprobó (si aplica)
- [ ] Criterio logico -> fisico evaluado para dominios de alta carga
- [ ] Docs actualizadas
- [ ] Decision/riesgo high-signal guardado en Engram (`SISEM_SHARED`)
- [ ] PR template completado con referencias al RFC
