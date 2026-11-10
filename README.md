# SISEM

![SISEM](frontend/public/assets/brand/logos/primary/sisem.webp)

![React](https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white)
![Django](https://img.shields.io/badge/Django-5+-0C4B33?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-API-red)
![pnpm](https://img.shields.io/badge/pnpm-package--manager-F69220?logo=pnpm&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-auth--db-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-cache-DC382D?logo=redis&logoColor=white)

Sistema de Informacion de Registros Electronicos de Salud para Metro CDMX. SISEM centraliza operacion clinica, seguridad y trazabilidad en una arquitectura moderna React + Django.

## Que es SISEM

SISEM es una plataforma web para gestion clinica y administrativa. Combina frontend React 19 con backend Django/DRF, usa JWT en cookies HttpOnly y protege operaciones mutables con CSRF (`X-CSRF-TOKEN`).

## Stack principal

- Frontend: React 19, TypeScript, Vite, Bun.
- Backend: Django 5+, Django REST Framework.
- Datos: PostgreSQL (Auth domain DB) y Redis (channels/realtime).
- Infra local: Docker Compose.

## Levantar rapido

### Opcion recomendada: Docker

```bash
git clone https://github.com/Luis-Ant/SISEM.git
cd <repo-dir>

cp .env.example .env
docker compose up --build
```

Notas del contrato docker-first de desarrollo:
- Baseline Auth-first: PostgreSQL por dominio con servicio `auth-db`.
- Backend consume `DB_*` derivados de `AUTH_DB_*` en `docker-compose.yml`.
- Seed automatico al iniciar contenedores (`backend/seed_e2e.py`).
- Persistencia activa de datos en volumen nombrado `auth_db_data`.
- SMTP y enlaces de correo de Auth se controlan con `EMAIL_*`, `SISEM_LOGIN_URL`, `SISEM_SUPPORT_EMAIL`.

Verificacion rapida:
- Frontend: `http://localhost:5173`
- Backend (admin): `http://localhost:5000/admin/`

### Opcion local (sin Docker)

No recomendada. El contrato operativo de desarrollo en SISEM es docker-first.

## Flujo IA del equipo

### Agent Teams Lite

- Orquestacion por subagentes para tareas de implementacion y analisis.
- Flujo SDD para cambios grandes: propuesta -> spec -> design -> tasks -> apply -> verify.
- Trabajo por dominios con ownership explicito para reducir colisiones en paralelo.
- Reglas operativas y jerarquia en `AGENTS.md`.

### Engram

- Memoria compartida de equipo para decisiones, fixes y hallazgos clave.
- Convencion de proyectos: `SISEM_SHARED` (equipo) y `SISEM_LOCAL` (notas locales).
- Sync automatico con hooks Git para export/import de memoria compartida.
- Topic key estable por dominio o feature para mantener trazabilidad real.

### Git Hooks

- Hooks versionados en `.githooks/` para automatizar el sync de Engram.
- Activacion one-time con `./.engram/scripts/install-hooks.sh`.
- Alcance: automatizacion local de sync/memoria; no reemplaza CI/CD ni los checks de PR.

### Jira (ya no se usa)

- Desde el 2026-11-10 la planeación y trazabilidad van en SDD, Engram y el PR (`docs/governance/decision-sin-jira.md`).

## Baseline operativo Fase 1 (cerrado)

- Modelo operativo oficial: **monolito modular evolutivo** con estrategia de datos **DB por dominio en PostgreSQL**.
- Flujo de entrega obligatorio: **SDD -> planificacion TDD-first -> implementacion por dominio -> Engram -> PR/Merge**.
- No se ejecutan movimientos big-bang `old -> new`; runtime actual sigue activo mientras avanza la migracion incremental.
- El refactor funcional de Auth se planifica despues de Fase 1, con criterios de aceptacion explicitos (SDD/PR).

## Modelo operativo por dominios

- Estrategia vigente: monolito modular evolutivo (6-12 meses), sin big-bang ni migracion a microservicios full.
- Refactor integral activo por dominios completos (datos, diseno, DB y enfoque tecnico).
- Base incremental creada en `backend/domains/` y `frontend/src/domains/` sin romper runtime actual.
- Politica de datos obligatoria: `DB por dominio` en PostgreSQL (aislamiento logico ahora, aislamiento fisico cuando cumpla criterios).
- Regla de integracion: no acceso directo cross-domain a tablas/esquemas; la integracion entre dominios se hace por API, eventos o read-models.
- Reglas de dependencias, ownership DB y governance documentadas en `docs/README.md`.

## Estandares de arquitectura (operativos)

### 1) Arquitectura recomendada (obligatoria)

- SISEM evoluciona como **monolito modular** con DDD pragmatico (sin sobre-ingenieria).
- Capas obligatorias por modulo/dominio:
  - `presentation`: transporte (HTTP/UI), validacion y mapeo.
  - `application`: casos de uso, orquestacion y limites transaccionales.
  - `domain`: reglas de negocio, invariantes y politicas.
  - `infrastructure`: ORM, persistencia, integraciones externas.
- Regla dura: la logica critica de negocio vive en `application/domain`, no en views, serializers, forms, rutas, componentes UI ni utils genericos.

### 2) Organizacion de carpetas por dominio de negocio

- Backend objetivo: `backend/domains/<dominio>/{presentation,use_cases,infrastructure,domain,tests}`.
- Frontend objetivo: `frontend/src/domains/<dominio>/{components,hooks,pages,state,adapters,types}`.
- `shared`/`common` se limita a cross-cutting tecnico (tokens, cliente API base, logging, telemetry, test tooling).
- Anti-patrones prohibidos:
  - Modulos `misc/common/utils` con decisiones de negocio.
  - Acceso directo cross-domain a tablas/esquemas.

### 3) Patrones de diseno recomendados (cuando aplican)

- **Use Cases / Application Services**: patron por defecto para operaciones de negocio.
- **Repository Pattern**: usar cuando hay complejidad real de persistencia, consistencia transaccional o multiples fuentes.
- **Domain Events (internal-first)**: primero eventos internos; eventos externos solo cuando haya integracion justificada.
- **Policies**: centralizar permisos/reglas contextuales en politicas dedicadas.
- **Transacciones**: abrir/cerrar limites en capa `application`.
- Evitar complejidad prematura: no microservicios, no CQRS full ni event sourcing full sin decision de arquitectura documentada.

### 4) Comunicacion inter-dominio (obligatoria)

- Mecanismos permitidos unicamente:
  - Contrato formal query/service (sync request/response).
  - Caso de uso orquestador en capa `application` (workflows multi-dominio).
  - Domain Events (internal-first, suscriptores explicitos).
- Anti-acoplamiento obligatorio:
  - Prohibido depender de modelos internos, repositorios, tablas o reglas de otro dominio.
  - Prohibido acceso cross-domain no controlado a datos.
- Cuando usar cada mecanismo:
  - Contrato query/service para lecturas/escrituras deterministicas con respuesta inmediata.
  - Orquestador para flujos ordenados/transaccionales entre dominios.
  - Eventos de dominio para side-effects desacoplados y consistencia eventual.

### 5) Comunicacion en tiempo real (excepcion controlada)

- Realtime no es transporte por defecto; el default sigue siendo API request/response.
- Recomendado para notificaciones operativas, presencia colaborativa, progreso en vivo y tableros de baja latencia.
- No recomendado para CRUD core, decisiones security-critical ni persistencia primaria de auditoria.
- Todo realtime debe vivir en modulo dedicado con contratos estandarizados de canal, auth y mensaje.
- Handlers/consumidores WebSocket delegan logica critica a casos de uso de `application`.
- Toda feature realtime nueva requiere justificacion de negocio + documentacion explicita.

### 6) Auditoria completa (obligatoria)

- La auditoria es capability transversal obligatoria para eventos auth, lecturas/cambios sensibles y operaciones criticas.
- Contrato minimo de evento de auditoria:
  - `actor`, `timestamp`, `action`, `domain`, `resource`, `result`, `contextId/requestId`.
  - `ip` y `userAgent` cuando exista disponibilidad.
  - `beforeState` y `afterState` cuando corresponda mutacion.
- Implementacion recomendada:
  - Log explicito en casos de uso para operaciones criticas.
  - Hooks automaticos en rutas sensibles.
- Almacenamiento de auditoria: append-only, acceso restringido y masking/redaction de datos sensibles.
- El DoD de operaciones criticas exige verificacion de auditoria.

### 7) Permisos atomicos/granulares (obligatorio)

- Base de autorizacion: permisos atomicos, no nombres de rol como fuente unica.
- Roles = bundles de permisos, no criterio final.
- La autorizacion condicional/contextual vive en politicas dedicadas.
- Servicio central de autorizacion obligatorio; prohibido checkear role strings ad-hoc como base de seguridad.
- Backend es source of truth de seguridad; frontend solo aplica gating UX.

### 8) Estrategia de base de datos (integridad y seguridad primero)

- Politica por etapas (sin contradiccion): en etapa temprana SISEM opera con una sola instancia/engine PostgreSQL, con ownership estricto por dominio y aislamiento logico; el aislamiento fisico por DB dedicada se evalua despues con criterios documentados.
- Todo schema/tabla de dominio debe definir integridad explicita: PK/FK, unicidad, nullabilidad clara e indices alineados a queries reales.
- Los limites transaccionales de flujos criticos se definen en `application`/casos de uso; evitar control transaccional ad-hoc en capas de transporte.
- Para hotspots de concurrencia, documentar y aplicar patron seguro por caso (`SELECT ... FOR UPDATE`, versionado optimista, idempotency keys o serializacion en cola).
- Separar estado operacional de auditoria/historico: tablas transaccionales no reemplazan bitacora; auditoria/historico es append-only y optimizado para trazabilidad.

### 9) Estandares de colaboracion (obligatorio)

- Los docs de arquitectura son artefactos vivos: todo PR que cambie boundaries/comportamiento actualiza docs impactados en el mismo cambio.
- Modelo de ownership explicito: cada dominio define responsables primario y secundario para backend, frontend, DB y docs.
- DoD unico para todos los dominios/slices; evitar variantes locales ad-hoc.
- El review de PR debe pasar gates de cumplimiento arquitectonico, no solo lint/estilo.

### 10) Estrategia de testing (basada en riesgo)

- Aplicar piramide basada en riesgo: unit/service como base, integration/API para contratos y boundaries, E2E para journeys criticos.
- Prioridades obligatorias de cobertura: seguridad (authn/authz), trazabilidad de auditoria, flujos clinicos criticos, transiciones de estado y rutas sensibles a concurrencia.
- Regla: features criticas requieren cobertura automatizada proporcional al riesgo antes de merge.

### 10.1) Gobernanza TDD-first estricta (obligatoria)

- Alcance: toda NEW feature, NEW functionality y LARGE refactor.
- Regla de planificacion: los tasks de implementacion arrancan con tareas de testing (diseno + creacion) antes de escribir codigo productivo.
- Regla de ejecucion: ciclo obligatorio **Red -> Green -> Refactor** (fallo inicial, implementacion minima que pasa, refactor con tests en verde).
- Evidencia en PR: prueba de test-first (fallos iniciales + progresion de implementacion + estado final en verde).
- Excepcion: si TDD no aplica, se exige racional explicito + controles/tests compensatorios + aprobacion en el PR.

### 11) Estrategia de evolucion del sistema (por etapas)

- Etapa 1: estabilizar boundaries de monolito modular y ownership por dominio sobre infraestructura PostgreSQL compartida.
- Etapa 2: endurecer modulos de dominio (performance, observabilidad, confiabilidad y controles de seguridad) manteniendo contratos.
- Etapa 3: evaluar extraccion/separacion fisica solo con evidencia (presion de SLO, dolor operativo, compliance o necesidad real de escalado independiente).
- Regla dura: prohibido cambiar arquitectura por hype/preferencia sin necesidad medible y decision documentada.

### 12) Sintesis recomendada de decisiones de arquitectura

- Mantener monolito modular como forma por defecto del sistema.
- Mantener boundaries domain-first como unidad por defecto de planificacion y entrega.
- Mantener ownership DB por dominio en PostgreSQL como politica de datos obligatoria (logico primero, fisico por criterio).
- Mantener gobierno centralizado de seguridad/auditoria e integracion cross-domain por contratos.

### 13) Blueprint del sistema (canonico)

- Backend: Django/DRF en capas `presentation -> application -> domain -> infrastructure`, con casos de uso dueños de flujos criticos.
- Frontend: React domain-first donde UI actua como transporte/presentacion y el comportamiento vive en modulos de dominio/aplicacion.
- Seguridad: JWT en cookies HttpOnly + CSRF en mutaciones + politicas centralizadas de autorizacion.
- Auditoria: store append-only, restringido y con masking/redaction bajo contrato minimo obligatorio.
- Comunicacion: request/response por defecto; realtime como excepcion controlada; cross-domain solo por contratos/orquestadores/eventos.

### 14) Riesgos a evitar (anti-checklist de review)

- Pseudo-modularizacion por dominio (carpetas nuevas pero dependencias/ownership siguen acoplados).
- Sprawl de modulos compartidos (`common`/`shared`/`utils`) con decisiones de negocio.
- Complejidad prematura (microservicios/CQRS/event-sourcing sin evidencia).
- Seguridad dispersa (autorizacion duplicada en views/componentes/helpers en vez de politicas centralizadas).

### 15) Recomendacion final (operativa)

- Priorizar evolucion incremental disciplinada: boundaries, integridad y trazabilidad primero.
- Favorecer decisiones medibles con plan de rollback explicito sobre redisenos especulativos.
- Tratar docs y checklists como controles de ejecucion, no como anexos opcionales.

## Checklist rapido de PR (arquitectura)

- [ ] Las capas estan respetadas (`presentation` vs `application` vs `domain` vs `infrastructure`).
- [ ] No hay reglas de negocio criticas en capas de transporte/UI.
- [ ] Se mantienen limites de dominio y no hay acceso DB cross-domain directo.
- [ ] Los patrones elegidos estan justificados (use case/repository/eventos/policies/transacciones).
- [ ] La comunicacion inter-dominio usa solo contrato/orquestador/eventos.
- [ ] Si hay realtime, esta justificado, estandarizado y delega a casos de uso.
- [ ] Las operaciones criticas incluyen auditoria con contrato minimo.
- [ ] La autorizacion usa permisos atomicos + politicas centralizadas.
- [ ] No se introdujo complejidad innecesaria para la etapa actual.
- [ ] Los cambios DB documentan constraints/indices, limites transaccionales y estrategia de concurrencia.
- [ ] Features criticas incluyen cobertura automatizada proporcional al riesgo.
- [ ] NEW feature/NEW functionality/LARGE refactor muestran evidencia TDD-first (tasks tests-first + traza Red/Green/Refactor).
- [ ] Toda excepcion TDD deja racional explicito + controles compensatorios + aprobacion.
- [ ] Si cambiaron boundaries/flujos, los docs de arquitectura se actualizaron en el mismo PR.

## Flujo diario recomendado

1. Levanta entorno (`docker compose up --build`).
2. Implementa siguiendo el AGENTS mas especifico del area.
3. Corre checks minimos: `pnpm lint`, `pnpm test`, `python manage.py test`.
4. Guarda decisiones/fixes relevantes en Engram (`SISEM_SHARED`).
5. Commitea: verifica hooks activos y sincronizacion de Engram.

Playbook y onboarding:
- `docs/getting-started/ai-team-workflow.md`
- `docs/getting-started/onboarding-day-1-checklist.md`
- `docs/getting-started/github-hardening-ci-cd-baseline.md`
- `docs/guides/kan-74-legacy-naming-exceptions.md`

## Comandos utiles

```bash
# Docker
docker compose up --build
docker compose logs -f
docker compose down

# Reset explicito de datos (solo cuando lo necesites)
docker compose down -v

# Frontend
cd frontend && pnpm lint
cd frontend && pnpm test

# Backend
cd backend && python manage.py test
```

## Documentacion

- `docs/README.md` - indice general
- `docs/architecture/domain-map.md` - mapa de dominios y ownership
- `docs/architecture/context-map.md` - bounded contexts y relaciones
- `docs/architecture/dependency-rules.md` - reglas de dependencia y anti-colision
- `docs/architecture/repo-navigation-map.md` - navegacion del repo por capas
- `docs/architecture/db-ownership-migration-policy.md` - ownership DB + politica de migraciones
- `docs/guides/pr-merge-governance.md` - politica de PR/merge
- `docs/governance/repo-hygiene-policy.md` - higiene de repo (trackeado vs efimero + excepciones)
- `docs/guides/domain-dor-dod.md` - DoR/DoD por dominio
- `docs/guides/incremental-domain-migration.md` - estrategia old -> new
- `docs/getting-started/onboarding-day-1-checklist.md` - checklist day-1 IA-first
- `docs/api/README.md` - contratos API
- `docs/guides/ai-skills-matrix.md` - matriz de skills
- `AGENTS.md` - reglas operativas y jerarquia
