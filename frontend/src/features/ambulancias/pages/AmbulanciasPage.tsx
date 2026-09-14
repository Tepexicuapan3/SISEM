import { useState } from "react";
import { toast } from "sonner";
import { Ambulance, Check, Plus, X, XCircle } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Label } from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import {
  DataTable, type DataTableColumn,
} from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { ConfirmDestructiveDialog } from "@features/admin/shared/components/ConfirmDestructiveDialog";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useAmbulanceRequestsList } from "@features/ambulancias/queries/useAmbulanceRequestsList";
import { useCancelAmbulanceRequest } from "@features/ambulancias/mutations/useCancelAmbulanceRequest";
import { CreateAmbulanceRequestDialog } from "@features/ambulancias/components/CreateAmbulanceRequestDialog";
import { AuthorizeAmbulanceRequestDialog } from "@features/ambulancias/components/AuthorizeAmbulanceRequestDialog";
import { RejectAmbulanceRequestDialog } from "@features/ambulancias/components/RejectAmbulanceRequestDialog";
import { getAmbulanciasErrorMessage } from "@features/ambulancias/utils/ambulancias.feedback";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { AmbulanceRequestItem } from "@api/types";

const AUTH_FILTER = { ALL: "all", PENDIENTE: "pendiente", AUTORIZADA: "autorizada", RECHAZADA: "rechazada" } as const;
type AuthFilter = (typeof AUTH_FILTER)[keyof typeof AUTH_FILTER];

const AUTH_BADGE_VARIANT: Record<string, "secondary" | "outline" | "critical"> = {
  pendiente: "outline",
  autorizada: "secondary",
  rechazada: "critical",
};

export function AmbulanciasPage() {
  const { hasCapability } = usePermissionDependencies();
  const canRead = hasCapability("clinico.ambulancias.read", { allOf: ["clinico:ambulancias:read"] });
  const canWrite = hasCapability("clinico.ambulancias.write", { allOf: ["clinico:ambulancias:write"] });
  const canAuthorize = hasCapability("clinico.ambulancias.authorize", { allOf: ["clinico:ambulancias:authorize"] });

  const [authFilter, setAuthFilter] = useState<AuthFilter>(AUTH_FILTER.ALL);
  const [createOpen, setCreateOpen] = useState(false);
  const [authorizeTarget, setAuthorizeTarget] = useState<AmbulanceRequestItem | null>(null);
  const [rejectTarget, setRejectTarget] = useState<AmbulanceRequestItem | null>(null);
  const [cancelTarget, setCancelTarget] = useState<AmbulanceRequestItem | null>(null);

  const cancelRequest = useCancelAmbulanceRequest();

  const { data, isLoading, isError, refetch } = useAmbulanceRequestsList(
    { authorizationStatus: authFilter === AUTH_FILTER.ALL ? undefined : authFilter },
    { enabled: canRead },
  );

  const handleCancel = async () => {
    if (!cancelTarget) return;
    try {
      await cancelRequest.mutateAsync(cancelTarget.id);
      toast.success("Solicitud dada de baja");
      setCancelTarget(null);
    } catch (error) {
      toast.error("No se pudo dar de baja la solicitud", {
        description: getAmbulanciasErrorMessage(error, "Error al dar de baja la solicitud"),
      });
    }
  };

  const columns: DataTableColumn<AmbulanceRequestItem>[] = [
    { key: "folio", header: "Folio", accessorKey: "folio" },
    { key: "noExp", header: "Expediente", accessorKey: "noExp" },
    { key: "requestedByName", header: "Solicita", accessorKey: "requestedByName" },
    { key: "reasonName", header: "Motivo", accessorKey: "reasonName" },
    { key: "destinationName", header: "Destino", accessorKey: "destinationName" },
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
    {
      key: "actions",
      header: "",
      align: "center",
      render: (row) => (
        <div className="flex items-center justify-center gap-1">
          {canAuthorize && row.authorizationStatus === "pendiente" ? (
            <>
              <Button variant="ghost" size="icon" title="Autorizar" onClick={(e) => { e.stopPropagation(); setAuthorizeTarget(row); }}>
                <Check className="size-4 text-status-stable" />
              </Button>
              <Button variant="ghost" size="icon" title="Rechazar" onClick={(e) => { e.stopPropagation(); setRejectTarget(row); }}>
                <X className="size-4 text-status-critical" />
              </Button>
            </>
          ) : null}
          {canWrite && row.status === "activa" ? (
            <Button variant="ghost" size="icon" title="Dar de baja" onClick={(e) => { e.stopPropagation(); setCancelTarget(row); }}>
              <XCircle className="size-4 text-status-critical" />
            </Button>
          ) : null}
        </div>
      ),
    },
  ];

  if (!canRead) {
    return (
      <CatalogModuleLayout title="Ambulancias" description="Solicitudes de traslado" icon={<Ambulance className="size-5" />}>
        <AdminReadOnlyNotice message="No tienes permiso para ver las solicitudes de traslado." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout title="Ambulancias" description="Solicitudes de traslado interno en ambulancia entre unidades medicas." icon={<Ambulance className="size-5" />}>
      <TableHeaderBar
        search={
          <div className="flex flex-col gap-1">
            <Label>Autorizacion</Label>
            <Select value={authFilter} onValueChange={(v) => setAuthFilter(v as AuthFilter)}>
              <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={AUTH_FILTER.ALL}>Todas</SelectItem>
                <SelectItem value={AUTH_FILTER.PENDIENTE}>Pendientes</SelectItem>
                <SelectItem value={AUTH_FILTER.AUTORIZADA}>Autorizadas</SelectItem>
                <SelectItem value={AUTH_FILTER.RECHAZADA}>Rechazadas</SelectItem>
              </SelectContent>
            </Select>
          </div>
        }
        actions={
          canWrite ? (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="size-4" />
              Nueva solicitud
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
        footerNote={data ? `${data.total} solicitud(es) encontradas` : undefined}
        getRowKey={(row) => row.id.toString()}
        minWidthClassName="min-w-[1100px]"
      />

      <CreateAmbulanceRequestDialog open={createOpen} onOpenChange={setCreateOpen} />
      <AuthorizeAmbulanceRequestDialog
        open={Boolean(authorizeTarget)}
        onOpenChange={(next) => { if (!next) setAuthorizeTarget(null); }}
        request={authorizeTarget}
      />
      <RejectAmbulanceRequestDialog
        open={Boolean(rejectTarget)}
        onOpenChange={(next) => { if (!next) setRejectTarget(null); }}
        request={rejectTarget}
      />
      <ConfirmDestructiveDialog
        open={Boolean(cancelTarget)}
        onOpenChange={(next) => { if (!next) setCancelTarget(null); }}
        title="Dar de baja solicitud"
        description="Esta accion dara de baja la solicitud de traslado."
        onConfirm={() => { void handleCancel(); }}
        confirmDisabled={cancelRequest.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default AmbulanciasPage;
