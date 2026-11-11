import { useState } from "react";
import { ChevronDown, FilterX, Printer } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { ARRIVAL_TYPE, type VisitQueueItem, type VisitsListResponse } from "@api/types";
import { canRunRecepcionStatusAction } from "@features/operativo/shared/domain/visit-flow.constants";
import {
  RECEPCION_SERVICE,
  RECEPCION_SERVICE_LIST,
  RECEPCION_SERVICE_PROFILES,
  resolveRecepcionService,
  type RecepcionService,
} from "@features/recepcion/shared/domain/recepcion.services";
import { RecepcionServiceBadge } from "@features/recepcion/shared/components/RecepcionServiceBadge";
import { RecepcionStatusBadge } from "@features/recepcion/shared/components/RecepcionStatusBadge";
import {
  ARRIVAL_TYPE_FILTER,
  BANDEJA_PERIOD_LABEL,
  RECEPCION_ACTION,
  RECEPCION_ACTION_COPY,
  SERVICE_FILTER,
  STATUS_FILTER,
  type ArrivalTypeFilter,
  type RecepcionAction,
  type ServiceFilter,
  type StatusFilter,
} from "../pages/RecepcionAgendaPage.helpers";

interface Props {
  canReadAgenda:                boolean;
  canWriteRecepcion:             boolean;

  bandejaPeriod:                 string;
  setBandejaPeriod:              (period: string) => void;
  bandejaPage:                   number;
  setBandejaPage:                (updater: number | ((page: number) => number)) => void;
  bandejaCustomDesde:            string;
  setBandejaCustomDesde:         (value: string) => void;
  bandejaCustomHasta:            string;
  setBandejaCustomHasta:         (value: string) => void;
  bandejaIsHistorical:           boolean;
  bFechaDesde:                   string;
  bFechaHasta:                   string;

  historicalData:                VisitsListResponse | undefined;
  historicalLoading:             boolean;
  historicalFetching:            boolean;
  historicalIsError:             boolean;
  queueIsLoading:                boolean;
  queueIsError:                  boolean;

  visits:                        VisitQueueItem[];
  openVisits:                    VisitQueueItem[];
  waitingCount:                  number;
  activeDoctorCount:             number;
  openVisitsWithoutDoctorCount:  number;
  withAppointmentCount:          number;
  walkInCount:                   number;
  serviceCounts:                 Record<RecepcionService, number>;

  searchTerm:                    string;
  setSearchTerm:                 (value: string) => void;
  statusFilter:                  StatusFilter;
  setStatusFilter:               (value: StatusFilter) => void;
  arrivalTypeFilter:              ArrivalTypeFilter;
  setArrivalTypeFilter:          (value: ArrivalTypeFilter) => void;
  serviceFilter:                 ServiceFilter;
  setServiceFilter:              (value: ServiceFilter) => void;

  centroFilter:                  number | "all";
  setCentroFilter:                (value: number | "all") => void;
  centroOptions:                 { id: number; nombre: string }[];
  consultorioFilter:              number | "all";
  setConsultorioFilter:           (value: number | "all") => void;
  consultorioOptions:            { id: number; nombre: string }[];
  doctorFilter:                  number | "all";
  setDoctorFilter:                (value: number | "all") => void;
  doctorOptions:                 { id: number; nombre: string }[];

  filteredVisits:                VisitQueueItem[];

  visitStatusActionPending:      boolean;
  openStatusActionConfirmation:  (visitId: number, folio: string, targetStatus: RecepcionAction) => void;
  onMarkArrived:                 (visitId: number, folio: string) => void;
  setFichaVisit:                 (visit: VisitQueueItem) => void;
  setFichaOpen:                  (open: boolean) => void;
}

