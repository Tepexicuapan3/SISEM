"""Pedir la autorizacion de una receta cuando la necesita.

El registro de la autorizacion se crea al agregar el medicamento (como
siempre). La solicitud en el motor de autorizaciones, que es la que avisa al
autorizador, se crea al FINALIZAR la consulta con la receta completa
(decision del usuario 2026-11-12): `sync_motor=False` mientras la consulta
esta abierta. Vive aparte de los casos de uso de consulta y de receta para
que los dos lo usen sin importarse entre si.
"""
from apps.consulta_medica.repositories.prescription_authorization_repository import (
    PrescriptionAuthorizationRepository,
)
from apps.consulta_medica.repositories.prescription_item_repository import PrescriptionItemRepository
from apps.consulta_medica.services import autorizacion_motor_service as motor
from apps.catalogos.models import Medicamentos


def request_authorization_if_needed(prescription, visit, *, sync_motor=True):
    """
    Recalcula los conteos de la receta completa (items ACTIVOS) y crea una
    solicitud de autorizacion PENDIENTE si hace falta (al menos un
    medicamento ESPECIAL o controlado) y todavia no hay una pendiente --
    ver docstring de PrescriptionAuthorization.
    """
    items = PrescriptionItemRepository.list_for_prescription(prescription)

    medications_count = 0
    specialized_count = 0
    controlled_count = 0
    for item in items:
        medications_count += 1
        if item.medication.cuadro_basico == Medicamentos.CuadroBasico.ESPECIAL:
            specialized_count += 1
        if item.medication.is_controlled:
            controlled_count += 1

    requires_authorization = any(item.medication.requires_prescription_authorization for item in items)
    if not requires_authorization:
        return

    pending = PrescriptionAuthorizationRepository.get_pending_for_prescription(prescription)
    if pending is not None:
        # Ya hay una solicitud pendiente -- se actualiza para reflejar el
        # estado ACTUAL de la receta (el autorizador debe ver los
        # conteos vigentes, no un snapshot congelado del primer item que
        # disparo la solicitud).
        PrescriptionAuthorizationRepository.update_counts(
            pending,
            medications_count=medications_count,
            specialized_count=specialized_count,
            controlled_count=controlled_count,
        )
        # Motor de autorizaciones (solo con AUTORIZACIONES_RECETAS_V2): recalcula su solicitud.
        if sync_motor:
            motor.sincronizar_solicitud(pending)
        return

    authorization = PrescriptionAuthorizationRepository.create(
        prescription,
        visit,
        prescribed_by_id=prescription.created_by_id,
        medications_count=medications_count,
        specialized_count=specialized_count,
        controlled_count=controlled_count,
    )
    # Motor de autorizaciones (solo con AUTORIZACIONES_RECETAS_V2): crea su solicitud.
    if sync_motor:
        motor.sincronizar_solicitud(authorization)
