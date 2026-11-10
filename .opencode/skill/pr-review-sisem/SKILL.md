---
name: pr-review-sisem
description: >
  Revisión de Pull Requests en SISEM con enforcement de governance, arquitectura,
  seguridad y evidencia TDD-first. Trigger: cuando el usuario pida revisar PRs,
  auditar PRs pendientes, decidir aprobación, o ejecutar approve + squash.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

Usar esta skill SIEMPRE que el usuario pida cualquiera de estos flujos:

- Revisar un PR específico (`#123` o URL)
- Auditar PRs abiertos / pendientes de atención
- Decidir si un PR se puede aprobar
- Ejecutar acciones sobre PR (approve, request changes, squash merge)

Triggers típicos:

- "revisar PR"
- "qué PRs hay pendientes"
- "auditá el backlog de PRs"
- "si está bien, aprobá y squash"

## SISEM Non-Negotiables

1. **No inventar evidencia**: todo hallazgo debe estar respaldado por diff, checks, tests o docs.
2. **Governance primero**: aplicar gates de `docs/guides/pr-merge-governance.md`.
3. **Arquitectura obligatoria**: validar `docs/architecture/dependency-rules.md` y boundaries por dominio.
4. **TDD-first cuando aplica**: para NEW feature/NEW functionality/LARGE refactor, exigir evidencia Red → Green → Refactor o excepción aprobada.
5. **Seguridad y trazabilidad**: verificar señales de JWT HttpOnly + CSRF, permisos atómicos, y cobertura de auditoría cuando el alcance lo requiere.
6. **No mergear por defecto**: solo ejecutar merge si el usuario lo pidió explícitamente en este hilo.
7. **Sin bypasses peligrosos**: no usar flags de bypass/admin para saltar protecciones de rama/checks.

## Review Modes (obligatorio distinguir)

| Modo | Qué hacer | Qué NO hacer |
| --- | --- | --- |
| `analysis-only` | Analizar, clasificar, recomendar acción | No aprobar ni mergear |
| `action-approve` | Aprobar PR si pasa todos los gates | No mergear si no fue pedido |
| `action-approve-squash` | Aprobar + squash merge si todo está en verde | No forzar merge con checks rojos |
| `action-request-changes` | Dejar feedback estructurado con bloqueantes | No usar comentarios ambiguos |

Si la intención del usuario es ambigua, pedir confirmación antes de ejecutar acciones de aprobación/merge.

## Review Process

### Phase 1 — Gather PR data

```bash
# Listado inicial (si el usuario pide backlog)
gh pr list --state open --limit 30

# Contexto completo de un PR
gh pr view {number} --json title,body,author,baseRefName,headRefName,labels,reviewDecision,isDraft,mergeable,commits,files,additions,deletions,url

# Checks y estado CI
gh pr checks {number}

# Diff completo para análisis técnico
gh pr diff {number} --patch
```

### Phase 2 — Load SISEM documentary baseline

Mínimo obligatorio para dictamen:

1. `docs/guides/pr-merge-governance.md`
2. `docs/architecture/dependency-rules.md`
3. `docs/guides/domain-dor-dod.md`
4. `docs/architecture/overview.md`

Cuando el PR toca contratos/API o auth-access, sumar:

- `docs/api/standards.md` + módulo afectado
- `docs/domains/auth-access/*` (si aplica)

### Phase 3 — SISEM compliance checklist

#### A) Governance & Traceability

- [ ] PR referencia cambio SDD (si aplica)
- [ ] Dominio(s) impactado(s) declarado(s)
- [ ] Si cruza dominios: RFC/documentación de impacto incluida

#### B) Architecture & Boundaries

- [ ] Capas respetadas (`presentation/application/domain/infrastructure`)
- [ ] No hay lógica crítica en capa de transporte/UI
- [ ] No hay acceso DB cross-domain directo
- [ ] Dependencias/imports respetan reglas de dominio

#### C) Security, AuthZ, Audit

