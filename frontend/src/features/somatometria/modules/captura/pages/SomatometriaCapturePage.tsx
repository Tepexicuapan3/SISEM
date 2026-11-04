import { useState } from "react";
import { useForm, useWatch, type UseFormRegisterReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ClipboardList, ListChecks } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { ApiError } from "@api/utils/errors";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Separator } from "@shared/ui/separator";
import { Textarea } from "@shared/ui/textarea";
import { toast } from "sonner";
import { VISIT_STATUS } from "@api/types";
import type { CaptureVitalsRequest, LatestPatientVitals, TodayCapturePayload } from "@api/types";
import { canCaptureVitals } from "@features/operativo/shared/domain/visit-flow.constants";
import {
  captureVitalsFormSchema,
  type CaptureVitalsFormInput,
  type CaptureVitalsFormValues,
} from "@features/somatometria/modules/captura/domain/capture-vitals.schemas";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { SinCentroAviso } from "@/domains/auth-access/contracts/navigation-auth";
import { useCaptureVitals } from "@features/somatometria/modules/captura/mutations/useCaptureVitals";
import { useLatestVitals } from "@features/somatometria/modules/captura/queries/useLatestVitals";
import { useSomatometriaQueue } from "@features/somatometria/modules/captura/queries/useSomatometriaQueue";
import { useSomatometriaWaitingQueue } from "@features/somatometria/modules/captura/queries/useSomatometriaWaitingQueue";
import { usePatientLookupHistorico } from "@features/recepcion/modules/checkin/queries/usePatientLookup";
import { SomatometriaQueueCards } from "@features/somatometria/modules/captura/components/SomatometriaQueueCards";
import { SomatometriaWaitingCards } from "@features/somatometria/modules/captura/components/SomatometriaWaitingCards";
import { SomatometriaHistorialView } from "@features/somatometria/modules/captura/components/SomatometriaHistorialView";
import { TodayCaptureBanner } from "@features/somatometria/modules/captura/components/TodayCaptureBanner";

/** Item de la bandeja tal cual lo devuelve `useSomatometriaQueue` -- se
 * infiere del propio hook en vez de importar un tipo aparte para no
 * arriesgar un nombre/ruta equivocado. */
type QueueVisit = NonNullable<
  ReturnType<typeof useSomatometriaQueue>["data"]
>["items"][number];

// ─── Constantes ───────────────────────────────────────────────────────────────

const CAPTURE_VITALS_DOMAIN_ERROR_MESSAGE: Record<
  | "VITALS_INCOMPLETE"
  | "ROLE_NOT_ALLOWED"
  | "VISIT_STATE_INVALID"
  | "VITALS_ALREADY_CAPTURED",
  string
> = {
  VITALS_INCOMPLETE:
    "No se puede liberar la visita: completa los vitales minimos requeridos.",
  ROLE_NOT_ALLOWED: "No tenes permiso para capturar vitales en esta visita.",
  VISIT_STATE_INVALID:
    "La visita ya no esta en un estado valido para somatometria. Actualiza la bandeja.",
  // D8/task 3.6 (change `somatometria-modulo-integral`): un 409 sobre el
  // POST de captura significa que esta visita YA tiene vitales -- nunca
  // se sobreescriben en silencio. El mensaje redirige a la edicion
  // auditada en vez de mostrar un error crudo.
  VITALS_ALREADY_CAPTURED:
    "Ya capturado — usa Corregir para modificar los signos vitales de esta visita.",
};

type CaptureVitalsDomainErrorCode =
  keyof typeof CAPTURE_VITALS_DOMAIN_ERROR_MESSAGE;

const FALLBACK_CAPTURE_VITALS_ERROR_MESSAGE =
  "No se pudieron guardar los vitales. Intenta nuevamente.";

const DEFAULT_FORM_VALUES: CaptureVitalsFormInput = {
  weightKg: "",
  heightCm: "",
  temperatureC: "",
  oxygenSaturationPct: "",
  heartRateBpm: "",
  respiratoryRateBpm: "",
  bloodPressureSystolic: "",
  bloodPressureDiastolic: "",
  glucosaCapilarMgdl: "",
  waistCircumferenceCm: "",
  observations: "",
};

