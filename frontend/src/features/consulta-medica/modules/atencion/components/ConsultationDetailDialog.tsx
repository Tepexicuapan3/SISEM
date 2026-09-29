import type { UseFormReturn } from "react-hook-form";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Textarea } from "@shared/ui/textarea";
import { EmitirIncapacidadButton } from "@features/consulta-medica/modules/atencion/components/EmitirIncapacidadButton";
import { SubirResultadoEstudioButton } from "@features/consulta-medica/modules/atencion/components/SubirResultadoEstudioButton";
import { EmitirPaseButton } from "@features/consulta-medica/modules/atencion/components/EmitirPaseButton";
import { SecondaryDiagnosesButton } from "@features/consulta-medica/modules/atencion/components/SecondaryDiagnosesButton";
import { PhysicalExamButton } from "@features/consulta-medica/modules/atencion/components/PhysicalExamButton";
import { PrescriptionItemsButton } from "@features/consulta-medica/modules/atencion/components/PrescriptionItemsButton";
import {
  VISIT_STATUS,
  type CieSearchItem,
  type VisitQueueItem,
  type VisitStatus,
  type VisitVitalsPayload,
} from "@api/types";
import type {
  SaveDiagnosisFormInput,
  SaveDiagnosisFormValues,
  SavePrescriptionsFormInput,
  SavePrescriptionsFormValues,
} from "@features/consulta-medica/modules/atencion/domain/consultation.schemas";
import { VitalMetric } from "./VitalMetric";
import { AppointmentAlertBadge, ConsultationElapsedBadge } from "./ConsultationBadges";
import {
  formatArrivalTypeLabel,
  formatBloodPressure,
  formatCapturedAtTime,
  formatMetricWithUnit,
  formatOptionalMetric,
  formatServiceTypeLabel,
  formatSomatometriaNotes,
  formatStatusLabel,
  hasVitalValue,
} from "../pages/DoctorConsultationPage.helpers";

const CONSULTATION_NOTE_FIELDS = [
  { name: "currentIllness", label: "Padecimiento actual" },
  { name: "systemsReview", label: "Interrogatorio por aparatos y sistemas" },
  { name: "diagnosticPlan", label: "Plan diagnostico" },
  { name: "therapeuticPlan", label: "Plan terapeutico" },
] as const satisfies readonly {
  name: keyof SaveDiagnosisFormInput;
  label: string;
}[];

interface Props {
  isDetailRoute:                     boolean;
  handleConsultationModalOpenChange: (open: boolean) => void;
  selectedVisit:                     VisitQueueItem | null;
  hasStaleSelectedVisit:             boolean;
  selectedVisitStatus:                VisitStatus;
  consultationStartedAtByVisitId:    Record<number, Date>;
  now:                                Date;
  selectedMinutesUntil:              number | null;
  selectedAppointmentDate:            string | null;
  selectedVitals:                     VisitVitalsPayload | null;
  hasOptionalVitals:                  boolean;
  canStartSelectedVisit:              boolean;
  startConsultation:                  { isPending: boolean };
  saveDiagnosis:                      { isPending: boolean };
  closeVisit:                         { isPending: boolean };
  savePrescriptions:                  { isPending: boolean };
  handleStartConsultation:            () => void | Promise<void>;
  canWriteDoctorConsultation:        boolean;
  cieSearchTerm:                      string;
  setCieSearchTerm:                   (value: string) => void;
  selectedCieCode:                    string;
  diagnosisForm:                      UseFormReturn<SaveDiagnosisFormInput, unknown, SaveDiagnosisFormValues>;
  selectedCieByVisitId:               Record<number, CieSearchItem>;
  setSelectedCieByVisitId:            (updater: (current: Record<number, CieSearchItem>) => Record<number, CieSearchItem>) => void;
  selectedCieLabel:                   string;
  handleClearCieSelection:            () => void;
  canSaveClinicalData:                boolean;
  shouldSearchCies:                   boolean;
  ciesSearchQuery:                    { isFetching: boolean; isError: boolean };
  ciesSearchItems:                    CieSearchItem[];
  handleSelectCie:                    (cie: CieSearchItem) => void;
  prescriptionsForm:                  UseFormReturn<SavePrescriptionsFormInput, unknown, SavePrescriptionsFormValues>;
  selectedSavedPrescriptions:        string[];
  handleSaveDraftClick:                () => void;
  handleSavePrescriptionClick:        () => void;
  handleResetDrafts:                  () => void;
  handleCloseConsultationClick:      () => void;
  canCloseSelectedVisit:              boolean;
  navigate:                            (path: string) => void;
}

