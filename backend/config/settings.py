"""
Django settings — SISEM + SIRES unificado.
"""



import os
import sys
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from corsheaders.defaults import default_headers
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent
POSTAL_CODES_FILE_PATH = BASE_DIR / "storage" / "catalogs" / "codigos_postales.txt"

SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-_n@vgo%v8a9+b#2ywbwea_k0++f6e44=$2)kjd$d&*gi*jbl4)",
)

DEBUG = config("DEBUG", default=True, cast=bool)

ALLOW_ALL_HOSTS = config("ALLOW_ALL_HOSTS", default=False, cast=bool)
if ALLOW_ALL_HOSTS:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [
        host.strip()
        for host in str(
            config(
                "ALLOWED_HOSTS",
                default="localhost,127.0.0.1,0.0.0.0,backend,sires-backend,host.docker.internal",
            )
        ).split(",")
        if host.strip()
    ]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "channels",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    # Local apps
    "apps.authentication",
    "apps.recepcion",
    "apps.somatometria",
    "apps.consulta_medica",
    "apps.pases",
    "apps.catalogos",
    "apps.administracion",
    "apps.personal",
    "apps.medicos",
    "apps.realtime",
    "apps.farmacia",
    'apps.recepcion.routers',
    "apps.contratos_oxigeno",
    "apps.almacen_insumos",
    "apps.portal_citas",
    "apps.comunicados",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.administracion.middleware.request_id.RequestIDMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "middlewares.auth.JWTAuthenticationMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Oracle ────────────────────────────────────────────────────────────────────
ORACLE_CONFIG = {
    "user": config("ORACLE_USER", default="SERMED"),
    "password": config("ORACLE_PASSWORD", default=""),
    "host": config("ORACLE_HOST", default="11.121.252.12"),
    "port": config("ORACLE_PORT", default="1526"),
    "service_name": config("ORACLE_SERVICE", default="NOMINAP"),
    "instant_client_dir": config(
        "ORACLE_INSTANT_CLIENT", default=r"C:\oracle\instantclient_11_2"
    ),
}

# ── Databases ─────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_NAME", default="sermed"),
        "USER": config("POSTGRES_USER", default="sermed"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="112233"),
        "HOST": config("POSTGRES_HOST", default="50.192.41.223"),
        "PORT": config("POSTGRES_PORT", default="5432"),
        "OPTIONS": {"client_encoding": "UTF8", "options": "-c search_path=sires,public"},
    },
    "expedientes": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("EXPEDIENTES_NAME", default="sermed"),
        "USER": config("EXPEDIENTES_USER", default="sermed"),
        "PASSWORD": config("EXPEDIENTES_PASSWORD", default="112233"),
        "HOST": config("EXPEDIENTES_HOST", default="127.0.0.1"),
        "PORT": config("EXPEDIENTES_PORT", default="5432"),
        "OPTIONS": {"client_encoding": "UTF8"},
    },
}

if "test" in sys.argv:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

DATABASE_ROUTERS = [
    "routers.ExpedientesRouter",
    "apps.recepcion.routers.RecepcionCitasRouter",
]

# ── Channels ──────────────────────────────────────────────────────────────────
CHANNEL_REDIS_URL = config("CHANNEL_REDIS_URL", default="")

if "test" in sys.argv or not CHANNEL_REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [CHANNEL_REDIS_URL],
            },
        }
    }

# ── Cache (Redis) ────────────────────────────────────────────────────────────
# DB distinta a la de Celery (db=1) para no mezclar keyspaces.
CACHE_REDIS_URL = config("CACHE_REDIS_URL", default="redis://127.0.0.1:6379/2")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": CACHE_REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

if "test" in sys.argv:
    # LocMemCache en tests: evita ensuciar el Redis real con sesiones
    # activas que Django no rollbackea entre tests (a diferencia de la DB).
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# ── Feature flags ────────────────────────────────────────────────────────────