const SOMATOMETRIA_QUEUE_PERMISSION_REQUIREMENT = {
  allOf: ["clinico:somatometria:read"],
} as const;

const SOMATOMETRIA_CAPTURE_PERMISSION_REQUIREMENT = {
  allOf: ["clinico:somatometria:read"],
} as const;

// ─── Helpers ──────────────────────────────────────────────────────────────────

const toPositiveNumber = (value: unknown): number | null => {
  const normalized =
    typeof value === "number" ? value : Number(value ?? Number.NaN);
  if (!Number.isFinite(normalized) || normalized <= 0) return null;
  return normalized;
};

const calculateBmi = (weightKg: number, heightCm: number): number => {
  const heightMeters = heightCm / 100;
  return Number((weightKg / (heightMeters * heightMeters)).toFixed(2));
};

const formatBmi = (value: number): string => value.toFixed(2);

const formatStatusLabel = (status: string): string =>
  status.replace(/_/g, " ");

const formatFechaNac = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
};

const numberOrEmpty = (value: number | null): string =>
  value !== null ? String(value) : "";

const formatCapturedAt = (iso: string): string =>
  new Date(iso).toLocaleDateString("es-MX", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });

/** Metricas puras (sin `capturedAt`) -- forma comun entre `LatestPatientVitals`
 * (ultima captura del paciente, cualquier dia) y `TodayCapturePayload.values`
 * (captura de hoy en otra visita, candidata a reuso). */
type VitalsMetricsInput = Omit<LatestPatientVitals, "capturedAt">;

const metricsToFormValues = (
  metrics: VitalsMetricsInput,
): CaptureVitalsFormInput => ({
  weightKg: numberOrEmpty(metrics.weightKg),
  heightCm: numberOrEmpty(metrics.heightCm),
  temperatureC: numberOrEmpty(metrics.temperatureC),
  oxygenSaturationPct: numberOrEmpty(metrics.oxygenSaturationPct),
  heartRateBpm: numberOrEmpty(metrics.heartRateBpm),
  respiratoryRateBpm: numberOrEmpty(metrics.respiratoryRateBpm),
  bloodPressureSystolic: numberOrEmpty(metrics.bloodPressureSystolic),
  bloodPressureDiastolic: numberOrEmpty(metrics.bloodPressureDiastolic),
  glucosaCapilarMgdl: numberOrEmpty(metrics.glucosaCapilarMgdl),
  waistCircumferenceCm: numberOrEmpty(metrics.waistCircumferenceCm),
  observations: "",
});

/** Convierte la ultima captura del paciente (si existe) en los valores
 * iniciales del formulario -- se usa SOLO como `defaultValues` de
 * `useForm`, nunca via `form.reset()` en un efecto: este componente se
 * remonta por visita (`key={visit.id}` en el padre), asi que `useForm` ya
 * arranca con el valor correcto sin necesitar sincronizarlo despues. */
const buildDefaultValues = (
  latest: LatestPatientVitals | null,
): CaptureVitalsFormInput => (latest ? metricsToFormValues(latest) : DEFAULT_FORM_VALUES);

const buildCaptureVitalsPayload = (
  values: CaptureVitalsFormValues,
  reusedFromVisitId: number | null,
): CaptureVitalsRequest => ({
  weightKg:              values.weightKg,
  heightCm:              values.heightCm,
  temperatureC:          values.temperatureC,
  oxygenSaturationPct:   values.oxygenSaturationPct,
  heartRateBpm:          values.heartRateBpm,
  respiratoryRateBpm:    values.respiratoryRateBpm,
  bloodPressureSystolic: values.bloodPressureSystolic,
  bloodPressureDiastolic: values.bloodPressureDiastolic,
  glucosaCapilarMgdl:    values.glucosaCapilarMgdl,
  waistCircumferenceCm:  values.waistCircumferenceCm,
  notes:                 values.observations,
  reusedFromVisitId:     reusedFromVisitId ?? undefined,
});

