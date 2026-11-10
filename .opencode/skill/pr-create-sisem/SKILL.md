---
name: pr-create-sisem
description: >
  Crea Pull Requests estandarizadas para SISEM con estructura obligatoria,
  trazabilidad SDD y evidencia completa para reducir rechazos por
  redacción incompleta. Trigger: cuando el usuario pida crear, abrir o
  preparar una PR para revisión.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

Usar esta skill cuando el usuario pida:

- Crear/abrir una PR
- Preparar cuerpo de PR (aunque todavía no la abra)
- Estandarizar descripción para evitar rechazos de governance
- Dejar una PR "review-ready" para `pr-review-sisem`

Triggers típicos:

- "creá la PR"
- "abrí pull request"
- "prepará la descripción de PR"
- "dejarla lista para aprobar/squash"

## Goal

Entregar PRs consistentes, completas y verificables para que `pr-review-sisem` pueda validarlas sin pedir información faltante.

## SISEM Non-Negotiables

1. **Sin PR desde `main`**: trabajar siempre desde rama de ticket.
2. **Trazabilidad obligatoria**: SDD (si aplica) + dominios impactados. Jira ya no se usa (`docs/governance/decision-sin-jira.md`).
3. **Evidencia documental obligatoria**: ruta, decisión, impacto.
4. **Testing/TDD-first**: incluir evidencia real o excepción aprobada.
5. **Sin placeholders**: no dejar `TODO`, `N/A` vacío o secciones sin justificar.
6. **No inventar evidencia**: cada afirmación debe tener comando, output, diff o referencia documental.
7. **Cross-domain con control**: si cruza dominios, declarar RFC/impacto explícitamente.

## PR Modes

| Modo | Resultado esperado |
| --- | --- |
| `draft-body` | Genera cuerpo de PR estandarizado, sin abrir PR |
| `create-pr` | Push de rama (si falta) + `gh pr create` con template completo |
| `create-pr-ready` | Crea PR + valida que no falte evidencia crítica |

Si el usuario no especifica modo, usar `create-pr`.

## Required Input Contract

Antes de crear la PR, confirmar:

- Resumen de alcance (incluye/no incluye)
- Tipo de cambio (`feat`, `fix`, `chore`, `docs`, `refactor`, etc.)
- Dominio principal y estado (`legacy|hybrid|domain-first`)
- Evidencia de tests (y TDD-first si aplica)

Si falta algo, solicitarlo antes de abrir la PR.

## Branch and Title Conventions

### Branch

Usar convención SISEM:

```text
<tipo>/<dominio>/<slug>
```

Ejemplo:

```text
fix/auth/KAN-61-contract-alignment
```

### PR Title

Formato recomendado:

```text
<type>(<domain>): <short summary>
```

Ejemplo:

```text
fix(auth): align auth payload contract and docs [KAN-61]
```

## Workflow

### Phase 1 — Gather change evidence

```bash
git status
git diff --staged
git diff
git log --oneline -n 15
```

Para PR a `main`, también inspeccionar divergencia:

```bash
git diff main...HEAD
```

### Phase 2 — Validate readiness before opening PR

- Rama actual no es `main`
- Cambios comprometidos en commits coherentes
- Evidencia de pruebas disponible
- Docs actualizadas si cambió behavior/boundary/contrato

### Phase 3 — Build PR body using canonical template

Usar plantilla en `assets/pr-body-template.md` y completar TODOs.

Reglas de llenado:

- Cada sección debe tener contenido concreto
- Si algo no aplica, explicar por qué (no dejar vacío)
- Incluir evidencia mínima de comandos/tests/documentos

### Phase 4 — Create PR

```bash
git push -u origin "$(git branch --show-current)"
gh pr create --title "<title>" --body "$(cat <<'EOF'
<PR body completo>
EOF
)"
```

### Phase 5 — Post-create self-check (mandatory)

- Verificar PR creada y body renderizado correctamente
- Confirmar que no quedaron placeholders (`TODO`, `<...>`, `pendiente`)
- Confirmar que secciones críticas están completas:
  - SDD
  - Dominio y data impact
  - Evidencia TDD/testing
  - Evidencia documental
  - Risks/Rollback

## Alignment Contract with `pr-review-sisem`

La PR DEBE permitir validar explícitamente:

1. Governance & traceability (SDD/dominios/RFC)
2. Architecture boundaries (capas y reglas de dependencia)
3. Security/AuthZ/Audit impactos
4. Testing + evidencia TDD-first (si aplica)
5. Sync documental en el mismo cambio

Si falta cualquiera, completar antes de solicitar review.

## Commands

```bash
# Estado de la rama y cambios
git status
git diff --staged
git diff

# Ver divergencia contra main
git diff main...HEAD

# Crear PR
git push -u origin "$(git branch --show-current)"
gh pr create --title "<type>(<domain>): <summary>" --body "$(cat <<'EOF'
<body from assets/pr-body-template.md>
EOF
)"

# Editar PR si faltó algo
gh pr edit <number> --body-file /tmp/pr-body.md
```

## Resources

- **Template**: `assets/pr-body-template.md`
- **Governance**: `docs/guides/pr-merge-governance.md`
- **Dependency rules**: `docs/architecture/dependency-rules.md`
- **PR template**: `.github/pull_request_template.md`
- **Review contract**: `.opencode/skill/pr-review-sisem/SKILL.md`
