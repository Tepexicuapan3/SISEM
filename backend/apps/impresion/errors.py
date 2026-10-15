"""
apps/impresion/errors.py
============================
Excepcion de dominio del modulo Impresion. Mismo contrato
``code``/``message``/``status_code``/``details`` que
``apps.comunicados.errors.ComunicadoError`` para reusar
``response_service.error_response``.
"""


class PrintError(Exception):
    def __init__(self, code, message, status_code, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
