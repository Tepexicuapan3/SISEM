"""
Plan contraer la llave vieja (docs/plans/contraer-llave-paciente.md), bloque C0.

Las pantallas buscan y mandan lo que el usuario eligio: el expediente del
titular + pkNum. Esta es la UNICA conversion de esa llave al registro de
cns_paciente; de aqui para adentro todo se guarda y se lee por id_paciente
(y la historia, por id_persona). El id_paciente nunca sale del servidor.

Que llega en pkNum:
  0                    titular
  PK_NUM de SERMED     familiar
  > 100 000 000        recien nacido provisional (su cd_provisional)
  cd_familiar          familiar del legado sin PK_NUM (transitorio)
"""
from __future__ import annotations

from apps.consulta_medica.models import Patient
from apps.consulta_medica.services.patient_link_service import find_patient_by_record_key
from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp


def paciente_de_llave(no_exp, pk_num, *, crear=True, created_by_id=None) -> Patient | None:
    """
    Registro de la persona elegida en pantalla. Con `crear`, si todavia no
    existe se abre por la puerta central (verifica en SERMED, guardias de
    recien nacido). Un provisional NUNCA se crea aqui: solo existe si se
    registro en Recien nacidos; una clave provisional desconocida da None.
    """
    from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository
    from apps.consulta_medica.services.newborn_service import es_clave_provisional

    if not no_exp or pk_num is None:
        return None
    no_exp = normalizar_no_exp(no_exp)
    paciente = find_patient_by_record_key(no_exp, pk_num)
    if paciente is not None or not crear or es_clave_provisional(pk_num):
        return paciente
    paciente, _ = PatientRepository.get_or_create(no_exp, pk_num, created_by_id=created_by_id)
    return paciente


def registros_de_la_persona(paciente: Patient) -> list[Patient]:
    """Todas las afiliaciones de la persona (para leer su historia junta)."""
    return list(Patient.objects.filter(person_id=paciente.person_id).order_by("id_patient"))