const resolveCaptureVitalsErrorMessage = (error: unknown): string => {
  if (!(error instanceof ApiError)) return FALLBACK_CAPTURE_VITALS_ERROR_MESSAGE;
  const domainCode = error.code as CaptureVitalsDomainErrorCode;
  if (domainCode in CAPTURE_VITALS_DOMAIN_ERROR_MESSAGE)
    return CAPTURE_VITALS_DOMAIN_ERROR_MESSAGE[domainCode];
  return error.message || FALLBACK_CAPTURE_VITALS_ERROR_MESSAGE;
};

// ─── Componentes internos ─────────────────────────────────────────────────────

interface MetricFieldProps {
  fieldId: string;
  label: string;
  unit: string;
  step?: number;
  disabled?: boolean;
  error?: string;
  registration: UseFormRegisterReturn;
  optional?: boolean;
}

const MetricField = ({
  fieldId,
  label,
  unit,
  step,
  disabled,
  error,
  registration,
  optional,
}: MetricFieldProps) => (
  <div className="space-y-2">
    <Label htmlFor={fieldId}>
      {label}
      {optional ? (
        <span className="ml-1 text-xs font-normal text-txt-muted">(opcional)</span>
      ) : null}
    </Label>
    <div className="flex overflow-hidden rounded-2xl border border-line-struct bg-paper">
      <Input
        id={fieldId}
        data-testid={`somato-${fieldId}-input`}
        type="number"
        step={step}
        disabled={disabled}
        className="rounded-none border-0 focus-visible:ring-0"
        {...registration}
      />
      <span className="inline-flex min-w-16 items-center justify-center border-l border-line-hairline bg-subtle px-3 text-sm text-txt-muted">
        {unit}
      </span>
    </div>
    {error ? (
      <p className="text-sm text-status-critical" role="alert">
        {error}
      </p>
    ) : null}
  </div>
);

function PatientInfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted">
        {label}
      </span>
      <span className="text-sm font-medium text-txt-body">{value ?? "—"}</span>
    </div>
  );
}

// ─── Formulario de vitales (uno por visita: el padre lo monta con
// `key={visit.id}`, asi que cada instancia nueva arranca limpia) ─────────────

interface VitalsCaptureFormProps {
  visit: QueueVisit;
  initialVitals: LatestPatientVitals | null;
  todayCapture: TodayCapturePayload | null;
  canCaptureSomatometriaVitals: boolean;
  canCaptureSelectedVisit: boolean;
}

