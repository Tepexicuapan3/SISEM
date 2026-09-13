# SISEM Docs

Indice canonico de documentacion para operar SISEM con el modelo actual: monolito modular evolutivo, trabajo por dominios y flujo Jira + SDD-Orchestrator + Engram.

## Start Here

1. `docs/getting-started/setup.md`
2. `docs/getting-started/ai-team-workflow.md`
3. `docs/getting-started/onboarding-day-1-checklist.md`

## Onboarding por areas raiz

- `backend/apps/README.md` - onboarding operativo para runtime backend actual y reglas de coexistencia.
- `frontend/src/README.md` - onboarding rapido para estructura y limites del runtime frontend.

## Flujo Operativo (canonico)

- Estrategia de arquitectura: monolito modular evolutivo (sin migracion a microservicios full en esta fase).
- Estrategia de datos: DB por dominio con PostgreSQL como target estrategico.
- Flujo de entrega obligatorio: Jira -> SDD-Orchestrator -> planificacion TDD-first -> Engram -> PR/Merge.
- Entrega por dominios completos con ownership explicito (backend + frontend + DB + docs).

## Dominios

- `docs/domains/README.md` - indice canonico de documentacion por dominio.
- `docs/domains/auth-access/README.md` - hub canonico del Dominio 1 (auth/access).
- `docs/domains/auth-access/cierre-formal-mvp-fase2.md` - cierre documental formal validado con cliente (MVP/Fase 2, reglas operativas, excepciones, trazabilidad, KPIs y DoR).
- `docs/domains/auth-access/baseline-as-is.md` - baseline tecnico AS-IS (KAN-47) con trazabilidad de flujos/modulos/endpoints/permisos/deuda.
- `docs/domains/auth-access/boundary-map-acl.md` - boundary map + ACL tecnico canonico (KAN-48) para fronteras, contratos permitidos y guardrails de ejecucion.
- `docs/domains/auth-access/db-domain-to-be-map.md` - mapa TO-BE DB-domain de Auth-Access para KAN-103 Batch 1 (S1+S2), con trazabilidad KAN-107/KAN-106 y fases `expand -> migrate -> contract`.
- `docs/domains/auth-access/db-domain-execution-plan-s1-s6.md` - plan ejecutable KAN-103 Batch 2 para subtareas S1..S6 (S3/S4: KAN-109/KAN-105), con checkpoints, AC/DoD/TDD-first y rollback por fase.
- `docs/domains/auth-access/db-cross-domain-contracts.md` - contratos cross-domain permitidos para datos fuera de auth-access (ej. centros de atención), anti-patrones SQL prohibidos y transición FK->contract reference.
- `docs/domains/auth-access/db-gap-analysis-prioritization.md` - gap analysis de datos Auth-Access con prioridad explícita `must/should/could` (criterio de aceptación obligatorio KAN-103).
- `docs/domains/auth-access/local-db-bootstrap-strategy.md` - estrategia reproducible de DB local para auth-access (migraciones, seeders, factories y setup/reset Docker).
- `docs/domains/auth-access/kan-103-go-no-go-checklist.md` - checklist final KAN-103 (S1..S6) con evidencia requerida y criterios bloqueantes/no-bloqueantes para dictamen Go/No-Go.
- `docs/domains/auth-access/permissions-source-of-truth.md` - slice runtime inicial de KAN-49 para backend source of truth de permisos/capabilities.
- `docs/domains/auth-access/request-id-traceability-contract.md` - contrato canonico de trazabilidad `X-Request-ID` para KAN-51.
- `docs/domains/auth-access/rbac-views-extraction-slices-plan.md` - plan de extraccion incremental de `rbac_views` por slices con coexistencia y rollback (KAN-52).
- `docs/domains/auth-access/tdd-risk-strategy-kan-55.md` - estrategia TDD-first por riesgo (P0/P1/P2) por slice con gate go/no-go (KAN-55).
- `docs/domains/auth-access/tdd-evidence-templates.md` - plantillas de evidencia Red->Green->Refactor para Jira/PR (KAN-55).
- `docs/domains/auth-access/tdd-exception-policy.md` - politica de excepciones TDD con aprobacion y controles compensatorios (KAN-55).
- `docs/domains/auth-access/kan-56-s1-apply-evidence.md` - evidencia de apply KAN-56 (slice S1 read-only), checklist dark launch/canary/rollback y validacion contractual.
- `docs/domains/auth-access/kan-62-read-source-switch-hardening.md` - hardening operativo del switch read-only RBAC (precedencia `RBAC_READ_SLICE_SOURCE` vs `RBAC_READ_S1_ENABLED` y rollback explícito a legacy).
- `docs/domains/auth-access/kan-61-rbac-critical-use-cases-apply-evidence.md` - evidencia de apply KAN-61 para extraccion de mutaciones RBAC criticas a use_cases/policies.
- `docs/domains/auth-access/jira-workflow-operating-model.md` - workflow operativo Jira de Auth-Access (columnas, gates, WIP, due dates, bloqueos, daily/cierre y reglas para agentes IA).
- `docs/domains/auth-access/kan-58a-s2-apply-evidence.md` - evidencia de apply KAN-58A (slice S2 mutaciones de roles), TDD Red/Green/Refactor y rollback por flag.
- `docs/domains/auth-access/kan-59-apply-evidence.md` - evidencia de apply KAN-59 (frontend guards/routing capability-first), trazabilidad PRs #59/#60/#61 y ciclo TDD Red/Green/Refactor.
- `docs/domains/auth-access/kan-65-admin-capabilities-apply-evidence.md` - evidencia de apply KAN-65 (capabilities admin users/roles, AC traceability y cierre documental).
- `docs/domains/auth-access/kan-65-pr-evidence-draft.md` - borrador evidence-first de descripcion de PR para KAN-65.
- `docs/domains/auth-access/kan-66-concurrency-hardening-apply-evidence.md` - evidencia de apply KAN-66 para hardening de concurrencia/idempotencia en RBAC write hotspots.
- `docs/domains/auth-access/kan-67-cutover-legacy-retirement.md` - evidencia KAN-67 para cutover incremental y retiro controlado de porciones legacy en `rbac_views` (S3) con rollback por flag.
- `docs/domains/auth-access/kan-68-startup-quality-gate.md` - evidencia de quality gate KAN-68 para pre-deploy validation, rollback rehearsal y checklist go/no-go.
- `docs/domains/auth-access/kan-69-observability-baseline.md` - baseline operativo de observabilidad auth-access (métricas, alertas mínimas, tablero/snapshot inicial).
- `docs/domains/auth-access/kan-89-auth-qa-e2e-reproducibility-baseline.md` - baseline reproducible KAN-89 para QA E2E auth con dataset canónico, protocolo Docker-first y dictamen GO/NO-GO por modo.
- `docs/domains/auth-access/kan-86-backend-quality-run-go-no-go.md` - corrida Docker-first backend para login/onboarding/reset-password con evidencia de startup y dictamen Go/No-Go Módulo 1.
- `docs/domains/auth-access/kan-91-module-1-closure-acta.md` - acta de cierre KAN-91 para orquestación DoD del Módulo 1 con dictamen compuesto GO/NO-GO y trazabilidad Jira+Notion+docs.
- `docs/domains/auth-access/kan-101-apply-evidence.md` - evidencia de implementación KAN-101 para `change-password` autenticado con traza TDD-first Red/Green/Refactor y checklist de governance.
- `docs/domains/auth-access/kan-60-s1-qa-regression-go-no-go.md` - evidencia de regresión funcional Sprint 1 con checklist pre-deploy y dictamen QA Go/No-Go (KAN-60).
- `docs/domains/auth-access/kan-71-multi-sprint-demo-process.md` - guía institucional de demo multi-sprint (plantilla reusable, checklist mínimo y flujo operativo de cierre).
- `docs/domains/auth-access/kan-70-evidence-matrix-template.md` - matriz plantilla AC->evidencia para cierre evidence-first y trazabilidad TDD por fase.
- Nota de discoverability: los links legacy en `docs/guides/` para PRD de auth-access se mantienen como **deprecados** y redirigen a la ruta canonica del dominio.

