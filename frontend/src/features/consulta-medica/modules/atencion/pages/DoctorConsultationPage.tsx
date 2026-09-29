import { useEffect, useState } from "react";
import { AlarmClock, ClipboardList, Stethoscope } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useNavigate, useParams } from "react-router-dom";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import {
  VISIT_STATUS,
  type CieSearchItem,
} from "@api/types";
import { useDebounce } from "@shared/hooks/useDebounce";
import { usePermissionDependencies } from "@/domains/auth-access/contracts/navigation-auth";
import {
  canCloseConsultation,
  canStartConsultation,
} from "@features/operativo/shared/contracts/visit-flow";
import {
  saveDiagnosisFormSchema,
  savePrescriptionsFormSchema,
  type SaveDiagnosisFormInput,
  type SaveDiagnosisFormValues,
  type SavePrescriptionsFormInput,
  type SavePrescriptionsFormValues,
} from "@features/consulta-medica/modules/atencion/domain/consultation.schemas";
import { useCloseVisit } from "@features/consulta-medica/modules/atencion/mutations/useCloseVisit";
import { useSaveDiagnosis } from "@features/consulta-medica/modules/atencion/mutations/useSaveDiagnosis";
import { useSavePrescriptions } from "@features/consulta-medica/modules/atencion/mutations/useSavePrescriptions";
import { useStartConsultation } from "@features/consulta-medica/modules/atencion/mutations/useStartConsultation";
import { useCieSearch } from "@features/consulta-medica/modules/atencion/queries/useCieSearch";
import { useDoctorQueue } from "@features/consulta-medica/modules/atencion/queries/useDoctorQueue";

import {
  buildDiagnosisFingerprint,
  buildDiagnosisPayload,
  CLOSE_CONSULTATION_DOMAIN_ERROR_MESSAGE,
  DEFAULT_DIAGNOSIS_FORM_VALUES,
  DEFAULT_PRESCRIPTIONS_FORM_VALUES,
  DOCTOR_QUEUE_PERMISSION_REQUIREMENT,
  DOCTOR_WRITE_PERMISSION_REQUIREMENT,
  FALLBACK_CLOSE_CONSULTATION_ERROR_MESSAGE,
  FALLBACK_SAVE_DIAGNOSIS_ERROR_MESSAGE,
  FALLBACK_SAVE_PRESCRIPTIONS_ERROR_MESSAGE,
  FALLBACK_START_CONSULTATION_ERROR_MESSAGE,
  formatCieLabel,
  formatDateShort,
  getMinutesUntilAppointment,
  hasVitalValue,
  OPEN_VISIT_STATUSES,
  resolveDomainErrorMessage,
  SAVE_DIAGNOSIS_DOMAIN_ERROR_MESSAGE,
  SAVE_PRESCRIPTIONS_DOMAIN_ERROR_MESSAGE,
  START_CONSULTATION_DOMAIN_ERROR_MESSAGE,
  toPrescriptionItems,
  type VisitStatusOverrideState,
} from "./DoctorConsultationPage.helpers";
import { OpenConsultationsGrid } from "@features/consulta-medica/modules/atencion/components/OpenConsultationsGrid";
import { ConsultationDetailDialog } from "@features/consulta-medica/modules/atencion/components/ConsultationDetailDialog";
import { DoctorPipelineView } from "@features/consulta-medica/modules/atencion/components/DoctorPipelineView";

