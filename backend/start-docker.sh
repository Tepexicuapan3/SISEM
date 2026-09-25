#!/bin/sh
#start-docker.sh
set -eu

python -m scripts.wait_for_db

if [ "${RUN_MIGRATE_ON_BOOT:-true}" = "true" ]; then
  python manage.py migrate
fi

if [ "${RUN_SEED_ON_BOOT:-true}" = "true" ]; then
  python manage.py seed_auth_access --base --quiet
fi

# Resincroniza el arbol de navegacion (cat_modulos) con el codigo en cada
# arranque -- sin esto, un modulo/ruta nuevo programado en
# navigation_seed.py no aparece en el sidebar hasta que alguien corre el
# comando a mano. Idempotente (get_or_create + diff de campos), seguro de
# correr en cada deploy. --prune desactiva (soft-delete) modulos que ya no
# estan en el seed, nunca los borra.
if [ "${RUN_NAV_SEED_ON_BOOT:-true}" = "true" ]; then
  python manage.py seed_navigation_permissions
  # Da de alta (idempotente) los permisos create/update/delete de los
  # catalogos migrados a CRUD completo (change catalogos-crud). Sin esto,
  # el codigo define el permiso en catalogos_crud_permissions_seed.py pero
  # nunca queda como fila real en cat_permisos -- quedaba pendiente de
  # correr a mano (ver docs/continuar-en-trabajo.md), causando permisos
  # huerfanos reportados por seed_navigation_menu.
  python manage.py seed_catalogos_crud_permissions
  python manage.py seed_navigation_menu --prune
fi

if [ "${RUN_E2E_SEED_ON_BOOT:-false}" = "true" ]; then
  echo "[BOOT][KAN-89] running seed_e2e.py at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python manage.py shell -c "import seed_e2e; seed_e2e.run()"
fi

exec env DJANGO_SETTINGS_MODULE=config.settings daphne -b 0.0.0.0 -p 5000 config.asgi:application
