# Backend Apps - Onboarding rapido

Este README es la entrada rapida para el arbol `backend/apps/` (runtime legado + coexistencia incremental con `backend/domains/`).

## Que vive en `backend/apps/`

- Implementaciones activas de endpoints DRF y modulos de negocio en produccion.
- Capas operativas por modulo: `views.py`/`serializers.py` (presentation), `uses_case/` o `use_cases/` (application), `repositories/` (infrastructure).
- Integraciones transversales tecnicas (auth, csrf, response shape, audit).

## Checklist operativo obligatorio (antes de tocar codigo)

1. Alcance y criterios de aceptacion (cambio SDD o descripcion del PR).
2. Artefactos SDD al dia (proposal/spec/design/tasks segun fase).
3. Contexto y decisiones relevantes persistidas en Engram (`SISEM_SHARED`).
4. Persistencias de Engram con `topic_key` obligatorio (`feature/{slug}/decision`, `feature/{slug}/progress`, `bug/{id-or-slug}/fix`, `ops/{area}/config`, `docs/{topic}/note`).
5. Hooks Git activos y sincronizacion de Engram antes de merge.
6. Si el alcance es nueva feature/nueva funcionalidad/refactor grande: plan de tareas visible con tests primero y evidencia Red -> Green -> Refactor (o excepcion con rationale + controles compensatorios + aprobacion).

## Reglas no negociables

- Arquitectura: mantener separacion `presentation -> application -> domain -> infrastructure`.
- Logica critica en `use_cases`/dominio, nunca en transport (`views.py`, `serializers.py`).
- Ownership de datos por dominio: cada tabla/schema/migracion tiene un solo owner.
- Prohibido acceso SQL cross-domain directo; usar contratos (API/eventos/read-models).
- Migracion incremental sin big-bang: `apps` y `domains` conviven hasta DoD por dominio.

## Part 2 operativo (comunicacion, realtime, auditoria, permisos)

- Comunicacion inter-dominio: solo contrato query/service, caso de uso orquestador o domain events.
- Anti-acoplamiento: prohibido depender de modelos internos/repositorios/reglas de otro dominio.
- Realtime: excepcion controlada; no usar para decisiones criticas ni CRUD core. Los handlers delegan a `use_cases`.
- Auditoria obligatoria en operaciones criticas con contrato minimo: `actor`, `timestamp`, `action`, `domain`, `resource`, `result`, `contextId/requestId` (+ `ip/userAgent` y `beforeState/afterState` cuando aplique).
- Permisos: autorizacion basada en permisos atomicos y politicas centralizadas; role strings ad-hoc no son base de seguridad.

## Part 3 operativo (DB, testing, evolucion, governance)

- DB por etapas: PostgreSQL compartido al inicio con ownership logico por dominio; separacion fisica solo por criterio documentado.
- Integridad obligatoria en cambios de datos: PK/FK, unicidad, nullabilidad explicita, indices por patron real de consulta.
- Limites transaccionales y estrategia de concurrencia definidos en `use_cases` para flujos criticos (`FOR UPDATE`/versionado/idempotencia/serializacion segun caso).
- Testing basado en riesgo: cubrir de forma proporcional auth/authz, auditoria, flujos clinicos criticos y transiciones sensibles a concurrencia.
- Si un PR cambia boundaries o comportamiento arquitectonico, actualizar docs afectados en el mismo cambio.

## Referencias

- `backend/apps/AGENTS.md`
- `backend/AGENTS.md`
- `docs/architecture/domain-map.md`
- `docs/architecture/db-ownership-migration-policy.md`
- `docs/guides/incremental-domain-migration.md`
