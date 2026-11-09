import { useEffect } from "react";
import { useWatch, type UseFormReturn } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@shared/ui/button";
import { visitsAPI } from "@api/resources/visits.api";
import { FollowUpScheduler } from "./FollowUpScheduler";
import type { ConsultationMorbidity } from "@api/types";
import type {
  SaveDiagnosisFormInput,
  SaveDiagnosisFormValues,
} from "@features/consulta-medica/modules/atencion/domain/consultation.schemas";
import {
  MORBIDITY_LABELS,
  describeSuggestion,
} from "@features/consulta-medica/modules/atencion/domain/consultation-morbidity";

interface Props {
  visitId: number | null;
  cieCode: string;
  diagnosisForm: UseFormReturn<SaveDiagnosisFormInput, unknown, SaveDiagnosisFormValues>;
  disabled: boolean;
}

/**
 * Documento 5.3, con las reglas del legado (body-consultadirectac.jsp):
 * - "Primera vez / subsecuente de la enfermedad": obligatoria para cerrar.
 *   SIRES sugiere el valor segun las consultas anteriores con ese CIE-10.
 * - "Cita": si se marca, la fecha de seguimiento es obligatoria.
 * - P-12: el médico saca la cita de SU agenda (ver FollowUpScheduler); se
 *   crea al finalizar la consulta (sin horario la agenda recepción).
 */
export function MorbidityAndFollowUpFields({ visitId, cieCode, diagnosisForm, disabled }: Props) {
  const morbidity = useWatch({ control: diagnosisForm.control, name: "morbidity" });
  const followUpEnabled = useWatch({ control: diagnosisForm.control, name: "followUpEnabled" });
  const followUpDate = useWatch({ control: diagnosisForm.control, name: "followUpDate" });
  const followUpError = diagnosisForm.formState.errors.followUpDate?.message;

  // Cambiar la fecha invalida el horario elegido.
  useEffect(() => {
    diagnosisForm.setValue("followUpSlotId", "", { shouldDirty: true });
  }, [followUpDate, followUpEnabled, diagnosisForm]);

  const { data: suggestion } = useQuery({
    queryKey: ["consulta-medica", "morbidity-suggestion", visitId, cieCode],
    queryFn: () => visitsAPI.getMorbiditySuggestion(visitId as number, cieCode),
    enabled: visitId !== null && cieCode.length > 0 && !disabled,
    staleTime: 60 * 1000,
  });
  const suggestionText = suggestion
    ? describeSuggestion(suggestion.suggestion, suggestion.previousConsultations, suggestion.cieCode)
    : null;
  const canApplySuggestion = Boolean(suggestion?.suggestion) && suggestion?.suggestion !== morbidity;

  const applySuggestion = () => {
    if (!suggestion?.suggestion) return;
    diagnosisForm.setValue("morbidity", suggestion.suggestion, { shouldDirty: true, shouldValidate: true });
  };

  return (
    <div className="space-y-4">
      <fieldset className="space-y-2" disabled={disabled}>
        <legend className="text-sm font-medium">
          Primera vez o subsecuente de la enfermedad{" "}
          <span className="text-status-critical">*</span>
        </legend>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {(Object.keys(MORBIDITY_LABELS) as ConsultationMorbidity[]).map((value) => (
            <label key={value} className="flex items-center gap-2 text-sm">
              <input type="radio" value={value} {...diagnosisForm.register("morbidity")} />
              {MORBIDITY_LABELS[value]}
            </label>
          ))}
        </div>
        {suggestionText ? (
          <div className="flex flex-wrap items-center gap-2 text-xs text-txt-muted">
            <span>{suggestionText}</span>
            {canApplySuggestion ? (
              <Button type="button" variant="link" size="sm" className="h-auto p-0" onClick={applySuggestion}>
                Usar sugerencia
              </Button>
            ) : null}
          </div>
        ) : null}
        {!morbidity ? (
          <p className="text-xs text-txt-muted">Obligatorio para finalizar la consulta.</p>
        ) : null}
      </fieldset>

      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" disabled={disabled} {...diagnosisForm.register("followUpEnabled")} />
          Indicar fecha de seguimiento (cita)
        </label>
        {followUpEnabled ? (
          <FollowUpScheduler visitId={visitId} diagnosisForm={diagnosisForm} disabled={disabled} />
        ) : null}
        {followUpError ? (
          <p className="text-sm text-status-critical" role="alert">
            {followUpError}
          </p>
        ) : null}
      </div>
    </div>
  );
}
