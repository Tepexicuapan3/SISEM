import { useState } from "react";
import { Check, ClipboardCheck, X } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@shared/ui/tabs";
import {
  DataTable, type DataTableColumn,
} from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { usePendingPrescriptionAuthorizations } from "@features/autorizacion-recetas/queries/usePendingPrescriptionAuthorizations";
import { usePrescriptionAuthorizationsHistory } from "@features/autorizacion-recetas/queries/usePrescriptionAuthorizationsHistory";
import { AuthorizePrescriptionDialog } from "@features/autorizacion-recetas/components/AuthorizePrescriptionDialog";
import { RejectPrescriptionDialog } from "@features/autorizacion-recetas/components/RejectPrescriptionDialog";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { PrescriptionAuthorizationItem, PrescriptionAuthorizationStatus } from "@api/types";

const STATUS_FILTER = { ALL: "all", PENDIENTE: "pendiente", AUTORIZADA: "autorizada", RECHAZADA: "rechazada" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const STATUS_BADGE_VARIANT: Record<PrescriptionAuthorizationStatus, "secondary" | "outline" | "critical"> = {
  pendiente: "outline",
  autorizada: "secondary",
  rechazada: "critical",
};

export function AutorizacionRecetasPage() {
  const { hasCapability } = usePermissionDependencies();
  const canAuthorize = hasCapability("clinico.recetas.authorize", { allOf: ["clinico:recetas:authorize"] });

  const [authorizeTarget, setAuthorizeTarget] = useState<PrescriptionAuthorizationItem | null>(null);
  const [rejectTarget, setRejectTarget] = useState<PrescriptionAuthorizationItem | null>(null);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>(STATUS_FILTER.ALL);
  const [fechaInicio, setFechaInicio] = useState("");
  const [fechaFin, setFechaFin] = useState("");

  const pendingQuery = usePendingPrescriptionAuthorizations({ enabled: canAuthorize });
  const historyQuery = usePrescriptionAuthorizationsHistory(
    {
      estatus: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter,
      fechaInicio: fechaInicio || undefined,
      fechaFin: fechaFin || undefined,
    },
    { enabled: canAuthorize },
  );

  const handleClearFilters = () => {
    setStatusFilter(STATUS_FILTER.ALL);
    setFechaInicio("");
    setFechaFin("");
  };

  const buildColumns = (showActions: boolean): DataTableColumn<PrescriptionAuthorizationItem>[] => [
    { key: "noExp", header: "Expediente", accessorKey: "noExp" },
    { key: "pkNum", header: "PK", accessorKey: "pkNum" },
    { key: "medicationsCount", header: "Medicamentos", accessorKey: "medicationsCount", align: "center" },
    { key: "specializedCount", header: "Especiales", accessorKey: "specializedCount", align: "center" },
    { key: "controlledCount", header: "Controlados", accessorKey: "controlledCount", align: "center" },
    {
      key: "status",
      header: "Estatus",
      align: "center",
      render: (row) => (
        <Badge variant={STATUS_BADGE_VARIANT[row.status] ?? "outline"} className="text-xs capitalize">
          {row.status}
        </Badge>
      ),
    },
    ...(showActions
      ? [
          {
            key: "actions",
            header: "",
            align: "center" as const,
            render: (row: PrescriptionAuthorizationItem) => (
              <div className="flex items-center justify-center gap-1">
                {canAuthorize && row.status === "pendiente" ? (
                  <>
                    <Button variant="ghost" size="icon" title="Autorizar" onClick={(e) => { e.stopPropagation(); setAuthorizeTarget(row); }}>
                      <Check className="size-4 text-status-stable" />
                    </Button>
                    <Button variant="ghost" size="icon" title="Rechazar" onClick={(e) => { e.stopPropagation(); setRejectTarget(row); }}>
                      <X className="size-4 text-status-critical" />
                    </Button>
                  </>
                ) : null}
              </div>
            ),
          },
        ]
      : []),
  ];

  if (!canAuthorize) {
    return (
      <CatalogModuleLayout title="Autorizacion de Recetas" description="Cola de recetas pendientes de autorizacion" icon={<ClipboardCheck className="size-5" />}>
        <AdminReadOnlyNotice message="No tienes permiso para autorizar recetas." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout
      title="Autorizacion de Recetas"
      description="Autoriza o rechaza recetas con medicamentos especiales o controlados."
      icon={<ClipboardCheck className="size-5" />}
    >
      <Tabs defaultValue="pendientes" className="space-y-4">
        <TabsList>
          <TabsTrigger value="pendientes">Pendientes</TabsTrigger>
          <TabsTrigger value="historial">Historial</TabsTrigger>
        </TabsList>

        <TabsContent value="pendientes" className="space-y-4">
          <DataTable
            columns={buildColumns(true)}
            rows={pendingQuery.data?.items ?? []}
            isLoading={pendingQuery.isLoading}
            isError={pendingQuery.isError}
            onRetry={() => pendingQuery.refetch()}
            footerNote={pendingQuery.data ? `${pendingQuery.data.total} receta(s) pendiente(s)` : undefined}
            getRowKey={(row) => row.id.toString()}
            minWidthClassName="min-w-[900px]"
          />
        </TabsContent>

        <TabsContent value="historial" className="space-y-4">
          <TableHeaderBar
            search={
              <div className="flex flex-wrap items-end gap-3">
                <div className="flex flex-col gap-1">
                  <Label>Estatus</Label>
                  <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
                    <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={STATUS_FILTER.ALL}>Todos</SelectItem>
                      <SelectItem value={STATUS_FILTER.PENDIENTE}>Pendientes</SelectItem>
                      <SelectItem value={STATUS_FILTER.AUTORIZADA}>Autorizadas</SelectItem>
                      <SelectItem value={STATUS_FILTER.RECHAZADA}>Rechazadas</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor="autorizacion-recetas-fecha-inicio">Desde</Label>
                  <Input id="autorizacion-recetas-fecha-inicio" type="date" value={fechaInicio} onChange={(e) => setFechaInicio(e.target.value)} />
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor="autorizacion-recetas-fecha-fin">Hasta</Label>
                  <Input id="autorizacion-recetas-fecha-fin" type="date" value={fechaFin} onChange={(e) => setFechaFin(e.target.value)} />
                </div>
                <Button variant="outline" onClick={handleClearFilters}>Limpiar filtros</Button>
              </div>
            }
          />

          <DataTable
            columns={buildColumns(true)}
            rows={historyQuery.data?.items ?? []}
            isLoading={historyQuery.isLoading}
            isError={historyQuery.isError}
            onRetry={() => historyQuery.refetch()}
            hasFilters={statusFilter !== STATUS_FILTER.ALL || Boolean(fechaInicio) || Boolean(fechaFin)}
            onClearFilters={handleClearFilters}
            footerNote={historyQuery.data ? `${historyQuery.data.total} receta(s) encontradas` : undefined}
            getRowKey={(row) => row.id.toString()}
            minWidthClassName="min-w-[900px]"
          />
        </TabsContent>
      </Tabs>

      <AuthorizePrescriptionDialog
        open={Boolean(authorizeTarget)}
        onOpenChange={(next) => { if (!next) setAuthorizeTarget(null); }}
        authorization={authorizeTarget}
      />
      <RejectPrescriptionDialog
        open={Boolean(rejectTarget)}
        onOpenChange={(next) => { if (!next) setRejectTarget(null); }}
        authorization={rejectTarget}
      />
    </CatalogModuleLayout>
  );
}

export default AutorizacionRecetasPage;
