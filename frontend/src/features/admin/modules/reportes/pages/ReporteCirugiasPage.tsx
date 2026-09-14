import { useState } from "react";
import { Download, Scissors, Search } from "lucide-react";
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
import { useSurgeryReport } from "@features/admin/modules/reportes/queries/useSurgeryReport";
import { useExportSurgeryReport } from "@features/admin/modules/reportes/mutations/useExportSurgeryReport";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { SurgeryReportItem } from "@api/types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ReporteCirugiasPage() {
  const { hasCapability } = usePermissionDependencies();
  const canRead = hasCapability("clinico.reportes.cirugias.read", {
    allOf: ["clinico:cirugias:read"],
  });

  const today = todayIso();
  const [fechaInicio, setFechaInicio] = useState(today);
  const [fechaFin, setFechaFin] = useState(today);
  const [appliedFilters, setAppliedFilters] = useState({ fechaInicio: today, fechaFin: today });

  const { data, isLoading, isError, refetch } = useSurgeryReport(appliedFilters, { enabled: canRead });
  const { exportReport, isExporting } = useExportSurgeryReport();

  const handleBuscar = () => setAppliedFilters({ fechaInicio, fechaFin });

  const columns: DataTableColumn<SurgeryReportItem>[] = [
    { key: "date", header: "Fecha", accessorKey: "date" },
    { key: "time", header: "Hora", accessorKey: "time" },
    { key: "folio", header: "Folio", accessorKey: "folio" },
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
      key: "performedStatus",
      header: "Realizacion",
      align: "center",
      accessorKey: "performedStatus",
    },
  ];

  if (!canRead) {
    return (
      <CatalogModuleLayout title="Informe de Cirugias" description="Cirugias agendadas en un rango de fechas" icon={<Scissors className="size-5" />}>
        <AdminReadOnlyNotice message="No tienes permiso para ver este reporte." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout
      title="Informe de Cirugias"
      description="Cirugias agendadas con fecha dentro del rango seleccionado."
      icon={<Scissors className="size-5" />}
    >
      <TableHeaderBar
        search={
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-cirugias-fecha-inicio">Desde</Label>
              <Input id="reporte-cirugias-fecha-inicio" type="date" value={fechaInicio} onChange={(e) => setFechaInicio(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-cirugias-fecha-fin">Hasta</Label>
              <Input id="reporte-cirugias-fecha-fin" type="date" value={fechaFin} onChange={(e) => setFechaFin(e.target.value)} />
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
        footerNote={data ? `${data.total} cirugia(s) encontradas` : undefined}
        minWidthClassName="min-w-[1100px]"
      />
    </CatalogModuleLayout>
  );
}

export default ReporteCirugiasPage;
