"""
Plan identidad del paciente, Fases 6 y 7 (bloque C1): recien nacido
provisional y su vinculacion con SERMED.

  - Alta (registrar_recien_nacido): como el legado (body-registro.jsp), solo
    hijos, desde el expediente del titular. Registro de cns_paciente con
    no_exp del titular, pk_num NULL y cd_familiar de la secuencia de
    provisionales (> 100 000 000: por encima del PK_NUM de SERMED; el legado llega a ~52 896), mas
    PACIENTE_PROVISIONAL. Vigencia: hoy + DIAS_VIGENCIA_RN (60). Clinica: la de
    adscripcion del titular. CURP opcional.
  - Candidatos: familiares de SERMED del mismo titular con la misma fecha de
    nacimiento y el mismo sexo, que no se hayan descartado.
  - Vincular (un clic): el registro de SERMED del bebe pasa a la MISMA persona
    que el provisional. Nada se mueve: la historia del provisional queda en su
    registro y se ve por persona (Fase 4). El provisional queda B (vinculado).
  - Descartar: "no es la misma persona"; no vuelve a proponerse.
  - Guardias contra duplicados:
      * candado por titular al registrar (dos personas registrando al mismo
        bebe a la vez) y control de provisional repetido;
      * guardia 2: si SERMED ya tiene ese hijo, se avisa en vez de crear un
        provisional innecesario;
      * guardia 1 (verificar_rn_pendiente): no se abre un registro nuevo de un
        familiar de SERMED que coincide con un provisional pendiente: primero
        se vincula.
Todo queda en cns_bitacora_cambios. Interruptor: IDENTIDAD_RECIEN_NACIDOS.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from apps.consulta_medica.models import (
    ChangeLog,
    Patient,
    PatientIdentifier,
    PersonDiscard,
    ProvisionalPatient,
    Sex,
)
from apps.consulta_medica.services.change_log_service import PROCESS_SIRES, build_key, record_change
from apps.consulta_medica.services.curp_rules import curp_mismatches, normalize_curp, sermed_sex_to_sires
from apps.consulta_medica.services.patient_identifier_service import register_identifier
from apps.consulta_medica.services.patient_registry_service import (
    ORIGEN_ATENCION,
    ORIGEN_REGULARIZACION,
    normalizar_no_exp,
)
from apps.recepcion.services.errors import VisitDomainError

logger = logging.getLogger(__name__)

# Por encima del maximo PK_NUM posible de SERMED (CAT_FAMILIAR.PK_NUM es
# NUMBER(8): hasta 99 999 999). Recepcion y las tablas operativas usan el
# cd_familiar del provisional en el lugar del pk_num (como ya pasa con los
# familiares del legado sin PK_NUM): asi nunca puede confundirse con un
# familiar real. El legado llega a ~52 896.
BASE_CD_FAMILIAR = 100_000_000


def es_clave_provisional(pk_num) -> bool:
    """La "pk_num" que llega es el cd_familiar de un recien nacido provisional."""
    return isinstance(pk_num, int) and pk_num > BASE_CD_FAMILIAR
MENSAJE_SERMED_NO_DISPONIBLE = (
    "No se pudo consultar SERMED en este momento. No significa que el expediente no exista: avisá a sistemas."
)


def habilitado() -> bool:
    return bool(settings.IDENTIDAD_PACIENTE.get("RECIEN_NACIDOS"))


def _exigir_habilitado():
    if not habilitado():
        raise VisitDomainError(
            "RECIEN_NACIDOS_DESHABILITADO", "El registro de recién nacidos no está habilitado.", 409,
        )


def _candado(clave: str) -> None:
    """Candado de la transaccion en curso (solo Postgres; SQLite serializa)."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [clave])


def _siguiente_cd_familiar() -> int:
    _candado("sires:cd_familiar_provisional")
    actual = Patient.objects.filter(legacy_family_code__gt=BASE_CD_FAMILIAR).aggregate(m=Max("legacy_family_code"))["m"]
    return (actual or BASE_CD_FAMILIAR) + 1


def _usuario(user):
    return user if user is not None else PROCESS_SIRES


def _texto(valor) -> str | None:
    texto = str(valor).strip() if valor is not None else ""
    return texto or None


# ── SERMED (replica, solo lectura) ───────────────────────────────────────────

