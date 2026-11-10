# Frontend Testing Guide

Stack de testing del frontend SISEM:

- Vitest + Testing Library (unit e integration)
- MSW (mock de red)
- Playwright (E2E)

Reglas del agente para esta carpeta: `frontend/src/test/AGENTS.md`.

## Estructura

```txt
frontend/src/test/
├── unit/
├── integration/
├── e2e/
├── mocks/
│   ├── handlers/
│   ├── browser.ts
│   ├── server.ts
│   └── handlers.ts
├── factories/
├── setup.ts
└── utils.ts
```

## Comandos

```bash
cd frontend

# Unit + Integration (watch)
bun test

# Unit + Integration (run)
bun run test:run

# UI runner
bun run test:ui

# Cobertura
bun run test:coverage

# E2E
bunx playwright test

# Smoke E2E KAN-27
bun run test:e2e:smoke

# Suite E2E KAN-4 (smoke + excepciones)
bun run test:e2e:kan4

# Quality gate KAN-4 smoke (critical UI + API + E2E)
bun run quality:kan4:smoke

# Quality gate KAN-4 release (suite completa)
bun run quality:kan4:release
```

## Integracion CI reproducible (agnostica)

Si el repo aun no define pipeline versionado, integra este gate en tu runner CI:

```bash
cd frontend
bun install
bun run quality:kan4:smoke
```

Artefactos que deben conservarse por corrida:

- `frontend/playwright-report/`
- `frontend/test-results/`

## Mocks en Desarrollo (Offline)

Activar en frontend:

```env
VITE_USE_MSW=true
```

Con eso MSW intercepta requests en navegador y permite desarrollar sin backend activo.

## Credenciales Mock (Login)

### Exitos por rol

| Usuario | Landing |
| --- | --- |
| `admin` | `/admin/roles` |
| `clinico` o `medico` | `/clinico/consultas` |
| `recepcion` | `/recepcion/agenda` |
| `farmacia` | `/farmacia/recetas` |
| `urgencias` | `/urgencias/triage` |
| `hospital` | `/hospital` |
| `newuser` | onboarding requerido |

### Escenarios de error

| Caso | Resultado |
| --- | --- |
| `username=error` o `password=wrong` | `INVALID_CREDENTIALS` (401) |
| `username=locked` | `ACCOUNT_LOCKED` (423) |
| `username=inactive` | `USER_INACTIVE` (403) |
| `username=expired` | `ACCOUNT_EXPIRED` (401) |
| `username=maintenance` | `SERVICE_UNAVAILABLE` (503) |
| `username=broken` | `INTERNAL_SERVER_ERROR` (500) |

## Recovery / Reset / Onboarding (mocks)

- OTP valido por defecto: `123456`
- OTP expirado: `000000`
- OTP invalidado por intentos: `999999`
- `error@fail.com` en request-reset-code -> `USER_NOT_FOUND` (404)

Passwords magicas para simular errores:

- `ExpiredToken1!` -> `TOKEN_EXPIRED` (401)
- `TokenInvalid1!` -> `TOKEN_INVALID` (401)
- `InvalidToken1!` -> `INTERNAL_SERVER_ERROR` o `ONBOARDING_FAILED` segun flujo

## Reglas de Calidad

- Tests deterministas (sin sleeps fijos).
- Cubrir estados `loading`, `empty`, `success`, `error`.
- Mantener handlers de MSW alineados a contratos en `docs/api/`.
- Reusar factories y evitar data inline repetida.

## Hooks de verificacion Part 2

- Validar que flujos cross-domain usan contratos/adapters/eventos explicitos.
- Si hay realtime, verificar que los handlers no toman decisiones de negocio/seguridad.
- En acciones sensibles, cubrir envio de metadata de correlacion para auditoria backend.
- Verificar gating UX por permisos atomicos/dependencias (sin checks ad-hoc por string de rol).

## Hooks de verificacion Part 3

- Aplicar piramide por riesgo: unit/integration como base; E2E solo para journeys criticos.
- Priorizar cobertura en seguridad/authz UX, trazabilidad de auditoria, flujos clinicos criticos y transiciones de estado.
- En flujos con concurrencia UI, cubrir condiciones de carrera (optimistic updates, retrys, transiciones asincronas superpuestas).
- Para features criticas, exigir evidencia de cobertura automatizada proporcional antes de merge.

## Gobernanza TDD-first estricta (obligatoria)

- Alcance: NEW feature, NEW functionality y LARGE refactor.
- Regla de tasking: primero tareas de diseno/creacion de tests; despues tareas de implementacion.
- Ciclo requerido: **Red -> Green -> Refactor** (fallo inicial, implementacion minima en verde, refactor sin romper tests).
- Evidencia de PR: adjuntar fallo inicial + progresion de implementacion + estado final en verde.
- Excepciones: solo con racional explicito, controles/tests compensatorios y aprobacion en el PR.