export function BandejaView({
  canReadAgenda,
  canWriteRecepcion,
  bandejaPeriod,
  setBandejaPeriod,
  bandejaPage,
  setBandejaPage,
  bandejaCustomDesde,
  setBandejaCustomDesde,
  bandejaCustomHasta,
  setBandejaCustomHasta,
  bandejaIsHistorical,
  bFechaDesde,
  bFechaHasta,
  historicalData,
  historicalLoading,
  historicalFetching,
  historicalIsError,
  queueIsLoading,
  queueIsError,
  visits,
  openVisits,
  waitingCount,
  activeDoctorCount,
  openVisitsWithoutDoctorCount,
  withAppointmentCount,
  walkInCount,
  serviceCounts,
  searchTerm,
  setSearchTerm,
  statusFilter,
  setStatusFilter,
  arrivalTypeFilter,
  setArrivalTypeFilter,
  serviceFilter,
  setServiceFilter,
  centroFilter,
  setCentroFilter,
  centroOptions,
  consultorioFilter,
  setConsultorioFilter,
  consultorioOptions,
  doctorFilter,
  setDoctorFilter,
  doctorOptions,
  filteredVisits,
  visitStatusActionPending,
  openStatusActionConfirmation,
  onMarkArrived,
  setFichaVisit,
  setFichaOpen,
}: Props) {
  // Centro, consultorio y médico casi no se tocan en el día a día: van
  // plegados para que la búsqueda y el estado queden a la vista.
  const advancedActive =
    (centroFilter !== "all" ? 1 : 0) +
    (consultorioFilter !== "all" ? 1 : 0) +
    (doctorFilter !== "all" ? 1 : 0);
  const [showAdvanced, setShowAdvanced] = useState(advancedActive > 0);
  const hasActiveFilters =
    searchTerm.trim() !== "" ||
    statusFilter !== STATUS_FILTER.OPEN ||
    arrivalTypeFilter !== ARRIVAL_TYPE_FILTER.ALL ||
    serviceFilter !== SERVICE_FILTER.ALL ||
    advancedActive > 0;
  const clearFilters = () => {
    setSearchTerm("");
    setStatusFilter(STATUS_FILTER.OPEN);
    setArrivalTypeFilter(ARRIVAL_TYPE_FILTER.ALL);
    setServiceFilter(SERVICE_FILTER.ALL);
    setCentroFilter("all");
    setConsultorioFilter("all");
    setDoctorFilter("all");
  };
  const kpiClass = (active: boolean) =>
    [
      "rounded-xl border bg-paper p-4 text-left transition-colors",
      active
        ? "border-primary ring-1 ring-primary"
        : "border-line-struct hover:border-primary/50 hover:bg-subtle/30",
    ].join(" ");

  return (
    <>
      {/* ── Vista bandeja ────────────────────────────────────────────── */}
      {!canReadAgenda ? (
        <p className="text-sm text-txt-muted" role="status">
          No tienes permisos completos para ver la agenda de recepción. Pide
          a tu administrador que te los asigne.
        </p>
      ) : null}

      {/* ── Selector de período ───────────────────────────────────────── */}
      {canReadAgenda ? (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line-struct bg-paper px-4 py-3">
          {Object.keys(BANDEJA_PERIOD_LABEL).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => { setBandejaPeriod(p); setBandejaPage(1); }}
              className={[
                "rounded-lg px-3 py-1.5 text-xs font-medium border transition-colors",
                bandejaPeriod === p
                  ? "border-primary bg-primary text-white"
                  : "border-line-struct bg-subtle/30 text-txt-muted hover:text-txt-body hover:bg-subtle",
              ].join(" ")}
            >
              {BANDEJA_PERIOD_LABEL[p]}
            </button>
          ))}
          {bandejaPeriod === "custom" && (
            <div className="flex items-center gap-2 ml-2">
              <input
                type="date"
                value={bandejaCustomDesde}
                onChange={(e) => { setBandejaCustomDesde(e.target.value); setBandejaPage(1); }}
                className="h-8 rounded-md border border-line-struct bg-paper px-2 text-xs"
              />
              <span className="text-xs text-txt-muted">→</span>
              <input
                type="date"
                value={bandejaCustomHasta}
                min={bandejaCustomDesde}
                onChange={(e) => { setBandejaCustomHasta(e.target.value); setBandejaPage(1); }}
                className="h-8 rounded-md border border-line-struct bg-paper px-2 text-xs"
              />
            </div>
          )}
          {bandejaIsHistorical && (historicalFetching) && (
            <span className="ml-auto text-xs text-txt-muted">Cargando...</span>
          )}
        </div>
      ) : null}

      {canReadAgenda && (bandejaIsHistorical ? historicalLoading : queueIsLoading) ? (
        <p className="text-sm text-txt-muted">
          Cargando agenda de recepción...
        </p>
      ) : null}

      {canReadAgenda && (bandejaIsHistorical ? historicalIsError : queueIsError) ? (
        <Alert variant="warning">
          <AlertTitle>Error al cargar</AlertTitle>
          <AlertDescription>
            No se pudo cargar la agenda. Revisa tu conexión y presiona
            "Actualizar".
          </AlertDescription>
        </Alert>
      ) : null}

      {canReadAgenda &&
      !(bandejaIsHistorical ? historicalLoading : queueIsLoading) &&
      !(bandejaIsHistorical ? historicalIsError : queueIsError) &&
      visits.length > 0 ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <button
              type="button"
              title="Ver todas las visitas abiertas"
              className={kpiClass(statusFilter === STATUS_FILTER.OPEN)}
              onClick={() => setStatusFilter(STATUS_FILTER.OPEN)}
            >
              <p className="text-sm text-txt-muted">Visitas abiertas</p>
              <p className="text-2xl font-semibold text-txt-body">
                {openVisits.length}
              </p>
            </button>
            <button
              type="button"
              title="Ver solo los pacientes en espera"
              className={kpiClass(statusFilter === STATUS_FILTER.EN_ESPERA)}
              onClick={() => setStatusFilter(STATUS_FILTER.EN_ESPERA)}
            >
              <p className="text-sm text-txt-muted">En espera</p>
              <p className="text-2xl font-semibold text-txt-body">
                {waitingCount}
              </p>
            </button>
            <article className="rounded-xl border border-line-struct bg-paper p-4">
              <p className="text-sm text-txt-muted">Doctores con carga</p>
              <p className="text-2xl font-semibold text-txt-body">
                {activeDoctorCount}
              </p>
            </article>
            <article className="rounded-xl border border-line-struct bg-paper p-4">
              <p className="text-sm text-txt-muted">Sin médico asignado</p>
              <p className="text-2xl font-semibold text-txt-body">
                {openVisitsWithoutDoctorCount}
              </p>
            </article>
          </section>

          <section
            role="status"
            aria-label="Resumen de visitas abiertas"
            className="flex flex-wrap items-center gap-2 rounded-xl border border-line-struct bg-subtle p-3 text-xs"
          >
            {[
              { label: "Con cita", value: withAppointmentCount },
              { label: "Sin cita", value: walkInCount },
              { label: "Medicina general", value: serviceCounts[RECEPCION_SERVICE.MEDICINA_GENERAL] },
              { label: "Especialidad", value: serviceCounts[RECEPCION_SERVICE.ESPECIALIDAD] },
              { label: "Urgencias", value: serviceCounts[RECEPCION_SERVICE.URGENCIAS] },
            ].map((chip) => (
              <span
                key={chip.label}
                className="inline-flex items-center gap-1.5 rounded-full border border-line-hairline bg-paper px-3 py-1 text-txt-muted"
              >
                {chip.label}
                <span className="font-semibold text-txt-body">{chip.value}</span>
              </span>
            ))}
          </section>

          <section className="space-y-4 rounded-xl border border-line-struct bg-paper p-4">
            <div className="grid gap-3 md:grid-cols-4">
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="agenda-search">
                  Buscar por folio, paciente o cita
                </Label>
                <Input
                  id="agenda-search"
                  type="search"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Nombre, expediente o folio"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="agenda-status-filter">Estado</Label>
                <Select
                  value={statusFilter}
                  onValueChange={(value) => setStatusFilter(value as StatusFilter)}
                >
                  <SelectTrigger id="agenda-status-filter" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={STATUS_FILTER.OPEN}>Abiertas</SelectItem>
                    <SelectItem value={STATUS_FILTER.ALL}>Todas</SelectItem>
                    <SelectItem value={STATUS_FILTER.EN_ESPERA}>En espera</SelectItem>
                    <SelectItem value={STATUS_FILTER.EN_SOMATOMETRIA}>
                      En somatometría
                    </SelectItem>
                    <SelectItem value={STATUS_FILTER.LISTA_PARA_DOCTOR}>
                      Lista para doctor
                    </SelectItem>
                    <SelectItem value={STATUS_FILTER.EN_CONSULTA}>En consulta</SelectItem>
                    <SelectItem value={STATUS_FILTER.CERRADA}>Cerrada</SelectItem>
                    <SelectItem value={STATUS_FILTER.CANCELADA}>Cancelada</SelectItem>
                    <SelectItem value={STATUS_FILTER.NO_SHOW}>No asistió</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="agenda-arrival-filter">Tipo de llegada</Label>
                <Select
                  value={arrivalTypeFilter}
                  onValueChange={(value) => {
                    setArrivalTypeFilter(value as ArrivalTypeFilter);
                  }}
                >
                  <SelectTrigger id="agenda-arrival-filter" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ARRIVAL_TYPE_FILTER.ALL}>Todos</SelectItem>
                    <SelectItem value={ARRIVAL_TYPE_FILTER.APPOINTMENT}>
                      Con cita
                    </SelectItem>
                    <SelectItem value={ARRIVAL_TYPE_FILTER.WALK_IN}>
                      Sin cita
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="agenda-service-filter">Servicio</Label>
                <Select
                  value={serviceFilter}
                  onValueChange={(value) => setServiceFilter(value as ServiceFilter)}
                >
                  <SelectTrigger id="agenda-service-filter" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={SERVICE_FILTER.ALL}>Todos</SelectItem>
                    {RECEPCION_SERVICE_LIST.map((service) => (
                      <SelectItem key={service} value={service}>
                        {RECEPCION_SERVICE_PROFILES[service].label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="gap-1.5"
                aria-expanded={showAdvanced}
                onClick={() => setShowAdvanced((v) => !v)}
              >
                <ChevronDown
                  className={["size-4 transition-transform", showAdvanced ? "rotate-180" : ""].join(" ")}
                />
                Más filtros (centro, consultorio, médico)
                {advancedActive > 0 ? (
                  <span className="rounded-full bg-primary px-1.5 text-[10px] font-semibold text-white">
                    {advancedActive}
                  </span>
                ) : null}
              </Button>
              {hasActiveFilters ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="gap-1.5"
                  onClick={clearFilters}
                >
                  <FilterX className="size-4" />
                  Limpiar filtros
                </Button>
              ) : null}
              <span className="ml-auto text-xs text-txt-muted">
                {filteredVisits.length} de {visits.length} visita(s)
              </span>
            </div>

            {showAdvanced ? (
            <div className="grid gap-3 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="agenda-centro-filter">Centro de atención</Label>
                <Select
                  value={centroFilter === "all" ? "all" : String(centroFilter)}
                  onValueChange={(value) => {
                    setCentroFilter(value === "all" ? "all" : Number(value));
                    setConsultorioFilter("all");
                    setDoctorFilter("all");
                  }}
                >
                  <SelectTrigger id="agenda-centro-filter" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos los centros</SelectItem>
                    {centroOptions.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="agenda-cons-filter">Consultorio</Label>
                <Select
                  value={consultorioFilter === "all" ? "all" : String(consultorioFilter)}
                  onValueChange={(value) =>
                    setConsultorioFilter(value === "all" ? "all" : Number(value))
                  }
                >
                  <SelectTrigger id="agenda-cons-filter" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos los consultorios</SelectItem>
                    {consultorioOptions.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="agenda-doctor-filter">Médico</Label>
                <Select
                  value={doctorFilter === "all" ? "all" : String(doctorFilter)}
                  onValueChange={(value) =>
                    setDoctorFilter(value === "all" ? "all" : Number(value))
                  }
                >
                  <SelectTrigger id="agenda-doctor-filter" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos los médicos</SelectItem>
                    {doctorOptions.map((d) => (
                      <SelectItem key={d.id} value={String(d.id)}>{d.nombre}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            ) : null}

            {filteredVisits.length === 0 ? (
              <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-line-struct py-8 text-center">
                <p className="text-sm text-txt-muted">
                  Ningún paciente coincide con los filtros.
                </p>
                {hasActiveFilters ? (
                  <Button type="button" variant="outline" size="sm" onClick={clearFilters}>
                    Limpiar filtros
                  </Button>
                ) : null}
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {filteredVisits.map((visit) => {
                  const visitService = resolveRecepcionService(visit);
                  const canRunAction = canRunRecepcionStatusAction(
                    visit.status,
                  );
                  const canMarkNoShow =
                    visit.arrivalType === ARRIVAL_TYPE.APPOINTMENT;
                  const actionDisabled =
                    !canRunAction ||
                    !canWriteRecepcion ||
                    visitStatusActionPending;

                  return (
                    <article
                      key={visit.id}
                      className="flex flex-col gap-0 rounded-xl border border-line-struct bg-paper overflow-hidden"
                    >
                      {/* ── Banda superior: ficha + estado ─────────────── */}
                      <div className="flex items-center justify-between gap-2 border-b border-line-hairline bg-subtle/30 px-4 py-2">
                        <div className="flex items-center gap-2">
                          {visit.numFicha ? (
                            <span className="text-2xl font-black text-primary leading-none">
                              #{visit.numFicha}
                            </span>
                          ) : null}
                          {visit.llegadaPendiente ? (
                            // Ficha automática de la cita: el número sale con "Llegó".
                            <span
                              title="Ficha automática de la cita. Da Llegó cuando el paciente esté en la sala."
                              className="rounded-full bg-status-alert/10 px-2 py-0.5 text-[11px] font-semibold text-status-alert"
                            >
                              Por llegar
                            </span>
                          ) : null}
                          {visit.turnoNombre ? (
                            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary uppercase tracking-wide">
                              {visit.turnoNombre}
                            </span>
                          ) : null}
                          <span className="font-mono text-xs text-txt-muted">{visit.folio}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            title="Ver e imprimir ficha"
                            className="rounded-lg p-1.5 text-txt-muted hover:bg-subtle hover:text-primary transition-colors"
                            onClick={() => { setFichaVisit(visit); setFichaOpen(true); }}
                          >
                            <Printer className="size-4" />
                          </button>
                          <RecepcionStatusBadge status={visit.status} />
                        </div>
                      </div>

                      {/* ── Datos del paciente ──────────────────────────── */}
                      <div className="px-4 pt-3 pb-2">
                        {visit.nombrePaciente ? (
                          <p className="text-base font-bold text-txt-body truncate">
                            {visit.nombrePaciente}
                          </p>
                        ) : null}
                        <p className="mt-0.5 font-mono text-xs text-txt-muted">
                          Exp.&nbsp;
                          <span className="font-semibold text-txt-body">{visit.noExp || "—"}</span>
                          {visit.pkNum > 0 ? (
                            <span className="ml-1 font-sans font-normal"> · Familiar #{visit.pkNum}</span>
                          ) : (
                            <span className="ml-1 font-sans font-normal"> · Titular</span>
                          )}
                        </p>
                      </div>

                      {/* ── Detalles en grid de 2 columnas ─────────────── */}
                      <div className="grid grid-cols-2 gap-x-4 gap-y-2 px-4 py-3 border-t border-line-hairline">
                        <div>
                          <p className="text-[10px] font-medium uppercase tracking-wide text-txt-muted">Hora registro</p>
                          <p className="text-sm font-bold font-mono text-txt-muted">
                            {visit.fechaAlta
                              ? new Date(visit.fechaAlta).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", hour12: false })
                              : "—"}
                          </p>
                          {visit.fechaAlta && (
                            <p className="text-[10px] font-mono text-txt-muted/60">
                              {new Date(visit.fechaAlta).toLocaleDateString("es-MX", { day: "2-digit", month: "2-digit", year: "numeric" })}
                            </p>
                          )}
                        </div>

                        {visit.horaConsulta ? (
                          <div>
                            <p className="text-[10px] font-medium uppercase tracking-wide text-txt-muted">Hora cita</p>
                            <p className="text-sm font-bold font-mono text-primary">{visit.horaConsulta}</p>
                            {(visit.fechaConsulta ?? visit.fechaCita ?? visit.fechaAlta) && (
                              <p className="text-[10px] font-mono text-primary/60">
                                {(() => {
                                  const raw = visit.fechaConsulta ?? visit.fechaCita ?? visit.fechaAlta!;
                                  const d   = raw.includes("T") ? new Date(raw) : new Date(raw + "T00:00:00");
                                  return d.toLocaleDateString("es-MX", { day: "2-digit", month: "2-digit", year: "numeric" });
                                })()}
                              </p>
                            )}
                          </div>
                        ) : null}

                        <div>
                          <p className="text-[10px] font-medium uppercase tracking-wide text-txt-muted">Servicio</p>
                          <div className="mt-0.5"><RecepcionServiceBadge service={visitService} /></div>
                        </div>

                        {visit.doctorNombre ? (
                          <div className="col-span-2">
                            <p className="text-[10px] font-medium uppercase tracking-wide text-txt-muted">Médico</p>
                            <p className="text-xs font-semibold text-txt-body truncate">{visit.doctorNombre}</p>
                          </div>
                        ) : null}

                        {visit.consultorioNombre ? (
                          <div>
                            <p className="text-[10px] font-medium uppercase tracking-wide text-txt-muted">Consultorio</p>
                            <p className="text-xs font-medium text-txt-body">{visit.consultorioNombre}</p>
                          </div>
                        ) : null}

                        {visit.centroNombre ? (
                          <div>
                            <p className="text-[10px] font-medium uppercase tracking-wide text-txt-muted">Centro</p>
                            <p className="text-xs font-medium text-txt-body truncate">{visit.centroNombre}</p>
                          </div>
                        ) : null}

                        <div>
                          <p className="text-[10px] font-medium uppercase tracking-wide text-txt-muted">Tipo de cita</p>
                          <p className="text-xs font-medium text-txt-body">{visit.tipoCitaNombre ?? "—"}</p>
                        </div>

                        {visit.notes ? (
                          <div className="col-span-2">
                            <p className="text-[10px] font-medium uppercase tracking-wide text-txt-muted">Motivo</p>
                            <p className="text-xs text-txt-muted truncate">{visit.notes}</p>
                          </div>
                        ) : null}
                      </div>

                      <footer className="border-t border-line-hairline px-4 py-2">
                        <div className="flex flex-wrap items-center justify-end gap-1.5">
                          <Button
                            type="button"
                            size="sm"
                            disabled={actionDisabled}
                            onClick={() => {
                              // Sin dialogo de confirmacion a proposito:
                              // "Llego" es una accion frecuente y reversible
                              // (a diferencia de cancelar/no-show), agregar
                              // una confirmacion ahi solo sumaba un clic
                              // extra sin beneficio real para recepcion.
                              onMarkArrived(visit.id, visit.folio);
                            }}
                          >
                            {
                              RECEPCION_ACTION_COPY[
                                RECEPCION_ACTION.EN_SOMATOMETRIA
                              ].label
                            }
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={actionDisabled}
                            onClick={() => {
                              openStatusActionConfirmation(
                                visit.id,
                                visit.folio,
                                RECEPCION_ACTION.CANCELADA,
                              );
                            }}
                          >
                            {
                              RECEPCION_ACTION_COPY[RECEPCION_ACTION.CANCELADA]
                                .label
                            }
                          </Button>
                          {canMarkNoShow ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={actionDisabled}
                              onClick={() => {
                                openStatusActionConfirmation(
                                  visit.id,
                                  visit.folio,
                                  RECEPCION_ACTION.NO_SHOW,
                                );
                              }}
                            >
                              {
                                RECEPCION_ACTION_COPY[RECEPCION_ACTION.NO_SHOW]
                                  .label
                              }
                            </Button>
                          ) : null}
                        </div>
                      </footer>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          {/* ── Paginación histórica ─────────────────────────────────── */}
          {bandejaIsHistorical && historicalData && historicalData.totalPages > 1 ? (
            <div className="flex items-center justify-between rounded-xl border border-line-struct bg-paper px-4 py-2">
              <p className="text-xs text-txt-muted">
                {historicalData.total} ficha(s) · página {bandejaPage} de {historicalData.totalPages}
              </p>
              <div className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={bandejaPage <= 1}
                  onClick={() => setBandejaPage((p) => p - 1)}
                >
                  Anterior
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={bandejaPage >= historicalData.totalPages}
                  onClick={() => setBandejaPage((p) => p + 1)}
                >
                  Siguiente
                </Button>
              </div>
            </div>
          ) : null}
        </>
      ) : null}

      {canReadAgenda &&
      !(bandejaIsHistorical ? historicalLoading : queueIsLoading) &&
      !(bandejaIsHistorical ? historicalIsError : queueIsError) &&
      visits.length === 0 ? (
        <p className="text-sm text-txt-muted">
          {bandejaIsHistorical
            ? `Sin fichas para el período seleccionado (${bFechaDesde} → ${bFechaHasta}).`
            : 'Todavía no hay pacientes registrados hoy. Usa "Check-in por QR" cuando llegue el primero.'}
        </p>
      ) : null}
    </>
  );
}
