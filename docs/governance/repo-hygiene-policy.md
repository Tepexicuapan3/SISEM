# Politica de Higiene de Repositorio

> TL;DR: En SISEM se versiona solo el source of truth operativo. Todo lo generado/efimero se ignora. Las excepciones son explicitas, temporales y trazables.

## Objetivo y alcance

Esta politica define que se trackea y que se ignora para mantener el repositorio auditable, reproducible y sin ruido operativo.

Aplica a todo el repo, incluyendo trabajo local de agentes IA y automatizaciones de equipo.

## Clasificacion obligatoria de archivos/directorios

### 1) Source of truth (trackeado)

Se versiona todo artefacto que represente contrato, decision operativa o automatizacion reproducible del equipo.

Reglas explicitas por carpeta:

- `.engram/`: se trackean exports compartidos de `SISEM_SHARED` y scripts versionados de sync.
- `.githooks/`: se trackean hooks del repo porque automatizan el sync de Engram y estandarizan el flujo local.
- `.github/`: se trackean templates, configuraciones y workflows de GitHub como parte del gobierno del repositorio.
- `.opencode/`: se trackean skills, instrucciones y metadatos de configuracion del equipo (por ejemplo, `skill/`, matrices y docs de skilling).

### 2) Generado o efimero (ignorado)

No se versionan caches, salidas temporales, artefactos de ejecucion local ni dependencias runtime recreables.

Incluye, como minimo:

- `.cache/`, `.ruff_cache/`, logs temporales y salidas locales de tooling.
- reportes/resultados de test y e2e generados en runtime (por ejemplo `frontend/playwright-report/`, `frontend/test-results/`).
- artefactos de compilacion y dependencias descargables (`node_modules/`, builds locales, entornos virtuales, etc.).
- runtime deps/estado efimero de `.opencode/` (cache local, temporales, sesiones locales, lockfiles no canonicos si aparecen).
- directorios accidentales por typo tipo `.play*` (ej.: `.playwrite/`, `.playwrigth/`, `.playwright-tmp/`).

### 3) Excepciones condicionales (controladas)

Solo se permite versionar artefactos normalmente ignorados cuando cumplen TODAS estas condiciones:

1. Existe necesidad de auditoria o evidencia tecnica para el PR.
2. Se documenta en el PR que artefacto se incluye, por que y por cuanto tiempo.
3. Se acota a una ruta explicitamente acordada (idealmente `docs/` o carpeta de evidencia con contexto).
4. Se define plan de limpieza (retiro del artefacto en el siguiente ciclo aplicable).

## Nota operativa sobre hooks y CI

- `.githooks/` es automatizacion local para sync de Engram y hygiene operativa.
- No reemplaza CI/CD ni branch protection.
- Los gates de calidad/merge se mantienen en los mecanismos de PR y checks del repositorio (`.github/` + governance de PR).

## Checklist rapido de higiene

- [ ] Lo que agrego es source of truth real y reutilizable.
- [ ] No estoy subiendo cache, salida efimera ni artefactos locales.
- [ ] Si es excepcion, deje justificacion, alcance y plan de limpieza en PR.
- [ ] No existe ningun directorio typo tipo `.play*` dentro del cambio.

## References

- `docs/README.md`
- `docs/getting-started/engram-team-sync.md`
- `docs/getting-started/ai-team-workflow.md`
- `docs/guides/pr-merge-governance.md`
