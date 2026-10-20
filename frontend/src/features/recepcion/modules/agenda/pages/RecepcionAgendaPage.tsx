import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { CalendarClock, CalendarDays, ClipboardList, List, QrCode, RefreshCcw, Settings2 } from "lucide-react";
import { useDebounce }           from "@shared/hooks/useDebounce";
import { useCitasList }          from "@features/recepcion/modules/citas/queries/useCitasList";
import { usePatientLookupHistorico }  from "@features/recepcion/modules/checkin/queries/usePatientLookup";
import { visitsAPI }                   from "@api/resources/visits.api";
import { TurnoIndicator } from "@features/recepcion/shared/components/TurnoIndicator";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@shared/ui/alert-dialog";
import { Button } from "@shared/ui/button";
import { Textarea } from "@shared/ui/textarea";
import {
  ARRIVAL_TYPE,
  VISIT_STATUS,
  type VisitQueueItem,
  type VisitStatus,
} from "@api/types";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { useVisitStatusAction } from "@features/recepcion/modules/checkin/mutations/useVisitStatusAction";
import { useRecepcionAgendaQueue } from "@features/recepcion/modules/agenda/queries/useRecepcionAgendaQueue";
import { RecepcionQuickCheckinDialog } from "@features/recepcion/modules/agenda/components/RecepcionQuickCheckinDialog";
import { DisponibilidadView } from "@features/recepcion/modules/agenda/components/DisponibilidadView";
import { HistorialView } from "@features/recepcion/modules/agenda/components/HistorialView";
import { BandejaView } from "@features/recepcion/modules/agenda/components/BandejaView";
import { mapVisitToCheckinDefaults } from "@features/recepcion/modules/checkin/domain/checkin.mappers";
import type { CheckinFormInput } from "@features/recepcion/modules/checkin/domain/checkin.schemas";
import { FichaModal } from "@features/recepcion/shared/components/FichaModal";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { useConsultoriosList } from "@features/admin/modules/catalogos/consultorios/queries/useConsultoriosList";
import { useMedicosList } from "@features/admin/modules/medicos/hooks/useMedicos";
import {
  RECEPCION_QUEUE_PERMISSION_REQUIREMENT,
  RECEPCION_WRITE_PERMISSION_REQUIREMENT,
} from "@features/recepcion/shared/domain/recepcion.permissions";
import {
  RECEPCION_SERVICE,
  resolveRecepcionService,
  type RecepcionService,
} from "@features/recepcion/shared/domain/recepcion.services";
import { isOpenVisitStatus } from "@features/recepcion/shared/utils/recepcion-format";
import {
  ARRIVAL_TYPE_FILTER,
  FALLBACK_VISIT_STATUS_ERROR_MESSAGE,
  getBandejaPeriodRange,
  getMonday,
  matchesArrivalType,
  matchesSearch,
  matchesService,
  matchesStatus,
  RECEPCION_ACTION,
  RECEPCION_ACTION_COPY,
  resolveDomainErrorMessage,
  SERVICE_FILTER,
  shouldRefreshQueueAfterError,
  buildDoctorFilterOptions,
  sortAgendaVisits,
  STATUS_FILTER,
  VISIT_STATUS_DOMAIN_ERROR_MESSAGE,
  type ArrivalTypeFilter,
  type PendingStatusAction,
  type RecepcionAction,
  type ServiceFilter,
  type StatusFilter,
} from "./RecepcionAgendaPage.helpers";

