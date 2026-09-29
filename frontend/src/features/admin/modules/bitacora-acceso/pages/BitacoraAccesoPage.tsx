import { useState } from "react";
import { ScrollText } from "lucide-react";
import { useDebounce } from "@shared/hooks/useDebounce";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { AdminPageIntro } from "@features/admin/shared/components/AdminPageIntro";
import { useAccessLog } from "@features/admin/modules/bitacora-acceso/queries/useAccessLog";
import {
  ACCESS_LOG_ACTION_LABELS,
  ACCESS_LOG_EVENT_TYPE_LABELS,
  ACCESS_LOG_SECTION_LABELS,
  formatAccessLogDate,
} from "@features/admin/modules/bitacora-acceso/domain/access-log.labels";
import type { AccessLogAction, AccessLogEventType, AccessLogItem, AccessLogSection } from "@api/types";

const ALL = "all";

const columns: DataTableColumn<AccessLogItem>[] = [
  {
    key: "occurredAt",
    header: "Fecha y hora",
    render: (row) => <span className="whitespace-nowrap">{formatAccessLogDate(row.occurredAt)}</span>,
  },
  {
    key: "actor",
    header: "Usuario",
    render: (row) => (
      <div className="flex flex-col">
        <span>{row.actorName ?? "—"}</span>
        <span className="text-xs text-txt-muted">{row.actorUsername ?? "Sin usuario"}</span>
      </div>
    ),
  },
  {
    key: "patient",
    header: "Expediente",
    render: (row) => (row.noExp ? `${row.noExp} / ${row.pkNum ?? 0}` : "—"),
  },
  {
    key: "action",
    header: "Acción",
    render: (row) => ACCESS_LOG_ACTION_LABELS[row.action] ?? row.action,
  },
  {
    key: "eventType",
    header: "Evento",
    render: (row) => (
      <Badge
        variant={row.eventType === "diagnostico_restringido" ? "critical" : "outline"}
        className="text-xs"
      >
        {ACCESS_LOG_EVENT_TYPE_LABELS[row.eventType] ?? row.eventType}
        {row.redactedCount ? ` (${row.redactedCount})` : ""}
      </Badge>
    ),
  },
  {
    key: "section",
    header: "Sección",
    render: (row) => (row.section ? ACCESS_LOG_SECTION_LABELS[row.section] ?? row.section : "—"),
  },
  { key: "ipAddress", header: "IP", render: (row) => row.ipAddress ?? "—" },
];

export function BitacoraAccesoPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [noExp, setNoExp] = useState("");
  const [usuario, setUsuario] = useState("");
  const [tipo, setTipo] = useState<AccessLogEventType | typeof ALL>(ALL);
  const [accion, setAccion] = useState<AccessLogAction | typeof ALL>(ALL);
  const [seccion, setSeccion] = useState<AccessLogSection | typeof ALL>(ALL);
  const [fechaInicio, setFechaInicio] = useState("");
  const [fechaFin, setFechaFin] = useState("");

  const debouncedNoExp = useDebounce(noExp.trim(), 400);
  const debouncedUsuario = useDebounce(usuario.trim(), 400);

  const { data, isLoading, isFetching, error, refetch } = useAccessLog({
    page,
    pageSize,
    noExp: debouncedNoExp || undefined,
    usuario: debouncedUsuario || undefined,
    tipo: tipo === ALL ? undefined : tipo,
    accion: accion === ALL ? undefined : accion,
    seccion: seccion === ALL ? undefined : seccion,
    fechaInicio: fechaInicio || undefined,
    fechaFin: fechaFin || undefined,
  });

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, data?.totalPages ?? 1);
  const hasFilters =
    Boolean(debouncedNoExp || debouncedUsuario || fechaInicio || fechaFin) ||
    tipo !== ALL ||
    accion !== ALL ||
    seccion !== ALL;

  const withPageReset = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setPage(1);
  };

  const handleClearFilters = () => {
    setNoExp("");
    setUsuario("");
    setTipo(ALL);
    setAccion(ALL);
    setSeccion(ALL);
    setFechaInicio("");
    setFechaFin("");
    setPage(1);
  };

  return (
    <div className="mx-auto w-full space-y-6 px-4 pb-2 sm:px-6 lg:max-w-[1360px] lg:px-8 xl:px-10">
      <AdminPageIntro
        title="Bitácora de acceso"
        description="Quién vio, modificó o exportó información del expediente clínico, y qué diagnósticos sensibles se mostraron restringidos (NOM-024)."
        icon={<ScrollText className="size-12" />}
      />

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="bitacora-no-exp">Expediente</Label>
          <Input
            id="bitacora-no-exp"
            className="w-36"
            value={noExp}
            onChange={(e) => withPageReset(setNoExp)(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="bitacora-usuario">Usuario</Label>
          <Input
            id="bitacora-usuario"
            className="w-44"
            value={usuario}
            onChange={(e) => withPageReset(setUsuario)(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label>Evento</Label>
          <Select value={tipo} onValueChange={(v) => withPageReset(setTipo)(v as AccessLogEventType | typeof ALL)}>
            <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Todos</SelectItem>
              {Object.entries(ACCESS_LOG_EVENT_TYPE_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label>Acción</Label>
          <Select value={accion} onValueChange={(v) => withPageReset(setAccion)(v as AccessLogAction | typeof ALL)}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Todas</SelectItem>
              {Object.entries(ACCESS_LOG_ACTION_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label>Sección</Label>
          <Select value={seccion} onValueChange={(v) => withPageReset(setSeccion)(v as AccessLogSection | typeof ALL)}>
            <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Todas</SelectItem>
              {Object.entries(ACCESS_LOG_SECTION_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="bitacora-fecha-inicio">Desde</Label>
          <Input
            id="bitacora-fecha-inicio"
            type="date"
            value={fechaInicio}
            onChange={(e) => withPageReset(setFechaInicio)(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="bitacora-fecha-fin">Hasta</Label>
          <Input
            id="bitacora-fecha-fin"
            type="date"
            value={fechaFin}
            onChange={(e) => withPageReset(setFechaFin)(e.target.value)}
          />
        </div>
        <Button variant="outline" onClick={handleClearFilters} disabled={!hasFilters}>
          Limpiar filtros
        </Button>
      </div>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        isLoading={isLoading}
        isError={Boolean(error)}
        errorTitle="No se pudo cargar la bitácora"
        errorDescription="Ocurrió un error al obtener los registros. Intenta nuevamente."
        hasFilters={hasFilters}
        onRetry={() => void refetch()}
        onClearFilters={handleClearFilters}
        pagination={{
          page,
          pageSize,
          total,
          totalPages,
          onPageChange: setPage,
          onPageSizeChange: withPageReset(setPageSize),
        }}
        getRowKey={(row) => row.id.toString()}
        emptyTitle="Sin registros"
        emptyDescription="Cuando el personal consulte expedientes, los accesos se listarán aquí."
        footerNote={isFetching ? "Actualizando…" : `${total} registro(s)`}
        minWidthClassName="min-w-[900px]"
      />
    </div>
  );
}

export default BitacoraAccesoPage;
