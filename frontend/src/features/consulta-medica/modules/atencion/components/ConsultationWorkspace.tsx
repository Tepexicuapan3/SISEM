import type { UseFormReturn } from "react-hook-form";
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
import { PrescriptionSummary } from "@features/consulta-medica/modules/atencion/components/PrescriptionSummary";
import { canStartConsultation } from "@features/operativo/shared/contracts/visit-flow";
import { ChronicConditionsNotice } from "@features/padrones/components/ChronicConditionsNotice";
import { ChronicControlPanel } from "@features/padrones/components/ChronicControlPanel";
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
import { ConsultationSection } from "./ConsultationSection";
import { MorbidityAndFollowUpFields } from "./MorbidityAndFollowUpFields";
import { SoapNoteFields } from "./SoapNoteFields";
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

const SECTIONS = [
  { id: "consulta-visita", label: "Visita" },
  { id: "consulta-diagnostico", label: "Diagnóstico" },
  { id: "consulta-nota", label: "Nota médica" },
  { id: "consulta-receta", label: "Receta" },
  { id: "consulta-documentos", label: "Otros documentos" },
] as const;

/** Indice de apartados: salta a cada uno sin perder el encabezado del paciente. */
function ConsultationSectionNav() {
  return (
    <nav aria-label="Apartados de la consulta" className="mt-2 -mb-1 flex gap-1 overflow-x-auto">
      {SECTIONS.map((section) => (
        <a
          key={section.id}
          href={`#${section.id}`}
          className="shrink-0 rounded-md px-2.5 py-1 text-xs font-medium text-txt-muted transition-colors hover:bg-subtle/40 hover:text-txt-body"
          onClick={(event) => {
            event.preventDefault();
            document.getElementById(section.id)?.scrollIntoView?.({ behavior: "smooth", block: "start" });
          }}
        >
          {section.label}
        </a>
      ))}
    </nav>
  );
}