def _titular_en_sermed(no_exp: str):
    from apps.administracion.models import CatEmpleado

    try:
        return CatEmpleado.objects.filter(no_exp=no_exp).first()
    except Exception as exc:
        logger.error("No se pudo consultar el titular %s en SERMED: %s", no_exp, exc)
        raise VisitDomainError("EXPEDIENTES_NO_DISPONIBLE", MENSAJE_SERMED_NO_DISPONIBLE, 503) from exc


def _familiares_sermed(no_exp: str) -> list | None:
    """Familiares de SERMED del titular; None si la replica no responde."""
    from apps.administracion.models import CatFamiliar

    try:
        return list(CatFamiliar.objects.filter(no_expf=no_exp).order_by("pk_num"))
    except Exception as exc:
        logger.error("No se pudo consultar los familiares de %s en SERMED: %s", no_exp, exc)
        return None


def _coincide(familiar, fecha_nacimiento: date | None, sexo: str | None) -> bool:
    """Misma fecha de nacimiento y mismo sexo. Si SERMED no trae el sexo, basta
    la fecha: preferimos proponer de mas (una persona confirma) que perder la
    coincidencia."""
    if not fecha_nacimiento or familiar.fe_nac != fecha_nacimiento:
        return False
    sexo_sermed = sermed_sex_to_sires(familiar.cd_sexo)
    return sexo_sermed is None or sexo is None or sexo_sermed == sexo


def _nombre(apellido_p, apellido_m, nombre) -> str:
    return " ".join(p for p in (nombre, apellido_p, apellido_m) if p)


def _familiar_contract(familiar) -> dict:
    return {
        "pkNum": familiar.pk_num,
        "nombre": _nombre(familiar.ds_paterno, familiar.ds_materno, familiar.ds_nombre),
        "fechaNacimiento": familiar.fe_nac.isoformat() if familiar.fe_nac else None,
        "sexo": sermed_sex_to_sires(familiar.cd_sexo),
        "parentesco": _texto(familiar.cd_parentesco),
    }


# ── Lectura ──────────────────────────────────────────────────────────────────

def candidatos(provisional: ProvisionalPatient) -> list[dict]:
    """Familiares de SERMED que podrian ser este recien nacido."""
    if provisional.status != ProvisionalPatient.Status.PENDING:
        return []
    familiares = _familiares_sermed(provisional.holder_no_exp)
    if not familiares:
        return []
    from apps.consulta_medica.services.patient_link_service import find_patient_by_record_key

    paciente = provisional.patient
    descartados = set(
        PersonDiscard.objects.filter(patient=paciente).values_list("candidate_no_exp", "candidate_pk_num")
    )
    resultado = []
    for familiar in familiares:
        if not _coincide(familiar, paciente.birth_date, paciente.sex):
            continue
        if (provisional.holder_no_exp, familiar.pk_num) in descartados:
            continue
        registro = find_patient_by_record_key(provisional.holder_no_exp, familiar.pk_num)
        if registro is not None and registro.person_id == paciente.person_id:
            continue
        resultado.append({**_familiar_contract(familiar), "yaTieneRegistro": registro is not None})
    return resultado


def _contract(provisional: ProvisionalPatient) -> dict:
    paciente = provisional.patient
    pendiente = provisional.status == ProvisionalPatient.Status.PENDING
    return {
        "idPaciente": paciente.pk,
        "cdFamiliar": paciente.legacy_family_code,
        "nombre": _nombre(paciente.paternal_surname, paciente.maternal_surname, paciente.first_name),
        "fechaNacimiento": paciente.birth_date.isoformat() if paciente.birth_date else None,
        "sexo": paciente.sex,
        "curp": paciente.curp,
        "madre": provisional.mother_name,
        "orden": provisional.birth_order,
        "estatus": provisional.status,
        "clinica": provisional.clinic_code,
        "vigencia": provisional.valid_until.isoformat(),
        "vigente": pendiente and provisional.valid_until >= timezone.localdate(),
        "pkNumSermed": provisional.linked_pk_num,
        "candidatos": candidatos(provisional) if pendiente else [],
    }


def vigente(provisional: ProvisionalPatient) -> bool:
    return (
        provisional.status == ProvisionalPatient.Status.PENDING
        and provisional.valid_until >= timezone.localdate()
    )


def provisional_por_clave(no_exp: str, pk_num) -> ProvisionalPatient | None:
    """Provisional de recepcion: (no_exp del titular, cd_familiar en lugar del pk_num)."""
    if not es_clave_provisional(pk_num):
        return None
    return (
        ProvisionalPatient.objects.select_related("patient")
        .filter(holder_no_exp=normalizar_no_exp(no_exp), patient__legacy_family_code=pk_num).first()
    )


