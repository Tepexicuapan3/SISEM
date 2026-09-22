"""
prescription_dispensation_repository -- acceso jsonb-safe a
VisitPrescriptionItem / VisitPrescription / PrescriptionAuthorization para
la dispensacion de farmacia.

REGLA NO NEGOCIABLE (ver sdd/dispensacion-farmacia/design, riesgo jsonb):
PROHIBIDO `select_related("prescription")` o cualquier navegacion
`item.prescription.*` en este archivo. `VisitPrescription.items` es un
`JSONField` que mapea a una columna `jsonb` en Postgres, con un conflicto
real psycopg2/Django ya documentado en `consulta_medica/models.py:308-314`
-- todo acceso pasa por columnas explicitas via `.values()`, NUNCA por la
fila completa. Tampoco se reusa `PrescriptionItemRepository.to_contract`
(linea 62: `item.prescription.id_visit_id` dispara un lazy-load completo de
`VisitPrescription`, jsonb incluido).
"""
from __future__ import annotations

from apps.consulta_medica.models import (
    PrescriptionAuthorization,
    VisitPrescription,
    VisitPrescriptionItem,
)

# Columnas explicitas -- "prescription__id_visit_id" es un JOIN a una
# columna escalar de VisitPrescription (id_visit_id), NUNCA a `items`.
ITEM_DISPENSATION_FIELDS = (
    "id_prescription_item",
    "prescription_id",
    "prescription__id_visit_id",
    "medication_id",
    "medication__name",
    "medication__presentation",
    "dose",
    "indications",
    "quantity",
    "dispensed_quantity",
    "dispensation_status",
    "status",
)


class PrescriptionDispensationRepository:
    @staticmethod
    def get_prescription_row(prescription_id):
        """Fila de VisitPrescription SIN el campo `items` -- solo lo minimo
        para validar existencia/estatus antes de abrir la transaccion."""
        return (
            VisitPrescription.objects.filter(pk=prescription_id)
            .values("id_prescription", "is_active", "id_visit_id")
            .first()
        )

    @staticmethod
    def list_items_for_prescription(prescription_id):
        """Preview (GET /prescriptions/<id>/dispensation): todos los items
        ACTIVOS de la receta, jsonb-safe."""
        return list(
            VisitPrescriptionItem.objects.filter(
                prescription_id=prescription_id,
                is_active=True,
                status=VisitPrescriptionItem.Status.ACTIVO,
            )
            .order_by("id_prescription_item")
            .values(*ITEM_DISPENSATION_FIELDS)
        )

    @staticmethod
    def lock_items_for_dispense(item_ids):
        """Paso 2 del design: `SELECT ... FOR UPDATE` de los items del
        payload, ordenados por PK (lock deterministico -- evita deadlock y
        es la primera capa de idempotencia, ver design seccion c). Debe
        llamarse DENTRO de `transaction.atomic()`. Items cancelados o de
        otra receta simplemente no aparecen en el resultado -- el use-case
        detecta el faltante comparando contra los ids pedidos."""
        return list(
            VisitPrescriptionItem.objects.select_for_update()
            .filter(
                pk__in=item_ids,
                is_active=True,
                status=VisitPrescriptionItem.Status.ACTIVO,
            )
            .order_by("pk")
            .values(*ITEM_DISPENSATION_FIELDS)
        )

    @staticmethod
    def update_item_dispensation(item_id, *, dispensed_quantity, dispensation_status):
        """Paso 6 del design: UPDATE sobre una fila ya lockeada -- solo se
        llama DESPUES de que el stock se descargo con exito (paso 5), asi
        que no puede fallar por contencion ni por stock."""
        return VisitPrescriptionItem.objects.filter(pk=item_id).update(
            dispensed_quantity=dispensed_quantity,
            dispensation_status=dispensation_status,
        )

    @staticmethod
    def get_latest_authorization_status(prescription_id):
        """Ultima `PrescriptionAuthorization` de la receta, si alguna vez
        se creo -- solo LECTURA del modelo de Autorizacion de Recetas, cero
        archivos de esa feature tocados (ver instrucciones del change). Si
        nunca se creo ninguna (receta sin medicamentos ESPECIAL/
        controlados), se devuelve None y la receta se considera dispensable
        sin gate adicional de autorizacion."""
        row = (
            PrescriptionAuthorization.objects.filter(prescription_id=prescription_id)
            .order_by("-created_at")
            .values("status")
            .first()
        )
        return row["status"] if row else None

    @staticmethod
    def list_prescriptions_with_pending_items():
        """Ids de receta (+ id_visit) con al menos un item ACTIVO en estatus
        pendiente/parcial -- usado por la cola de dispensacion."""
        return list(
            VisitPrescriptionItem.objects.filter(
                is_active=True,
                status=VisitPrescriptionItem.Status.ACTIVO,
                dispensation_status__in=[
                    VisitPrescriptionItem.DispensationStatus.PENDIENTE,
                    VisitPrescriptionItem.DispensationStatus.PARCIAL,
                ],
            )
            .values("prescription_id", "prescription__id_visit_id")
            .distinct()
            .order_by("prescription_id")
        )