export interface ConsultationWorkspaceProps {
  /** "dialog": dentro del modal; "page": ocupa la pagina con indice de apartados. */
  variant:                            "dialog" | "page";
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

/**
 * Contenido de la consulta: paciente fijo arriba, apartados y acciones fijas abajo.
 * Lo usan el modal (vista actual) y la vista escritorio (PROPUESTA, Fase 2).
 */
export function ConsultationWorkspace({
  variant,
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
}: ConsultationWorkspaceProps) {
  const showStartButton = canStartConsultation(selectedVisitStatus);

  return (
    <>
      {selectedVisit ? (
        <>
          {/* Paciente: siempre visible mientras se captura la consulta */}
          <div className="sticky top-0 z-10 border-b border-line-hairline bg-paper/95 px-5 py-3 backdrop-blur sm:px-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                {selectedVisit.nombrePaciente ? (
                  <p className="text-lg leading-tight font-bold break-words text-txt-body">
                    {selectedVisit.nombrePaciente}
                  </p>
                ) : null}
                <p className="mt-0.5 font-mono text-xs text-txt-muted">
                  Exp. {selectedVisit.noExp}
                  {selectedVisit.pkNum > 0
                    ? ` · familiar #${selectedVisit.pkNum}`
                    : selectedVisit.nombrePaciente
                      ? " · Titular"
                      : ""}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-mono text-sm font-medium text-txt-muted">
                  {selectedVisit.folio}
                </p>
                <Badge variant="outline" className="uppercase">
                  {formatStatusLabel(selectedVisitStatus)}
                </Badge>
              </div>
            </div>
            {variant === "page" ? <ConsultationSectionNav /> : null}
          </div>

          <div className="space-y-5 px-5 py-5 sm:px-6">
            <ConsultationSection
              id="consulta-visita"
              title="Datos de la visita"
              actions={
                showStartButton ? (
                  <Button
                    type="button"
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
                ) : null
              }
            >
              {/* Padron de cronicos: aviso y sugerencia de inscripcion */}
              <ChronicConditionsNotice visitId={selectedVisit.id} cieCode={selectedCieCode} />
              <ChronicControlPanel visitId={selectedVisit.id} />

              <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div>
                  <dt className="text-xs text-txt-muted">Servicio</dt>
                  <dd className="text-sm font-medium text-txt-body">
                    {formatServiceTypeLabel(selectedVisit.serviceType)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-txt-muted">Modalidad</dt>
                  <dd className="text-sm font-medium text-txt-body">
                    {formatArrivalTypeLabel(selectedVisit.arrivalType)}
                  </dd>
                </div>
                {selectedVisit.doctorNombre ? (
                  <div>
                    <dt className="text-xs text-txt-muted">Médico</dt>
                    <dd className="text-sm font-medium break-words text-txt-body">
                      {selectedVisit.doctorNombre}
                    </dd>
                  </div>
                ) : null}
                {selectedVisit.consultorioNombre ? (
                  <div>
                    <dt className="text-xs text-txt-muted">Consultorio</dt>
                    <dd className="text-sm font-medium break-words text-txt-body">
                      {selectedVisit.consultorioNombre}
                    </dd>
                  </div>
                ) : null}
                {selectedVisit.horaConsulta ? (
                  <div>
                    <dt className="text-xs text-txt-muted">Hora cita</dt>
                    <dd className="mt-0.5 flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium text-txt-body">
                        {selectedVisit.horaConsulta}
                      </span>
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
                    </dd>
                  </div>
                ) : null}
              </dl>

              <div className="rounded-lg border border-line-hairline bg-subtle/20 p-3">
                <p className="text-xs font-medium tracking-wide text-txt-muted uppercase">
                  Motivo de consulta
                </p>
                <p className="mt-1 text-sm leading-relaxed break-words whitespace-pre-wrap text-txt-body">
                  {selectedVisit.notes?.trim() ||
                    "Sin motivo de consulta capturado en recepcion."}
                </p>
              </div>

              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                  <p className="text-xs font-medium tracking-wide text-txt-muted uppercase">
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
                <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-5">
                  <VitalMetric
                    label="Peso"
                    value={formatMetricWithUnit(selectedVitals?.weightKg, "kg")}
                  />
                  <VitalMetric
                    label="Talla"
                    value={formatMetricWithUnit(selectedVitals?.heightCm, "cm")}
                  />
                  <VitalMetric
                    label="Temperatura"
                    value={formatMetricWithUnit(selectedVitals?.temperatureC, "C", {
                      digits: 1,
                    })}
                  />
                  <VitalMetric
                    label="Saturacion de oxigeno"
                    value={formatMetricWithUnit(selectedVitals?.oxygenSaturationPct, "%")}
                  />
                  <VitalMetric
                    label="IMC"
                    value={formatOptionalMetric(selectedVitals?.bmi, { digits: 1 })}
                  />
                </div>
              </div>

              {hasOptionalVitals ? (
                <div className="space-y-2">
                  <p className="text-xs font-medium tracking-wide text-txt-muted uppercase">
                    Vitals adicionales
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                    {hasVitalValue(selectedVitals?.bloodPressureSystolic) ||
                    hasVitalValue(selectedVitals?.bloodPressureDiastolic) ? (
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
                        value={formatMetricWithUnit(selectedVitals?.heartRateBpm, "lpm")}
                      />
                    ) : null}

                    {hasVitalValue(selectedVitals?.respiratoryRateBpm) ? (
                      <VitalMetric
                        label="Frecuencia respiratoria"
                        value={formatMetricWithUnit(selectedVitals?.respiratoryRateBpm, "rpm")}
                      />
                    ) : null}
                  </div>
                </div>
              ) : null}

              <div className="rounded-lg border border-line-hairline bg-subtle/20 p-3">
                <p className="text-xs font-medium tracking-wide text-txt-muted uppercase">
                  Observaciones de somatometria
                </p>
                <p className="mt-1 text-sm leading-relaxed break-words whitespace-pre-wrap text-txt-body">
                  {formatSomatometriaNotes(selectedVitals?.notes)}
                </p>
              </div>
            </ConsultationSection>

            {!canWriteDoctorConsultation ? (
              <p className="text-sm text-txt-muted" role="status">
                No tenes permisos completos para registrar diagnostico,
                receta o cierre de consulta.
              </p>
            ) : null}

            <ConsultationSection
              id="consulta-diagnostico"
              title="Diagnóstico"
              description={
                selectedVisitStatus === VISIT_STATUS.EN_CONSULTA
                  ? "Al guardar el diagnóstico se crea la nota de la consulta; después podrás registrar diagnósticos secundarios, exploración física y medicamentos. El CIE es opcional para guardar avance y obligatorio para finalizar."
                  : "El CIE es opcional para guardar avance y obligatorio para finalizar."
              }
              actions={
                <SecondaryDiagnosesButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
              }
            >
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
                  <div className="flex flex-wrap items-center gap-2 rounded-lg border border-brand/40 bg-brand/5 px-3 py-2">
                    <p className="text-sm break-words text-txt-body">
                      CIE seleccionado: <strong>{selectedCieLabel}</strong>
                    </p>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={!canSaveClinicalData || saveDiagnosis.isPending}
                      onClick={handleClearCieSelection}
                    >
                      Quitar CIE
                    </Button>
                  </div>
                ) : (
                  <p className="text-xs text-txt-muted">
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
                  <div className="max-h-52 space-y-1 overflow-y-auto rounded-lg border border-line-hairline bg-paper p-1">
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
                        <p className="text-xs break-words text-txt-muted">
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
                  className="min-h-20 resize-y leading-relaxed"
                  disabled={!canSaveClinicalData || saveDiagnosis.isPending}
                  {...diagnosisForm.register("primaryDiagnosis")}
                />
                {diagnosisForm.formState.errors.primaryDiagnosis?.message ? (
                  <p className="text-sm text-status-critical" role="alert">
                    {diagnosisForm.formState.errors.primaryDiagnosis.message}
                  </p>
                ) : null}
              </div>

              <MorbidityAndFollowUpFields
                visitId={selectedVisit?.id ?? null}
                consultationDate={selectedVisit?.fechaConsulta ?? null}
                cieCode={selectedCieCode}
                diagnosisForm={diagnosisForm}
                disabled={!canSaveClinicalData || saveDiagnosis.isPending}
              />
            </ConsultationSection>

            <ConsultationSection
              id="consulta-nota"
              title="Nota médica"
              description="Se imprime en la nota de la consulta."
              actions={
                <PhysicalExamButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
              }
            >
              <SoapNoteFields
                diagnosisForm={diagnosisForm}
                disabled={!canSaveClinicalData || saveDiagnosis.isPending}
              />

              <div className="space-y-2">
                <Label htmlFor="finalNote">Nota final</Label>
                <Textarea
                  id="finalNote"
                  rows={5}
                  className="min-h-28 resize-y leading-relaxed"
                  disabled={!canSaveClinicalData || saveDiagnosis.isPending}
                  {...diagnosisForm.register("finalNote")}
                />
                {diagnosisForm.formState.errors.finalNote?.message ? (
                  <p className="text-sm text-status-critical" role="alert">
                    {diagnosisForm.formState.errors.finalNote.message}
                  </p>
                ) : null}
              </div>
            </ConsultationSection>

            <ConsultationSection
              id="consulta-receta"
              title="Receta"
              description="Los medicamentos del catálogo y las indicaciones generales se imprimen en la receta."
            >
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-txt-body">Medicamentos</p>
                  <PrescriptionItemsButton
                    visitId={selectedVisit.id}
                    disabled={!canSaveClinicalData}
                  />
                </div>
                <PrescriptionSummary
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
              </div>

              <div className="space-y-2 border-t border-line-hairline pt-4">
                <Label htmlFor="prescriptions">
                  Indicaciones generales (se imprimen al pie de la receta)
                </Label>
                <p className="text-xs leading-relaxed text-txt-muted">
                  Los medicamentos se agregan arriba, en Medicamentos. Aquí
                  van indicaciones como dieta, reposo o cuidados; una por
                  línea.
                </p>
                <Textarea
                  id="prescriptions"
                  rows={4}
                  className="min-h-24 resize-y leading-relaxed"
                  disabled={!canSaveClinicalData || savePrescriptions.isPending}
                  {...prescriptionsForm.register("itemsText")}
                  placeholder="Opcional"
                />
                {prescriptionsForm.formState.errors.itemsText?.message ? (
                  <p className="text-sm text-status-critical" role="alert">
                    {prescriptionsForm.formState.errors.itemsText.message}
                  </p>
                ) : null}
                <div className="flex flex-wrap items-start justify-between gap-3">
                  {selectedSavedPrescriptions.length > 0 ? (
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-txt-muted">Guardadas:</p>
                      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm leading-relaxed break-words text-txt-body">
                        {selectedSavedPrescriptions.map((item, index) => (
                          <li key={`${selectedVisit.id}-rx-${index}-${item}`}>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="text-xs text-txt-muted">
                      Aún no hay indicaciones generales guardadas.
                    </p>
                  )}
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
                    Guardar indicaciones
                  </Button>
                </div>
              </div>
            </ConsultationSection>

            <ConsultationSection
              id="consulta-documentos"
              title="Otros documentos"
              description="Incapacidad, resultados de estudios y pase a otra unidad."
            >
              <div className="flex flex-wrap gap-2">
                <EmitirIncapacidadButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
                <SubirResultadoEstudioButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
                <EmitirPaseButton
                  visitId={selectedVisit.id}
                  disabled={!canSaveClinicalData}
                />
              </div>
            </ConsultationSection>
          </div>

          {/* Acciones: las secundarias a la izquierda, guardar y finalizar a la derecha */}
          <div className="sticky bottom-0 z-10 flex flex-col-reverse gap-2 border-t border-line-hairline bg-paper/95 px-5 py-3 backdrop-blur sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  navigate("/clinico/consultas/doctor");
                }}
              >
                Volver a bandeja
              </Button>
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
            </div>
            <div className="flex flex-wrap gap-2 sm:justify-end">
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
            </div>
          </div>
        </>
      ) : (
        <p className="px-5 py-5 text-sm text-txt-muted sm:px-6" role="status">
          {hasStaleSelectedVisit
            ? "La consulta seleccionada ya no esta disponible. Elige otra consulta abierta."
            : "Selecciona una consulta abierta para iniciar la atencion clinica."}
        </p>
      )}
    </>
  );
}