def miembros_recepcion(no_exp: str, *, historico: bool) -> list[dict]:
    """
    Plan identidad, bloque C2: provisionales pendientes como familiares para el
    buscador de recepcion (check-in, agenda). Viajan con su cd_familiar en el
    lugar del pk_num; todo lo que sigue (visita, signos, consulta, alergias)
    los resuelve por esa llave. Sin el interruptor, no aparece ninguno.
    """
    if not habilitado():
        return []
    miembros = []
    provisionales = (
        ProvisionalPatient.objects.select_related("patient")
        .filter(holder_no_exp=normalizar_no_exp(no_exp), status=ProvisionalPatient.Status.PENDING)
        .order_by("patient__birth_date", "birth_order")
    )
    for provisional in provisionales:
        activo = vigente(provisional)
        if not historico and not activo:
            continue
        paciente = provisional.patient
        nacimiento = paciente.birth_date
        edad = None
        if nacimiento:
            hoy = timezone.localdate()
            edad = hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
        miembros.append({
            "noExp": provisional.holder_no_exp,
            "pkNum": paciente.legacy_family_code,
            "nombre": _nombre(paciente.paternal_surname, paciente.maternal_surname, paciente.first_name),
            "edad": edad,
            "fechaNac": nacimiento.isoformat() if nacimiento else None,
            "parentesco": "RECIEN NACIDO (PROVISIONAL)",
            "estatus": "ACTIVO" if activo else "NO ACTIVO",
            "cdClinica": provisional.clinic_code,
            "foto": None,
            "provisional": True,
            "idPaciente": paciente.pk,
        })
    return miembros


def listar(no_exp: str) -> dict:
    no_exp = normalizar_no_exp(no_exp)
    provisionales = (
        ProvisionalPatient.objects.filter(holder_no_exp=no_exp)
        .select_related("patient").order_by("status", "patient__birth_date", "birth_order")
    )
    return {"habilitado": habilitado(), "provisionales": [_contract(p) for p in provisionales]}


# ── Alta ─────────────────────────────────────────────────────────────────────

