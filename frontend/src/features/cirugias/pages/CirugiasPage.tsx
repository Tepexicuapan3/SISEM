import { useState } from "react";
import { Scissors, Plus, XCircle } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import {
  DataTable, type DataTableColumn,
} from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useSurgeriesList } from "@features/cirugias/queries/useSurgeriesList";
import { ScheduleSurgeryDialog } from "@features/cirugias/components/ScheduleSurgeryDialog";
import { CancelSurgeryDialog } from "@features/cirugias/components/CancelSurgeryDialog";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { SurgeryItem } from "@api/types";

const STATUS_FILTER = { ALL: "all", ACTIVA: "activa", CANCELADA: "cancelada" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

export function CirugiasPage() {
  const { hasCapability } = usePermissionDependencies();
  const canRead = hasCapability("clinico.cirugias.read", { allOf: ["clinico:cirugias:read"] });
  const canWrite = hasCapability("clinico.cirugias.write", { allOf: ["clinico:cirugias:write"] });

  const [fechaInicio, setFechaInicio] = useState("");
  const [fechaFin, setFechaFin] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(STATUS_FILTER.ACTIVA);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [surgeryToCancel, setSurgeryToCancel] = useState<SurgeryItem | null>(null);

  const { data, isLoading, isError, refetch } = useSurgeriesList(
    {
      fechaInicio: fechaInicio || undefined,
      fechaFin: fechaFin || undefined,
      status: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter,
    },
    { enabled: canRead },
  );

  const columns: DataTableColumn<SurgeryItem>[] = [
    { key: "folio", header: "Folio", accessorKey: "folio" },
    { key: "scheduledDate", header: "Fecha", accessorKey: "scheduledDate" },
    { key: "scheduledTime", header: "Hora", accessorKey: "scheduledTime" },
    { key: "noExp", header: "Expediente", accessorKey: "noExp" },
    { key: "surgeonName", header: "Cirujano", accessorKey: "surgeonName" },
    { key: "surgeryTypeName", header: "Tipo", accessorKey: "surgeryTypeName" },
    { key: "classificationName", header: "Clasificacion", accessorKey: "classificationName" },
    {
      key: "status",
      header: "Estatus",
      align: "center",
      render: (row) => (
        <Badge variant={row.status === "activa" ? "secondary" : "outline"} className="text-xs">
          {row.status === "activa" ? "Activa" : "Cancelada"}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "center",
      render: (row) =>
        canWrite && row.status === "activa" ? (
          <Button
            variant="ghost"
            size="icon"
            title="Cancelar cirugia"
            onClick={(event) => {
              event.stopPropagation();
              setSurgeryToCancel(row);
              setCancelOpen(true);
            }}
          >
            <XCircle className="size-4 text-status-critical" />
          </Button>
        ) : null,
    },
  ];

  if (!canRead) {
    return (
      <CatalogModuleLayout title="Cirugias" description="Agenda quirurgica" icon={<Scissors className="size-5" />}>
        <AdminReadOnlyNotice message="No tienes permiso para ver la agenda quirurgica." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout title="Cirugias" description="Agenda quirurgica: programa, consulta y cancela cirugias." icon={<Scissors className="size-5" />}>
      <TableHeaderBar
        search={
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="cirugias-fecha-inicio">Desde</Label>
              <Input id="cirugias-fecha-inicio" type="date" value={fechaInicio} onChange={(e) => setFechaInicio(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="cirugias-fecha-fin">Hasta</Label>
              <Input id="cirugias-fecha-fin" type="date" value={fechaFin} onChange={(e) => setFechaFin(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Estatus</Label>
              <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
                <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={STATUS_FILTER.ALL}>Todas</SelectItem>
                  <SelectItem value={STATUS_FILTER.ACTIVA}>Activas</SelectItem>
                  <SelectItem value={STATUS_FILTER.CANCELADA}>Canceladas</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        }
        actions={
          canWrite ? (
            <Button onClick={() => setScheduleOpen(true)}>
              <Plus className="size-4" />
              Agendar cirugia
            </Button>
          ) : undefined
        }
      />

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        isLoading={isLoading}
        isError={isError}
        onRetry={() => refetch()}
        footerNote={data ? `${data.total} cirugia(s) encontradas` : undefined}
        getRowKey={(row) => row.id.toString()}
        minWidthClassName="min-w-[1100px]"
      />

      <ScheduleSurgeryDialog open={scheduleOpen} onOpenChange={setScheduleOpen} />
      <CancelSurgeryDialog
        open={cancelOpen}
        onOpenChange={(next) => {
          setCancelOpen(next);
          if (!next) setSurgeryToCancel(null);
        }}
        surgery={surgeryToCancel}
      />
    </CatalogModuleLayout>
  );
}

export default CirugiasPage;