## Estandares operativos (arquitectura + organizacion + patrones)

### Arquitectura (obligatoria)

- Monolito modular evolutivo con DDD pragmatico.
- Capas por dominio/modulo: `presentation`, `application`, `domain`, `infrastructure`.
- Regla dura: no ubicar logica critica de negocio en views/serializers/forms/rutas/componentes UI/utils.

### Organizacion de carpetas (obligatoria)

- Backend target: `backend/domains/<dominio>/{presentation,use_cases,infrastructure,domain,tests}`.
- Frontend target: `frontend/src/domains/<dominio>/{components,hooks,pages,state,adapters,types}`.
- Shared modules solo para cross-cutting tecnico; no decisiones de negocio.
- Prohibido: acceso DB cross-domain directo desde codigo de aplicacion.

### Patrones recomendados (cuando usar)

- Use Cases/Application Services como default.
- Repository cuando hay complejidad/consistencia/multiples fuentes.
- Domain Events con enfoque internal-first.
- Policies para autorizacion y reglas contextuales.
- Transacciones delimitadas en `application`.
- Evitar complejidad prematura (microservicios/CQRS full/event sourcing full sin ADR).

### Comunicacion inter-dominio (obligatoria)

- Mecanismos permitidos: contrato query/service, caso de uso orquestador, domain events.
- Prohibido acoplarse a modelos internos/repositorios/tablas/reglas de otro dominio.
- Prohibido acceso cross-domain no controlado a datos de dominio.
- Guia de uso:
  - Contrato query/service: respuesta inmediata y deterministica.
  - Orquestador: flujo ordenado o transaccional entre dominios.
  - Eventos: side-effects desacoplados y consistencia eventual.

