from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('api/v1/', include('apps.administracion.urls')),
    path('api/v1/', include('apps.catalogos.urls')),
    path('api/v1/', include('apps.authentication.urls')),
    path('api/v1/', include('apps.recepcion.urls')),
    path('api/v1/', include('apps.somatometria.urls')),
    path('api/v1/', include('apps.consulta_medica.urls')),
    path('api/v1/', include('apps.pases.urls')),
    path('api/v1/', include('apps.cirugias.urls')),
    path('api/v1/', include('apps.ambulancias.urls')),
    path('api/v1/', include('apps.farmacia.urls')),
    path('api/v1/', include('apps.medicos.urls')),
    path('api/v1/', include('apps.contratos_oxigeno.urls')),
    path('api/v1/', include('apps.almacen_insumos.urls')),
    path('api/v1/', include('apps.portal_citas.urls')),
    path('api/v1/', include('apps.comunicados.urls')),
    #path('recetas/', include('apps.recetas.urls')),
]

# En producción (DEBUG=False), nginx sirve /media/ directo desde el volumen
# Docker (ver nginx/proxy.conf), Django nunca llega a manejar esas requests.
# En desarrollo local sin nginx delante (runserver directo), no hay quien
# responda /media/... salvo este fallback estándar de Django.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
