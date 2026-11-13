import { useEffect, useState } from "react";
import { AlarmClock, AppWindow, ClipboardList, PanelsTopLeft, Stethoscope } from "lucide-react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useNavigate, useParams } from "react-router-dom";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import {
  VISIT_STATUS,
  type CieSearchItem,
} from "@api/types";
import { useDebounce } from "@shared/hooks/useDebounce";
import { SinCentroAviso, usePermissionDependencies } from "@/domains/auth-access/contracts/navigation-auth";
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
import { usePrescriptionItems } from "@features/consulta-medica/modules/atencion/queries/usePrescriptionItems";
import { usePrintDocument } from "@shared/hooks/usePrintDocument";
import { PRINT_CAPABILITIES } from "@shared/components/print/printCapabilities";
import { AttendedTodayPanel } from "@features/consulta-medica/modules/atencion/components/AttendedTodayPanel";

import {
  buildDiagnosisFingerprint,
  buildDiagnosisPayload,
  buildFollowUpSlotId,
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
import { ConsultationWorkspace } from "@features/consulta-medica/modules/atencion/components/ConsultationWorkspace";
import { useConsultationLayoutStore } from "@features/consulta-medica/modules/atencion/state/consultationLayoutStore";
import { DoctorDeskLayout } from "@features/consulta-medica/modules/atencion/components/DoctorDeskLayout";
import {
  DeskQueueList,
  NextAppointmentNotice,
} from "@features/consulta-medica/modules/atencion/components/DeskQueueList";
import { DeskEmptyConsultation } from "@features/consulta-medica/modules/atencion/components/DeskEmptyConsultation";
import { useDoctorAttendedToday } from "@features/consulta-medica/modules/atencion/queries/useDoctorAttendedToday";
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
  // Mismo query que el panel de atendidas: solo para el contador de Mi consultorio.
  const attendedTodayQuery = useDoctorAttendedToday({ enabled: canReadDoctorQueue });
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
  const layout = useConsultationLayoutStore((state) => state.layout);
  const setLayout = useConsultationLayoutStore((state) => state.setLayout);

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
  // 5.3: "primera vez / subsecuente de la enfermedad", obligatoria para cerrar.
  const selectedMorbidity = useWatch({ control: diagnosisForm.control, name: "morbidity" });
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

  // Al cerrar se ofrece imprimir la receta si tiene medicamentos activos
  // (lo que imprime el backend; sin ellos daria 409).
  const canPrintReceta = hasCapability(
    PRINT_CAPABILITIES.receta.key,
    PRINT_CAPABILITIES.receta.fallback,
  );
  const prescriptionItemsQuery = usePrescriptionItems(selectedVisit?.id, {
    enabled: canPrintReceta && selectedVisitStatus === VISIT_STATUS.EN_CONSULTA,
  });
  const activeMedications = (prescriptionItemsQuery.data?.items ?? []).filter(
    (item) => item.status === "activo",
  );
  const hasActiveMedications = activeMedications.length > 0;
  // Especial o controlado: al cerrar la receta queda pendiente de autorizacion.
  const prescriptionNeedsAuthorization = activeMedications.some((item) => item.requiresAuthorization);
  const { print: printReceta } = usePrintDocument("receta");
  const canPrintNota = hasCapability(
    PRINT_CAPABILITIES.nota.key,
    PRINT_CAPABILITIES.nota.fallback,
  );

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
    Boolean(selectedCieCode) &&
    // Igual que el legado: no se cierra sin "primera vez o subsecuente".
    Boolean(selectedMorbidity);

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
      toast.success("Indicaciones guardadas");
    } catch (error) {
      toast.error("No se pudieron guardar las indicaciones", {
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

      const closeResult = await closeVisit.mutateAsync({
        visitId: selectedVisit.id,
        data: { ...diagnosisPayload, followUpSlotId: buildFollowUpSlotId(values) },
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
      const seguimiento = closeResult.followUpAppointment;
      const closedVisitId = selectedVisit.id;
      const followUpText = seguimiento
        ? `Cita de seguimiento ${seguimiento.folio}, ${new Date(seguimiento.fechaHora).toLocaleString("es-MX", {
            dateStyle: "medium",
            timeStyle: "short",
            timeZone: "America/Mexico_City",
          })}.`
        : undefined;
      const authorizationText = prescriptionNeedsAuthorization
        ? "La receta quedó pendiente de autorización: se avisa al autorizador y, cuando la autorice, podrás imprimirla."
        : undefined;
      toast.success("Consulta cerrada", {
        ...(hasActiveMedications && !prescriptionNeedsAuthorization
          ? {
              action: {
                label: "Imprimir receta",
                onClick: () => void printReceta(closedVisitId),
              },
            }
          : {}),
        description: [authorizationText, followUpText].filter(Boolean).join(" ") || undefined,
      });
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

  const workspaceProps = {
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
  };

  const nextAppointmentBanner =
    nextPendingVisit && nextPendingVisit.minutesUntil !== null && nextPendingVisit.minutesUntil <= 15 ? (
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
    ) : null;

  // Siguiente paciente sugerido en Mi consultorio: retomar el que esta en
  // consulta; si no, la proxima cita; si no, el primero que espera.
  const suggestedNextVisit =
    visits.find((visit) => visit.status === VISIT_STATUS.EN_CONSULTA) ??
    nextPendingVisit?.visit ??
    visits.find((visit) => visit.status === VISIT_STATUS.LISTA_PARA_DOCTOR) ??
    null;

  const isQueueReady =
    view === "consulta" && canReadDoctorQueue && !queueQuery.isLoading && !queueQuery.isError;

  return (
    <section className="space-y-6 p-6">
      <SinCentroAviso />
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

        <div className="flex flex-wrap items-center gap-2">
        {view === "consulta" ? (
          <div
            role="radiogroup"
            aria-label="Vista de la consulta"
            className="flex items-center gap-1 rounded-xl border border-line-struct bg-subtle/20 p-1"
          >
            {([
              { value: "ventana", label: "Ventana", Icon: AppWindow },
              { value: "escritorio", label: "Escritorio", Icon: PanelsTopLeft },
            ] as const).map(({ value, label, Icon }) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={layout === value}
                onClick={() => setLayout(value)}
                className={[
                  "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                  layout === value
                    ? "bg-paper text-txt-body shadow-sm"
                    : "text-txt-muted hover:text-txt-body",
                ].join(" ")}
              >
                <Icon className="size-3.5" /> {label}
              </button>
            ))}
          </div>
        ) : null}

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

      {isQueueReady && layout === "ventana" && visits.length === 0 ? (
        <p className="text-sm text-txt-muted">
          No hay pacientes listos para doctor.
        </p>
      ) : null}

      {isQueueReady && layout === "ventana" && (visits.length > 0 || isDetailRoute) ? (
        <section className="space-y-4">
          {nextAppointmentBanner}

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
            {...workspaceProps}
          />
        </section>
      ) : null}

      {/* Mi consultorio (PROPUESTA): cola, consulta y atendidas a la vista. */}
      {isQueueReady && layout === "escritorio" ? (
        <DoctorDeskLayout
          key={selectedVisitId ?? "sin-paciente"}
          hasOpenConsultation={isDetailRoute}
          queueCount={visits.length}
          attendedCount={attendedTodayQuery.data?.total}
          queue={
            <div className="space-y-3">
              {nextPendingVisit && nextPendingVisit.minutesUntil !== null && nextPendingVisit.minutesUntil <= 15 ? (
                <NextAppointmentNotice
                  visit={nextPendingVisit.visit}
                  minutesUntil={nextPendingVisit.minutesUntil}
                  onOpen={handleVisitChange}
                />
              ) : null}
              {visits.length > 0 ? (
                <DeskQueueList
                  visits={visits}
                  now={now}
                  consultationStartedAtByVisitId={consultationStartedAtByVisitId}
                  selectedVisitId={selectedVisitId}
                  onSelectVisit={handleVisitChange}
                />
              ) : (
                <p className="py-6 text-center text-sm text-txt-muted">No hay pacientes listos para doctor.</p>
              )}
            </div>
          }
          consultation={
            isDetailRoute ? (
              <section
                aria-label="Consulta en curso"
                data-testid="doctor-consultation-workspace"
                className="rounded-xl border border-line-struct bg-paper"
              >
                <ConsultationWorkspace variant="page" {...workspaceProps} />
              </section>
            ) : (
              <DeskEmptyConsultation nextVisit={suggestedNextVisit} onOpen={handleVisitChange} />
            )
          }
          attended={<AttendedTodayPanel variant="card" canPrint={canPrintReceta} canPrintNote={canPrintNota} />}
        />
      ) : null}

      {view === "consulta" && canReadDoctorQueue && layout === "ventana" ? (
        <AttendedTodayPanel canPrint={canPrintReceta} canPrintNote={canPrintNota} />
      ) : null}
    </section>
  );
};

export default DoctorConsultationPage;