# D8 (sdd/medico-pk-independiente/design): habilita el alta de médicos SIN
# usuario del sistema (medicos.CatMedico.id_usuario = NULL). Se mantiene
# apagado hasta Fase 5 del cambio: mientras la respuesta de la API siga
# exponiendo "id" como id_usuario_id (contrato dual, D7), un médico sin
# usuario serializaría "id": null y rompería el frontend legacy. Mantenerlo
# apagado también garantiza que el rollback de la migración de switch
# (medicos/0007_switch_surrogate_pk.py) siga siendo posible sin pérdida de
# datos (restaurar PRIMARY KEY sobre id_usuario falla si existe algún
# médico con id_usuario NULL).
MEDICOS_ALLOW_SIN_USUARIO = config("MEDICOS_ALLOW_SIN_USUARIO", default=False, cast=bool)

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL      = config("CELERY_BROKER_URL",     default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND  = config("CELERY_RESULT_BACKEND",  default="redis://127.0.0.1:6379/1")
CELERY_TIMEZONE        = "America/Mexico_City"
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT  = ["json"]

CELERY_BEAT_SCHEDULE = {
    "citas-recordatorios-24h": {
        "task": "apps.recepcion.tasks.enviar_recordatorios_proximos",
        "schedule": crontab(hour=8, minute=0),
    },
    "citas-generar-slots": {
        "task": "apps.recepcion.tasks.generar_slots_todos_medicos",
        "schedule": crontab(hour=1, minute=0),  # diario a la 1am
    },
    "citas-marcar-no-asistio": {
        "task": "apps.recepcion.tasks.marcar_no_asistio",
        "schedule": crontab(minute=0),
    },
    "auth-cerrar-sesiones-abandonadas": {
        "task": "apps.authentication.tasks.cerrar_sesiones_abandonadas",
        "schedule": 90.0,  # segundos
    },
}

# ── Citas ─────────────────────────────────────────────────────────────────────
# ``frontend/`` vive en la raíz del repo, como hermano de ``backend/`` (donde
# está este settings.py). BASE_DIR ya es ``backend/`` (ver arriba), así que
# hay que subir un nivel más con ``.parent`` para llegar a la raíz del repo
# antes de bajar a ``frontend/...`` -- si no, la ruta resuelve a
# ``backend/frontend/...`` (inexistente) y el logo nunca se dibuja en el PDF.
CITAS_LOGO_PATH = (
    BASE_DIR.parent
    / "frontend"
    / "public"
    / "assets"
    / "brand"
    / "logos"
    / "primary"
    / "sisem.webp"
)
# Marca de agua del comprobante del portal (Fase 5): los dos logos "unidos"
# (SISEM + Citas en Línea, conectados) -- mismo compuesto que usa el header
# del correo OTP del portal (ver apps/portal_citas/services/email_service.py).
# Vive DENTRO de backend/ (a diferencia de CITAS_LOGO_PATH) porque no
# necesita hostearse en ningún lado: el PDF lo lee directo del disco, no es
# una imagen embebida en un correo.
CITAS_COMPROBANTE_WATERMARK_PATH = (
    BASE_DIR
    / "apps"
    / "portal_citas"
    / "static"
    / "portal_citas"
    / "email"
    / "logos-unidos-sisem-portal.png"
)
CITAS_BASE_URL = config("CITAS_BASE_URL", default="https://sires.metro.cdmx.gob.mx")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# ── Media (módulo Comunicados) ──────────────────────────────────────────────
# Archivos subidos desde SISEM (flyers/anuncios del portal de citas). Servido
# por nginx vía `alias` en `nginx/proxy.conf` (ver `apps.comunicados`), NO por
# Django -- greenfield, no existía ninguna clave MEDIA_* antes de este change.
MEDIA_URL = "/media/"
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/app/media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "EXCEPTION_HANDLER": "apps.administracion.exceptions.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "USER_ID_FIELD": "id_usuario",
}

# TTL de la sesion activa en Redis (control de sesion unica, sliding
# expiration). Si nadie hace un request autenticado en este lapso, la
# sesion se libera sola y "auth-cerrar-sesiones-abandonadas" cierra su
# fila de historial en el siguiente barrido.
ACTIVE_SESSION_TTL_SECONDS = config("ACTIVE_SESSION_TTL_SECONDS", default=60 * 30, cast=int)