def registrar_recien_nacido(
    no_exp, *, paterno, materno, nombre, fecha_nacimiento: date, sexo, madre=None, orden=1,
    curp=None, user=None, confirmar_aunque_exista=False,
) -> dict:
    _exigir_habilitado()
    no_exp = normalizar_no_exp(no_exp)
    paterno, materno, nombre = _texto(paterno), _texto(materno), _texto(nombre)
    errores = {}
    if not nombre:
        errores["firstName"] = ["El nombre es obligatorio."]
    if not paterno and not materno:
        errores["paternalSurname"] = ["Se requiere al menos un apellido."]
    if not fecha_nacimiento:
        errores["birthDate"] = ["La fecha de nacimiento es obligatoria."]
    elif fecha_nacimiento > timezone.localdate():
        errores["birthDate"] = ["La fecha de nacimiento no puede ser futura."]
    if sexo not in Sex.values:
        errores["sex"] = ["El sexo debe ser M, F o X."]
    if not isinstance(orden, int) or orden < 1:
        errores["birthOrder"] = ["El orden de nacimiento empieza en 1."]
    curp_normalizada = None
    if _texto(curp):
        curp_normalizada = normalize_curp(curp)
        if curp_normalizada is None:
            errores["curp"] = ["CURP con formato inválido."]
        elif fecha_nacimiento and sexo in Sex.values:
            for campo, mensaje in curp_mismatches(curp_normalizada, birth_date=fecha_nacimiento, sex=sexo).items():
                errores.setdefault(campo, []).append(mensaje)
    if errores:
        raise VisitDomainError("VALIDATION_ERROR", "Hay errores en el formulario.", 422, details=errores)

    titular = _titular_en_sermed(no_exp)
    if titular is None:
        raise VisitDomainError(
            "TITULAR_NO_EN_SERMED", f"El expediente {no_exp} no existe en SERMED.", 404,
        )
    if curp_normalizada:
        duenio = Patient.objects.filter(curp=curp_normalizada).first()
        if duenio:
            raise VisitDomainError(
                "CURP_ALREADY_REGISTERED", f"Esta CURP ya pertenece al expediente {duenio.no_exp}.", 409,
                details={"curp": ["CURP registrada en otro paciente."], "noExp": duenio.no_exp},
            )

    user_id = getattr(user, "pk", None)
    with transaction.atomic():
        # Dos personas registrando al mismo bebe a la vez: la segunda espera y
        # encuentra el provisional de la primera.
        _candado(f"sires:recien_nacido:{no_exp}")
        if ProvisionalPatient.objects.filter(
            holder_no_exp=no_exp, status=ProvisionalPatient.Status.PENDING, birth_order=orden,
            patient__birth_date=fecha_nacimiento, patient__sex=sexo,
        ).exists():
            raise VisitDomainError(
                "RN_YA_REGISTRADO",
                "Ya hay un recién nacido provisional de este titular con esa fecha, sexo y orden de nacimiento.",
                409,
            )
        if not confirmar_aunque_exista:
            en_sermed = [f for f in (_familiares_sermed(no_exp) or []) if _coincide(f, fecha_nacimiento, sexo)]
            if en_sermed:
                raise VisitDomainError(
                    "RN_YA_EN_SERMED",
                    "SERMED ya tiene un hijo de este titular con esa fecha de nacimiento y sexo: "
                    "atendelo desde ahí en vez de registrar un provisional.",
                    409, details={"candidatos": [_familiar_contract(f) for f in en_sermed]},
                )

        cd_familiar = _siguiente_cd_familiar()
        paciente = Patient.objects.create(
            no_exp=no_exp, pk_num=None, legacy_family_code=cd_familiar,
            paternal_surname=paterno, maternal_surname=materno, first_name=nombre,
            birth_date=fecha_nacimiento, sex=sexo, curp=curp_normalizada,
            curp_source=Patient.CurpSource.CAPTURED if curp_normalizada else None,
            created_by_id=user_id, updated_by_id=user_id,
        )
        register_identifier(
            paciente, PatientIdentifier.IdType.CD_FAMILIAR, cd_familiar,
            reason=ChangeLog.Reason.NEWBORN_REGISTRATION, user=_usuario(user),
        )
        provisional = ProvisionalPatient.objects.create(
            patient=paciente, holder_no_exp=no_exp, mother_name=_texto(madre), birth_order=orden,
            clinic_code=_texto(titular.cd_clinica),
            valid_until=timezone.localdate() + timedelta(days=settings.IDENTIDAD_PACIENTE.get("DIAS_VIGENCIA_RN", 60)),
            created_by_id=user_id,
        )
        record_change(
            table="cns_paciente", key=build_key("id_paciente", paciente.pk),
            action=ChangeLog.Action.CREATE, reason=ChangeLog.Reason.NEWBORN_REGISTRATION, user=_usuario(user),
            new={
                "no_exp": no_exp, "cd_familiar": cd_familiar, "first_name": nombre,
                "paternal_surname": paterno, "maternal_surname": materno,
                "birth_date": fecha_nacimiento, "sex": sexo, "curp": curp_normalizada,
                "mother_name": _texto(madre), "birth_order": orden,
                "valid_until": provisional.valid_until, "confirmado_aunque_exista": confirmar_aunque_exista,
            },
        )
    return _contract(provisional)


# ── Vinculacion ──────────────────────────────────────────────────────────────

def _provisional_para_actualizar(id_paciente: int) -> ProvisionalPatient:
    provisional = (
        ProvisionalPatient.objects.select_for_update().select_related("patient").filter(pk=id_paciente).first()
    )
    if provisional is None:
        raise VisitDomainError("RN_NO_ENCONTRADO", "No existe ese recién nacido provisional.", 404)
    return provisional


