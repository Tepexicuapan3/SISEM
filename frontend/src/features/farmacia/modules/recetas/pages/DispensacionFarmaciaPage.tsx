import { useEffect, useState } from "react";
import { Pill, RotateCcw } from "lucide-react";
import { Label } from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { Button } from "@shared/ui/button";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useAlmacenesList } from "@features/almacen-insumos/modules/catalogos/queries/useCatalogosQueries";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { DispensationQueueItem } from "@api/types";
import { useDispensationQueue } from "../queries/useDispensacionQueries";
import { DispensePrescriptionDialog } from "../components/DispensePrescriptionDialog";

const DISPENSE_CAPABILITY = "farmacia.recetas.dispense";
const DISPENSE_REQUIREMENT = { allOf: ["farmacia:recetas:dispensar"] };

export function DispensacionFarmaciaPage() {
  const { hasCapability } = usePermissionDependencies();
  const canDispense = hasCapability(DISPENSE_CAPABILITY, DISPENSE_REQUIREMENT);

  const almacenesQuery = useAlmacenesList({ tipo: "FARMACIA" }, { enabled: canDispense });
  const [idAlmacen, setIdAlmacen] = useState<number | null>(null);
  const [dispenseTarget, setDispenseTarget] = useState<DispensationQueueItem | null>(null);

  useEffect(() => {
    if (idAlmacen === null && almacenesQuery.data?.items.length) {
      setIdAlmacen(almacenesQuery.data.items[0].id);
    }
  }, [almacenesQuery.data, idAlmacen]);

  const queueQuery = useDispensationQueue(
    idAlmacen ? { idAlmacen } : undefined,
    { enabled: canDispense && idAlmacen !== null },
  );

  if (!canDispense) {
    return (
      <CatalogModuleLayout
        title="Dispensación de Recetas"
        description="Cola de recetas pendientes de dispensación en farmacia"
        icon={<Pill className="size-5" />}
      >
        <AdminReadOnlyNotice message="No tienes permiso para dispensar recetas." />
      </CatalogModuleLayout>
    );
  }

  const columns: DataTableColumn<DispensationQueueItem>[] = [
    { key: "noExp", header: "Expediente", accessorKey: "noExp" },
    { key: "pkNum", header: "PK", accessorKey: "pkNum" },
    { key: "patientName", header: "Paciente", accessorKey: "patientName" },
    {
      key: "actions",
      header: "",
      align: "center",
      render: (row) => (
        <Button size="sm" onClick={(e) => { e.stopPropagation(); setDispenseTarget(row); }}>
          Dispensar
        </Button>
      ),
    },
  ];

  return (
    <CatalogModuleLayout
      title="Dispensación de Recetas"
      description="Cola de recetas autorizadas con items pendientes de dispensación."
      icon={<Pill className="size-5" />}
    >
      <TableHeaderBar
        search={
          <div className="flex flex-col gap-1">
            <Label>Almacén de farmacia</Label>
            <Select
              value={idAlmacen ? String(idAlmacen) : ""}
              onValueChange={(v) => setIdAlmacen(Number(v))}
            >
              <SelectTrigger className="w-64">
                <SelectValue placeholder="Selecciona un almacén" />
              </SelectTrigger>
              <SelectContent>
                {(almacenesQuery.data?.items ?? []).map((almacen) => (
                  <SelectItem key={almacen.id} value={String(almacen.id)}>
                    {almacen.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
        actions={
          <Button
            variant="outline" size="sm"
            disabled={queueQuery.isFetching}
            onClick={() => { void queueQuery.refetch(); }}
          >
            <RotateCcw className="size-3 mr-1" />
            Actualizar
          </Button>
        }
      />

      <DataTable
        columns={columns}
        rows={queueQuery.data?.items ?? []}
        isLoading={queueQuery.isLoading}
        isError={queueQuery.isError}
        onRetry={() => { void queueQuery.refetch(); }}
        footerNote={queueQuery.data ? `${queueQuery.data.total} receta(s) pendiente(s)` : undefined}
        getRowKey={(row) => row.prescriptionId.toString()}
        emptyTitle="Sin recetas pendientes"
        emptyDescription="Las recetas autorizadas con items pendientes aparecen aquí."
        minWidthClassName="min-w-[700px]"
      />

      <DispensePrescriptionDialog
        open={Boolean(dispenseTarget)}
        onOpenChange={(next) => { if (!next) setDispenseTarget(null); }}
        prescriptionId={dispenseTarget?.prescriptionId ?? null}
        idAlmacen={idAlmacen}
      />
    </CatalogModuleLayout>
  );
}

export default DispensacionFarmaciaPage;
