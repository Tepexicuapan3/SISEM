# Onboarding Day-1 Checklist (IA-First)

> TL;DR: Este checklist deja a cualquier developer listo para trabajar en SISEM con flujo SDD + Engram + PR desde el primer dia.

## Objetivo

Garantizar que una persona nueva pueda iniciar una tarea por dominio sin romper runtime, sin perder contexto y con gates de calidad activos.

## Checklist operativo (obligatorio)

### 1) Contexto del repo

- [ ] Leer `README.md` (baseline Fase 1 y estrategia monolito modular evolutivo).
- [ ] Leer `AGENTS.md` raiz y el `AGENTS.md` mas especifico del area a tocar.
- [ ] Confirmar estrategia de datos: `DB por dominio` con PostgreSQL target.

### 2) Tooling y gates

- [ ] Ejecutar `./.engram/scripts/install-hooks.sh`.
- [ ] Verificar hooks y binarios:

```bash
git config --get core.hooksPath
ls .githooks
```

### 3) SDD

- [ ] Definir `change-name` del cambio.
- [ ] Ejecutar flujo SDD segun alcance:
  - Cambio grande: `/sdd-new <change>` o `/sdd-ff <change>`
  - Implementacion incremental: `/sdd-apply <change>`
- [ ] Para NEW feature/NEW functionality/LARGE refactor, definir tasking tests-first y ciclo Red -> Green -> Refactor desde el plan inicial.

### 4) Engram (memoria de equipo)

- [ ] Revisar contexto previo en `SISEM_SHARED` antes de implementar.
- [ ] Guardar solo eventos high-signal (decisiones, bugfix raiz, convenciones, config compartida).
- [ ] Usar `topic_key` estable para evitar duplicados.

### 5) PR y merge governance

- [ ] Usar `.github/pull_request_template.md` completo.
- [ ] Incluir estado SDD + impacto por dominio.
- [ ] Si hay impacto cross-domain, adjuntar RFC (`docs/templates/rfc-cross-domain-template.md`).
- [ ] Validar reglas de dependencia y ownership de datos antes de merge.
- [ ] Adjuntar evidencia TDD-first (fallo inicial + progresion + verde final) o justificar excepcion con controles compensatorios y aprobacion.

## No hacer (guardrails)

- No hacer migraciones big-bang `old -> new`.
- No hacer acceso SQL cross-domain directo.
- No arrancar refactor funcional de Auth sin plan SDD + criterios de aceptacion.

## Referencias

- `README.md`
- `AGENTS.md`
- `docs/getting-started/ai-team-workflow.md`
- `docs/guides/pr-merge-governance.md`
- `docs/guides/domain-dor-dod.md`
- `docs/guides/incremental-domain-migration.md`
- `docs/templates/rfc-cross-domain-template.md`
