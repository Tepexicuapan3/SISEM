"""
apps/impresion/repositories/print_log_repository.py
=======================================================
Unica capa que toca el ORM para ``PrintLog`` / ``PrintCounter``. Debe
invocarse dentro de ``transaction.atomic()``: el lock del contador solo
vive lo que dura la transaccion.
"""

from apps.impresion.models import PrintCounter, PrintLog


class PrintLogRepository:
    @staticmethod
    def reserve_copy(documento, resource_id):
        """Reserva y devuelve el siguiente numero de copia (1 = ORIGINAL).

        ``get_or_create`` garantiza que la fila exista (la unicidad
        resuelve la carrera de la primera impresion) y luego se re-lee con
        ``select_for_update`` para serializar impresiones concurrentes del
        mismo documento. Si la transaccion hace rollback, el contador
        tambien (sin copias fantasma).
        """
        counter, _ = PrintCounter.objects.get_or_create(
            documento=documento, resource_id=resource_id
        )
        counter = PrintCounter.objects.select_for_update().get(pk=counter.pk)
        counter.last_copy += 1
        counter.save(update_fields=["last_copy"])
        return counter.last_copy

    @staticmethod
    def create_log(**fields):
        """Inserta la fila de bitacora. ``IntegrityError`` si la copia ya
        existe (ultima defensa; en SQLite el lock es no-op)."""
        return PrintLog.objects.create(**fields)
