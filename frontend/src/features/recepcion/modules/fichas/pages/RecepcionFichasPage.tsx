import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Archive, Printer, RefreshCcw, Search } from "lucide-react";
import { useDebounce } from "@shared/hooks/useDebounce";
import { DataTable } from "@features/admin/shared/components/DataTable";
import type { DataTableColumn } from "@features/admin/shared/components/DataTable";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { FichaModal } from "@features/recepcion/shared/components/FichaModal";
import { RecepcionStatusBadge } from "@features/recepcion/shared/components/RecepcionStatusBadge";
import { visitsAPI } from "@api/resources/visits.api";
import { SinCentroAviso } from "@/domains/auth-access/contracts/navigation-auth";
import {
  VISIT_STATUS,
  type VisitQueueItem,
  type VisitStatus,
} from "@api/types";
import {
  RECEPCION_SERVICE,
  RECEPCION_SERVICE_PROFILES,
} from "@features/recepcion/shared/domain/recepcion.services";

// ─── Período ─────────────────────────────────────────────────────────────────

const PERIOD = {
  TODAY:  "today",
  WEEK:   "week",
  MONTH:  "month",
  YEAR:   "year",
  CUSTOM: "custom",
} as const;
type Period = (typeof PERIOD)[keyof typeof PERIOD];

const PERIOD_LABEL: Record<Period, string> = {
  today:  "Hoy",
  week:   "Esta semana",
  month:  "Este mes",
  year:   "Este año",
  custom: "Rango personalizado",
};

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function periodRange(period: Period, customDesde: string, customHasta: string) {
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().slice(0, 10);

  switch (period) {
    case PERIOD.TODAY:
      return { fechaDesde: todayStr(), fechaHasta: todayStr() };
    case PERIOD.WEEK: {
      const d = new Date(today);
      const day = d.getDay();
      d.setDate(d.getDate() - (day === 0 ? 6 : day - 1)); // lunes
      return { fechaDesde: fmt(d), fechaHasta: todayStr() };
    }
    case PERIOD.MONTH:
      return {
        fechaDesde: fmt(new Date(today.getFullYear(), today.getMonth(), 1)),
        fechaHasta: todayStr(),
      };
    case PERIOD.YEAR:
      return { fechaDesde: `${today.getFullYear()}-01-01`, fechaHasta: todayStr() };
    case PERIOD.CUSTOM:
      return { fechaDesde: customDesde, fechaHasta: customHasta };
  }
}

// ─── Constantes de UI ─────────────────────────────────────────────────────────

const STATUS_FILTER_OPTIONS: { value: VisitStatus | "all"; label: string }[] = [
  { value: "all",                      label: "Todos los estados" },
  { value: VISIT_STATUS.EN_ESPERA,         label: "En espera" },
  { value: VISIT_STATUS.EN_SOMATOMETRIA,   label: "En somatometría" },
  { value: VISIT_STATUS.LISTA_PARA_DOCTOR, label: "Lista para doctor" },
  { value: VISIT_STATUS.EN_CONSULTA,       label: "En consulta" },
  { value: VISIT_STATUS.CERRADA,           label: "Cerrada" },
  { value: VISIT_STATUS.CANCELADA,         label: "Cancelada" },
  { value: VISIT_STATUS.NO_SHOW,           label: "No show" },
];

const SERVICE_FILTER_OPTIONS = [
  { value: "all",                               label: "Todos los servicios" },
  { value: RECEPCION_SERVICE.MEDICINA_GENERAL,  label: RECEPCION_SERVICE_PROFILES.medicina_general.label },
  { value: RECEPCION_SERVICE.ESPECIALIDAD,      label: RECEPCION_SERVICE_PROFILES.especialidad.label },
  { value: RECEPCION_SERVICE.URGENCIAS,         label: RECEPCION_SERVICE_PROFILES.urgencias.label },
];

function formatFechaHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-MX", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
    timeZone: "America/Mexico_City",
  });
}

const esExpediente = (v: string) => /^\d+$/.test(v.trim());

// ─── Página ───────────────────────────────────────────────────────────────────