export const RecepcionAgendaPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const shouldFocusCheckin = searchParams.get("focus") === "checkin";
  const focusFolio = searchParams.get("folio");

  const { hasCapability } = usePermissionDependencies();
  const canReadAgenda = hasCapability(
    "flow.visits.queue.read",
    RECEPCION_QUEUE_PERMISSION_REQUIREMENT,
  );
  const canWriteRecepcion = hasCapability(
    "flow.recepcion.queue.write",
    RECEPCION_WRITE_PERMISSION_REQUIREMENT,
  );
  const queueQuery = useRecepcionAgendaQueue({ enabled: canReadAgenda });
  const visitStatusAction = useVisitStatusAction();

  const [view,         setView]         = useState<"bandeja" | "disponibilidad" | "historial">("bandeja");
  const [calCentroId,  setCalCentroId]  = useState<number | null>(null);
  const [calMedicoId,  setCalMedicoId]  = useState<number | null>(null);
  const [calWeekStart, setCalWeekStart] = useState(() => getMonday(new Date()));
  const [medicoSearch, setMedicoSearch] = useState("");

  // ── Historial NOM-024 ───────────────────────────────────────────────────────
  const [histNoExp,         setHistNoExp]         = useState("");
  const [histFechaDesde,    setHistFechaDesde]    = useState("");
  const [histFechaHasta,    setHistFechaHasta]    = useState("");
  const [histSelectedPkNum, setHistSelectedPkNum] = useState<number | null>(null);
  const [histTab,           setHistTab]           = useState<"citas" | "visitas">("citas");

  const histDebouncedNoExp = useDebounce(histNoExp, 400);
  const histEnabled = view === "historial" && canReadAgenda && histDebouncedNoExp.trim().length >= 4;

  const { data: histPatient } = usePatientLookupHistorico(histDebouncedNoExp.trim(), histEnabled);

  // Citas del expediente (filtradas por pkNum client-side)
  const { data: histCitasData, isLoading: histCitasLoading } = useCitasList(
    { noExp: histDebouncedNoExp.trim() || undefined, pageSize: 500,
      fechaDesde: histFechaDesde || undefined, fechaHasta: histFechaHasta || undefined },
    { enabled: histEnabled },
  );
  const histCitas = [...(histCitasData?.items ?? [])]
    .filter((c) => histSelectedPkNum === null || c.pkNum === histSelectedPkNum)
    .sort((a, b) => new Date(b.fechaHora).getTime() - new Date(a.fechaHora).getTime());

  // Visitas (fichas) del expediente — para movimientos NOM-024
  const { data: histVisitsData, isLoading: histVisitsLoading } = useQuery({
    queryKey: ["hist-visits", histDebouncedNoExp.trim(), histFechaDesde, histFechaHasta],
    queryFn:  () => visitsAPI.getAll({ noExp: histDebouncedNoExp.trim(), pageSize: 500 }),
    enabled:  histEnabled,
    staleTime: 30_000,
  });
  const histVisits = [...(histVisitsData?.items ?? [])]
    .filter((v) => histSelectedPkNum === null || v.pkNum === histSelectedPkNum)
    .sort((a, b) => new Date(b.fechaAlta ?? 0).getTime() - new Date(a.fechaAlta ?? 0).getTime());

  // Reset member selector al cambiar expediente
  const prevNoExp = useDebounce(histNoExp, 600);
  if (prevNoExp !== histNoExp && histSelectedPkNum !== null) {
    setHistSelectedPkNum(null);
  }

  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(
    STATUS_FILTER.OPEN,
  );
  const [arrivalTypeFilter, setArrivalTypeFilter] = useState<ArrivalTypeFilter>(
    ARRIVAL_TYPE_FILTER.ALL,
  );
  const [serviceFilter, setServiceFilter] = useState<ServiceFilter>(
    SERVICE_FILTER.ALL,
  );
  const [doctorFilter,      setDoctorFilter]      = useState<number | "all">("all");
  const [consultorioFilter, setConsultorioFilter] = useState<number | "all">("all");
  const [centroFilter,      setCentroFilter]      = useState<number | "all">("all");
  const [fichaOpen, setFichaOpen] = useState(false);
  const [fichaVisit, setFichaVisit] = useState<VisitQueueItem | null>(null);

  // ── Período histórico de la bandeja ────────────────────────────────────────
  const [bandejaPeriod, setBandejaPeriod] = useState("today");
  const [bandejaCustomDesde, setBandejaCustomDesde] = useState("");
  const [bandejaCustomHasta, setBandejaCustomHasta] = useState("");
  const [bandejaPage, setBandejaPage] = useState(1);

  const bandejaIsHistorical = bandejaPeriod !== "today";
  const { fechaDesde: bFechaDesde, fechaHasta: bFechaHasta } =
    getBandejaPeriodRange(bandejaPeriod, bandejaCustomDesde, bandejaCustomHasta);
  const bandejaCanQuery = bandejaIsHistorical && Boolean(bFechaDesde) && Boolean(bFechaHasta);

  const {
    data: historicalData,
    isLoading: historicalLoading,
    isFetching: historicalFetching,
    isError: historicalIsError,
    refetch: historicalRefetch,
  } = useQuery({
    queryKey: ["bandeja-historica", bFechaDesde, bFechaHasta, bandejaPage, statusFilter, serviceFilter],
    queryFn: () =>
      visitsAPI.getAll({
        page: bandejaPage,
        pageSize: 50,
        fechaDesde: bFechaDesde || undefined,
        fechaHasta: bFechaHasta || undefined,
        status:
          statusFilter !== STATUS_FILTER.ALL && statusFilter !== STATUS_FILTER.OPEN
            ? (statusFilter as VisitStatus)
            : undefined,
        serviceType:
          serviceFilter !== SERVICE_FILTER.ALL
            ? (serviceFilter as "medicina_general" | "especialidad" | "urgencias")
            : undefined,
      }),
    enabled: bandejaCanQuery,
    staleTime: 60_000,
  });

  const [quickCheckinOpen, setQuickCheckinOpen] = useState(
    () => shouldFocusCheckin,
  );
  const [quickCheckinDefaults, setQuickCheckinDefaults] = useState<
    Partial<CheckinFormInput> | undefined
  >(undefined);
  const [pendingStatusAction, setPendingStatusAction] =
    useState<PendingStatusAction | null>(null);
  // Solo se usa cuando pendingStatusAction.targetStatus === CANCELADA -- el
  // backend exige motivo unicamente para esa transicion (VISIT_MOTIVO_REQUERIDO).
  const [cancelMotivo, setCancelMotivo] = useState("");

  const visits = bandejaIsHistorical
    ? (historicalData?.items ?? [])
    : (queueQuery.data?.items ?? []);
  const openVisits = visits.filter((visit) => isOpenVisitStatus(visit.status));
  const waitingCount = visits.filter(
    (visit) => visit.status === VISIT_STATUS.EN_ESPERA,
  ).length;
  const withAppointmentCount = openVisits.filter(
    (visit) => visit.arrivalType === ARRIVAL_TYPE.APPOINTMENT,
  ).length;
  const walkInCount = openVisits.filter(
    (visit) => visit.arrivalType === ARRIVAL_TYPE.WALK_IN,
  ).length;
  const serviceCounts = openVisits.reduce<Record<RecepcionService, number>>(
    (accumulator, visit) => {
      const service = resolveRecepcionService(visit);
      return {
        ...accumulator,
        [service]: (accumulator[service] ?? 0) + 1,
      };
    },
    {
      [RECEPCION_SERVICE.MEDICINA_GENERAL]: 0,
      [RECEPCION_SERVICE.ESPECIALIDAD]: 0,
      [RECEPCION_SERVICE.URGENCIAS]: 0,
      [RECEPCION_SERVICE.SIN_CLASIFICAR]: 0,
    },
  );
  const activeDoctorCount = new Set(
    openVisits
      .map((visit) => visit.doctorId)
      .filter((doctorId): doctorId is number => typeof doctorId === "number"),
  ).size;
  const openVisitsWithoutDoctorCount = openVisits.filter(
    (visit) => visit.doctorId == null,
  ).length;

  // ── Catálogos reales para filtros (carga única, filtrado client-side) ────────
  // Estrategia: cargar TODO una sola vez al montar; filtrar en memoria.
  // Sin llamadas extra al cambiar filtros → O(1) por interacción.

  const { data: centrosData } = useCentrosAtencionList({ isActive: true });
  const centroOptions = (centrosData?.items ?? []).map((c) => ({ id: c.id, nombre: c.name }));

  const { data: consultoriosData } = useConsultoriosList(
    { isActive: true, pageSize: 500 },
  );
  const allConsultorios = consultoriosData?.items ?? [];

  const { data: medicosData } = useMedicosList({ estatusMedico: "ACTIVO" });
  const allMedicos = medicosData?.items ?? [];

  // Filtrado client-side: si hay centro seleccionado → solo los de ese centro
  const selectedCentroId = centroFilter !== "all" ? centroFilter : null;

  const consultorioOptions = (
    selectedCentroId
      ? allConsultorios.filter((c) => c.centerId === selectedCentroId)
      : allConsultorios
  ).map((c) => ({ id: c.id, nombre: `#${c.numero} — ${c.name}` }));

  // El filtro compara contra `visit.doctorId` (espacio USUARIO): las opciones usan
  // `usuarioId`, no `m.id` (No. Médico).
  const doctorOptions = buildDoctorFilterOptions(
    selectedCentroId
      ? allMedicos.filter((m) =>
          m.centros.some((mc) => mc.centroId === selectedCentroId),
        )
      : allMedicos,
  );

  // ── Listado visual de médicos — vista Disponibilidad ──────────────────────
  const disponibilidadMedicos = (calCentroId
    ? allMedicos.filter((m) => m.centros.some((c) => c.centroId === calCentroId))
    : allMedicos
  ).filter((m) =>
    m.nombreCompleto.toLowerCase().includes(medicoSearch.trim().toLowerCase()),
  );

  const filteredVisits = visits
    .filter((visit) => matchesStatus(visit, statusFilter))
    .filter((visit) => matchesArrivalType(visit, arrivalTypeFilter))
    .filter((visit) => matchesSearch(visit, searchTerm))
    .filter((visit) => {
      const service = resolveRecepcionService(visit);
      return matchesService(service, serviceFilter);
    })
    .filter((visit) => doctorFilter      === "all" || visit.doctorId      === doctorFilter)
    .filter((visit) => consultorioFilter === "all" || visit.consultorioId === consultorioFilter)
    .filter((visit) => centroFilter      === "all" || visit.centroId      === centroFilter)
    .sort(sortAgendaVisits);
  const legacyFocusedVisit = focusFolio
    ? visits.find((visit) => visit.folio === focusFolio)
    : undefined;
  const resolvedQuickCheckinDefaults =
    quickCheckinDefaults ||
    (shouldFocusCheckin && legacyFocusedVisit
      ? mapVisitToCheckinDefaults(legacyFocusedVisit)
      : undefined);
  const pendingActionCopy = pendingStatusAction
    ? RECEPCION_ACTION_COPY[pendingStatusAction.targetStatus]
    : null;
  const pendingActionRequiresMotivo =
    pendingStatusAction?.targetStatus === RECEPCION_ACTION.CANCELADA;
  const cancelMotivoValido = cancelMotivo.trim().length > 0;

  const handleOpenQuickCheckin = (defaults?: Partial<CheckinFormInput>) => {
    setQuickCheckinDefaults(defaults);
    setQuickCheckinOpen(true);
  };

  const openStatusActionConfirmation = (
    visitId: number,
    folio: string,
    targetStatus: RecepcionAction,
  ) => {
    if (!canWriteRecepcion || visitStatusAction.isPending) {
      return;
    }

    setCancelMotivo("");
    setPendingStatusAction({ visitId, folio, targetStatus });
  };

  // "Llego" -> envia a somatometria SIN dialogo de confirmacion (a
  // diferencia de cancelar/no-show, que si lo piden por ser
  // irreversibles). Mismo flujo de mutacion/toast/refetch-on-error que
  // `handleConfirmStatusAction`, pero disparado directo desde el boton.
  const handleMarkArrived = async (visitId: number, folio: string) => {
    if (!canWriteRecepcion || visitStatusAction.isPending) {
      return;
    }

    try {
      await visitStatusAction.mutateAsync({
        visitId,
        targetStatus: RECEPCION_ACTION.EN_SOMATOMETRIA,
      });

      toast.success(
        RECEPCION_ACTION_COPY[RECEPCION_ACTION.EN_SOMATOMETRIA].successMessage,
        { description: `Folio ${folio}.` },
      );
    } catch (error) {
      if (shouldRefreshQueueAfterError(error)) {
        void queueQuery.refetch?.();
      }

      toast.error("No se pudo actualizar el estado", {
        description: resolveDomainErrorMessage(
          error,
          VISIT_STATUS_DOMAIN_ERROR_MESSAGE,
          FALLBACK_VISIT_STATUS_ERROR_MESSAGE,
        ),
      });
    }
  };

  const handleConfirmStatusAction = async () => {
    if (!pendingStatusAction) {
      return;
    }

    const requiresMotivo = pendingStatusAction.targetStatus === RECEPCION_ACTION.CANCELADA;
    if (requiresMotivo && !cancelMotivoValido) {
      return;
    }

    try {
      await visitStatusAction.mutateAsync({
        visitId: pendingStatusAction.visitId,
        targetStatus: pendingStatusAction.targetStatus,
        motivo: requiresMotivo ? cancelMotivo.trim() : undefined,
      });

      toast.success(
        RECEPCION_ACTION_COPY[pendingStatusAction.targetStatus].successMessage,
      );
    } catch (error) {
      if (shouldRefreshQueueAfterError(error)) {
        void queueQuery.refetch?.();
      }

      toast.error("No se pudo actualizar el estado", {
        description: resolveDomainErrorMessage(
          error,
          VISIT_STATUS_DOMAIN_ERROR_MESSAGE,
          FALLBACK_VISIT_STATUS_ERROR_MESSAGE,
        ),
      });
    } finally {
      setPendingStatusAction(null);
      setCancelMotivo("");
    }
  };

  return (
    <section className="space-y-5 p-6">
      <header className="flex flex-col gap-3 rounded-xl border border-line-struct bg-paper p-5 md:flex-row md:items-start md:justify-between">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 rounded-full border border-line-hairline bg-subtle px-3 py-1 text-xs font-medium text-txt-muted">
            <CalendarClock className="size-3.5" />
            Centro de recepcion
          </div>
          <h1 className="text-2xl font-semibold text-txt-body">
            Citas y check-in operativo
          </h1>
          <p className="max-w-2xl text-sm text-txt-muted">
            Gestiona check-in de pacientes y agenda de citas con contexto
            operativo en tiempo real.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Tab switcher */}
          <div className="flex items-center gap-1 rounded-xl border border-line-struct bg-subtle/20 p-1">
            <button
              type="button"
              onClick={() => setView("bandeja")}
              className={[
                "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                view === "bandeja"
                  ? "bg-paper text-txt-body shadow-sm"
                  : "text-txt-muted hover:text-txt-body",
              ].join(" ")}
            >
              <List className="size-3.5" /> Bandeja
            </button>
            <button
              type="button"
              onClick={() => setView("disponibilidad")}
              className={[
                "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                view === "disponibilidad"
                  ? "bg-paper text-txt-body shadow-sm"
                  : "text-txt-muted hover:text-txt-body",
              ].join(" ")}
            >
              <CalendarDays className="size-3.5" /> Disponibilidad
            </button>
            <button
              type="button"
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

          <TurnoIndicator />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-9"
            title="Configurar turnos y fichas"
            onClick={() => navigate("/recepcion/turnos")}
          >
            <Settings2 className="size-4" />
          </Button>
          {view === "bandeja" && !bandejaIsHistorical ? (
            <span className="rounded-full border border-line-hairline bg-subtle px-3 py-1 text-xs font-medium text-txt-muted">
              Sync: {queueQuery.connectionStatus ?? "idle"}
            </span>
          ) : null}
          <Button
            type="button"
            variant="outline"
            className="gap-2"
            onClick={() => navigate("/recepcion/checkin/qr")}
          >
            <QrCode className="size-4" />
            Check-in por QR
          </Button>
          {view === "bandeja" ? (
            <Button
              type="button"
              variant="ghost"
              className="gap-2"
              onClick={() => bandejaIsHistorical ? void historicalRefetch() : void queueQuery.refetch?.()}
            >
              <RefreshCcw className="size-4" />
              Actualizar
            </Button>
          ) : null}
        </div>
      </header>

      {/* ── Vista disponibilidad ────────────────────────────────────── */}
      {view === "disponibilidad" ? (
        <DisponibilidadView
          centroOptions={centroOptions}
          calCentroId={calCentroId}
          setCalCentroId={setCalCentroId}
          calMedicoId={calMedicoId}
          setCalMedicoId={setCalMedicoId}
          calWeekStart={calWeekStart}
          setCalWeekStart={setCalWeekStart}
          medicoSearch={medicoSearch}
          setMedicoSearch={setMedicoSearch}
          disponibilidadMedicos={disponibilidadMedicos}
          allMedicos={allMedicos}
          onOpenQuickCheckin={handleOpenQuickCheckin}
        />
      ) : null}

      {view === "bandeja" ? (
        <BandejaView
          canReadAgenda={canReadAgenda}
          canWriteRecepcion={canWriteRecepcion}
          bandejaPeriod={bandejaPeriod}
          setBandejaPeriod={setBandejaPeriod}
          bandejaPage={bandejaPage}
          setBandejaPage={setBandejaPage}
          bandejaCustomDesde={bandejaCustomDesde}
          setBandejaCustomDesde={setBandejaCustomDesde}
          bandejaCustomHasta={bandejaCustomHasta}
          setBandejaCustomHasta={setBandejaCustomHasta}
          bandejaIsHistorical={bandejaIsHistorical}
          bFechaDesde={bFechaDesde}
          bFechaHasta={bFechaHasta}
          historicalData={historicalData}
          historicalLoading={historicalLoading}
          historicalFetching={historicalFetching}
          historicalIsError={historicalIsError}
          queueIsLoading={queueQuery.isLoading}
          queueIsError={queueQuery.isError}
          visits={visits}
          openVisits={openVisits}
          waitingCount={waitingCount}
          activeDoctorCount={activeDoctorCount}
          openVisitsWithoutDoctorCount={openVisitsWithoutDoctorCount}
          withAppointmentCount={withAppointmentCount}
          walkInCount={walkInCount}
          serviceCounts={serviceCounts}
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          arrivalTypeFilter={arrivalTypeFilter}
          setArrivalTypeFilter={setArrivalTypeFilter}
          serviceFilter={serviceFilter}
          setServiceFilter={setServiceFilter}
          centroFilter={centroFilter}
          setCentroFilter={setCentroFilter}
          centroOptions={centroOptions}
          consultorioFilter={consultorioFilter}
          setConsultorioFilter={setConsultorioFilter}
          consultorioOptions={consultorioOptions}
          doctorFilter={doctorFilter}
          setDoctorFilter={setDoctorFilter}
          doctorOptions={doctorOptions}
          filteredVisits={filteredVisits}
          visitStatusActionPending={visitStatusAction.isPending}
          openStatusActionConfirmation={openStatusActionConfirmation}
          onMarkArrived={handleMarkArrived}
          setFichaVisit={setFichaVisit}
          setFichaOpen={setFichaOpen}
        />
      ) : null}

      {/* ── Historial NOM-024 ─────────────────────────────────────────── */}
      {view === "historial" ? (
        <HistorialView
          histNoExp={histNoExp}
          setHistNoExp={setHistNoExp}
          histFechaDesde={histFechaDesde}
          setHistFechaDesde={setHistFechaDesde}
          histFechaHasta={histFechaHasta}
          setHistFechaHasta={setHistFechaHasta}
          histDebouncedNoExp={histDebouncedNoExp}
          histEnabled={histEnabled}
          histPatient={histPatient}
          histSelectedPkNum={histSelectedPkNum}
          setHistSelectedPkNum={setHistSelectedPkNum}
          histTab={histTab}
          setHistTab={setHistTab}
          histCitas={histCitas}
          histCitasLoading={histCitasLoading}
          histVisits={histVisits}
          histVisitsLoading={histVisitsLoading}
        />
      ) : null}

      <AlertDialog
        open={pendingStatusAction !== null}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            setPendingStatusAction(null);
            setCancelMotivo("");
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar accion de recepcion</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingStatusAction && pendingActionCopy
                ? pendingActionCopy.getDescription(pendingStatusAction.folio)
                : "Confirma la accion seleccionada para continuar."}
            </AlertDialogDescription>
          </AlertDialogHeader>

          {pendingActionRequiresMotivo ? (
            <div className="space-y-1.5">
              <label
                htmlFor="motivo-cancelacion-visita"
                className="text-sm font-medium text-txt-body"
              >
                Motivo de la cancelacion <span className="text-status-critical">*</span>
              </label>
              <Textarea
                id="motivo-cancelacion-visita"
                rows={3}
                maxLength={255}
                value={cancelMotivo}
                onChange={(e) => setCancelMotivo(e.target.value)}
                disabled={visitStatusAction.isPending}
                placeholder="Ej. el paciente se retiro, se resolvio por otro medio..."
                aria-invalid={!cancelMotivoValido}
              />
              <p className="text-xs text-txt-muted">
                Obligatorio para cancelar una visita.
              </p>
            </div>
          ) : null}

          <AlertDialogFooter>
            <AlertDialogCancel>Volver</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              className="whitespace-nowrap"
              disabled={
                visitStatusAction.isPending ||
                (pendingActionRequiresMotivo && !cancelMotivoValido)
              }
              onClick={() => {
                void handleConfirmStatusAction();
              }}
            >
              {pendingActionCopy?.confirmLabel ?? "Confirmar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <RecepcionQuickCheckinDialog
        open={quickCheckinOpen}
        onOpenChange={(nextOpen) => {
          setQuickCheckinOpen(nextOpen);
          if (!nextOpen) setQuickCheckinDefaults(undefined);
        }}
        canWrite={canWriteRecepcion}
        initialValues={resolvedQuickCheckinDefaults}
        activeVisits={visits}
      />

      <FichaModal
        open={fichaOpen}
        onOpenChange={setFichaOpen}
        visit={fichaVisit}
      />
    </section>
  );
};

export default RecepcionAgendaPage;