export function ConsultationDetailDialog({
  isDetailRoute,
  handleConsultationModalOpenChange,
  selectedVisit,
  hasStaleSelectedVisit,
  selectedVisitStatus,
  consultationStartedAtByVisitId,
  now,
  selectedMinutesUntil,
  selectedAppointmentDate,
  selectedVitals,
  hasOptionalVitals,
  canStartSelectedVisit,
  startConsultation,
  saveDiagnosis,
  closeVisit,
  savePrescriptions,
  handleStartConsultation,
  canWriteDoctorConsultation,
  cieSearchTerm,
  setCieSearchTerm,
  selectedCieCode,
  diagnosisForm,
  selectedCieByVisitId,
  setSelectedCieByVisitId,
  selectedCieLabel,
  handleClearCieSelection,
  canSaveClinicalData,
  shouldSearchCies,
  ciesSearchQuery,
  ciesSearchItems,
  handleSelectCie,
  prescriptionsForm,
  selectedSavedPrescriptions,
  handleSaveDraftClick,
  handleSavePrescriptionClick,
  handleResetDrafts,
  handleCloseConsultationClick,
  canCloseSelectedVisit,
  navigate,
}: Props) {
  return (
    <Dialog
      open={isDetailRoute}
      onOpenChange={handleConsultationModalOpenChange}
    >
      <DialogContent
        className="max-h-[90vh] overflow-y-auto sm:max-w-4xl"
        data-testid="doctor-consultation-modal"
      >
        <DialogHeader>
          <DialogTitle>Detalle de consulta medica</DialogTitle>
          <DialogDescription>
            Inicia la consulta, registra diagnostico, receta y finaliza la
            atencion clinica.
          </DialogDescription>
        </DialogHeader>

        {selectedVisit ? (
          <div className="space-y-4">
            <div className="space-y-4 rounded-lg border border-line-hairline bg-subtle/30 p-4">
              {/* Encabezado: folio + estado */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-mono font-medium text-txt-muted">
                  {selectedVisit.folio}
                </p>
                <Badge variant="outline" className="uppercase">
                  {formatStatusLabel(selectedVisitStatus)}
                </Badge>
              </div>

              {/* Nombre del paciente */}
              {selectedVisit.nombrePaciente ? (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-txt-muted">
                    Paciente
                  </p>
                  <p className="text-xl font-bold text-txt-body">
                    {selectedVisit.nombrePaciente}
                  </p>
                  <p className="text-xs text-txt-muted font-mono mt-0.5">
                    Exp. {selectedVisit.noExp}
                    {selectedVisit.pkNum > 0 ? ` · familiar #${selectedVisit.pkNum}` : " · Titular"}
                  </p>
                </div>
              ) : (
                <p className="text-sm text-txt-muted font-mono">
                  Exp. {selectedVisit.noExp}{selectedVisit.pkNum > 0 ? ` · familiar #${selectedVisit.pkNum}` : ""}
                </p>
              )}

              {/* Datos de la cita */}
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                <div>
                  <p className="text-xs text-txt-muted">Servicio</p>
                  <p className="text-sm font-medium text-txt-body">
                    {formatServiceTypeLabel(selectedVisit.serviceType)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-txt-muted">Modalidad</p>
                  <p className="text-sm font-medium text-txt-body">
                    {formatArrivalTypeLabel(selectedVisit.arrivalType)}
                  </p>
                </div>
                {selectedVisit.doctorNombre ? (
                  <div>
                    <p className="text-xs text-txt-muted">Médico</p>
                    <p className="text-sm font-medium text-txt-body">
                      {selectedVisit.doctorNombre}
                    </p>
                  </div>
                ) : null}
                {selectedVisit.consultorioNombre ? (
                  <div>
                    <p className="text-xs text-txt-muted">Consultorio</p>
                    <p className="text-sm font-medium text-txt-body">
                      {selectedVisit.consultorioNombre}
                    </p>
                  </div>
                ) : null}
                {selectedVisit.horaConsulta ? (
                  <div>
                    <p className="text-xs text-txt-muted">Hora cita</p>
                    <div className="flex items-center gap-2 flex-wrap mt-0.5">
                      <p className="text-sm font-medium text-txt-body font-mono">
                        {selectedVisit.horaConsulta}
                      </p>
                      {selectedAppointmentDate ? (
                        <span className="text-xs text-txt-muted">{selectedAppointmentDate}</span>
                      ) : null}
                      {selectedVisitStatus === VISIT_STATUS.EN_CONSULTA ? (
                        <ConsultationElapsedBadge
                          startedAt={consultationStartedAtByVisitId[selectedVisit.id]}
                          now={now}
                        />
                      ) : (
                        <AppointmentAlertBadge minutesUntil={selectedMinutesUntil} />
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
              <div className="rounded-lg border border-line-hairline bg-paper p-3">
                <p className="text-xs font-medium uppercase tracking-wide text-txt-muted">
                  Motivo de consulta
                </p>
                <p className="mt-1 text-sm text-txt-body">
                  {selectedVisit.notes?.trim() ||
                    "Sin motivo de consulta capturado en recepcion."}
                </p>
              </div>

              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                  <p className="text-xs font-medium uppercase tracking-wide text-txt-muted">
                    Signos vitales
                  </p>
                  {selectedVitals ? (
                    <p
                      className="text-xs text-txt-muted"
                      data-testid="vitals-captured-at"
                    >
                      Tomados {formatCapturedAtTime(selectedVitals.capturedAt)}
                      {selectedVitals.reusedFrom
                        ? ` · reusados de la visita ${selectedVitals.reusedFrom.sourceFolio} (${formatServiceTypeLabel(
                            selectedVitals.reusedFrom.sourceServiceType,
                          )}), tomados ${formatCapturedAtTime(
                            selectedVitals.reusedFrom.capturedAt,
                          )}`
                        : selectedVitals.reusedFromVisitId != null
                        ? " · reusados de otra visita del mismo dia"
                        : ""}
                    </p>
                  ) : null}
                </div>
                {selectedVitals?.updatedBy ? (
                  // Fase 3 (edicion auditada, spec `consulta-medica/vitals-display`):
                  // un valor corregido NUNCA debe presentarse como si fuera
                  // el original -- se avisa explicitamente quien corrigio y
                  // cuando (`updatedAt` = `fch_modf`, DISTINTO de
                  // `capturedAt` = `fch_alta`, que nunca cambia).
                  <p
                    className="text-xs font-medium text-status-alert"
                    data-testid="vitals-updated-by"
                  >
                    Corregido por {selectedVitals.updatedBy.nombre ?? "usuario desconocido"}
                    {selectedVitals.updatedAt
                      ? ` el ${formatCapturedAtTime(selectedVitals.updatedAt)}`
                      : ""}
                  </p>
                ) : null}
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
                  <VitalMetric
                    label="Peso"
                    value={formatMetricWithUnit(
                      selectedVitals?.weightKg,
                      "kg",
                    )}
                  />
                  <VitalMetric
                    label="Talla"
                    value={formatMetricWithUnit(
                      selectedVitals?.heightCm,
                      "cm",
                    )}
                  />
                  <VitalMetric
                    label="Temperatura"
                    value={formatMetricWithUnit(
                      selectedVitals?.temperatureC,
                      "C",
                      {
                        digits: 1,
                      },
                    )}
                  />
                  <VitalMetric
                    label="Saturacion de oxigeno"
                    value={formatMetricWithUnit(
                      selectedVitals?.oxygenSaturationPct,
                      "%",
                    )}
                  />
                  <VitalMetric
                    label="IMC"
                    value={formatOptionalMetric(selectedVitals?.bmi, {
                      digits: 1,
                    })}
                  />
                </div>
              </div>

              <div className="rounded-lg border border-line-hairline bg-paper p-3">
                <p className="text-xs font-medium uppercase tracking-wide text-txt-muted">
                  Observaciones de somatometria
                </p>
                <p className="mt-1 text-sm text-txt-body">
                  {formatSomatometriaNotes(selectedVitals?.notes)}
                </p>
              </div>

              {hasOptionalVitals ? (
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-txt-muted">
                    Vitals adicionales
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                    {hasVitalValue(
                      selectedVitals?.bloodPressureSystolic,
                    ) ||
                    hasVitalValue(
                      selectedVitals?.bloodPressureDiastolic,
                    ) ? (
                      <VitalMetric
                        label="Presion arterial"
                        value={`${formatBloodPressure(
                          selectedVitals?.bloodPressureSystolic,
                          selectedVitals?.bloodPressureDiastolic,
                        )} mmHg`}
                      />
                    ) : null}

                    {hasVitalValue(selectedVitals?.heartRateBpm) ? (
                      <VitalMetric
                        label="Frecuencia cardiaca"
                        value={formatMetricWithUnit(
                          selectedVitals?.heartRateBpm,
                          "lpm",
                        )}
                      />
                    ) : null}

                    {hasVitalValue(selectedVitals?.respiratoryRateBpm) ? (
                      <VitalMetric
                        label="Frecuencia respiratoria"
                        value={formatMetricWithUnit(
                          selectedVitals?.respiratoryRateBpm,
                          "rpm",
                        )}
                      />
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>

            <Button
              type="button"
              variant="outline"
              disabled={
                !canStartSelectedVisit ||
                startConsultation.isPending ||
                saveDiagnosis.isPending ||
                closeVisit.isPending
              }
              onClick={() => {
                void handleStartConsultation();
              }}
            >
              Iniciar consulta
            </Button>

            {!canWriteDoctorConsultation ? (
              <p className="text-sm text-txt-muted" role="status">
                No tenes permisos completos para registrar diagnostico,
                receta o cierre de consulta.
              </p>
            ) : null}

            <div className="space-y-2">
              <Label htmlFor="cieSearch">
                Buscar CIE (opcional para guardar avance, obligatorio para
                finalizar)
              </Label>
              <Input
                id="cieSearch"
                value={cieSearchTerm}
                placeholder="Ej. A090 o gastroenteritis"
                disabled={!canSaveClinicalData || saveDiagnosis.isPending}
                onChange={(event) => {
                  const nextSearch = event.target.value;
                  setCieSearchTerm(nextSearch);

                  if (selectedCieCode) {
                    diagnosisForm.setValue("cieCode", "", {
                      shouldDirty: true,
                      shouldValidate: true,
                    });
                  }

                  if (
                    selectedVisit &&
                    selectedCieByVisitId[selectedVisit.id]
                  ) {
                    setSelectedCieByVisitId((current) => {
                      const next = { ...current };
                      delete next[selectedVisit.id];
                      return next;
                    });
                  }
                }}
              />
              <input
                type="hidden"
                {...diagnosisForm.register("cieCode")}
              />

              {selectedCieCode ? (
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm text-txt-muted">
                    CIE seleccionado: <strong>{selectedCieLabel}</strong>
                  </p>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={
                      !canSaveClinicalData || saveDiagnosis.isPending
                    }
                    onClick={handleClearCieSelection}
                  >
                    Quitar CIE
                  </Button>
                </div>
              ) : (
                <p className="text-sm text-txt-muted">
                  Escribe al menos 2 caracteres para buscar por clave o
                  descripcion.
                </p>
              )}

              {shouldSearchCies && ciesSearchQuery.isFetching ? (
                <p className="text-sm text-txt-muted">Buscando CIE...</p>
              ) : null}

              {shouldSearchCies && ciesSearchQuery.isError ? (
                <p className="text-sm text-status-critical" role="alert">
                  No se pudo cargar resultados CIE.
                </p>
              ) : null}

              {shouldSearchCies &&
              !ciesSearchQuery.isFetching &&
              !ciesSearchQuery.isError &&
              ciesSearchItems.length === 0 ? (
                <p className="text-sm text-txt-muted">
                  Sin coincidencias para esa busqueda.
                </p>
              ) : null}

              {shouldSearchCies &&
              !ciesSearchQuery.isError &&
              ciesSearchItems.length > 0 ? (
                <div className="max-h-44 space-y-1 overflow-y-auto rounded-lg border border-line-hairline bg-paper p-2">
                  {ciesSearchItems.map((item) => (
                    <button
                      key={`${selectedVisit.id}-cie-${item.code}`}
                      type="button"
                      className="w-full rounded-md border border-transparent px-3 py-2 text-left text-sm text-txt-body transition hover:border-brand/40 hover:bg-subtle/30"
                      onClick={() => {
                        handleSelectCie(item);
                      }}
                    >
                      <p className="font-medium">{item.code}</p>
                      <p className="text-xs text-txt-muted">
                        {item.description}
                      </p>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="primaryDiagnosis">
                Diagnostico principal
              </Label>
              <Textarea
                id="primaryDiagnosis"
                rows={3}
                disabled={!canSaveClinicalData || saveDiagnosis.isPending}
                {...diagnosisForm.register("primaryDiagnosis")}
              />
              {diagnosisForm.formState.errors.primaryDiagnosis
                ?.message ? (
                <p className="text-sm text-status-critical" role="alert">
                  {
                    diagnosisForm.formState.errors.primaryDiagnosis
                      .message
                  }
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="finalNote">Nota final</Label>
              <Textarea
                id="finalNote"
                rows={5}
                disabled={!canSaveClinicalData || saveDiagnosis.isPending}
                {...diagnosisForm.register("finalNote")}
              />
              {diagnosisForm.formState.errors.finalNote?.message ? (
                <p className="text-sm text-status-critical" role="alert">
                  {diagnosisForm.formState.errors.finalNote.message}
                </p>
              ) : null}
            </div>

            {/* his_notas ampliada (documento "Historia Clinica Unificada", 5.2): opcionales. */}
            {CONSULTATION_NOTE_FIELDS.map(({ name, label }) => (
              <div key={name} className="space-y-2">
                <Label htmlFor={name}>{label}</Label>
                <Textarea
                  id={name}
                  rows={3}
                  disabled={!canSaveClinicalData || saveDiagnosis.isPending}
                  {...diagnosisForm.register(name)}
                />
              </div>
            ))}

            <div className="space-y-2">
              <Label htmlFor="prescriptions">
                Receta (una indicacion por linea)
              </Label>
              <Textarea
                id="prescriptions"
                rows={6}
                disabled={
                  !canSaveClinicalData || savePrescriptions.isPending
                }
                {...prescriptionsForm.register("itemsText")}
                placeholder="Opcional"
              />
              {prescriptionsForm.formState.errors.itemsText?.message ? (
                <p className="text-sm text-status-critical" role="alert">
                  {prescriptionsForm.formState.errors.itemsText.message}
                </p>
              ) : null}
            </div>

            <div className="rounded-lg border border-line-hairline bg-subtle/20 p-3">
              <p className="text-sm font-semibold text-txt-body">
                Indicaciones guardadas
              </p>
              {selectedSavedPrescriptions.length > 0 ? (
                <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-txt-muted">
                  {selectedSavedPrescriptions.map((item, index) => (
                    <li key={`${selectedVisit.id}-rx-${index}-${item}`}>
                      {item}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-sm text-txt-muted">
                  Aun no hay receta registrada para esta visita.
                </p>
              )}
            </div>

            <div className="flex flex-wrap gap-2 border-t border-line-hairline pt-4">
              <Button
                type="button"
                variant="outline"
                disabled={
                  !canSaveClinicalData ||
                  !diagnosisForm.formState.isValid ||
                  saveDiagnosis.isPending ||
                  closeVisit.isPending
                }
                onClick={handleSaveDraftClick}
              >
                Guardar diagnostico
              </Button>

              {selectedVisit ? (
                <SecondaryDiagnosesButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
              ) : null}

              {selectedVisit ? (
                <PhysicalExamButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
              ) : null}

              <Button
                type="button"
                variant="outline"
                disabled={
                  !canSaveClinicalData ||
                  !prescriptionsForm.formState.isValid ||
                  savePrescriptions.isPending
                }
                onClick={handleSavePrescriptionClick}
              >
                Guardar receta
              </Button>

              {selectedVisit ? (
                <PrescriptionItemsButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
              ) : null}

              {selectedVisit ? (
                <EmitirIncapacidadButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
              ) : null}

              {selectedVisit ? (
                <SubirResultadoEstudioButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
              ) : null}

              {selectedVisit ? (
                <EmitirPaseButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
              ) : null}

              <Button
                type="button"
                variant="ghost"
                disabled={
                  saveDiagnosis.isPending ||
                  savePrescriptions.isPending ||
                  closeVisit.isPending
                }
                onClick={handleResetDrafts}
              >
                Restaurar borradores
              </Button>

              <Button
                type="button"
                disabled={
                  !canCloseSelectedVisit ||
                  !diagnosisForm.formState.isValid ||
                  closeVisit.isPending ||
                  saveDiagnosis.isPending
                }
                onClick={handleCloseConsultationClick}
              >
                Finalizar consulta
              </Button>

              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  navigate("/clinico/consultas/doctor");
                }}
              >
                Volver a bandeja
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-txt-muted" role="status">
            {hasStaleSelectedVisit
              ? "La consulta seleccionada ya no esta disponible. Elige otra consulta abierta."
              : "Selecciona una consulta abierta para iniciar la atencion clinica."}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
