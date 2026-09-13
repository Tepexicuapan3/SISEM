import { useState } from "react";
import { Download, FileText, Search } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import {
  DataTable,
  type DataTableColumn,
} from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useDailyConsultationReport } from "@features/admin/modules/reportes/queries/useDailyConsultationReport";
import { useExportDailyConsultationReport } from "@features/admin/modules/reportes/mutations/useExportDailyConsultationReport";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { DailyConsultationReportItem } from "@api/types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ReporteConsultasDiarioPage() {
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

  const { data, isLoading, isError, refetch } = useDailyConsultationReport(
    appliedFilters,
    { enabled: canRead },
  );
  const { exportReport, isExporting } = useExportDailyConsultationReport();

  const handleBuscar = () => {
    setAppliedFilters({ fechaInicio, fechaFin });
  };

  const columns: DataTableColumn<DailyConsultationReportItem>[] = [
    { key: "date", header: "Fecha", accessorKey: "date" },
    { key: "time", header: "Hora", accessorKey: "time" },
    { key: "folio", header: "Folio", accessorKey: "folio" },
    { key: "noExp", header: "Expediente", accessorKey: "noExp" },
    { key: "patientName", header: "Paciente", accessorKey: "patientName" },
    { key: "doctorName", header: "Médico", accessorKey: "doctorName" },
    {
      key: "diagnosis",
      header: "Diagnóstico",
      render: (row) =>
        row.cieCode
          ? `${row.primaryDiagnosis} (${row.cieCode})`
          : row.primaryDiagnosis,
    },
    { key: "consultorio", header: "Consultorio", accessorKey: "consultorio" },
  ];

  if (!canRead) {
    return (
      <CatalogModuleLayout
        title="Informe Diario de Consulta Médica"
        description="Consultas cerradas en un rango de fechas"
        icon={<FileText className="size-5" />}
      >
        <AdminReadOnlyNotice message="No tienes permiso para ver este reporte." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout
      title="Informe Diario de Consulta Médica"
      description="Consultas cerradas en un rango de fechas. Equivalente moderno del informe diario del sistema anterior."
      icon={<FileText className="size-5" />}
    >
      <TableHeaderBar
        search={
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-consultas-fecha-inicio">Desde</Label>
              <Input
                id="reporte-consultas-fecha-inicio"
                type="date"
                value={fechaInicio}
                onChange={(event) => setFechaInicio(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-consultas-fecha-fin">Hasta</Label>
              <Input
                id="reporte-consultas-fecha-fin"
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
        footerNote={data ? `${data.total} consulta(s) encontradas` : undefined}
        minWidthClassName="min-w-[1100px]"
      />
    </CatalogModuleLayout>
  );
}
