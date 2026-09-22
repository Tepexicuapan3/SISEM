"""
prescription_dispensation_usecase -- orquesta la dispensacion de farmacia de
una receta AUTORIZADA. Puente receta -> kardex: este modulo hace RBAC +
audit + estado (consulta_medica); `almacen_insumos` escribe el stock real.

Ver sdd/dispensacion-farmacia/design seccion (a) para el orden EXACTO de la
transaccion -- no reordenar los pasos sin releer esa seccion.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.almacen_insumos.models.catalogos import Almacen
from apps.almacen_insumos.models.farmacia import MedicamentoInsumo
from apps.almacen_insumos.services import dispensacion_service
from apps.almacen_insumos.services.kardex_service import InsufficientStockError
from apps.authentication.services.permission_dependencies import (
    evaluate_permission_requirement,
)
from apps.consulta_medica.models import PrescriptionAuthorization, VisitPrescriptionItem
from apps.consulta_medica.repositories.prescription_dispensation_repository import (
    PrescriptionDispensationRepository,
)
from apps.recepcion.models import Visit
from apps.recepcion.services.errors import VisitDomainError

# Un solo permiso cubre las 3 vistas (cola, preview y confirmacion) -- ver
# sdd/dispensacion-farmacia/tasks, fase 4, tarea 4.1.
DISPENSE_PERMISSION_REQUIREMENT = {"allOf": ["farmacia:recetas:dispensar"]}

_QUANTIZE_STEP = Decimal("0.0001")


def _ensure_dispense_role(roles, permissions=None):
    permission_state = evaluate_permission_requirement(
        DISPENSE_PERMISSION_REQUIREMENT, permissions or [],
    )
    if permission_state["granted"]:
        return

    raise VisitDomainError(
        "ROLE_NOT_ALLOWED",
        "No tenes permiso para dispensar recetas.",
        403,
    )


def _ensure_prescription_authorized(prescription_id):
    """
    Gate de lectura sobre Autorizacion de Recetas (cero archivos de esa
    feature tocados, solo un SELECT). Si la receta nunca genero una
    solicitud de autorizacion (solo medicamentos BASICO no controlados) se
    considera dispensable sin gate adicional; si genero una, tiene que
    haber quedado AUTORIZADA -- PENDIENTE o RECHAZADA bloquean.
    """
    status = PrescriptionDispensationRepository.get_latest_authorization_status(prescription_id)
    if status is not None and status != PrescriptionAuthorization.Status.AUTORIZADA:
        raise VisitDomainError(
            "PRESCRIPTION_NOT_AUTHORIZED",
            "La receta todavia no esta autorizada para dispensarse.",
            409,
        )


def _get_active_mappings(medication_ids):
    rows = MedicamentoInsumo.objects.filter(
        medicamento_id__in=medication_ids, is_active=True,
    ).values("medicamento_id", "insumo_id", "factor_conversion", "permite_fraccion")
    return {row["medicamento_id"]: row for row in rows}


def _compute_quantity(quantity, factor_conversion):
    """Decimal siempre, nunca float (ver design seccion b)."""
    return (Decimal(quantity) * factor_conversion).quantize(
        _QUANTIZE_STEP, rounding=ROUND_HALF_UP,
    )


def _get_prescription_or_error(prescription_id):
    prescription_row = PrescriptionDispensationRepository.get_prescription_row(prescription_id)
    if prescription_row is None or not prescription_row["is_active"]:
        raise VisitDomainError("PRESCRIPTION_NOT_FOUND", "Receta no encontrada.", 404)
    return prescription_row


def get_dispensation_preview(prescription_id, roles, permissions=None):
    """GET /prescriptions/<id>/dispensation -- muestra `computedQuantity`
    por item ANTES de confirmar, y marca explicitamente los items sin
    insumo mapeado (spec: "Bloqueo explicito sin mapeo")."""
    _ensure_dispense_role(roles, permissions)

    prescription_row = _get_prescription_or_error(prescription_id)
    items = PrescriptionDispensationRepository.list_items_for_prescription(prescription_id)

    medication_ids = [item["medication_id"] for item in items]
    mappings = _get_active_mappings(medication_ids)

    contract_items = []
    for item in items:
        mapping = mappings.get(item["medication_id"])
        pending_quantity = item["quantity"] - item["dispensed_quantity"]

        computed_quantity = None
        if mapping is not None and pending_quantity > 0:
            computed_quantity = _compute_quantity(pending_quantity, mapping["factor_conversion"])

        contract_items.append({
            "itemId": item["id_prescription_item"],
            "medicationId": item["medication_id"],
            "medicationName": item["medication__name"],
            "presentation": item["medication__presentation"],
            "dose": item["dose"],
            "indications": item["indications"],
            "quantity": item["quantity"],
            "dispensedQuantity": item["dispensed_quantity"],
            "pendingQuantity": pending_quantity,
            "dispensationStatus": item["dispensation_status"],
            "hasMapping": mapping is not None,
            "factorConversion": str(mapping["factor_conversion"]) if mapping else None,
            "permiteFraccion": mapping["permite_fraccion"] if mapping else None,
            "computedQuantity": str(computed_quantity) if computed_quantity is not None else None,
        })

    return {
        "prescriptionId": prescription_row["id_prescription"],
        "visitId": prescription_row["id_visit_id"],
        "items": contract_items,
    }


def list_pending_dispensation_queue(roles, permissions=None, *, id_almacen=None):
    """GET /prescriptions/dispensations/pending?idAlmacen= -- recetas
    AUTORIZADAS con al menos un item pendiente/parcial, filtradas por el
    centro de atencion del almacen de farmacia solicitado."""
    _ensure_dispense_role(roles, permissions)

    almacen = None
    if id_almacen is not None:
        almacen = Almacen.objects.filter(pk=id_almacen, is_active=True).first()
        if almacen is None:
            raise VisitDomainError(
                "VALIDATION_ERROR",
                "Hay errores en el formulario",
                422,
                details={"idAlmacen": ["Almacen invalido o inactivo."]},
            )

    pending_rows = PrescriptionDispensationRepository.list_prescriptions_with_pending_items()
    if not pending_rows:
        return {"items": [], "total": 0}

    visit_ids = [row["prescription__id_visit_id"] for row in pending_rows]
    visits_by_id = {
        row["id_visit"]: row
        for row in Visit.objects.filter(pk__in=visit_ids).values(
            "id_visit", "no_exp", "pk_num", "nombre_paciente", "consultorio__id_center_id",
        )
    }

    items = []
    for row in pending_rows:
        prescription_id = row["prescription_id"]
        visit_id = row["prescription__id_visit_id"]

        visit = visits_by_id.get(visit_id)
        if visit is None:
            continue

        if almacen is not None and visit["consultorio__id_center_id"] != almacen.id_centro_atencion_id:
            continue

        auth_status = PrescriptionDispensationRepository.get_latest_authorization_status(
            prescription_id,
        )
        if auth_status is not None and auth_status != PrescriptionAuthorization.Status.AUTORIZADA:
            continue

        items.append({
            "prescriptionId": prescription_id,
            "visitId": visit_id,
            "noExp": visit["no_exp"],
            "pkNum": visit["pk_num"],
            "patientName": visit["nombre_paciente"],
        })

    return {"items": items, "total": len(items)}


def dispense(
    prescription_id,
    roles,
    *,
    id_almacen,
    item_requests,
    actor_id,
    permissions=None,
    audit_hook,
):
    """
    POST /prescriptions/<id>/dispense -- orden EXACTO (design seccion a):
      1) RBAC + receta AUTORIZADA (solo lectura, FUERA del atomic)
      2) lock de items por PK, DENTRO del atomic
      3) resolver MedicamentoInsumo (422 si falta, sin escribir nada)
      4) calcular con Decimal + validar invariantes de idempotencia
      5) descontar stock PRIMERO (puede levantar InsufficientStockError)
      6) marcar dispensed_quantity/dispensation_status DESPUES
      7) log_event(..., raise_on_error=True)
    El try/except de InsufficientStockError ENVUELVE al atomic -- NUNCA
    vive adentro (TransactionManagementError si se captura dentro).
    """
    _ensure_dispense_role(roles, permissions)

    if not item_requests:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"items": ["Debes indicar al menos un item a dispensar."]},
        )

    item_ids = [request["itemId"] for request in item_requests]
    if len(set(item_ids)) != len(item_ids):
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"items": ["No repitas el mismo item en la misma solicitud."]},
        )
    requested_by_item_id = {request["itemId"]: request["quantity"] for request in item_requests}

    # Paso 1 -- RBAC + estado, SOLO LECTURA, fuera del atomic.
    _get_prescription_or_error(prescription_id)
    _ensure_prescription_authorized(prescription_id)

    almacen = Almacen.objects.filter(
        pk=id_almacen, is_active=True, tipo=Almacen.Tipo.FARMACIA,
    ).first()
    if almacen is None:
        raise VisitDomainError(
            "VALIDATION_ERROR",
            "Hay errores en el formulario",
            422,
            details={"idAlmacen": ["Almacen de farmacia invalido o inactivo."]},
        )

    updates: list[tuple[int, int, str]] = []

    try:
        with transaction.atomic():
            # Paso 2 -- lock ordenado por PK.
            locked_rows = PrescriptionDispensationRepository.lock_items_for_dispense(item_ids)
            locked_by_id = {row["id_prescription_item"]: row for row in locked_rows}

            missing_ids = [item_id for item_id in item_ids if item_id not in locked_by_id]
            if missing_ids:
                raise VisitDomainError(
                    "PRESCRIPTION_ITEM_NOT_FOUND",
                    "Uno o mas items de receta no existen o estan cancelados.",
                    404,
                    details={"itemIds": missing_ids},
                )

            foreign_item_ids = [
                item_id for item_id, row in locked_by_id.items()
                if row["prescription_id"] != prescription_id
            ]
            if foreign_item_ids:
                raise VisitDomainError(
                    "PRESCRIPTION_ITEM_NOT_FOUND",
                    "Uno o mas items no pertenecen a esta receta.",
                    404,
                    details={"itemIds": foreign_item_ids},
                )

            # Paso 3 -- resolver mapeo, 422 global si falta uno, sin
            # escribir nada todavia.
            medication_ids = [row["medication_id"] for row in locked_by_id.values()]
            mappings = _get_active_mappings(medication_ids)
            unmapped_medication_ids = sorted({
                row["medication_id"]
                for row in locked_by_id.values()
                if row["medication_id"] not in mappings
            })
            if unmapped_medication_ids:
                raise VisitDomainError(
                    "MEDICATION_NOT_MAPPED",
                    "Uno o mas medicamentos no tienen insumo mapeado en farmacia.",
                    422,
                    details={"medicationIds": unmapped_medication_ids},
                )

            # Paso 4 -- calcular con Decimal + invariantes de idempotencia
            # (ver design seccion c): ALREADY_DISPENSED /
            # DISPENSATION_EXCEEDS_PRESCRIBED sobre las filas ya lockeadas.
            lineas = []
            for item_id in item_ids:
                row = locked_by_id[item_id]
                requested_quantity = requested_by_item_id[item_id]

                if row["dispensation_status"] == VisitPrescriptionItem.DispensationStatus.DISPENSADO:
                    raise VisitDomainError(
                        "ALREADY_DISPENSED",
                        "Este item de receta ya fue dispensado por completo.",
                        409,
                        details={"itemId": item_id},
                    )

                new_dispensed_quantity = row["dispensed_quantity"] + requested_quantity
                if new_dispensed_quantity > row["quantity"]:
                    raise VisitDomainError(
                        "DISPENSATION_EXCEEDS_PRESCRIBED",
                        "La cantidad solicitada excede lo prescrito para este item.",
                        409,
                        details={
                            "itemId": item_id,
                            "quantity": row["quantity"],
                            "dispensedQuantity": row["dispensed_quantity"],
                            "requestedQuantity": requested_quantity,
                        },
                    )

                mapping = mappings[row["medication_id"]]
                computed_quantity = _compute_quantity(requested_quantity, mapping["factor_conversion"])

                if not mapping["permite_fraccion"] and computed_quantity % 1 != 0:
                    raise VisitDomainError(
                        "FRACTIONAL_QUANTITY_NOT_ALLOWED",
                        "La cantidad calculada no admite fracciones para este insumo.",
                        422,
                        details={"itemId": item_id, "computedQuantity": str(computed_quantity)},
                    )

                new_status = (
                    VisitPrescriptionItem.DispensationStatus.DISPENSADO
                    if new_dispensed_quantity == row["quantity"]
                    else VisitPrescriptionItem.DispensationStatus.PARCIAL
                )

                lineas.append(dispensacion_service.DispensacionLinea(
                    insumo_id=mapping["insumo_id"],
                    cantidad=computed_quantity,
                    prescription_item_id=item_id,
                ))
                updates.append((item_id, new_dispensed_quantity, new_status))

            # Paso 5 -- descontar stock PRIMERO. `InsufficientStockError`
            # NO se captura aca -- sube hasta el except de afuera.
            dispensacion_service.registrar_dispensacion(
                almacen=almacen,
                lineas=lineas,
                created_by_id=actor_id,
            )

            # Paso 6 -- marcar estado DESPUES, ya con el stock descontado.
            for item_id, new_dispensed_quantity, new_status in updates:
                PrescriptionDispensationRepository.update_item_dispensation(
                    item_id,
                    dispensed_quantity=new_dispensed_quantity,
                    dispensation_status=new_status,
                )

            # Paso 7 -- audit estricta DENTRO del atomic.
            audit_hook(
                resource_id=prescription_id,
                datos_antes=None,
                datos_despues={
                    "idAlmacen": almacen.pk,
                    "items": [
                        {
                            "itemId": item_id,
                            "dispensedQuantity": new_dispensed_quantity,
                            "dispensationStatus": new_status,
                        }
                        for item_id, new_dispensed_quantity, new_status in updates
                    ],
                },
                strict=True,
            )
    except InsufficientStockError as exc:
        raise VisitDomainError("INSUFFICIENT_STOCK", str(exc), 409) from exc

    return {
        "prescriptionId": prescription_id,
        "idAlmacen": almacen.pk,
        "items": [
            {
                "itemId": item_id,
                "dispensedQuantity": new_dispensed_quantity,
                "dispensationStatus": new_status,
            }
            for item_id, new_dispensed_quantity, new_status in updates
        ],
    }
