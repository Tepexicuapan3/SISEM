from django.utils import timezone

from apps.somatometria.models import PatientLatestVitals, VisitVitalSigns


class VitalsRepository:
    @staticmethod
    def _metric_fields_from_payload(vitals_payload):
        """
        Campos de METRICA puros (sin autoria ni reuso) -- compartidos entre
        `create_for_visit` y `update_for_visit` para no duplicar la lista
        de columnas en dos lugares.
        """
        return {
            "weight_kg": vitals_payload["weightKg"],
            "height_cm": vitals_payload["heightCm"],
            "temperature_c": vitals_payload.get("temperatureC"),
            "oxygen_saturation_pct": vitals_payload.get("oxygenSaturationPct"),
            "heart_rate_bpm": vitals_payload.get("heartRateBpm"),
            "respiratory_rate_bpm": vitals_payload.get("respiratoryRateBpm"),
            "blood_pressure_systolic": vitals_payload.get("bloodPressureSystolic"),
            "blood_pressure_diastolic": vitals_payload.get("bloodPressureDiastolic"),
            "waist_circumference_cm": vitals_payload.get("waistCircumferenceCm"),
            "glucosa_capilar_mgdl": vitals_payload.get("glucosaCapilarMgdl"),
            "bmi": vitals_payload["bmi"],
            "notes": vitals_payload.get("notes"),
        }

    @staticmethod
    def create_for_visit(visit, vitals_payload, *, reused_from=None, captured_by):
        """
        Crea la fila de captura INICIAL de una visita. `captured_by` es
        kwarg-only SIN default a proposito (mismo criterio que
        `get_latest_for_patient`): un caller que se olvide de pasarlo debe
        explotar ruidoso, nunca guardar una captura sin autor.

        El `OneToOneField` sobre `id_visit` ya garantiza unicidad -- una
        carrera entre dos POST concurrentes pierde con `IntegrityError`,
        que el use case mapea a 409 VITALS_ALREADY_CAPTURED (la
        precondicion normal es el chequeo previo del use case; esto es
        solo la red de seguridad).
        """
        fields = VitalsRepository._metric_fields_from_payload(vitals_payload)
        vital_signs = VisitVitalSigns.objects.create(
            id_visit=visit,
            # Denormalizado desde la visita al crear (el paciente de una visita
            # no cambia despues de creada).
            patient_id=visit.patient_id,
            reused_from_visit=reused_from,
            captured_by=captured_by,
            **fields,
        )

        VitalsRepository._sync_latest_vitals(visit, fields)

        return vital_signs

    @staticmethod
    def update_for_visit(vital_signs, vitals_payload, *, updated_by):
        """
        Corrige una fila YA existente (Fase 3, edicion auditada). NUNCA
        toca `captured_by` ni `reused_from_visit` -- una correccion no
        reescribe quien tomo la medicion original ni de donde vino un
        reuso.
        """
        fields = VitalsRepository._metric_fields_from_payload(vitals_payload)
        for field_name, value in fields.items():
            setattr(vital_signs, field_name, value)
        vital_signs.updated_by = updated_by
        vital_signs.save(update_fields=[*fields.keys(), "updated_by", "fch_modf"])

        # Gotcha (design D2): si esta sincronizacion no corre tambien en el
        # camino de UPDATE, la proxima consulta precarga el valor viejo
        # (no corregido) desde `PatientLatestVitals`.
        VitalsRepository._sync_latest_vitals(vital_signs.id_visit, fields)

        return vital_signs

    @staticmethod
    def _sync_latest_vitals(visit, fields):
        """
        Espejo "ultima captura por paciente": se sobreescribe a proposito
        (a diferencia de `VisitVitalSigns`, que jamas se sobreescribe). Es
        solo para precargar la siguiente consulta, no forma parte del
        historial clinico. La clave es el registro del paciente
        (id_paciente; plan contraer la llave vieja): nunca el no_exp solo,
        que es de todo el nucleo familiar.

        Llamado por AMBOS `create_for_visit` y `update_for_visit`: una
        correccion que no re-espeje este cache dejaria la proxima consulta
        precargada con el valor NO corregido.
        """
        if visit.patient_id is None:
            return
        latest_defaults = dict(fields)
        latest_defaults.pop("notes", None)
        latest_defaults["id_visit_origen"] = visit
        PatientLatestVitals.objects.update_or_create(
            patient_id=visit.patient_id,
            defaults=latest_defaults,
        )

    @staticmethod
    def get_latest_for_patient(patient_id):
        if patient_id is None:
            return None
        return PatientLatestVitals.objects.filter(patient_id=patient_id).first()

    @staticmethod
    def get_latest_today_for_patient(patient_id, *, exclude_visit_id):
        """
        Fuente de verdad (NO el cache) de la captura de signos vitales de
        HOY para el mismo registro (id_paciente), en una visita distinta a
        `exclude_visit_id`. "Hoy" es el dia calendario LOCAL
        (`timezone.localdate()` / `fch_alta__date` con USE_TZ=True aplica
        la zona horaria configurada) -- nunca UTC crudo, para no ofrecer ni
        esconder capturas cerca de medianoche por error.
        """
        if patient_id is None:
            return None
        return (
            VisitVitalSigns.objects.select_related("id_visit")
            .filter(
                id_visit__patient_id=patient_id,
                fch_alta__date=timezone.localdate(),
            )
            .exclude(id_visit_id=exclude_visit_id)
            .exclude(id_visit__status__in=("cancelada", "no_show"))
            .order_by("-fch_alta")
            .first()
        )

    @staticmethod
    def get_vitals_by_visit_id(visit_id):
        return (
            VisitVitalSigns.objects.select_related("id_visit")
            .filter(id_visit_id=visit_id)
            .first()
        )

    @staticmethod
    def _metrics_contract(vital_signs):
        return {
            "weightKg": float(vital_signs.weight_kg),
            "heightCm": float(vital_signs.height_cm),
            "temperatureC": (
                float(vital_signs.temperature_c)
                if vital_signs.temperature_c is not None
                else None
            ),
            "oxygenSaturationPct": vital_signs.oxygen_saturation_pct,
            "heartRateBpm": vital_signs.heart_rate_bpm,
            "respiratoryRateBpm": vital_signs.respiratory_rate_bpm,
            "bloodPressureSystolic": vital_signs.blood_pressure_systolic,
            "bloodPressureDiastolic": vital_signs.blood_pressure_diastolic,
            "waistCircumferenceCm": vital_signs.waist_circumference_cm,
            "glucosaCapilarMgdl": vital_signs.glucosa_capilar_mgdl,
            "bmi": float(vital_signs.bmi),
        }

    @staticmethod
    def _reused_from_contract(origin_visit):
        """
        Detalle de la visita ORIGEN cuando esta captura fue un reuso --
        mismos nombres de campo que `today_to_contract` (`sourceFolio`,
        `sourceServiceType`, `capturedAt`) para que el medico vea folio,
        especialidad y hora de origen, no solo un id crudo. `None` cuando
        no hubo reuso (retrocompatible con `reusedFromVisitId: None`).
        """
        if origin_visit is None:
            return None
        # Reverse OneToOne: cacheado por select_related en las queries de
        # lista/detalle de visitas; si no vino precargado dispara 1 query
        # extra puntual (no hay N+1 de lista aca, es un solo objeto).
        origin_vitals = getattr(origin_visit, "vital_signs", None)
        return {
            "sourceVisitId": origin_visit.id_visit,
            "sourceFolio": origin_visit.folio,
            "sourceServiceType": origin_visit.service_type,
            "capturedAt": (
                origin_vitals.fch_alta.isoformat() if origin_vitals else None
            ),
        }

    @staticmethod
    def _lookup_user_nombres(user_ids):
        """
        Batch lookup de `DetUsuario.nombre_completo` (mismo patron que
        `doctor_nombres` en `visit_repository.py:165-169`) -- a proposito
        SIN `select_related`: `nombre_completo` vive en `DetUsuario`, no en
        `SyUsuario`, asi que un `select_related("captured_by")` no lo
        traeria igual.
        """
        ids = {user_id for user_id in user_ids if user_id}
        if not ids:
            return {}
        from apps.authentication.models import DetUsuario

        dets = DetUsuario.objects.filter(id_usuario_id__in=ids)
        return {det.id_usuario_id: det.nombre_completo for det in dets}

    @staticmethod
    def _user_ref_contract(user_id, user_nombres):
        if user_id is None:
            return None
        return {"id": user_id, "nombre": user_nombres.get(user_id)}

    @staticmethod
    def to_contract(vital_signs, user_nombres=None):
        contract = VitalsRepository._metrics_contract(vital_signs)
        contract["capturedAt"] = vital_signs.fch_alta.isoformat()
        # `fch_modf` (auto_now) es DISTINTO de `capturedAt` (fch_alta,
        # auto_now_add, jamas cambia): sin este campo separado, el
        # frontend no tiene forma de mostrar CUANDO se corrigio una
        # edicion sin confundirlo con el momento de la captura original
        # (Fase 3, spec `consulta-medica/vitals-display`).
        contract["updatedAt"] = vital_signs.fch_modf.isoformat()
        contract["reusedFromVisitId"] = vital_signs.reused_from_visit_id
        contract["reusedFrom"] = VitalsRepository._reused_from_contract(
            vital_signs.reused_from_visit
        )
        contract["hasVitals"] = True

        # `user_nombres` es opcional: si el caller ya tiene un batch
        # precalculado (ej. una lista de visitas) lo pasa y evitamos N+1;
        # si no, resolvemos aca mismo el batch de a lo sumo 2 ids (captura
        # + edicion) de ESTA fila puntual.
        if user_nombres is None:
            user_nombres = VitalsRepository._lookup_user_nombres(
                [vital_signs.captured_by_id, vital_signs.updated_by_id]
            )
        contract["capturedBy"] = VitalsRepository._user_ref_contract(
            vital_signs.captured_by_id, user_nombres
        )
        contract["updatedBy"] = VitalsRepository._user_ref_contract(
            vital_signs.updated_by_id, user_nombres
        )
        return contract

    @staticmethod
    def to_status_contract(vital_signs):
        """
        Contrato narrowed (D3, somatometria-modulo-integral) para callers
        SIN capability de lectura de metricas (ej. recepcion). Expone
        UNICAMENTE estado -- jamas peso/talla/presion/glucosa ni ningun
        otro valor numerico. Usado por `VisitRepository.to_contract`
        cuando `include_vitals_values=False`, solo en el LIST de visitas.
        """
        return {
            "hasVitals": True,
            "capturedAt": vital_signs.fch_alta.isoformat(),
            "reusedFromVisitId": vital_signs.reused_from_visit_id,
            "reusedFrom": VitalsRepository._reused_from_contract(
                vital_signs.reused_from_visit
            ),
        }

    @staticmethod
    def latest_to_contract(latest):
        contract = VitalsRepository._metrics_contract(latest)
        contract["capturedAt"] = latest.fch_modf.isoformat()
        return contract

    @staticmethod
    def today_to_contract(vital_signs):
        visit = vital_signs.id_visit
        return {
            "sourceVisitId": visit.id_visit,
            "sourceFolio": visit.folio,
            "sourceServiceType": visit.service_type,
            "capturedAt": vital_signs.fch_alta.isoformat(),
            "values": VitalsRepository._metrics_contract(vital_signs),
        }
