import os

from rest_framework import serializers

STUDY_RESULT_MAX_BYTES = 8 * 1024 * 1024  # 8 MB
_ALLOWED_STUDY_RESULT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_STUDY_RESULT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


class StartConsultationSerializer(serializers.Serializer):
    """No payload required for start action."""


class SaveDiagnosisSerializer(serializers.Serializer):
    primaryDiagnosis = serializers.CharField(max_length=255, allow_blank=False)
    finalNote = serializers.CharField(allow_blank=False)
    cieCode = serializers.CharField(
        max_length=8,
        allow_blank=True,
        required=False,
        allow_null=True,
    )
    subjective = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    objective = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    assessment = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    plan = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_primaryDiagnosis(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("primaryDiagnosis es obligatorio.")
        return normalized

    def validate_finalNote(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("finalNote es obligatorio.")
        return normalized

    def validate_cieCode(self, value):
        if value is None:
            return None

        normalized = value.strip().upper()
        if not normalized:
            return None

        return normalized


class SavePrescriptionsSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False),
        allow_empty=False,
    )

    def validate_items(self, value):
        normalized_items = []
        for item in value:
            normalized_item = item.strip()
            if normalized_item:
                normalized_items.append(normalized_item)

        if not normalized_items:
            raise serializers.ValidationError("Debes indicar al menos una receta.")

        return normalized_items


class CloseConsultationSerializer(SaveDiagnosisSerializer):
    # CIE-10 obligatorio para CERRAR la consulta (NOM-024-SSA3-2012). En
    # SaveDiagnosisSerializer (guardado de avance, todavía en consulta) se
    # deja opcional a propósito -- el doctor puede ir guardando antes de
    # definir el código.
    cieCode = serializers.CharField(max_length=8, allow_blank=False)

    def validate_cieCode(self, value):
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError(
                "cieCode es obligatorio para cerrar la consulta."
            )
        return normalized


class ClinicalHistoryUpdateSerializer(serializers.Serializer):
    """
    Todos los campos son opcionales a proposito: la Historia Clinica
    General se captura de forma incremental a lo largo de varias
    consultas, no en un solo formulario obligatorio (ver ClinicalHistory
    en models.py).
    """

    occupationId = serializers.IntegerField(required=False, allow_null=True)
    educationLevelId = serializers.IntegerField(required=False, allow_null=True)
    maritalStatusId = serializers.IntegerField(required=False, allow_null=True)
    religionId = serializers.IntegerField(required=False, allow_null=True)
    residenceTypeId = serializers.IntegerField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True, allow_null=True)
    familyHistory = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    currentIllness = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    systemsReview = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    headExam = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    neckExam = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    chestExam = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    abdomenExam = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    genitalsExam = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    limbsExam = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    diagnosticManagement = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    therapeuticManagement = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    allergies = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class OdontogramToothUpdateSerializer(serializers.Serializer):
    condition = serializers.CharField()
    notes = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True,
    )


class StomatologyHistoryUpdateSerializer(serializers.Serializer):
    """
    Todos los campos son opcionales -- misma logica de captura incremental
    que ClinicalHistoryUpdateSerializer.
    """

    familyDiabetes = serializers.BooleanField(required=False)
    familyCancer = serializers.BooleanField(required=False)
    familyHighBloodPressure = serializers.BooleanField(required=False)
    familyLowBloodPressure = serializers.BooleanField(required=False)
    causeOfDeath = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    personalDiabetes = serializers.BooleanField(required=False)
    personalAsthma = serializers.BooleanField(required=False)
    personalHighBloodPressure = serializers.BooleanField(required=False)
    personalLowBloodPressure = serializers.BooleanField(required=False)
    personalHepatitis = serializers.BooleanField(required=False)
    personalHiv = serializers.BooleanField(required=False)
    personalSmoking = serializers.BooleanField(required=False)
    personalAlcoholism = serializers.BooleanField(required=False)
    personalSubstanceAbuse = serializers.BooleanField(required=False)
    habits = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    diet = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    surgicalHistory = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    traumaticHistory = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    allergyMedications = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    allergyDentalMaterial = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    allergyAnesthesia = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    allergyFood = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    allergyEnvironment = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    allergyOther = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    currentIllnessHistory = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CreateMedicalLeaveSerializer(serializers.Serializer):
    leaveTypeId = serializers.IntegerField()
    days = serializers.IntegerField(min_value=1, max_value=180)
    startDate = serializers.DateField()
    isSubsequent = serializers.BooleanField(required=False, default=False)


class CreateStudyResultSerializer(serializers.Serializer):
    studyTypeId = serializers.IntegerField()
    resultDate = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    file = serializers.FileField()

    def validate_file(self, value):
        extension = (os.path.splitext(value.name or "")[1] or "").lower()
        content_type = getattr(value, "content_type", None)

        if extension not in _ALLOWED_STUDY_RESULT_EXTENSIONS or (
            content_type is not None
            and content_type not in _ALLOWED_STUDY_RESULT_CONTENT_TYPES
        ):
            raise serializers.ValidationError(
                "Formato no permitido. Usa PDF, JPG, PNG o WEBP.",
                code="invalid_file_format",
            )

        if value.size > STUDY_RESULT_MAX_BYTES:
            raise serializers.ValidationError(
                "El archivo excede el tamaño máximo permitido (8 MB).",
                code="file_too_large",
            )

        return value


class AddSecondaryDiagnosisSerializer(serializers.Serializer):
    cieCode = serializers.CharField(max_length=8, allow_blank=False)
    notes = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True,
    )

    def validate_cieCode(self, value):
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError("cieCode es obligatorio.")
        return normalized


class AddPrescriptionItemSerializer(serializers.Serializer):
    medicationId = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    indications = serializers.CharField(max_length=140, allow_blank=False)
    dose = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True,
    )


class SearchCieSerializer(serializers.Serializer):
    search = serializers.CharField(max_length=120, allow_blank=False)
    limit = serializers.IntegerField(min_value=1, max_value=20, required=False, default=8)

    def validate_search(self, value):
        normalized = value.strip()
        if len(normalized) < 2:
            raise serializers.ValidationError(
                "Debes ingresar al menos 2 caracteres para buscar CIE."
            )
        return normalized