def vincular(id_paciente: int, pk_num: int, *, user=None) -> dict:
    """El registro de SERMED del bebe pasa a la misma persona que el provisional."""
    _exigir_habilitado()
    from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository

    with transaction.atomic():
        provisional = _provisional_para_actualizar(id_paciente)
        if provisional.status != ProvisionalPatient.Status.PENDING:
            raise VisitDomainError("RN_YA_VINCULADO", "Este recién nacido ya está vinculado a SERMED.", 409)
        if pk_num not in {c["pkNum"] for c in candidatos(provisional)}:
            raise VisitDomainError(
                "CANDIDATO_NO_VALIDO",
                "Ese familiar de SERMED no coincide con el recién nacido (o ya se descartó).", 409,
            )
        # Regularizacion: el familiar viene de la replica; no aplica la guardia 1
        # (que justamente exige vincular primero).
        registro_sermed, _ = PatientRepository.get_or_create(
            provisional.holder_no_exp, pk_num, created_by_id=getattr(user, "pk", None),
            origen=ORIGEN_REGULARIZACION,
        )
        persona = provisional.patient.person_id
        persona_anterior = registro_sermed.person_id
        if persona_anterior != persona:
            # Todas las afiliaciones de la persona anterior pasan a la del
            # provisional (hoy, solo el registro de SERMED del bebe).
            Patient.objects.filter(person_id=persona_anterior).update(person_id=persona)
            record_change(
                table="cns_paciente", key=build_key("id_paciente", registro_sermed.pk),
                action=ChangeLog.Action.UPDATE, reason=ChangeLog.Reason.NEWBORN_LINK, user=_usuario(user),
                previous={"id_persona": persona_anterior}, new={"id_persona": persona},
            )
        ahora = timezone.now()
        provisional.status = ProvisionalPatient.Status.LINKED
        provisional.linked_pk_num = pk_num
        provisional.linked_at = ahora
        provisional.linked_by_id = getattr(user, "pk", None)
        provisional.save(update_fields=["status", "linked_pk_num", "linked_at", "linked_by_id"])
        record_change(
            table="cns_paciente_provisional", key=build_key("id_paciente", provisional.pk),
            action=ChangeLog.Action.UPDATE, reason=ChangeLog.Reason.NEWBORN_LINK, user=_usuario(user),
            previous={"sw_status": ProvisionalPatient.Status.PENDING, "pk_num_sermed": None},
            new={"sw_status": ProvisionalPatient.Status.LINKED, "pk_num_sermed": pk_num,
                 "id_paciente_sermed": registro_sermed.pk},
        )
    provisional.refresh_from_db()
    return _contract(provisional)


def descartar(id_paciente: int, pk_num: int, *, motivo=None, user=None) -> dict:
    """"No es la misma persona": la coincidencia no vuelve a proponerse."""
    _exigir_habilitado()
    with transaction.atomic():
        provisional = _provisional_para_actualizar(id_paciente)
        descarte, creado = PersonDiscard.objects.get_or_create(
            patient=provisional.patient, candidate_no_exp=provisional.holder_no_exp, candidate_pk_num=pk_num,
            defaults={"reason": _texto(motivo), "created_by_id": getattr(user, "pk", None)},
        )
        if creado:
            record_change(
                table="cns_persona_descarte",
                key=build_key("id_paciente", provisional.pk, "pk_num", pk_num),
                action=ChangeLog.Action.CREATE, reason=ChangeLog.Reason.NEWBORN_DISCARD, user=_usuario(user),
                new={"no_exp_candidato": provisional.holder_no_exp, "pk_num_candidato": pk_num,
                     "motivo": descarte.reason},
            )
    return _contract(provisional)


# ── Guardia 1 ────────────────────────────────────────────────────────────────

def verificar_rn_pendiente(no_exp: str, pk_num, *, origen: str) -> None:
    """
    Antes de crear el registro de un familiar de SERMED para atenderlo: si el
    titular tiene un provisional pendiente que coincide, primero hay que
    vincularlo (si no, el bebe quedaria con dos historias).
    """
    if not habilitado() or origen != ORIGEN_ATENCION or not pk_num or pk_num <= 0:
        return
    pendientes = list(
        ProvisionalPatient.objects.filter(holder_no_exp=no_exp, status=ProvisionalPatient.Status.PENDING)
        .select_related("patient")
    )
    if not pendientes:
        return
    familiar = next((f for f in (_familiares_sermed(no_exp) or []) if f.pk_num == pk_num), None)
    if familiar is None:
        return
    for provisional in pendientes:
        paciente = provisional.patient
        if not _coincide(familiar, paciente.birth_date, paciente.sex):
            continue
        if PersonDiscard.objects.filter(patient=paciente, candidate_no_exp=no_exp, candidate_pk_num=pk_num).exists():
            continue
        raise VisitDomainError(
            "RN_PENDIENTE_DE_VINCULAR",
            f"Este familiar coincide con el recién nacido provisional "
            f"{_nombre(paciente.paternal_surname, paciente.maternal_surname, paciente.first_name)} "
            f"(cd_familiar {paciente.legacy_family_code}). Vinculalo en Administración → Expedientes antes de atenderlo.",
            409, details={"idPacienteProvisional": paciente.pk, "pkNum": pk_num},
        )
