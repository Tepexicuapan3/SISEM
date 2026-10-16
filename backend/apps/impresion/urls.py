"""
apps/impresion/urls.py
==========================
Endpoint generico de impresion (montado por config/urls.py).
"""

from django.urls import path

from apps.impresion.views import PrintDocumentView

urlpatterns = [
    path(
        "impresion/<str:documento>/<int:resource_id>",
        PrintDocumentView.as_view(),
        name="impresion-documento",
    ),
]
