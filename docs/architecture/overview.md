# Arquitectura SISEM (baseline vigente)

> TL;DR: SISEM opera como monolito modular evolutivo con frontend React 19 + backend Django/DRF. El delivery se organiza por dominio y la estrategia de datos es DB por dominio con PostgreSQL como target.

## Problem / Context

El sistema necesita evolucionar sin romper la operacion actual. Un cambio big-bang de arquitectura o de base de datos no es viable por riesgo operativo y acoplamiento historico.

## Solution / Implementation

## Stack vigente

### Backend

- Django 5 + Django REST Framework.
- Redis para capacidades de soporte (cache/realtime).
- Baseline de datos: PostgreSQL con ownership por dominio.
- Etapa actual: una instancia/engine PostgreSQL compartida con aislamiento logico estricto; separacion fisica por dominio se evalua por criterios.

### Frontend

- React 19 + TypeScript + Vite.
- TanStack Query para server state.
- Zustand para UI state.
- Zod + React Hook Form para validacion/formularios.

## Modelo operativo de arquitectura

1. Monolito modular evolutivo (sin migracion full a microservicios ahora).
2. Trabajo por dominios completos con ownership explicito.
3. Coexistencia old/new (`legacy`, `hybrid`, `domain-first`) hasta cerrar DoD.
4. Integracion cross-domain solo por contratos (API/eventos/read-models), no por SQL directo.

## Capas y boundaries

### Backend

```text
presentation (views/serializers)
  -> use_cases
    -> infrastructure/repositories
      -> DB del dominio
```

- `presentation` mapea HTTP y permisos.
- `use_cases` contiene reglas de negocio.
- `infrastructure` implementa acceso a datos e integraciones.

### Frontend

```text
routes/pages
  -> domain components/hooks
    -> api resources
      -> backend API
```

- HTTP solo en `frontend/src/infrastructure/api/`.
- Componentes no acceden directamente a transporte.
- Estado de servidor y estado UI se separan.

## Seguridad base

- JWT en cookies HttpOnly.
- CSRF obligatorio (`X-CSRF-TOKEN`) en operaciones mutantes.
- Sin tokens en localStorage/sessionStorage.

## Estrategia de evolucion (Part 3)

1. **Etapa 1**: estabilizar boundaries del monolito modular y ownership por dominio sobre PostgreSQL compartido.
2. **Etapa 2**: endurecer dominios en performance, observabilidad, confiabilidad y controles de seguridad, manteniendo contratos.
3. **Etapa 3**: evaluar separacion/extraccion solo con evidencia (SLO, dolor operativo, compliance, escalado independiente).

Regla dura: no se aceptan cambios de arquitectura por hype o preferencia sin necesidad medible y decision documentada.

## Sintesis canonica de decisiones

- Monolito modular evolutivo como forma por defecto.
- Domain-first como unidad de entrega y ownership.
- DB por dominio en PostgreSQL (aislamiento logico primero, fisico por criterio).
- Seguridad/autorizacion/auditoria centralizadas.
- Integracion cross-domain exclusivamente por contratos, orquestacion o eventos.

## Blueprint de referencia

- **Backend**: `presentation -> application -> domain -> infrastructure`, casos de uso como dueños de flujos criticos.
- **Frontend**: estructura domain-first; UI solo transporte/presentacion.
- **Security**: JWT HttpOnly + CSRF en mutaciones + politicas centralizadas.
- **Audit**: almacenamiento append-only con acceso restringido y masking/redaction.
- **Communication**: request/response por defecto; realtime como excepcion controlada.

## Riesgos de arquitectura a vigilar

- Pseudo-modularizacion (solo mover carpetas sin boundaries reales).
- Sprawl de `shared/common/utils` con reglas de negocio.
- Complejidad prematura (microservicios/CQRS/event sourcing sin evidencia).
- Seguridad dispersa en views/componentes/helpers.

## Recomendacion final

Priorizar evolucion incremental disciplinada: reforzar boundaries, integridad y trazabilidad antes de proponer extracciones o redisenos mayores.

## Flujo de entrega

SDD-Orchestrator -> implementacion por dominio -> Engram -> PR/Merge.

## References

- `docs/architecture/domain-map.md`
- `docs/architecture/context-map.md`
- `docs/architecture/dependency-rules.md`
- `docs/architecture/db-ownership-migration-policy.md`
- `docs/guides/pr-merge-governance.md`