# ── Hardening HTTPS/cookies ───────────────────────────────────────────────────
# El gateway externo (ver repo ngnix-gateway, sisem.conf/citas.conf) SI
# termina TLS real (cert firmado por la CA interna) y manda X-Forwarded-Proto
# correcto -- nginx/proxy.conf de este repo lo respeta sin pisarlo. Por eso
# las cookies Secure van atadas a DEBUG (prendidas salvo en dev local sin
# proxy), no en False fijo. SECURE_SSL_REDIRECT queda en False a proposito:
# el redirect 80->443 ya lo hace el gateway, duplicarlo en Django generaria
# un loop si el header llegara a fallar.
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=not DEBUG, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False, cast=bool
)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=False, cast=bool)
# nginx (proxy.conf) ya manda X-Forwarded-Proto -- con esto Django sabe que
# la conexion real del cliente fue HTTPS aunque a el le llegue por HTTP
# desde el proxy interno, y no entra en loop de redirect.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── CORS / CSRF ───────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in str(
        config(
            "CORS_ALLOWED_ORIGINS",
            default="http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173",
        )
    ).split(",")
    if origin.strip()
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?$",
    r"^https?://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$",
    r"^https?://172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}(:\d+)?$",
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in str(
        config(
            "CSRF_TRUSTED_ORIGINS",
            default="http://localhost:5173,http://127.0.0.1:5173",
        )
    ).split(",")
    if origin.strip()
]

WS_ALLOW_ALL_ORIGINS = config("WS_ALLOW_ALL_ORIGINS", default=False, cast=bool)
WS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in str(config("WS_ALLOWED_ORIGINS", default="")).split(",")
    if origin.strip()
]

CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-request-id",
    "x-csrf-token",
]

CORS_EXPOSE_HEADERS = [
    "X-Request-ID",
    "X-Auth-Revision",
]

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER)
EMAIL_TIMEOUT = config("EMAIL_TIMEOUT", default=10, cast=int)

# ── SISEM branding ────────────────────────────────────────────────────────────
SISEM_LOGIN_URL = config("SISEM_LOGIN_URL", default="http://localhost:5173/login")
SISEM_SUPPORT_EMAIL = config(
    "SISEM_SUPPORT_EMAIL",
    default=DEFAULT_FROM_EMAIL or "soporte@sisem.local",
)
ALLOW_USER_CREATE_WITHOUT_EMAIL = config(
    "ALLOW_USER_CREATE_WITHOUT_EMAIL", default=False, cast=bool
)

# ── RBAC feature flags ────────────────────────────────────────────────────────
RBAC_READ_S1_ENABLED = config("RBAC_READ_S1_ENABLED", default=False, cast=bool)
RBAC_READ_SLICE_SOURCE = config("RBAC_READ_SLICE_SOURCE", default="auto")
RBAC_ROLE_MUTATION_S2_ENABLED = config(
    "RBAC_ROLE_MUTATION_S2_ENABLED", default=False, cast=bool
)
RBAC_ROLE_PERMISSION_S3_ENABLED = config(
    "RBAC_ROLE_PERMISSION_S3_ENABLED", default=False, cast=bool
)

# ── Navigation menu feature flags ─────────────────────────────────────────────
NAVIGATION_MENU_DB_ENABLED = config(
    "NAVIGATION_MENU_DB_ENABLED", default=True, cast=bool
)
NAVIGATION_MENU_SOURCE = config("NAVIGATION_MENU_SOURCE", default="auto")

# ── Portal Citas en Línea (Fase 6 — cancelación) ──────────────────────────────
# Ventana mínima (en horas) antes de la fecha/hora de la cita para permitir
# que el paciente la cancele por su cuenta desde el portal. Ajustable según
# política institucional (ej. si el hospital decide requerir más o menos
# anticipación para poder reasignar el horario liberado).
PORTAL_CANCELACION_VENTANA_HORAS = config(
    "PORTAL_CANCELACION_VENTANA_HORAS", default=2, cast=int
)