function VitalsCaptureForm({
  visit,
  initialVitals,
  todayCapture,
  canCaptureSomatometriaVitals,
  canCaptureSelectedVisit,
}: VitalsCaptureFormProps) {
  const captureVitals = useCaptureVitals();
  const [capturedBmi, setCapturedBmi] = useState<number | null>(null);

  // El formulario arranca precargado por default con los valores de hoy
  // cuando existe `todayCapture` -- ya no hace falta un click explicito de
  // "Reusar" para verlos: son el punto de partida de la captura, editables
  // como siempre. `reusedFromVisitId` es un valor derivado (no estado): se
  // marca la trazabilidad de reuso apenas existe una captura de hoy, sin
  // importar si la enfermera termina editando los valores o no -- siempre
  // partio de ahi.
  const reusedFromVisitId = todayCapture ? todayCapture.sourceVisitId : null;

  const form = useForm<CaptureVitalsFormInput, unknown, CaptureVitalsFormValues>({
    resolver: zodResolver(captureVitalsFormSchema),
    mode: "onChange",
    defaultValues: todayCapture
      ? metricsToFormValues(todayCapture.values)
      : buildDefaultValues(initialVitals),
  });

  const [watchedWeightKg, watchedHeightCm] = useWatch({
    control: form.control,
    name: ["weightKg", "heightCm"],
  });

  const previewWeight = toPositiveNumber(watchedWeightKg);
  const previewHeight = toPositiveNumber(watchedHeightCm);
  const bmiPreview =
    previewWeight !== null && previewHeight !== null
      ? calculateBmi(previewWeight, previewHeight)
      : null;
  const visibleBmi = bmiPreview ?? capturedBmi;

  const handleCaptureVitals = async (values: CaptureVitalsFormValues) => {
    if (!canCaptureSomatometriaVitals || !canCaptureSelectedVisit) return;

    try {
      await captureVitals.mutateAsync({
        visitId: visit.id,
        data: buildCaptureVitalsPayload(values, reusedFromVisitId),
      });

      toast.success("Signos vitales guardados correctamente.", {
        description: `Visita ${visit.folio} actualizada.`,
      });
      form.reset(DEFAULT_FORM_VALUES);
      setCapturedBmi(null);
    } catch (error) {
      setCapturedBmi(null);
      toast.error("No se pudo guardar", {
        description: resolveCaptureVitalsErrorMessage(error),
      });
    }
  };

  // Atajo de un solo click: envia la visita a consulta con los valores que
  // ya estan en el formulario (precargados con los de hoy por default, pero
  // editables si la enfermera llego a corregir algo antes de apretarlo).
  const handlePasarDirectoAConsulta = () => {
    void form.handleSubmit(handleCaptureVitals)();
  };

  const isFormDisabled = !canCaptureSelectedVisit || captureVitals.isPending;

  return (
    <>
      {todayCapture ? (
        <TodayCaptureBanner
          todayCapture={todayCapture}
          onPasarDirectoAConsulta={handlePasarDirectoAConsulta}
          disabled={isFormDisabled}
        />
      ) : null}

      {initialVitals && !todayCapture ? (
        <Alert>
          <AlertTitle>Valores precargados</AlertTitle>
          <AlertDescription>
            Estos datos son de la última consulta del paciente (
            {formatCapturedAt(initialVitals.capturedAt)}). Revísalos y ajusta
            lo que haya cambiado antes de guardar.
          </AlertDescription>
        </Alert>
      ) : null}

      <Separator />

      <form
        className="space-y-5"
        noValidate
        onSubmit={form.handleSubmit(handleCaptureVitals)}
      >
        {/* Estatura + Peso */}
        <div className="grid gap-4 md:grid-cols-2">
          <MetricField
            fieldId="heightCm"
            label="Estatura"
            unit="cm"
            step={0.1}
            disabled={isFormDisabled}
            error={form.formState.errors.heightCm?.message}
            registration={form.register("heightCm")}
          />
          <MetricField
            fieldId="weightKg"
            label="Peso"
            unit="kg"
            step={0.1}
            disabled={isFormDisabled}
            error={form.formState.errors.weightKg?.message}
            registration={form.register("weightKg")}
          />
        </div>

        {/* IMC (calculado) + Temperatura */}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="bmi">IMC</Label>
            <div className="flex overflow-hidden rounded-2xl border border-line-struct bg-paper">
              <Input
                id="bmi"
                data-testid="somato-bmi-input"
                readOnly
                value={visibleBmi !== null ? formatBmi(visibleBmi) : "--"}
                className="rounded-none border-0 focus-visible:ring-0 text-txt-muted"
              />
              <span className="inline-flex min-w-20 items-center justify-center border-l border-line-hairline bg-subtle px-3 text-sm text-txt-muted">
                kg/m²
              </span>
            </div>
          </div>
          <MetricField
            fieldId="temperatureC"
            label="Temperatura"
            unit="°C"
            step={0.1}
            disabled={isFormDisabled}
            error={form.formState.errors.temperatureC?.message}
            registration={form.register("temperatureC")}
          />
        </div>

        {/* Saturación O2 + Frecuencia Cardiaca */}
        <div className="grid gap-4 md:grid-cols-2">
          <MetricField
            fieldId="oxygenSaturationPct"
            label="Saturación de oxígeno"
            unit="%"
            disabled={isFormDisabled}
            error={form.formState.errors.oxygenSaturationPct?.message}
            registration={form.register("oxygenSaturationPct")}
          />
          <MetricField
            fieldId="heartRateBpm"
            label="Frecuencia cardiaca"
            unit="lpm"
            optional
            disabled={isFormDisabled}
            error={form.formState.errors.heartRateBpm?.message}
            registration={form.register("heartRateBpm")}
          />
        </div>

        {/* Frecuencia Respiratoria + Glucosa Capilar */}
        <div className="grid gap-4 md:grid-cols-2">
          <MetricField
            fieldId="respiratoryRateBpm"
            label="Frecuencia respiratoria"
            unit="rpm"
            optional
            disabled={isFormDisabled}
            error={form.formState.errors.respiratoryRateBpm?.message}
            registration={form.register("respiratoryRateBpm")}
          />
          <MetricField
            fieldId="glucosaCapilarMgdl"
            label="Glucosa capilar"
            unit="mg/dL"
            optional
            disabled={isFormDisabled}
            error={form.formState.errors.glucosaCapilarMgdl?.message}
            registration={form.register("glucosaCapilarMgdl")}
          />
        </div>

        {/* Circunferencia de cintura */}
        <div className="grid gap-4 md:grid-cols-2">
          <MetricField
            fieldId="waistCircumferenceCm"
            label="Circunferencia de cintura"
            unit="cm"
            optional
            disabled={isFormDisabled}
            error={form.formState.errors.waistCircumferenceCm?.message}
            registration={form.register("waistCircumferenceCm")}
          />
        </div>

        {/* Tensión Arterial */}
        <div className="space-y-2">
          <p className="text-sm font-medium leading-none">
            Tensión arterial
            <span className="ml-1 text-xs font-normal text-txt-muted">(opcional)</span>
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            <MetricField
              fieldId="bloodPressureSystolic"
              label="Sistólica"
              unit="mmHg"
              disabled={isFormDisabled}
              error={form.formState.errors.bloodPressureSystolic?.message}
              registration={form.register("bloodPressureSystolic")}
            />
            <MetricField
              fieldId="bloodPressureDiastolic"
              label="Diastólica"
              unit="mmHg"
              disabled={isFormDisabled}
              error={form.formState.errors.bloodPressureDiastolic?.message}
              registration={form.register("bloodPressureDiastolic")}
            />
          </div>
        </div>

        {/* Observaciones */}
        <div className="space-y-2">
          <Label htmlFor="observations">
            Observaciones
            <span className="ml-1 text-xs font-normal text-txt-muted">(opcional)</span>
          </Label>
          <Textarea
            id="observations"
            data-testid="somato-observations-input"
            rows={3}
            disabled={isFormDisabled}
            placeholder="Observaciones clínicas relevantes..."
            {...form.register("observations")}
          />
          {form.formState.errors.observations?.message ? (
            <p className="text-sm text-status-critical" role="alert">
              {form.formState.errors.observations.message}
            </p>
          ) : null}
        </div>

        {/* Guardar */}
        <div className="border-t border-line-hairline pt-4">
          <Button
            type="submit"
            data-testid="somato-save-button"
            className="w-full md:w-auto"
            disabled={isFormDisabled}
          >
            {captureVitals.isPending ? "Guardando..." : "Guardar signos vitales"}
          </Button>
        </div>
      </form>
    </>
  );
}

