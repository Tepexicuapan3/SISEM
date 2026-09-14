import { useState } from "react";
import { Ambulance, Download, Search } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Badge } from "@shared/ui/badge";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import {
  DataTable,
  type DataTableColumn,
} from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useAmbulanceReport } from "@features/admin/modules/reportes/queries/useAmbulanceReport";
import { useExportAmbulanceReport } from "@features/admin/modules/reportes/mutations/useExportAmbulanceReport";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { AmbulanceReportItem } from "@api/types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const AUTH_BADGE_VARIANT: Record<string, "secondary" | "outline" | "critical"> = {
  pendiente: "outline",
  autorizada: "secondary",
  rechazada: "critical",
};

export function ReporteAmbulanciasPage() {
  const { hasCapability } = usePermissionDependencies();
  const canRead = hasCapability("clinico.reportes.ambulancias.read", {
    allOf: ["clinico:ambulancias:read"],
  });

  const today = todayIso();
  const [fechaInicio, setFechaInicio] = useState(today);
  const [fechaFin, setFechaFin] = useState(today);
  const [appliedFilters, setAppliedFilters] = useState({ fechaInicio: today, fechaFin: today });

  const { data, isLoading, isError, refetch } = useAmbulanceReport(appliedFilters, { enabled: canRead });
  const { exportReport, isExporting } = useExportAmbulanceReport();

  const handleBuscar = () => setAppliedFilters({ fechaInicio, fechaFin });

  const columns: DataTableColumn<AmbulanceReportItem>[] = [
    { key: "date", header: "Fecha de Registro", accessorKey: "date" },
    { key: "folio", header: "Folio", accessorKey: "folio" },
    { key: "noExp", header: "Expediente", accessorKey: "noExp" },
    { key: "requestingClinicName", header: "Clinica Solicitante", accessorKey: "requestingClinicName" },
    { key: "reasonName", header: "Motivo", accessorKey: "reasonName" },
    { key: "destinationName", header: "Destino", accessorKey: "destinationName" },
    { key: "transferDate", header: "Fecha de Traslado", accessorKey: "transferDate" },
    {
      key: "authorizationStatus",
      header: "Autorizacion",
      align: "center",
      render: (row) => (
        <Badge variant={AUTH_BADGE_VARIANT[row.authorizationStatus] ?? "outline"} className="text-xs capitalize">
          {row.authorizationStatus}
        </Badge>
      ),
    },
    { key: "serviceNumber", header: "No. Servicio", accessorKey: "serviceNumber" },
  ];

  if (!canRead) {
    return (
      <CatalogModuleLayout title="Informe de Ambulancias" description="Solicitudes de traslado en un rango de fechas" icon={<Ambulance className="size-5" />}>
        <AdminReadOnlyNotice message="No tienes permiso para ver este reporte." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout
      title="Informe de Ambulancias"
      description="Solicitudes de traslado registradas con fecha dentro del rango seleccionado."
      icon={<Ambulance className="size-5" />}
    >
      <TableHeaderBar
        search={
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-ambulancias-fecha-inicio">Desde</Label>
              <Input id="reporte-ambulancias-fecha-inicio" type="date" value={fechaInicio} onChange={(e) => setFechaInicio(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-ambulancias-fecha-fin">Hasta</Label>
              <Input id="reporte-ambulancias-fecha-fin" type="date" value={fechaFin} onChange={(e) => setFechaFin(e.target.value)} />
            </div>
            <Button variant="outline" onClick={handleBuscar}>
              <Search className="size-4" />
              Buscar
            </Button>
          </div>
        }
        actions={
          <Button variant="outline" disabled={isExporting} onClick={() => exportReport(appliedFilters)}>
            <Download className="size-4" />
            Exportar Excel
          </Button>
        }
      />

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        isLoading={isLoading}
        isError={isError}
        onRetry={() => refetch()}
        footerNote={data ? `${data.total} solicitud(es) encontradas` : undefined}
        minWidthClassName="min-w-[1100px]"
      />
    </CatalogModuleLayout>
  );
}

export default ReporteAmbulanciasPage;
