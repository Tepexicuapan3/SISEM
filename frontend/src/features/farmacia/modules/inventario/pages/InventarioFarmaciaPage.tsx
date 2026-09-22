import { useEffect, useState } from "react";
import { Boxes, RotateCcw, AlertTriangle } from "lucide-react";
import { useDebounce } from "@shared/hooks/useDebounce";
import { DataTable } from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { TableOptionsMenu, type TableOptionItem } from "@features/admin/shared/components/TableOptionsMenu";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Label } from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { useAlmacenesList } from "@features/almacen-insumos/modules/catalogos/queries/useCatalogosQueries";
import { useExistenciasList } from "@features/almacen-insumos/modules/kardex/queries/useKardexQueries";
import { getCatalogErrorMessage } from "@features/almacen-insumos/modules/catalogos/utils/catalogos.feedback";

/**
 * Inventario de Farmacia (sdd/dispensacion-farmacia, tarea 6.3).
 *
 * CERO backend nuevo: reusa `useAlmacenesList({ tipo: "FARMACIA" })` +
 * `useExistenciasList({ idAlmacen })`, ambos ya usados por
 * `features/almacen-insumos/modules/kardex/pages/ExistenciasPage.tsx`.
 * Solo se agrega el selector de almacén de farmacia (un centro puede tener
 * mas de uno) y se acota la tabla a ese `idAlmacen`.
 */
export function InventarioFarmaciaPage() {
  const almacenesQuery = useAlmacenesList({ tipo: "FARMACIA" });
  const [idAlmacen, setIdAlmacen] = useState<number | null>(null);

  useEffect(() => {
    if (idAlmacen === null && almacenesQuery.data?.items.length) {
      setIdAlmacen(almacenesQuery.data.items[0].id);
    }
  }, [almacenesQuery.data, idAlmacen]);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [search, setSearch] = useState("");
  const [soloBajoCritico, setSoloBajoCritico] = useState(false);
  const debouncedSearch = useDebounce(search, 400);

  const { data, isLoading, isFetching, error, refetch } = useExistenciasList(
    {
      idAlmacen: idAlmacen ?? undefined,
      page, pageSize,
      search: debouncedSearch.trim() || undefined,
      soloBajoCritico: soloBajoCritico || undefined,
    },
    { enabled: idAlmacen !== null },
  );

  const tableOptions: TableOptionItem[] = [
    {
      id: "refresh", label: "Actualizar", icon: RotateCcw, isLoading: isFetching,
      disabled: isFetching, onSelect: () => { if (!isFetching) void refetch(); },
    },
  ];

  if (!almacenesQuery.isLoading && (almacenesQuery.data?.items.length ?? 0) === 0) {
    return (
      <CatalogModuleLayout
        title="Inventario de Farmacia"
        description="Existencias de los almacenes tipo farmacia."
        icon={<Boxes className="size-12" />}
      >
        <AdminReadOnlyNotice message="No hay almacenes de tipo farmacia configurados. Corre el seed de dispensacion o dalos de alta en Almacenes." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout
      title="Inventario de Farmacia"
      description="Saldos actuales de insumos en los almacenes de farmacia."
      icon={<Boxes className="size-12" />}
    >
      <TableHeaderBar
        search={
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label>Almacén</Label>
              <Select
                value={idAlmacen ? String(idAlmacen) : ""}
                onValueChange={(v) => { setIdAlmacen(Number(v)); setPage(1); }}
              >
                <SelectTrigger className="w-56">
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
            <TableSearch
              value={search}
              onChange={(v) => { setSearch(v); setPage(1); }}
              placeholder="Buscar insumo o código"
            />
          </div>
        }
        actions={
          <>
            <Button
              size="sm"
              variant={soloBajoCritico ? "default" : "outline"}
              onClick={() => { setSoloBajoCritico((v) => !v); setPage(1); }}
            >
              <AlertTriangle className="size-3 mr-1" />
              Bajo mínimo
            </Button>
            <TableOptionsMenu options={tableOptions} />
          </>
        }
      />

      <DataTable
        columns={[
          {
            key: "insumoCode", header: "Código", className: "w-28",
            render: (row) => <span className="font-mono text-xs">{row.insumoCode}</span>,
          },
          {
            key: "insumoNombre", header: "Insumo",
            render: (row) => (
              <span className="font-medium flex items-center gap-1">
                {row.bajoCritico && <AlertTriangle className="size-3 text-destructive" />}
                {row.insumoNombre}
              </span>
            ),
          },
          {
            key: "numLote", header: "Lote", className: "w-28",
            render: (row) => <span className="font-mono text-xs">{row.numLote || "—"}</span>,
          },
          {
            key: "cantidad", header: "Existencia", className: "w-24",
            render: (row) => (
              <span className={`tabular-nums font-semibold ${row.bajoCritico ? "text-destructive" : ""}`}>
                {Math.round(Number(row.cantidad))}
              </span>
            ),
          },
          {
            key: "stockMinimo", header: "Mínimo", className: "w-24",
            render: (row) => (
              <span className="tabular-nums text-muted-foreground">
                {row.stockMinimo ? Math.round(Number(row.stockMinimo)) : "—"}
              </span>
            ),
          },
          {
            key: "estado", header: "Estado", className: "w-24",
            render: (row) => (
              <Badge variant={row.bajoCritico ? "critical" : "default"}>
                {row.bajoCritico ? "Bajo mínimo" : "OK"}
              </Badge>
            ),
          },
        ]}
        rows={data?.items ?? []}
        isLoading={isLoading || search.trim() !== debouncedSearch.trim()}
        isError={Boolean(error)}
        errorTitle="No se pudo cargar el inventario de farmacia"
        errorDescription={getCatalogErrorMessage(error, "Intenta nuevamente.")}
        hasFilters={Boolean(debouncedSearch.trim()) || soloBajoCritico}
        onRetry={() => { void refetch(); }}
        onClearFilters={() => { setSearch(""); setSoloBajoCritico(false); setPage(1); }}
        pagination={{
          page, pageSize, total: data?.total ?? 0, totalPages: data?.totalPages ?? 1,
          onPageChange: setPage, onPageSizeChange: (v) => { setPageSize(v); setPage(1); },
        }}
        getRowKey={(row) => row.id.toString()}
        emptyTitle="Sin existencias"
        emptyDescription="Registra entradas de insumos de farmacia para ver los saldos aquí."
      />
    </CatalogModuleLayout>
  );
}

export default InventarioFarmaciaPage;