### Realtime (excepcion controlada)

- Realtime no reemplaza API request/response como default.
- Recomendado: notificaciones, presencia, progreso y tableros de baja latencia.
- No recomendado: CRUD core, decisiones security-critical, persistencia primaria de auditoria.
- Toda feature realtime debe documentar modulo dedicado + contrato de canal/auth/mensaje + justificacion de negocio.

### Auditoria completa (obligatoria)

- Cobertura minima: auth events, lecturas/cambios sensibles y operaciones criticas.
- Contrato minimo de evento: `actor`, `timestamp`, `action`, `domain`, `resource`, `result`, `contextId/requestId`; `ip`/`userAgent` cuando aplique; `beforeState`/`afterState` en mutaciones.
- Reglas de almacenamiento: append-only, acceso restringido y masking/redaction.
- El DoD de operaciones criticas debe incluir validacion de auditoria.

### Permisos atomicos/granulares (obligatorio)

- Autorizacion basada en permisos atomicos; roles como bundles.
- Politicas contextuales obligatorias para autorizacion condicional.
- Servicio central de autorizacion requerido; prohibidos checks ad-hoc de role strings.
- Backend es source of truth de seguridad; frontend aplica gating UX.

### Estrategia DB (Part 3, obligatoria)

- Baseline por etapas: una sola instancia/engine PostgreSQL al inicio con ownership estricto por dominio y aislamiento logico; separacion fisica por dominio solo cuando cumpla criterios documentados.
- Integridad primero: PK/FK, unicidad, nullabilidad explicita e indices segun patrones reales de consulta.
- Limites transaccionales definidos en `application`/casos de uso; evitar manejo transaccional en transporte.
- Concurrencia en hotspots: documentar y elegir patron seguro (`FOR UPDATE`, versionado optimista, idempotencia o serializacion).
- Separar estado operacional de auditoria/historico (append-only para trazabilidad).

### Colaboracion y governance (Part 3)

- Los docs de arquitectura son artefactos vivos: cualquier PR que cambie boundaries/flujo actualiza docs impactados en el mismo cambio.
- Ownership explicito por dominio (primario/secundario en backend, frontend, DB y docs).
- Un DoD base unico para todos los dominios/slices.
- Review de PR con gates de compliance arquitectonico + evidencia de testing proporcional al riesgo.
- Higiene de repositorio: source of truth trackeado, efimero ignorado y excepciones controladas segun `docs/governance/repo-hygiene-policy.md`.

### Testing por riesgo (Part 3)

- Piramide base: unit/service -> integration/API -> E2E para journeys criticos.
- Cobertura prioritaria: seguridad/authn/authz, auditoria, flujos clinicos criticos, transiciones de estado y concurrencia.
- Regla de merge: features criticas requieren cobertura automatizada proporcional al riesgo.
- Regla TDD-first (obligatoria): NEW feature/NEW functionality/LARGE refactor siguen Red -> Green -> Refactor.
- Regla de planning: el tasking debe iniciar con tareas de testing antes de tareas de implementacion.
- Regla de evidencia: PRs deben mostrar fallo inicial + progresion de implementacion + estado final en verde; excepciones requieren racional explicito + controles compensatorios + aprobacion.

### Evolucion del sistema (Part 3)

- Etapa 1: estabilizar boundaries y ownership en PostgreSQL compartido.
- Etapa 2: endurecer dominios (performance, observabilidad, confiabilidad, seguridad) sin romper contratos.
- Etapa 3: separar fisicamente solo con evidencia operativa/compliance/SLO.
- Prohibido redisenar arquitectura por hype o preferencia sin necesidad medible.

### Sintesis + blueprint + riesgos

