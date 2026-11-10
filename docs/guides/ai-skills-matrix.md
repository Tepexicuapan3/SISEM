# Matriz Maestra de Skills (IA)

> Estado actual de skills activas y reglas de auto-invoke en SISEM.

## Objetivo

Esta matriz centraliza:

- Que skill existe y para que sirve.
- Cuando debe auto-invocarse.
- En que alcance del repo se aplica con mayor prioridad.

La fuente de verdad operativa sigue siendo la jerarquia de `AGENTS.md`.

## Skills Activas

| Skill | Para que sirve | Trigger principal de carga |
| --- | --- | --- |
| `vercel-react-best-practices` | Rendimiento/refactor React | Crear o modificar componentes React |
| `interface-design` | Direccion visual y jerarquia UI | Disenar pantallas/layout antes de implementar |
| `web-design-guidelines` | Auditoria UX/a11y | Revisar cumplimiento UI/UX/accesibilidad |
| `typescript` | Tipado estricto | Definir tipos, contratos e interfaces |
| `tailwind-4` | Convenciones de estilos/tokens | Escribir o refactorizar estilos Tailwind |
| `zod-4` | Validacion de schemas | Formularios y validacion de contratos |
| `zustand-5` | Estado global/UI | Crear o editar stores |
| `django-drf` | Implementacion de APIs DRF | Crear endpoints/serializers/permisos/filtros |
| `api-design-principles` | Diseno de contratos REST | Definir/revisar recursos, status, versionado |
| `error-handling-patterns` | Contratos de error y resiliencia | Disenar errores, retries y fallback |
| `systematic-debugging` | Debugging por causa raiz | Bugs, regresiones y tests rotos |
| `brainstorming` | Planeacion previa | Discovery, alternativas y alcance antes de codear |
| `pytest` | Testing backend | Crear/refactor tests backend |
| `playwright` | E2E | Crear/mantener pruebas E2E |
| `pr-create-sisem` | Creacion estandarizada de PRs SISEM | Crear/abrir PRs con evidencia completa y formato uniforme |
| `pr-review-sisem` | Review de PRs con governance SISEM | Revisar PRs y decidir approve/request-changes/squash |
| `find-skills` | Descubrir/instalar skills | Usuario pide buscar o instalar nuevas skills |

## Auto-invoke Global (Root)

| Accion | Skill |
| --- | --- |
| Create/modify React components (performance-aware) | `vercel-react-best-practices` |
| Create new UI screens/layout direction before implementation | `interface-design` |
| Review UI/UX/accessibility compliance | `web-design-guidelines` |
| Write TypeScript types | `typescript` |
| Tailwind styling | `tailwind-4` |
| Zod / RHF validation | `zod-4` |
| Create/edit global stores | `zustand-5` |
| Design Django/DRF APIs | `django-drf` |
| Design/review API contracts and standards | `api-design-principles` |
| Design/review error contracts, retries, and fallback behavior | `error-handling-patterns` |
| Debug bugs, test failures, and regressions | `systematic-debugging` |
| User asks for planning/discovery before coding | `brainstorming` |
| Backend Python tests | `pytest` |
| E2E tests | `playwright` |
| Create/open PR with standardized SISEM structure and evidence | `pr-create-sisem` |
| Review/audit PRs and decide approve/request-changes/squash | `pr-review-sisem` |
| User asks to discover/install skills | `find-skills` |

## Prioridad por Alcance (AGENTS)

Cuando hay conflicto, gana el `AGENTS.md` mas especifico.

| Alcance | AGENTS | Skills clave |
| --- | --- | --- |
| Repo completo | `AGENTS.md` | Matriz global de 19 skills |
| Backend general | `backend/AGENTS.md` | `django-drf`, `api-design-principles`, `error-handling-patterns`, `systematic-debugging`, `pytest` |
| Implementacion backend por app | `backend/apps/AGENTS.md` | `django-drf`, `api-design-principles`, `error-handling-patterns`, `systematic-debugging`, `brainstorming`, `pytest` |
| Tests backend | `backend/tests/AGENTS.md` | `pytest`, `systematic-debugging`, `error-handling-patterns` |
| Frontend general | `frontend/AGENTS.md` | React/UI + tipos + estado + validacion + debugging |
| Frontend API | `frontend/src/api/AGENTS.md` | `typescript`, `zod-4`, `api-design-principles`, `error-handling-patterns`, `systematic-debugging` |
| Frontend componentes | `frontend/src/components/AGENTS.md` | `vercel-react-best-practices`, `interface-design`, `web-design-guidelines`, `tailwind-4` |
| Frontend features | `frontend/src/features/AGENTS.md` | `vercel-react-best-practices`, `interface-design`, `zod-4`, `zustand-5`, `error-handling-patterns` |
| Frontend admin | `frontend/src/features/admin/AGENTS.md` | Reglas admin + permisos/dependencias |
| Frontend rutas | `frontend/src/routes/AGENTS.md` | `vercel-react-best-practices`, `interface-design`, `error-handling-patterns`, `systematic-debugging` |
| Frontend tests | `frontend/src/test/AGENTS.md` | `playwright`, `systematic-debugging`, `typescript`, `error-handling-patterns` |
| Docs general | `docs/AGENTS.md` | `api-design-principles`, `error-handling-patterns`, `brainstorming` |
| Docs API | `docs/api/AGENTS.md` | `api-design-principles`, `error-handling-patterns` |

## Regla Operativa

1. Cargar primero el contexto mas especifico (subcarpeta).
2. Auto-invocar skill solo cuando el trigger aplica.
3. Si hay multiples triggers validos, priorizar el objetivo principal de la tarea.
4. Para bugs/regresiones, cargar `systematic-debugging` antes de proponer fixes.
