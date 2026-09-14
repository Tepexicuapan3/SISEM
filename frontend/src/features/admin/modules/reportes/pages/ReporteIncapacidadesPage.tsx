import { useState } from "react";
import { Download, FileHeart, Search } from "lucide-react";
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
import { useMedicalLeaveReport } from "@features/admin/modules/reportes/queries/useMedicalLeaveReport";
import { useExportMedicalLeaveReport } from "@features/admin/modules/reportes/mutations/useExportMedicalLeaveReport";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { MedicalLeaveReportItem } from "@api/types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ReporteIncapacidadesPage() {
  const { hasCapability } = usePermissionDependencies();
  const canRead = hasCapability("clinico.reportes.read", {
    allOf: ["clinico:reportes:read"],
  });

  const today = todayIso();
  const [fechaInicio, setFechaInicio] = useState(today);
  const [fechaFin, setFechaFin] = useState(today);
  const [appliedFilters, setAppliedFilters] = useState({
    fechaInicio: today,
    fechaFin: today,
  });

  const { data, isLoading, isError, refetch } = useMedicalLeaveReport(
    appliedFilters,
    { enabled: canRead },
  );
  const { exportReport, isExporting } = useExportMedicalLeaveReport();

  const handleBuscar = () => {
    setAppliedFilters({ fechaInicio, fechaFin });
  };

  const columns: DataTableColumn<MedicalLeaveReportItem>[] = [
    { key: "startDate", header: "Fecha Inicio", accessorKey: "startDate" },
    { key: "endDate", header: "Fecha Fin", accessorKey: "endDate" },
    { key: "days", header: "Días", accessorKey: "days", align: "center" },
    { key: "folio", header: "Folio", accessorKey: "folio" },
    { key: "noExp", header: "Expediente", accessorKey: "noExp" },
    { key: "patientName", header: "Paciente", accessorKey: "patientName" },
    { key: "doctorName", header: "Médico", accessorKey: "doctorName" },
    { key: "leaveTypeName", header: "Tipo de Licencia", accessorKey: "leaveTypeName" },
    {
      key: "isSubsequent",
      header: "Subsecuente",
      align: "center",
      render: (row) => (
        <Badge variant={row.isSubsequent ? "secondary" : "outline"} className="text-xs">
          {row.isSubsequent ? "Sí" : "No"}
        </Badge>
      ),
    },
  ];

  if (!canRead) {
    return (
      <CatalogModuleLayout
        title="Informe de Incapacidades"
        description="Licencias médicas emitidas en un rango de fechas"
        icon={<FileHeart className="size-5" />}
      >
        <AdminReadOnlyNotice message="No tienes permiso para ver este reporte." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout
      title="Informe de Incapacidades"
      description="Licencias médicas (incapacidades) con fecha de inicio en el rango seleccionado."
      icon={<FileHeart className="size-5" />}
    >
      <TableHeaderBar
        search={
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-incap-fecha-inicio">Desde</Label>
              <Input
                id="reporte-incap-fecha-inicio"
                type="date"
                value={fechaInicio}
                onChange={(event) => setFechaInicio(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-incap-fecha-fin">Hasta</Label>
              <Input
                id="reporte-incap-fecha-fin"
                type="date"
                value={fechaFin}
                onChange={(event) => setFechaFin(event.target.value)}
              />
            </div>
            <Button variant="outline" onClick={handleBuscar}>
              <Search className="size-4" />
              Buscar
            </Button>
          </div>
        }
        actions={
          <Button
            variant="outline"
            disabled={isExporting}
            onClick={() => exportReport(appliedFilters)}
          >
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
        footerNote={data ? `${data.total} incapacidad(es) encontradas` : undefined}
        minWidthClassName="min-w-[1100px]"
      />
    </CatalogModuleLayout>
  );
}
