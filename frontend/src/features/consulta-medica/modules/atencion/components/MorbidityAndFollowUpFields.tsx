import { useEffect } from "react";
import { useWatch, type UseFormReturn } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { visitsAPI } from "@api/resources/visits.api";
import type { ConsultationMorbidity } from "@api/types";
import type {
  SaveDiagnosisFormInput,
  SaveDiagnosisFormValues,
} from "@features/consulta-medica/modules/atencion/domain/consultation.schemas";
import {
  MORBIDITY_LABELS,
  describeSuggestion,
  minFollowUpDate,
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
 * - P-12: el médico puede elegir un horario libre de SU agenda; la cita se
 *   crea al finalizar la consulta (sin horario la agenda recepción).
 */
export function MorbidityAndFollowUpFields({ visitId, cieCode, diagnosisForm, disabled }: Props) {
  const morbidity = useWatch({ control: diagnosisForm.control, name: "morbidity" });
  const followUpEnabled = useWatch({ control: diagnosisForm.control, name: "followUpEnabled" });
  const followUpDate = useWatch({ control: diagnosisForm.control, name: "followUpDate" });
  const followUpSlotId = useWatch({ control: diagnosisForm.control, name: "followUpSlotId" });
  const followUpError = diagnosisForm.formState.errors.followUpDate?.message;

  // P-12: horarios libres de la agenda del médico para esa fecha.
  const fechaValida = followUpEnabled && !followUpError && /^\d{4}-\d{2}-\d{2}$/.test(followUpDate ?? "");
  const { data: followUpSlots, isFetching: loadingSlots } = useQuery({
    queryKey: ["consulta-medica", "follow-up-slots", visitId, followUpDate],
    queryFn: () => visitsAPI.getFollowUpSlots(visitId as number, followUpDate as string),
    enabled: visitId !== null && fechaValida && !disabled,
    staleTime: 30 * 1000,
  });
  const slots = followUpSlots?.slots ?? [];

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
          <div className="space-y-1 max-w-xs">
            <Label htmlFor="followUpDate">Fecha de seguimiento</Label>
            <Input
              id="followUpDate"
              type="date"
              min={minFollowUpDate()}
              disabled={disabled}
              {...diagnosisForm.register("followUpDate")}
            />
          </div>
        ) : null}
        {followUpEnabled && fechaValida ? (
          <div className="space-y-1 max-w-xs">
            <Label htmlFor="followUpSlotId">Horario de la cita (tu agenda)</Label>
            {loadingSlots ? (
              <p className="text-xs text-txt-muted">Buscando horarios...</p>
            ) : slots.length === 0 ? (
              <p className="text-xs text-txt-muted">
                No tienes horarios libres ese día. Elige otra fecha o deja la
                indicación para que la agende recepción.
              </p>
            ) : (
              <Select
                value={followUpSlotId || undefined}
                onValueChange={(value) =>
                  diagnosisForm.setValue("followUpSlotId", value, { shouldDirty: true })
                }
                disabled={disabled}
              >
                <SelectTrigger id="followUpSlotId" className="h-9">
                  <SelectValue placeholder="Elige un horario" />
                </SelectTrigger>
                <SelectContent>
                  {slots.map((slot) => (
                    <SelectItem key={slot.slotId} value={String(slot.slotId)}>
                      {slot.hora}
                      {slot.consultorioNombre ? ` · ${slot.consultorioNombre}` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <p className="text-xs text-txt-muted">
              {followUpSlotId
                ? "La cita se agenda al finalizar la consulta."
                : "Sin horario, la fecha queda como indicación y la cita la agenda recepción."}
            </p>
          </div>
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