export const DoctorConsultationPage = () => {
  const navigate = useNavigate();
  const params = useParams<{ visitId?: string }>();

  const { hasCapability } = usePermissionDependencies();
  const canReadDoctorQueue = hasCapability(
    "flow.doctor.queue.read",
    DOCTOR_QUEUE_PERMISSION_REQUIREMENT,
  );
  const canStartDoctorConsultation = hasCapability(
    "flow.doctor.consultation.start",
    DOCTOR_WRITE_PERMISSION_REQUIREMENT,
  );
  const canCloseDoctorConsultation = hasCapability(
    "flow.doctor.consultation.close",
    DOCTOR_WRITE_PERMISSION_REQUIREMENT,
  );
  const canWriteDoctorConsultation =
    canStartDoctorConsultation && canCloseDoctorConsultation;

  const queueQuery = useDoctorQueue({ enabled: canReadDoctorQueue });
  const startConsultation = useStartConsultation();
  const saveDiagnosis = useSaveDiagnosis();
  const savePrescriptions = useSavePrescriptions();
  const closeVisit = useCloseVisit();

  const [selectedVisitStatusOverride, setSelectedVisitStatusOverride] =
    useState<VisitStatusOverrideState | null>(null);
  const [diagnosisDraftByVisitId, setDiagnosisDraftByVisitId] = useState<
    Record<number, SaveDiagnosisFormValues>
  >({});
  const [prescriptionsDraftByVisitId, setPrescriptionsDraftByVisitId] =
    useState<Record<number, string[]>>({});
  const [
    savedDiagnosisFingerprintByVisitId,
    setSavedDiagnosisFingerprintByVisitId,
  ] = useState<Record<number, string>>({});
  const [cieSearchTerm, setCieSearchTerm] = useState("");
  const [selectedCieByVisitId, setSelectedCieByVisitId] = useState<
    Record<number, CieSearchItem>
  >({});

  const [view, setView] = useState<"consulta" | "pipeline">("consulta");

  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const [consultationStartedAtByVisitId, setConsultationStartedAtByVisitId] =
    useState<Record<number, Date>>({});

  const diagnosisForm = useForm<
    SaveDiagnosisFormInput,
    unknown,
    SaveDiagnosisFormValues
  >({
    resolver: zodResolver(saveDiagnosisFormSchema),
    mode: "onChange",
    defaultValues: DEFAULT_DIAGNOSIS_FORM_VALUES,
  });

  const prescriptionsForm = useForm<
    SavePrescriptionsFormInput,
    unknown,
    SavePrescriptionsFormValues
  >({
    resolver: zodResolver(savePrescriptionsFormSchema),
    mode: "onChange",
    defaultValues: DEFAULT_PRESCRIPTIONS_FORM_VALUES,
  });

  const visits = (queueQuery.data?.items ?? []).filter((visit) => {
    return OPEN_VISIT_STATUSES.has(visit.status);
  });

  // Próxima cita: la visita lista_para_doctor con horaConsulta más próxima
  const nextPendingVisit = (() => {
    const candidates = visits
      .filter((v) => v.horaConsulta && v.status === VISIT_STATUS.LISTA_PARA_DOCTOR)
      .map((v) => ({
        visit: v,
        minutesUntil: getMinutesUntilAppointment(v.horaConsulta, now),
      }))
      .filter(({ minutesUntil }) => minutesUntil !== null && minutesUntil > -60)
      .sort((a, b) => (a.minutesUntil ?? 999) - (b.minutesUntil ?? 999));
    return candidates[0] ?? null;
  })();

  const parsedVisitId = Number.parseInt(params.visitId ?? "", 10);
  const selectedVisitId = Number.isNaN(parsedVisitId) ? null : parsedVisitId;
  const isDetailRoute = params.visitId !== undefined;

  const selectedVisit =
    visits.find((visit) => visit.id === selectedVisitId) ?? null;

  const selectedCieCode = diagnosisForm.watch("cieCode").trim().toUpperCase();
  const debouncedCieSearchTerm = useDebounce(cieSearchTerm, 300);
  const normalizedCieSearchTerm = debouncedCieSearchTerm.trim();
  const shouldSearchCies =
    Boolean(selectedVisit) &&
    canWriteDoctorConsultation &&
    normalizedCieSearchTerm.length >= 2 &&
    selectedCieCode.length === 0;

  const ciesSearchQuery = useCieSearch(
    {
      search: normalizedCieSearchTerm,
      limit: 8,
    },
    {
      enabled: shouldSearchCies,
    },
  );

  const selectedCie = selectedVisit
    ? selectedCieByVisitId[selectedVisit.id]
    : undefined;
  const selectedCieLabel = selectedCie
    ? formatCieLabel(selectedCie)
    : selectedCieCode;
  const ciesSearchItems = ciesSearchQuery.data?.items ?? [];

  const hasStaleSelectedVisit =
    isDetailRoute && selectedVisitId !== null && selectedVisit === null;

  const selectedVisitStatusOverrideValue =
    selectedVisit &&
    selectedVisitStatusOverride?.visitId === selectedVisit.id &&
    selectedVisitStatusOverride.status !== selectedVisit.status
      ? selectedVisitStatusOverride.status
      : null;

  const selectedVisitStatus = selectedVisit
    ? (selectedVisitStatusOverrideValue ?? selectedVisit.status)
    : VISIT_STATUS.LISTA_PARA_DOCTOR;

  const canStartSelectedVisit =
    Boolean(selectedVisit) &&
    canStartDoctorConsultation &&
    canStartConsultation(selectedVisitStatus);

  const canSaveClinicalData =
    Boolean(selectedVisit) &&
    canCloseDoctorConsultation &&
    selectedVisitStatus === VISIT_STATUS.EN_CONSULTA;

  const canCloseSelectedVisit =
    Boolean(selectedVisit) &&
    canCloseDoctorConsultation &&
    canCloseConsultation(selectedVisitStatus) &&
    // cieCode es obligatorio para CERRAR (NOM-024) aunque siga opcional
    // para el guardado de avance -- ver consultation_usecase.close_consultation.
    Boolean(selectedCieCode);

  const selectedSavedPrescriptions = selectedVisit
    ? (prescriptionsDraftByVisitId[selectedVisit.id] ?? [])
    : [];

  const selectedVitals = selectedVisit?.vitals ?? null;
  const selectedMinutesUntil = selectedVisit
    ? getMinutesUntilAppointment(selectedVisit.horaConsulta, now)
    : null;
  const selectedAppointmentDate = selectedVisit
    ? (selectedVisit.fechaConsulta
        ? formatDateShort(selectedVisit.fechaConsulta)
        : selectedVisit.fechaCita
        ? formatDateShort(selectedVisit.fechaCita)
        : null)
    : null;
  const hasOptionalVitals =
    hasVitalValue(selectedVitals?.heartRateBpm) ||
    hasVitalValue(selectedVitals?.respiratoryRateBpm) ||
    hasVitalValue(selectedVitals?.bloodPressureSystolic) ||
    hasVitalValue(selectedVitals?.bloodPressureDiastolic);

  const hydrateDraftsForVisit = (visitId: number) => {
    const diagnosisDraft = diagnosisDraftByVisitId[visitId];
    const prescriptionsDraft = prescriptionsDraftByVisitId[visitId];
    const normalizedCieCode = (diagnosisDraft?.cieCode ?? "")
      .trim()
      .toUpperCase();
    const selectedCieForVisit = selectedCieByVisitId[visitId];

    diagnosisForm.reset(diagnosisDraft ?? DEFAULT_DIAGNOSIS_FORM_VALUES);
    prescriptionsForm.reset({
      itemsText: prescriptionsDraft ? prescriptionsDraft.join("\n") : "",
    });

    if (selectedCieForVisit && selectedCieForVisit.code === normalizedCieCode) {
      setCieSearchTerm(formatCieLabel(selectedCieForVisit));
      return;
    }

    setCieSearchTerm(normalizedCieCode);
  };

  const handleVisitChange = (nextVisitId: number) => {
    navigate(`/clinico/consultas/doctor/${nextVisitId}`);
  };

  const handleConsultationModalOpenChange = (open: boolean) => {
    if (!open) {
      navigate("/clinico/consultas/doctor");
    }
  };

  useEffect(() => {
    if (!selectedVisit || !isDetailRoute) {
      return;
    }

    const diagnosisDraft = diagnosisDraftByVisitId[selectedVisit.id];
    const prescriptionsDraft = prescriptionsDraftByVisitId[selectedVisit.id];
    const normalizedCieCode = (diagnosisDraft?.cieCode ?? "")
      .trim()
      .toUpperCase();

    diagnosisForm.reset(diagnosisDraft ?? DEFAULT_DIAGNOSIS_FORM_VALUES);
    prescriptionsForm.reset({
      itemsText: prescriptionsDraft ? prescriptionsDraft.join("\n") : "",
    });

    setCieSearchTerm(normalizedCieCode);
  }, [
    diagnosisDraftByVisitId,
    diagnosisForm,
    isDetailRoute,
    prescriptionsDraftByVisitId,
    prescriptionsForm,
    selectedVisit,
  ]);

  const handleStartConsultation = async () => {
    if (!selectedVisit || !canStartSelectedVisit) {
      return;
    }

    try {
      const result = await startConsultation.mutateAsync({
        visitId: selectedVisit.id,
      });

      setSelectedVisitStatusOverride({
        visitId: selectedVisit.id,
        status: result.status,
      });
      setConsultationStartedAtByVisitId((current) => ({
        ...current,
        [selectedVisit.id]: new Date(),
      }));
      toast.success("Consulta iniciada");
    } catch (error) {
      toast.error("No se pudo iniciar la consulta", {
        description: resolveDomainErrorMessage(
          error,
          START_CONSULTATION_DOMAIN_ERROR_MESSAGE,
          FALLBACK_START_CONSULTATION_ERROR_MESSAGE,
        ),
      });
    }
  };

  const handleSelectCie = (cie: CieSearchItem) => {
    if (!selectedVisit) {
      return;
    }

    setSelectedCieByVisitId((current) => ({
      ...current,
      [selectedVisit.id]: cie,
    }));
    diagnosisForm.setValue("cieCode", cie.code, {
      shouldDirty: true,
      shouldValidate: true,
    });

    const currentDiagnosis = diagnosisForm.getValues("primaryDiagnosis").trim();
    if (!currentDiagnosis) {
      diagnosisForm.setValue("primaryDiagnosis", cie.description, {
        shouldDirty: true,
        shouldValidate: true,
      });
    }

    setCieSearchTerm(formatCieLabel(cie));
  };

  const handleClearCieSelection = () => {
    if (selectedVisit) {
      setSelectedCieByVisitId((current) => {
        const next = { ...current };
        delete next[selectedVisit.id];
        return next;
      });
    }

    diagnosisForm.setValue("cieCode", "", {
      shouldDirty: true,
      shouldValidate: true,
    });
    setCieSearchTerm("");
  };

  const handleSaveDiagnosis = async (values: SaveDiagnosisFormValues) => {
    if (!selectedVisit || !canSaveClinicalData) {
      return;
    }

    const diagnosisPayload = buildDiagnosisPayload(values);

    try {
      await saveDiagnosis.mutateAsync({
        visitId: selectedVisit.id,
        data: diagnosisPayload,
      });

      setDiagnosisDraftByVisitId((current) => ({
        ...current,
        [selectedVisit.id]: values,
      }));
      setSavedDiagnosisFingerprintByVisitId((current) => ({
        ...current,
        [selectedVisit.id]: buildDiagnosisFingerprint(values),
      }));
      toast.success("Diagnostico guardado");
    } catch (error) {
      toast.error("No se pudo guardar el diagnostico", {
        description: resolveDomainErrorMessage(
          error,
          SAVE_DIAGNOSIS_DOMAIN_ERROR_MESSAGE,
          FALLBACK_SAVE_DIAGNOSIS_ERROR_MESSAGE,
        ),
      });
    }
  };

  const handleSavePrescriptions = async (
    values: SavePrescriptionsFormValues,
  ) => {
    if (!selectedVisit || !canSaveClinicalData) {
      return;
    }

    const items = toPrescriptionItems(values.itemsText);

    try {
      const result = await savePrescriptions.mutateAsync({
        visitId: selectedVisit.id,
        data: { items },
      });

      setPrescriptionsDraftByVisitId((current) => ({
        ...current,
        [selectedVisit.id]: result.items,
      }));
      toast.success("Receta guardada");
    } catch (error) {
      toast.error("No se pudo guardar la receta", {
        description: resolveDomainErrorMessage(
          error,
          SAVE_PRESCRIPTIONS_DOMAIN_ERROR_MESSAGE,
          FALLBACK_SAVE_PRESCRIPTIONS_ERROR_MESSAGE,
        ),
      });
    }
  };

  const handleCloseVisit = async (values: SaveDiagnosisFormValues) => {
    if (!selectedVisit || !canCloseSelectedVisit) {
      return;
    }

    const diagnosisPayload = buildDiagnosisPayload(values);

    const diagnosisFingerprint = buildDiagnosisFingerprint(values);
    const hasMatchingSavedDiagnosis =
      savedDiagnosisFingerprintByVisitId[selectedVisit.id] ===
      diagnosisFingerprint;

    try {
      if (!hasMatchingSavedDiagnosis) {
        await saveDiagnosis.mutateAsync({
          visitId: selectedVisit.id,
          data: diagnosisPayload,
        });

        setDiagnosisDraftByVisitId((current) => ({
          ...current,
          [selectedVisit.id]: values,
        }));
        setSavedDiagnosisFingerprintByVisitId((current) => ({
          ...current,
          [selectedVisit.id]: diagnosisFingerprint,
        }));
      }

      await closeVisit.mutateAsync({
        visitId: selectedVisit.id,
        data: diagnosisPayload,
      });

      setSelectedVisitStatusOverride({
        visitId: selectedVisit.id,
        status: VISIT_STATUS.CERRADA,
      });
      setConsultationStartedAtByVisitId((current) => {
        const next = { ...current };
        delete next[selectedVisit.id];
        return next;
      });
      toast.success("Consulta cerrada");
      navigate("/clinico/consultas/doctor");
      diagnosisForm.reset(DEFAULT_DIAGNOSIS_FORM_VALUES);
      prescriptionsForm.reset(DEFAULT_PRESCRIPTIONS_FORM_VALUES);
      setDiagnosisDraftByVisitId((current) => ({
        ...current,
        [selectedVisit.id]: DEFAULT_DIAGNOSIS_FORM_VALUES,
      }));
      setPrescriptionsDraftByVisitId((current) => ({
        ...current,
        [selectedVisit.id]: [],
      }));
      setSelectedCieByVisitId((current) => {
        const next = { ...current };
        delete next[selectedVisit.id];
        return next;
      });
      setCieSearchTerm("");
    } catch (error) {
      toast.error("No se pudo cerrar la consulta", {
        description: resolveDomainErrorMessage(
          error,
          CLOSE_CONSULTATION_DOMAIN_ERROR_MESSAGE,
          FALLBACK_CLOSE_CONSULTATION_ERROR_MESSAGE,
        ),
      });
    }
  };

  const handleResetDrafts = () => {
    if (selectedVisit) {
      hydrateDraftsForVisit(selectedVisit.id);
    } else {
      diagnosisForm.reset(DEFAULT_DIAGNOSIS_FORM_VALUES);
      prescriptionsForm.reset(DEFAULT_PRESCRIPTIONS_FORM_VALUES);
      setCieSearchTerm("");
    }

    toast.info("Borradores restaurados");
  };

  const handleSaveDraftClick = () => {
    void diagnosisForm.handleSubmit(handleSaveDiagnosis)();
  };

  const handleSavePrescriptionClick = () => {
    void prescriptionsForm.handleSubmit(handleSavePrescriptions)();
  };

  const handleCloseConsultationClick = () => {
    void diagnosisForm.handleSubmit(handleCloseVisit)();
  };

  return (
    <section className="space-y-6 p-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-semibold tracking-tight text-brand">
            Consulta medica
          </h1>
          <p className="text-sm text-txt-muted">
            Flujo clinico lineal: inicia consulta, registra diagnostico y
            finaliza la atencion.
          </p>
        </div>

        <div className="flex items-center gap-1 rounded-xl border border-line-struct bg-subtle/20 p-1">
          <button
            type="button"
            data-testid="doctor-tab-consulta"
            onClick={() => setView("consulta")}
            className={[
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              view === "consulta"
                ? "bg-paper text-txt-body shadow-sm"
                : "text-txt-muted hover:text-txt-body",
            ].join(" ")}
          >
            <Stethoscope className="size-3.5" /> Consulta
          </button>
          <button
            type="button"
            data-testid="doctor-tab-pipeline"
            onClick={() => setView("pipeline")}
            className={[
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              view === "pipeline"
                ? "bg-paper text-txt-body shadow-sm"
                : "text-txt-muted hover:text-txt-body",
            ].join(" ")}
          >
            <ClipboardList className="size-3.5" /> Pacientes en proceso
          </button>
        </div>
      </header>

      {view === "pipeline" ? <DoctorPipelineView /> : null}

      {view === "consulta" && !canReadDoctorQueue ? (
        <p className="text-sm text-txt-muted" role="status">
          No tenes permisos completos para cargar la bandeja del doctor.
        </p>
      ) : null}

      {view === "consulta" && canReadDoctorQueue && queueQuery.isLoading ? (
        <p className="text-sm text-txt-muted">Cargando bandeja del doctor...</p>
      ) : null}

      {view === "consulta" && canReadDoctorQueue && queueQuery.isError ? (
        <Alert variant="warning">
          <AlertTitle>Error al cargar</AlertTitle>
          <AlertDescription>
            No se pudo cargar la bandeja del doctor.
          </AlertDescription>
        </Alert>
      ) : null}

      {view === "consulta" &&
      canReadDoctorQueue &&
      !queueQuery.isLoading &&
      !queueQuery.isError &&
      visits.length === 0 ? (
        <p className="text-sm text-txt-muted">
          No hay pacientes listos para doctor.
        </p>
      ) : null}

      {view === "consulta" &&
      canReadDoctorQueue &&
      !queueQuery.isLoading &&
      !queueQuery.isError &&
      (visits.length > 0 || isDetailRoute) ? (
        <section className="space-y-4">
          {/* ── Banner próxima cita ────────────────────────────────── */}
          {nextPendingVisit && nextPendingVisit.minutesUntil !== null && nextPendingVisit.minutesUntil <= 15 ? (
            <div className={[
              "flex items-center gap-3 rounded-xl border px-4 py-3",
              nextPendingVisit.minutesUntil <= 5
                ? "border-red-300 bg-red-50"
                : "border-amber-300 bg-amber-50",
            ].join(" ")}>
              <AlarmClock className={[
                "size-5 shrink-0",
                nextPendingVisit.minutesUntil <= 5 ? "text-red-500 animate-pulse" : "text-amber-600",
              ].join(" ")} />
              <div className="flex-1 min-w-0">
                <p className={[
                  "text-sm font-bold",
                  nextPendingVisit.minutesUntil <= 5 ? "text-red-700" : "text-amber-800",
                ].join(" ")}>
                  {nextPendingVisit.minutesUntil <= 0
                    ? `La cita empezó hace ${Math.abs(nextPendingVisit.minutesUntil)} min — pendiente de atención`
                    : nextPendingVisit.minutesUntil <= 5
                    ? `¡La siguiente cita empieza en ${nextPendingVisit.minutesUntil} minuto${nextPendingVisit.minutesUntil === 1 ? "" : "s"}!`
                    : `Próxima cita en ${nextPendingVisit.minutesUntil} minutos`}
                </p>
                <p className="text-xs text-txt-muted mt-0.5 truncate">
                  {nextPendingVisit.visit.nombrePaciente ?? `Exp. ${nextPendingVisit.visit.noExp}`}
                  {nextPendingVisit.visit.consultorioNombre
                    ? ` · ${nextPendingVisit.visit.consultorioNombre}`
                    : null}
                </p>
              </div>
              <span className={[
                "font-mono text-xl font-bold shrink-0",
                nextPendingVisit.minutesUntil <= 5 ? "text-red-600" : "text-amber-700",
              ].join(" ")}>
                {nextPendingVisit.visit.horaConsulta}
              </span>
            </div>
          ) : null}

          {visits.length > 0 ? (
            <OpenConsultationsGrid
              visits={visits}
              now={now}
              consultationStartedAtByVisitId={consultationStartedAtByVisitId}
              onSelectVisit={handleVisitChange}
            />
          ) : null}

          <ConsultationDetailDialog
            isDetailRoute={isDetailRoute}
            handleConsultationModalOpenChange={handleConsultationModalOpenChange}
            selectedVisit={selectedVisit}
            hasStaleSelectedVisit={hasStaleSelectedVisit}
            selectedVisitStatus={selectedVisitStatus}
            consultationStartedAtByVisitId={consultationStartedAtByVisitId}
            now={now}
            selectedMinutesUntil={selectedMinutesUntil}
            selectedAppointmentDate={selectedAppointmentDate}
            selectedVitals={selectedVitals}
            hasOptionalVitals={hasOptionalVitals}
            canStartSelectedVisit={canStartSelectedVisit}
            startConsultation={startConsultation}
            saveDiagnosis={saveDiagnosis}
            closeVisit={closeVisit}
            savePrescriptions={savePrescriptions}
            handleStartConsultation={handleStartConsultation}
            canWriteDoctorConsultation={canWriteDoctorConsultation}
            cieSearchTerm={cieSearchTerm}
            setCieSearchTerm={setCieSearchTerm}
            selectedCieCode={selectedCieCode}
            diagnosisForm={diagnosisForm}
            selectedCieByVisitId={selectedCieByVisitId}
            setSelectedCieByVisitId={setSelectedCieByVisitId}
            selectedCieLabel={selectedCieLabel}
            handleClearCieSelection={handleClearCieSelection}
            canSaveClinicalData={canSaveClinicalData}
            shouldSearchCies={shouldSearchCies}
            ciesSearchQuery={ciesSearchQuery}
            ciesSearchItems={ciesSearchItems}
            handleSelectCie={handleSelectCie}
            prescriptionsForm={prescriptionsForm}
            selectedSavedPrescriptions={selectedSavedPrescriptions}
            handleSaveDraftClick={handleSaveDraftClick}
            handleSavePrescriptionClick={handleSavePrescriptionClick}
            handleResetDrafts={handleResetDrafts}
            handleCloseConsultationClick={handleCloseConsultationClick}
            canCloseSelectedVisit={canCloseSelectedVisit}
            navigate={navigate}
          />
        </section>
      ) : null}
    </section>
  );
};

export default DoctorConsultationPage;