- Sintesis canonica: monolito modular + domain-first + DB ownership por dominio + seguridad/auditoria centralizadas + integracion por contratos.
- Blueprint: backend en capas Django/DRF, frontend domain-first, JWT HttpOnly + CSRF, auditoria append-only, comunicacion API por defecto con realtime como excepcion.
- Riesgos a evitar: pseudo-modularizacion, sprawl de shared con reglas de negocio, complejidad prematura y seguridad dispersa.

## Arquitectura

- `docs/architecture/overview.md` - baseline tecnico vigente del sistema.
- `docs/architecture/domain-map.md` - ownership por dominio y estado de migracion.
- `docs/architecture/context-map.md` - limites de contexto y relaciones.
- `docs/architecture/dependency-rules.md` - reglas de dependencias y anti-acoplamiento.
- `docs/architecture/db-ownership-migration-policy.md` - politica de ownership DB y migracion.
- `docs/architecture/repo-navigation-map.md` - donde tocar segun tipo de cambio.
- `docs/architecture/legacy-reports-inventory.md` - inventario de documentos imprimibles y reportes gerenciales del legado (java-main), con mapeo preliminar a estado actual y priorizacion sugerida.

## Guides

- `docs/guides/pr-merge-governance.md` - governance de PR y gates de merge.
- `docs/guides/domain-dor-dod.md` - Definition of Ready / Definition of Done por dominio.
- `docs/guides/incremental-domain-migration.md` - coexistencia old/new y plan incremental.
- `docs/guides/ai-skills-matrix.md` - matriz activa de skills y auto-invoke.
- `docs/guides/kan-74-legacy-naming-exceptions.md` - registro de excepciones temporales de naming legacy durante rename a SISEM (KAN-75/76).
- `docs/guides/kan-74-phase4-closure-evidence.md` - evidencia final de cierre Fase 4 (scan allowlist, regression Docker-first, pack por subtask, notas Jira/SDD y plan de hygiene).
- `docs/guides/prd-dominio-1-auth-access.md` - **DEPRECADO** (stub legacy). Ver ruta canonica en `docs/domains/auth-access/prd.md`.
- `docs/guides/prd-dominio-1-auth-access-pendientes-reunion.md` - **DEPRECADO** (stub legacy). Ver ruta canonica en `docs/domains/auth-access/pending-decisions.md`.

## Governance

- `docs/governance/repo-hygiene-policy.md` - politica de higiene de repo (trackeado vs efimero vs excepciones condicionadas).
- `docs/governance/nom024-retention-policy.md` - retencion minima de expediente/auditoria (NOM-024/NOM-004/LGS) y reglas para migracion/decomision del legado.

## API

- `docs/api/README.md` - indice de contratos API.
- `docs/api/standards.md` - estandares transversales de contrato.
- `docs/api/modules/auth.md`
- `docs/api/modules/rbac.md`
- `docs/api/modules/catalogos.md`
- `docs/api/modules/doc_front.md`

## Getting Started

- `docs/getting-started/setup.md` - setup local y por Docker.
- `docs/getting-started/ai-team-workflow.md` - runbook diario de trabajo con IA.
- `docs/getting-started/onboarding-day-1-checklist.md` - checklist day-1.
- `docs/getting-started/engram-team-sync.md` - hooks y sincronizacion de memoria compartida.
- `docs/getting-started/github-hardening-ci-cd-baseline.md` - guia practica para branch protection, checks requeridos y hardening en GitHub UI.

## Runbooks

- `docs/runbooks/frontend-hardening-worktree.md` - aislamiento operativo de worktree para cambios de estabilidad frontend.

## Templates

- `docs/templates/README.md`
- `docs/templates/guide-template.md`
- `docs/templates/adr-template.md`
- `docs/templates/rfc-cross-domain-template.md`

## Governance minima para cambios cross-domain

Si un cambio toca mas de un dominio, deben estar alineados estos artefactos:

- `docs/architecture/domain-map.md`
- `docs/architecture/context-map.md`
- `docs/architecture/dependency-rules.md`
- `docs/architecture/db-ownership-migration-policy.md`
- `docs/architecture/repo-navigation-map.md`
- `docs/guides/pr-merge-governance.md`
- `docs/guides/domain-dor-dod.md`
- `docs/guides/incremental-domain-migration.md`
- `docs/templates/rfc-cross-domain-template.md`

## Convenciones de mantenimiento

- Mantener docs accionables y sin duplicidad.
- Remover contenido obsoleto en lugar de mantener playbooks legacy.
- Actualizar este indice cada vez que se agrega o elimina documentacion relevante.