// ─── Carga la ultima captura del paciente ANTES de montar el formulario
// (evita tener que "reescribirlo" despues con un efecto) ────────────────────

interface VitalsCaptureLoaderProps {
  visit: QueueVisit;
  canCaptureSomatometriaVitals: boolean;
  canCaptureSelectedVisit: boolean;
}

function VitalsCaptureLoader({
  visit,
  canCaptureSomatometriaVitals,
  canCaptureSelectedVisit,
}: VitalsCaptureLoaderProps) {
  const latestVitalsQuery = useLatestVitals(
    visit.id,
    canCaptureSomatometriaVitals,
  );

  if (canCaptureSomatometriaVitals && latestVitalsQuery.isLoading) {
    return (
      <p className="text-sm text-txt-muted">Cargando datos previos del paciente...</p>
    );
  }

  return (
    <VitalsCaptureForm
      visit={visit}
      initialVitals={latestVitalsQuery.data?.vitals ?? null}
      todayCapture={latestVitalsQuery.data?.todayCapture ?? null}
      canCaptureSomatometriaVitals={canCaptureSomatometriaVitals}
      canCaptureSelectedVisit={canCaptureSelectedVisit}
    />
  );
}

// ─── Página principal ─────────────────────────────────────────────────────────

export const SomatometriaCapturePage = () => {
  const { hasCapability } = usePermissionDependencies();
  const canReadSomatometriaQueue = hasCapability(
    "flow.somatometria.queue.read",
    SOMATOMETRIA_QUEUE_PERMISSION_REQUIREMENT,
  );
  const canCaptureSomatometriaVitals = hasCapability(
    "flow.somatometria.capture",
    SOMATOMETRIA_CAPTURE_PERMISSION_REQUIREMENT,
  );

  const queueQuery = useSomatometriaQueue({ enabled: canReadSomatometriaQueue });
  const waitingQueueQuery = useSomatometriaWaitingQueue({
    enabled: canReadSomatometriaQueue,
  });

  const [view, setView] = useState<"cola" | "historial">("cola");
  const [selectedVisitIdState, setSelectedVisitIdState] = useState<number | null>(null);

  const visits = queueQuery.data?.items ?? [];
  const waitingVisits = waitingQueueQuery.data?.items ?? [];

  const selectedVisitId =
    selectedVisitIdState !== null && visits.some((v) => v.id === selectedVisitIdState)
      ? selectedVisitIdState
      : (visits[0]?.id ?? null);

  const selectedVisit = visits.find((v) => v.id === selectedVisitId) ?? null;

  const canCaptureSelectedVisit =
    selectedVisit
      ? canCaptureSomatometriaVitals && canCaptureVitals(selectedVisit.status)
      : false;

  // Lookup de datos del paciente para mostrar edad y fecha nac
  const { data: patientData, isFetching: loadingPatient } = usePatientLookupHistorico(
    selectedVisit?.noExp ?? "",
    !!selectedVisit?.noExp,
  );

  const paciente = patientData
    ? [patientData.titular, ...patientData.dependientes]
        .filter(Boolean)
        .find((m) => m!.pkNum === selectedVisit?.pkNum) ?? null
    : null;

  const currentStatus = selectedVisit?.status ?? VISIT_STATUS.EN_SOMATOMETRIA;

  return (
    <section className="space-y-6 p-6">
      <SinCentroAviso />
      <header className="flex flex-col gap-3 rounded-xl border border-line-struct bg-paper p-5 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-txt-body">
            Somatometría
          </h1>
          <p className="text-sm text-txt-muted">
            Captura los signos vitales de la visita activa.
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex items-center gap-1 rounded-xl border border-line-struct bg-subtle/20 p-1">
          <button
            type="button"
            data-testid="somato-tab-cola"
            onClick={() => setView("cola")}
            className={[
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              view === "cola"
                ? "bg-paper text-txt-body shadow-sm"
                : "text-txt-muted hover:text-txt-body",
            ].join(" ")}
          >
            <ListChecks className="size-3.5" /> Cola
          </button>
          <button
            type="button"
            data-testid="somato-tab-historial"
            onClick={() => setView("historial")}
            className={[
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              view === "historial"
                ? "bg-paper text-txt-body shadow-sm"
                : "text-txt-muted hover:text-txt-body",
            ].join(" ")}
          >
            <ClipboardList className="size-3.5" /> Historial
          </button>
        </div>
      </header>

      {view === "historial" ? <SomatometriaHistorialView /> : null}

      {view === "cola" ? (
        <>
          {!canReadSomatometriaQueue ? (
            <p className="text-sm text-txt-muted" role="status">
              No tenes permisos completos para cargar la bandeja de somatometria.
            </p>
          ) : null}

          {canReadSomatometriaQueue && queueQuery.isLoading ? (
            <p className="text-sm text-txt-muted">Cargando bandeja...</p>
          ) : null}

          {canReadSomatometriaQueue && queueQuery.isError ? (
            <Alert variant="warning">
              <AlertTitle>Error al cargar</AlertTitle>
              <AlertDescription>
                No se pudo cargar la bandeja de somatometria.
              </AlertDescription>
            </Alert>
          ) : null}

          {canReadSomatometriaQueue &&
          !queueQuery.isLoading &&
          !queueQuery.isError &&
          visits.length === 0 ? (
            <p className="text-sm text-txt-muted">No hay pacientes en somatometria.</p>
          ) : null}

          {/* ── Cola de espera: independiente de la cola de somatometria --
              se muestra aunque no haya nadie EN somatometria todavia, porque
              justamente informa quien viene despues. ──────────────────── */}
          {canReadSomatometriaQueue ? (
            <section className="space-y-2 rounded-xl border border-line-hairline bg-paper p-5">
              <Label>Esperando pasar a somatometría</Label>
              {waitingQueueQuery.isLoading ? (
                <p className="text-sm text-txt-muted">Cargando cola de espera...</p>
              ) : null}
              {waitingQueueQuery.isError ? (
                <Alert variant="warning">
                  <AlertTitle>Error al cargar</AlertTitle>
                  <AlertDescription>
                    No se pudo cargar la cola de espera.
                  </AlertDescription>
                </Alert>
              ) : null}
              {!waitingQueueQuery.isLoading &&
              !waitingQueueQuery.isError &&
              waitingVisits.length === 0 ? (
                <p className="text-sm text-txt-muted">
                  No hay pacientes esperando pasar a somatometria.
                </p>
              ) : null}
              {!waitingQueueQuery.isLoading &&
              !waitingQueueQuery.isError &&
              waitingVisits.length > 0 ? (
                <SomatometriaWaitingCards visits={waitingVisits} />
              ) : null}
            </section>
          ) : null}

          {canReadSomatometriaQueue &&
          !queueQuery.isLoading &&
          !queueQuery.isError &&
          visits.length > 0 ? (
            <section className="space-y-5 rounded-xl border border-line-hairline bg-paper p-5">

              {/* ── Cola de somatometria (tarjetas) ─────────────────── */}
              <div className="space-y-2">
                <Label>En somatometría</Label>
                <SomatometriaQueueCards
                  visits={visits}
                  selectedVisitId={selectedVisitId}
                  onSelectVisit={setSelectedVisitIdState}
                />
              </div>

              {selectedVisit ? (
                <div className="flex items-center justify-between gap-2 rounded-xl border border-line-struct/60 bg-subtle/20 px-4 py-2">
                  <div>
                    <p className="text-xs text-txt-muted">Visita seleccionada · Folio</p>
                    <p className="text-sm font-medium font-mono text-txt-body">
                      {selectedVisit.folio}
                    </p>
                  </div>
                  <Badge variant="outline" className="uppercase">
                    {formatStatusLabel(currentStatus)}
                  </Badge>
                </div>
              ) : null}

              {/* ── Datos del paciente ─────────────────────────────── */}
              {selectedVisit ? (
                <div className="rounded-xl border border-line-struct/60 bg-subtle/20 px-4 py-3">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-txt-muted">
                    Datos del paciente
                  </p>
                  <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
                    <PatientInfoRow
                      label="Nombre"
                      value={selectedVisit.nombrePaciente}
                    />
                    <PatientInfoRow
                      label="Expediente"
                      value={
                        selectedVisit.noExp ? (
                          <span className="font-mono">
                            {selectedVisit.noExp}
                            {selectedVisit.pkNum > 0 ? (
                              <span className="ml-1 text-xs font-sans text-txt-muted">
                                Fam. #{selectedVisit.pkNum}
                              </span>
                            ) : null}
                          </span>
                        ) : "Sin expediente"
                      }
                    />
                    <PatientInfoRow
                      label="Edad"
                      value={
                        loadingPatient
                          ? "..."
                          : paciente?.edad != null
                          ? `${paciente.edad} años`
                          : null
                      }
                    />
                    <PatientInfoRow
                      label="Fecha nac."
                      value={
                        loadingPatient ? "..." : formatFechaNac(paciente?.fechaNac)
                      }
                    />
                  </div>
                </div>
              ) : null}

              {selectedVisit ? (
                <VitalsCaptureLoader
                  key={selectedVisit.id}
                  visit={selectedVisit}
                  canCaptureSomatometriaVitals={canCaptureSomatometriaVitals}
                  canCaptureSelectedVisit={canCaptureSelectedVisit}
                />
              ) : null}

              {!canCaptureSomatometriaVitals ? (
                <p className="text-sm text-txt-muted" role="status">
                  No tenes permisos completos para guardar vitales.
                </p>
              ) : null}

              {canCaptureSomatometriaVitals && !canCaptureSelectedVisit ? (
                <p className="text-sm text-status-alert" role="status">
                  Selecciona una visita en somatometria para capturar vitales.
                </p>
              ) : null}
            </section>
          ) : null}
        </>
      ) : null}
    </section>
  );
};

export default SomatometriaCapturePage;