export function RecepcionFichasPage() {
  const [period, setPeriod]         = useState<Period>(PERIOD.TODAY);
  const [customDesde, setCustomDesde] = useState("");
  const [customHasta, setCustomHasta] = useState("");
  const [search, setSearch]         = useState("");
  const [statusFilter, setStatusFilter] = useState<VisitStatus | "all">("all");
  const [serviceFilter, setServiceFilter] = useState<string>("all");
  const [page, setPage]             = useState(1);
  const [pageSize, setPageSize]     = useState(25);
  const [fichaOpen, setFichaOpen]   = useState(false);
  const [fichaVisit, setFichaVisit] = useState<VisitQueueItem | null>(null);

  const debouncedSearch = useDebounce(search, 400);
  const { fechaDesde, fechaHasta } = periodRange(period, customDesde, customHasta);

  const canQuery =
    period !== PERIOD.CUSTOM ||
    (customDesde.length === 10 && customHasta.length === 10);

  const queryParams = {
    page,
    pageSize,
    fechaDesde:  canQuery && fechaDesde ? fechaDesde : undefined,
    fechaHasta:  canQuery && fechaHasta ? fechaHasta : undefined,
    status:      statusFilter !== "all" ? (statusFilter as VisitStatus) : undefined,
    serviceType: serviceFilter !== "all" ? (serviceFilter as "medicina_general" | "especialidad" | "urgencias") : undefined,
    ...(debouncedSearch.trim()
      ? esExpediente(debouncedSearch)
        ? { noExp: debouncedSearch.trim() }
        : { folio: debouncedSearch.trim() }
      : {}),
  };

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["recepcion-fichas-archive", queryParams],
    queryFn:  () => visitsAPI.getAll(queryParams),
    enabled:  canQuery,
    staleTime: 30_000,
  });

  const handleRowClick = (visit: VisitQueueItem) => {
    setFichaVisit(visit);
    setFichaOpen(true);
  };

  const handlePeriodChange = (p: Period) => {
    setPeriod(p);
    setPage(1);
  };

  const columns: DataTableColumn<VisitQueueItem>[] = [
    {
      key: "numFicha",
      header: "#Ficha",
      className: "w-16",
      render: (row) =>
        row.numFicha ? (
          <span className="text-xl font-black text-primary leading-none">
            {row.numFicha}
          </span>
        ) : (
          <span className="text-txt-muted text-xs">—</span>
        ),
    },
    {
      key: "folio",
      header: "Folio",
      className: "w-36",
      render: (row) => (
        <span className="font-mono text-xs text-txt-muted">{row.folio}</span>
      ),
    },
    {
      key: "nombrePaciente",
      header: "Paciente",
      render: (row) => (
        <div>
          <p className="font-semibold text-sm text-txt-body truncate max-w-[180px]">
            {row.nombrePaciente || "—"}
          </p>
          <p className="text-[10px] font-mono text-txt-muted">
            Exp.&nbsp;{row.noExp || "—"}
            {row.pkNum > 0 ? ` · Fam. #${row.pkNum}` : " · Titular"}
          </p>
        </div>
      ),
    },
    {
      key: "serviceType",
      header: "Servicio",
      className: "w-32",
      render: (row) => {
        const svc = RECEPCION_SERVICE_PROFILES[row.serviceType as keyof typeof RECEPCION_SERVICE_PROFILES];
        return svc ? (
          <Badge variant="secondary" className="text-xs whitespace-nowrap">
            {svc.label}
          </Badge>
        ) : null;
      },
    },
    {
      key: "status",
      header: "Estado",
      className: "w-36",
      render: (row) => <RecepcionStatusBadge status={row.status} />,
    },
    {
      key: "doctorNombre",
      header: "Médico",
      className: "w-40",
      render: (row) => (
        <span className="text-xs text-txt-body truncate block max-w-[150px]">
          {row.doctorNombre || <span className="text-txt-muted">Sin asignar</span>}
        </span>
      ),
    },
    {
      key: "fechaAlta",
      header: "Fecha registro",
      className: "w-36",
      render: (row) => (
        <span className="font-mono text-xs text-txt-muted whitespace-nowrap">
          {formatFechaHora(row.fechaAlta)}
        </span>
      ),
    },
    {
      key: "actions" as keyof VisitQueueItem,
      header: "",
      className: "w-10",
      render: (row) => (
        <div onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
          <button
            type="button"
            title="Ver ficha"
            className="rounded-lg p-1.5 text-txt-muted hover:bg-subtle hover:text-primary transition-colors"
            onClick={() => handleRowClick(row)}
          >
            <Printer className="size-4" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <section className="space-y-5 p-6">
      <SinCentroAviso />
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="flex flex-col gap-3 rounded-xl border border-line-struct bg-paper p-5 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1.5">
          <div className="inline-flex items-center gap-2 rounded-full border border-line-hairline bg-subtle px-3 py-1 text-xs font-medium text-txt-muted">
            <Archive className="size-3.5" />
            Archivo histórico
          </div>
          <h1 className="text-2xl font-semibold text-txt-body">Fichas de consulta</h1>
          <p className="max-w-xl text-sm text-txt-muted">
            Consultá y descargá fichas por período. La paginación es server-side — filtrá primero para acotar.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="gap-2 self-start"
          disabled={isFetching}
          onClick={() => void refetch()}
        >
          <RefreshCcw className={`size-4 ${isFetching ? "animate-spin" : ""}`} />
          Actualizar
        </Button>
      </header>

      {/* ── Selector de período ─────────────────────────────────────────── */}
      <div className="rounded-xl border border-line-struct bg-paper p-4 space-y-3">
        <div className="flex flex-wrap gap-2">
          {(Object.keys(PERIOD) as Array<keyof typeof PERIOD>).map((key) => {
            const val = PERIOD[key];
            return (
              <button
                key={val}
                type="button"
                onClick={() => handlePeriodChange(val)}
                className={[
                  "rounded-lg px-4 py-2 text-sm font-medium border transition-colors",
                  period === val
                    ? "border-primary bg-primary text-white"
                    : "border-line-struct bg-subtle/30 text-txt-muted hover:text-txt-body hover:bg-subtle",
                ].join(" ")}
              >
                {PERIOD_LABEL[val]}
              </button>
            );
          })}
        </div>

        {period === PERIOD.CUSTOM && (
          <div className="flex flex-wrap items-end gap-3 pt-1">
            <div className="space-y-1">
              <p className="text-xs font-medium text-txt-muted">Desde</p>
              <input
                type="date"
                value={customDesde}
                onChange={(e) => { setCustomDesde(e.target.value); setPage(1); }}
                className="h-9 rounded-md border border-line-struct bg-paper px-3 text-sm"
              />
            </div>
            <div className="space-y-1">
              <p className="text-xs font-medium text-txt-muted">Hasta</p>
              <input
                type="date"
                value={customHasta}
                min={customDesde}
                onChange={(e) => { setCustomHasta(e.target.value); setPage(1); }}
                className="h-9 rounded-md border border-line-struct bg-paper px-3 text-sm"
              />
            </div>
            {canQuery && fechaDesde && fechaHasta && (
              <p className="text-xs text-txt-muted self-center">
                {fechaDesde} → {fechaHasta}
              </p>
            )}
          </div>
        )}
      </div>

      {/* ── Filtros de búsqueda ─────────────────────────────────────────── */}
      <div className="rounded-xl border border-line-struct bg-paper p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px] space-y-1">
            <p className="text-xs font-medium text-txt-muted">Buscar</p>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-txt-muted pointer-events-none" />
              <Input
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                placeholder="Folio (VIS-...) o número de expediente"
                className="pl-9 h-9"
              />
            </div>
          </div>

          <div className="space-y-1 w-44">
            <p className="text-xs font-medium text-txt-muted">Estado</p>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value as VisitStatus | "all"); setPage(1); }}
              className="h-9 w-full rounded-md border border-line-struct bg-paper px-3 text-sm"
            >
              {STATUS_FILTER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1 w-44">
            <p className="text-xs font-medium text-txt-muted">Servicio</p>
            <select
              value={serviceFilter}
              onChange={(e) => { setServiceFilter(e.target.value); setPage(1); }}
              className="h-9 w-full rounded-md border border-line-struct bg-paper px-3 text-sm"
            >
              {SERVICE_FILTER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {(search || statusFilter !== "all" || serviceFilter !== "all") && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => { setSearch(""); setStatusFilter("all"); setServiceFilter("all"); setPage(1); }}
            >
              Limpiar filtros
            </Button>
          )}
        </div>
      </div>

      {/* ── Tabla ──────────────────────────────────────────────────────── */}
      {!canQuery ? (
        <div className="rounded-xl border border-line-struct bg-paper py-12 text-center">
          <p className="text-sm text-txt-muted">Seleccioná una fecha de inicio y fin para el rango personalizado.</p>
        </div>
      ) : (
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          isLoading={isLoading}
          isError={Boolean(error)}
          errorTitle="No se pudo cargar el archivo de fichas"
          errorDescription="Verificá la conexión e intentá nuevamente."
          hasFilters={Boolean(search || statusFilter !== "all" || serviceFilter !== "all")}
          onRowClick={handleRowClick}
          onRetry={() => void refetch()}
          onClearFilters={() => { setSearch(""); setStatusFilter("all"); setServiceFilter("all"); setPage(1); }}
          pagination={{
            page,
            pageSize,
            total:      data?.total ?? 0,
            totalPages: data?.totalPages ?? 1,
            onPageChange: (p) => setPage(p),
            onPageSizeChange: (s) => { setPageSize(s); setPage(1); },
          }}
          getRowKey={(row) => String(row.id)}
          emptyTitle="Sin fichas para este período"
          emptyDescription="Ajustá los filtros o cambiá el rango de fechas."
        />
      )}

      <FichaModal
        open={fichaOpen}
        onOpenChange={setFichaOpen}
        visit={fichaVisit}
      />
    </section>
  );
}

export default RecepcionFichasPage;