- [ ] No hay secretos hardcodeados
- [ ] Contratos de auth/CSRF/JWT no se degradan
- [ ] Autorización no depende de role-strings ad-hoc
- [ ] Operaciones críticas mantienen trazabilidad/auditoría requerida

#### D) Testing & TDD Evidence

- [ ] CI relevante en verde
- [ ] Cobertura proporcional al riesgo
- [ ] Evidencia Red → Green → Refactor (cuando aplica)
- [ ] Excepción TDD documentada y aprobada (si corresponde)

#### E) Documentation Sync

- [ ] Docs actualizadas en el mismo PR si cambió behavior/boundary/contrato
- [ ] Sección de evidencia documental coherente y trazable

### Phase 4 — Decision matrix

| Resultado | Acción |
| --- | --- |
| Existe blocker de governance/seguridad/arquitectura/TDD | `request changes` |
| No blockers, pero hay ajustes menores | comentario + `needs work` |
| Todo verde y usuario pidió revisión solamente | recomendar `approve` |
| Todo verde y usuario pidió acción explícita | `approve` + `squash merge` |

## Standard Review Output (usar siempre)

```markdown
## Estado
- PR: #{number} - {title}
- Resultado: {APPROVE | REQUEST_CHANGES | NEEDS_WORK}

## Evidencia documental
| Ruta | Decisión aplicada | Impacto |
| --- | --- | --- |
| docs/guides/pr-merge-governance.md | {regla/gate validado} | {impacto} |
| docs/architecture/dependency-rules.md | {regla de boundary} | {impacto} |

## Hallazgos
### Bloqueantes
- [ ] {hallazgo bloqueante + evidencia}

### No bloqueantes
- [ ] {mejora recomendada}

## Acción
- {qué se ejecutó o qué debe ejecutarse}
```

## Request-Changes Comment Template (organizado)

```markdown
¡Hola {autor}! Gracias por el PR 

## Resumen
Buen avance en {área}. Antes de mergear, hay puntos bloqueantes de governance/compliance que debemos corregir.

## Bloqueantes (obligatorio)
1. **{Título corto}**
   - Evidencia: `{archivo}:{línea}` o check `{job}`
   - Riesgo: {por qué bloquea}
   - Corrección esperada: {acción concreta}

2. **{Título corto}**
   - Evidencia:
   - Riesgo:
   - Corrección esperada:

## Checklist de salida
- [ ] {fix 1}
- [ ] {fix 2}
- [ ] CI en verde

Cuando esté listo, vuelvo a revisar y si todo cierra lo aprobamos ✅
```

## Approve Comment Template

```markdown
Excelente trabajo {autor} 👏

## Validación
- Governance: OK
- Boundaries/arquitectura: OK
- Seguridad/trazabilidad: OK
- Testing/TDD-evidence: OK
- Docs/contratos: OK

No encontré bloqueantes. PR aprobado ✅
```

## Commands

```bash
# Aprobar PR
gh pr review {number} --approve --body "Aprobado tras validación de governance + arquitectura + seguridad + testing."

# Solicitar cambios (usar HEREDOC para comentario largo)
gh pr review {number} --request-changes --body "$(cat <<'EOF'
{comentario estructurado}
EOF
)"

# Comentario informativo sin bloquear
gh pr review {number} --comment --body "{feedback}"

# Squash merge (solo con pedido explícito del usuario y checks en verde)
gh pr merge {number} --squash --delete-branch
```

## Merge Safety Gates (antes de squash)

- [ ] PR no está en draft
- [ ] `gh pr checks` sin fallas
- [ ] No hay blockers pendientes en review comments
- [ ] Rama actualizada con `main` si la policy lo exige
- [ ] Usuario pidió explícitamente mergear en este hilo

Si cualquiera falla, no mergear y explicar el bloqueo con evidencia.

## References

- `docs/guides/pr-merge-governance.md`
- `docs/architecture/dependency-rules.md`
- `docs/guides/domain-dor-dod.md`
- `docs/architecture/overview.md`
- `docs/api/standards.md`

## Keywords

pr, review, github, governance, sisem, tdd, compliance, squash, approval
