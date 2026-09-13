import { useState } from "react";
import { Download, Search, Ticket } from "lucide-react";
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
import { useReferralReport } from "@features/admin/modules/reportes/queries/useReferralReport";
import { useExportReferralReport } from "@features/admin/modules/reportes/mutations/useExportReferralReport";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { ReferralReportItem } from "@api/types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const REFERRAL_TYPE_LABELS: Record<string, string> = {
  laboratorio: "Laboratorio",
  gabinete: "Gabinete",
  especialidad: "Especialidad",
  hospitalizacion: "Hospitalización",
  tercer_nivel: "Tercer Nivel",
};

export function ReportePasesPage() {
  const { hasCapability } = usePermissionDependencies();
  const canRead = hasCapability("clinico.pases.read", {
    allOf: ["clinico:pases:read"],
  });

  const today = todayIso();
  const [fechaInicio, setFechaInicio] = useState(today);
  const [fechaFin, setFechaFin] = useState(today);
  const [appliedFilters, setAppliedFilters] = useState({
    fechaInicio: today,
    fechaFin: today,
  });

  const { data, isLoading, isError, refetch } = useReferralReport(
    appliedFilters,
    { enabled: canRead },
  );
  const { exportReport, isExporting } = useExportReferralReport();

  const handleBuscar = () => {
    setAppliedFilters({ fechaInicio, fechaFin });
  };

  const columns: DataTableColumn<ReferralReportItem>[] = [
    { key: "date", header: "Fecha", accessorKey: "date" },
    { key: "folio", header: "Folio", accessorKey: "folio" },
    {
      key: "referralType",
      header: "Tipo",
      render: (row) => REFERRAL_TYPE_LABELS[row.referralType] ?? row.referralType,
    },
    { key: "noExp", header: "Expediente", accessorKey: "noExp" },
    { key: "patientName", header: "Paciente", accessorKey: "patientName" },
    { key: "doctorName", header: "Médico", accessorKey: "doctorName" },
    {
      key: "destination",
      header: "Destino",
      render: (row) => row.destinationCenterName ?? row.specialtyName ?? "—",
    },
    { key: "status", header: "Estatus", accessorKey: "status" },
  ];

  if (!canRead) {
    return (
      <CatalogModuleLayout
        title="Informe de Pases"
        description="Pases emitidos en un rango de fechas"
        icon={<Ticket className="size-5" />}
      >
        <AdminReadOnlyNotice message="No tienes permiso para ver este reporte." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout
      title="Informe de Pases"
      description="Pases de laboratorio, gabinete, especialidad, hospitalización y tercer nivel emitidos en un rango de fechas."
      icon={<Ticket className="size-5" />}
    >
      <TableHeaderBar
        search={
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-pases-fecha-inicio">Desde</Label>
              <Input
                id="reporte-pases-fecha-inicio"
                type="date"
                value={fechaInicio}
                onChange={(event) => setFechaInicio(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-pases-fecha-fin">Hasta</Label>
              <Input
                id="reporte-pases-fecha-fin"
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
        footerNote={data ? `${data.total} pase(s) encontrados` : undefined}
        minWidthClassName="min-w-[1100px]"
      />
    </CatalogModuleLayout>
  );
}
