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


def llave_de_paciente(id_paciente) -> tuple[str, int] | None:
    """
    Transitorio (hasta C6): la llave con la que el codigo que todavia no usa
    id_paciente identifica a ese registro -- (no_exp, pk_num), o el
    cd_provisional / cd_familiar en el lugar del pk_num. None si no existe.
    """
    from apps.consulta_medica.services.patient_link_service import _record_key

    paciente = Patient.objects.filter(pk=id_paciente).first()
    return _record_key(paciente) if paciente is not None else None


def registros_de_la_persona(paciente: Patient) -> list[Patient]:
    """Todas las afiliaciones de la persona (para leer su historia junta)."""
    return list(Patient.objects.filter(person_id=paciente.person_id).order_by("id_patient"))


def resolver_paciente_en_datos(attrs: dict) -> dict:
    """
    Para serializers que reciben al paciente: `idPaciente` (lo que manda la
    pantalla desde C0) o, transitorio, `noExp` + `pkNum`. Con idPaciente se
    completan noExp/pkNum desde cns_paciente para el codigo que todavia usa la
    llave (se retira en C6) y se agrega `idPaciente` resuelto.
    """
    from rest_framework import serializers

    id_paciente = attrs.get("idPaciente")
    if id_paciente is not None:
        llave = llave_de_paciente(id_paciente)
        if llave is None:
            raise serializers.ValidationError({"idPaciente": ["Paciente no encontrado."]})
        attrs["noExp"], attrs["pkNum"] = llave
    elif not attrs.get("noExp"):
        raise serializers.ValidationError({"idPaciente": ["Indica el paciente."]})
    return attrs


def q_pk_registro(pk_num, prefijo="patient__"):
    """
    Filtro por el "pkNum" que conoce la pantalla, contra cns_paciente: el
    PK_NUM de SERMED, o el cd_provisional / cd_familiar de quien no lo tiene.
    """
    from django.db.models import Q

    sin_pk = Q(**{f"{prefijo}pk_num__isnull": True}) & (
        Q(**{f"{prefijo}provisional_code": pk_num}) | Q(**{f"{prefijo}legacy_family_code": pk_num})
    )
    return Q(**{f"{prefijo}pk_num": pk_num}) | sin_pk


def q_registro(no_exp, pk_num, prefijo="patient__"):
    """Filtro por la llave que conoce la pantalla (expediente + pkNum), contra cns_paciente."""
    from django.db.models import Q

    return Q(**{f"{prefijo}no_exp": normalizar_no_exp(no_exp)}) & q_pk_registro(pk_num, prefijo)


def llave_publica(fila) -> tuple[str, int | None]:
    """
    (noExp, pkNum) que se le devuelve a la pantalla para una fila de atencion:
    salen de cns_paciente (la fila ya no las necesita guardar). Mientras haya
    filas sin paciente, se usa lo que la fila tenga.
    """
    from apps.consulta_medica.services.patient_link_service import _record_key

    paciente = getattr(fila, "patient", None)
    if paciente is not None:
        return _record_key(paciente)
    return getattr(fila, "no_exp", None) or "", getattr(fila, "pk_num", None)
