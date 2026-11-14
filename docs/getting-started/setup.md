# Setup SISEM

> TL;DR: Levantar SISEM con Docker es el camino oficial. El stack operativo usa Django/DRF + React 19 sobre PostgreSQL (dominio Auth) + Redis en contenedores.

## Prerequisitos

- Docker + Docker Compose
- Git

## Opcion recomendada: Docker

1. Clonar repositorio:

```bash
git clone https://github.com/Luis-Ant/SISEM.git
cd <repo-dir>
```

2. Crear env desde ejemplo:

```bash
cp .env.example .env
```

3. Levantar servicios:

```bash
docker compose up --build
```

Notas clave del entorno docker-first:
- Baseline Auth-first: `auth-db` (PostgreSQL) con variables canonicas `AUTH_DB_*`.
- Backend usa `DB_*` derivados de `AUTH_DB_*` en Docker (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`).
- El seed demo (`backend/seed_e2e.py`) se ejecuta automaticamente en el arranque (`RUN_SEED_ON_BOOT=true`).
- La data persiste en volumen Docker (`auth_db_data`).
- SMTP y enlaces de email Auth se parametrizan con `EMAIL_*`, `SISEM_LOGIN_URL` y `SISEM_SUPPORT_EMAIL`.

4. Verificacion rapida:

- Frontend: `http://localhost:5173`
- Backend admin: `http://localhost:5000/admin/`

5. Logs utiles:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

## Opcion local (sin Docker)

Es el entorno de **desarrollo** que se usa hoy (Windows, sin Docker). Docker
se usa **solo en el servidor**, al desplegar: el `Dockerfile` del backend es
el que arma el servidor, asi que cualquier dependencia de sistema nueva
(WeasyPrint/Pango, fuentes) se agrega tambien ahi.

Backend (Python 3.12, entorno virtual `backend\venv`):

```powershell
cd backend
.\venv\Scripts\activate
python manage.py migrate
python manage.py runserver
```

Pruebas de backend:

```powershell
cd backend
.\venv\Scripts\python.exe manage.py test apps.padrones --noinput
```

- Por defecto usan **SQLite en memoria** (`config/settings.py`): no tocan la
  base real.
- Las que SQLite no reproduce (concurrencia, triggers) se corren con
  `TESTS_EN_POSTGRES=1`: Django crea y borra su propia base `test_<nombre>`
  en el mismo servidor.

Frontend:

```powershell
cd frontend
pnpm dev
pnpm vitest run
```

Cuidado con `pip freeze > requirements.txt` en Windows: agrega paquetes que el
`Dockerfile` del servidor no puede compilar (por ejemplo `mysqlclient`).

## Comandos operativos frecuentes

```bash
# Docker
docker compose up --build
docker compose down

# Reset explicito de datos (solo cuando se requiere limpiar DB)
docker compose down -v
docker compose logs -f

# Frontend
cd frontend && bun lint
cd frontend && bun test

# Backend
cd backend && python manage.py test
```

## Troubleshooting rapido

### El frontend no conecta al backend

- Verificar `VITE_API_URL` en `.env`.
- Verificar puerto backend (`5000`) y estado del contenedor.

### El backend no levanta

- Revisar `.env` y credenciales de PostgreSQL Auth (`AUTH_DB_NAME`, `AUTH_DB_USER`, `AUTH_DB_PASSWORD`).
- Revisar logs: `docker compose logs -f backend auth-db`.

### Hooks o gates no activos

- Ejecutar `./.engram/scripts/install-hooks.sh`.
- Confirmar `core.hooksPath`:

```bash
git config --get core.hooksPath
```

## References

- `docs/getting-started/ai-team-workflow.md`
- `docs/getting-started/onboarding-day-1-checklist.md`
- `docs/architecture/overview.md`
