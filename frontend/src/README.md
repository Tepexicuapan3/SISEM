# Frontend `src` - Onboarding rapido

Guia corta para ubicarse en `frontend/src/` y evitar romper estandares de arquitectura durante cambios cotidianos.

## Mapa rapido

- `domains/`: estructura objetivo por dominio de negocio.
- `features/`: implementacion por feature (coexistencia incremental).
- `infrastructure/api/`: clientes HTTP, contratos y adapters de transporte.
- `shared/`: UI/components/layouts/hooks/styles/utilidades tecnicas compartidas.
- `app/`: bootstrap, providers, config y router de composicion de aplicacion.
- `app/router/`: enrutado y guards de navegacion.
- `test/`: utilidades y estrategia de tests frontend.

### Estado auth-access (migración incremental)

- `frontend/src/domains/auth-access` concentra `hooks`, `adapters`, `types`, `state`, `pages` + `components` de auth UI y RBAC (`admin/users`, `admin/roles`, shared/components/queries/mutations/domain/utils movibles).
- Lote 5 cleanup final: se retiraron wrappers legacy de `frontend/src/features/auth/**` y `frontend/src/features/admin/modules/rbac/**`; auth/rbac frontend queda canonizado en `domains/auth-access`.

## Aliases canonicos (Fase 4)

- Base: `@/*` -> `src/*`
- Canones por capa:
  - `@app/*` -> `src/app/*`
  - `@infra/*` -> `src/infrastructure/*`
  - `@shared/*` -> `src/shared/*`
- Atajos permitidos:
  - `@api/*` -> `src/infrastructure/api/*`
  - `@routes/*` -> `src/app/router/*`
  - `@realtime/*` -> `src/infrastructure/realtime/*`

> Cierre de transicion: imports legacy `@/api/*`, `@/routes/*`, `@/realtime/*`, `@/components/{ui,shared,layouts}/*`, `@/{config,providers,store,styles,hooks}/*` quedan deprecados y removidos de la config.

## Checklist obligatorio de entrega

1. Alcance y criterios de aceptacion (cambio SDD o descripcion del PR).
2. SDD: artefactos al dia segun fase.
3. Engram: decisiones y hallazgos relevantes guardados en `SISEM_SHARED`.
4. Engram: usar `topic_key` obligatorio (`feature/{slug}/decision`, `feature/{slug}/progress`, `bug/{id-or-slug}/fix`, `ops/{area}/config`, `docs/{topic}/note`).
5. Hooks Git activos y sincronizacion de Engram antes de merge.
6. Si el alcance es nueva feature/nueva funcionalidad/refactor grande: tareas visibles con tests primero y evidencia Red -> Green -> Refactor (o excepcion con rationale + controles compensatorios + aprobacion).

## Reglas clave (Part 1-3)

- Mantener modelo de monolito modular evolutivo con DDD pragmatico.
- Respetar capas: `presentation`, `application`, `domain`, `infrastructure`.
- Evitar logica critica en componentes/paginas/helpers de UI.
- Organizar por dominio primero; evitar modulos `common/misc/utils` con decisiones de negocio.
- Coordinar cross-domain via contratos (API/eventos/adapters), no acoplamiento directo.

## Reglas clave (Part 2)

- Comunicacion inter-dominio: usar solo contratos formales, orquestacion explicita o eventos documentados.
- Realtime: tratarlo como excepcion controlada; no usarlo para decisiones de seguridad ni CRUD core.
- Handlers WebSocket/eventos delegan decisiones de negocio a hooks/casos de uso de dominio.
- Auditoria: frontend colabora con trazabilidad (por ejemplo `X-Request-ID`) pero no reemplaza auditoria backend.
- Permisos: checks en UI son solo gating UX; seguridad real se valida en backend con permisos atomicos/politicas.

## Reglas clave (Part 3)

- Testing por riesgo: priorizar unit/integration para reglas de UI y contratos; usar E2E para journeys clinicos criticos.
- Cobertura proporcional obligatoria en flujos criticos (auth UX, permisos, metadata de auditoria, transiciones de estado y escenarios de concurrencia UI).
- Si cambian boundaries/contratos domain-first, actualizar docs de arquitectura en el mismo PR.
- Mantener evolucion incremental: evitar redisenos por hype (microfrontends/event-bus global) sin evidencia y decision documentada.

## Siguientes lecturas

- `frontend/src/AGENTS.md`
- `frontend/AGENTS.md`
- `docs/architecture/repo-navigation-map.md`
- `docs/guides/incremental-domain-migration.md`
