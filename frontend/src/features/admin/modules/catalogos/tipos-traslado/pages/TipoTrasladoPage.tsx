import { useState } from "react";
import { toast } from "sonner";
import { Map, Download, Plus, RotateCcw } from "lucide-react";
import { useDebounce } from "@shared/hooks/useDebounce";
import { DataTable } from "@features/admin/shared/components/DataTable";
import { TableColumnVisibility, type ColumnVisibilityState } from "@features/admin/shared/components/TableColumnVisibility";
import { TableFilterMenu } from "@features/admin/shared/components/TableFilterMenu";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { TableOptionsMenu, type TableOptionItem } from "@features/admin/shared/components/TableOptionsMenu";
import { TablePrimaryAction } from "@features/admin/shared/components/TablePrimaryAction";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { ConfirmDestructiveDialog } from "@features/admin/shared/components/ConfirmDestructiveDialog";
import { useTableDetailsDialog } from "@features/admin/shared/hooks/useTableDetailsDialog";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useDeleteTipoTraslado } from "@features/admin/modules/catalogos/tipos-traslado/mutations/useDeleteTipoTraslado";
import { useUpdateTipoTraslado } from "@features/admin/modules/catalogos/tipos-traslado/mutations/useUpdateTipoTraslado";
import { useTipoTrasladoList } from "@features/admin/modules/catalogos/tipos-traslado/queries/useTipoTrasladoList";
import {
  buildTipoTrasladoTableColumns,
  buildTipoTrasladoVisibilityOptions,
} from "@features/admin/modules/catalogos/tipos-traslado/components/TipoTrasladoTableColumns";
import { TipoTrasladoCreateDialog } from "@features/admin/modules/catalogos/tipos-traslado/components/TipoTrasladoCreateDialog";
import { TipoTrasladoDetailsDialog } from "@features/admin/modules/catalogos/tipos-traslado/components/TipoTrasladoDetailsDialog";
import { getTipoTrasladoErrorMessage } from "@features/admin/modules/catalogos/tipos-traslado/utils/tipos-traslado.feedback";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { TipoTrasladoListItem } from "@api/types";

const STATUS_FILTER = { ALL: "all", ACTIVE: "active", INACTIVE: "inactive" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) => String(value ?? "").toLowerCase();

export function TipoTrasladoPage() {
  const { hasCapability } = usePermissionDependencies();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(STATUS_FILTER.ALL);
  const [columnVisibility, setColumnVisibility] = useState<ColumnVisibilityState>({
    name: true, isActive: true, actions: true,
  });
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [tipoTrasladoToDelete, setTipoTrasladoToDelete] = useState<TipoTrasladoListItem | null>(null);

  const {
    open: detailsOpen, selectedItem: selectedTipoTraslado, openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails, setOpen: setDetailsOpen,
  } = useTableDetailsDialog<TipoTrasladoListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateTipoTraslado = useUpdateTipoTraslado();
  const deleteTipoTraslado = useDeleteTipoTraslado();

  const canReadTipoTraslado = hasCapability("admin.catalogs.tipostraslado.read", { allOf: ["admin:catalogos:tipos_traslado:read"] });
  const canCreateTipoTraslado = hasCapability("admin.catalogs.tipostraslado.create", { allOf: ["admin:catalogos:tipos_traslado:create"] });
  const canUpdateTipoTraslado = hasCapability("admin.catalogs.tipostraslado.update", { allOf: ["admin:catalogos:tipos_traslado:update"] });
  const canDeleteTipoTraslado = hasCapability("admin.catalogs.tipostraslado.delete", { allOf: ["admin:catalogos:tipos_traslado:delete"] });
  const readOnlyCatalogMessage = "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useTipoTrasladoList(
    {
      page, pageSize,
      isActive: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadTipoTraslado },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows = normalizedSearch.length === 0
    ? allRows
    : allRows.filter((item) => normalizeSearchValue(item.name).includes(normalizedSearch));

  const showActions = canReadTipoTraslado || canUpdateTipoTraslado || canDeleteTipoTraslado;
  const isStatusPending = updateTipoTraslado.isPending;

  const handleToggleStatus = async (item: TipoTrasladoListItem) => {
    const nextStatus = !item.isActive;
    try {
      await updateTipoTraslado.mutateAsync({ id: item.id, data: { isActive: nextStatus } });
      toast.success(nextStatus ? "Registro activado" : "Registro desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", { description: getTipoTrasladoErrorMessage(mutationError, "Error al actualizar estado") });
    }
  };

  const handleDeleteTipoTraslado = async () => {
    if (!tipoTrasladoToDelete) return;
    try {
      await deleteTipoTraslado.mutateAsync({ id: tipoTrasladoToDelete.id });
      toast.success("Registro eliminado", { description: `${tipoTrasladoToDelete.name} se elimino correctamente.` });
      setDeleteOpen(false);
      setTipoTrasladoToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", { description: getTipoTrasladoErrorMessage(mutationError, "Error al eliminar registro") });
    }
  };

  const columns = buildTipoTrasladoTableColumns({
    canReadTipoTraslado, canUpdateTipoTraslado, canDeleteTipoTraslado, isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (item) => { void handleToggleStatus(item); },
    onRequestDelete: (item) => { setTipoTrasladoToDelete(item); setDeleteOpen(true); },
  });
  const visibilityOptions = buildTipoTrasladoVisibilityOptions(showActions);
  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters = canReadTipoTraslado && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription = canReadTipoTraslado && error
    ? getTipoTrasladoErrorMessage(error, "No se pudo obtener el listado. Intenta nuevamente.")
    : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    { id: "refresh-tipos-traslado", label: "Actualizar", icon: RotateCcw, isLoading: isFetching, disabled: isFetching, onSelect: () => { if (!isFetching) void refetch(); } },
    { id: "export-tipos-traslado", label: "Exportar", icon: Download, loadingAnimation: "pulse" },
  ];

  const filterSections = [{
    id: "status", label: "Estado",
    options: [
      { id: STATUS_FILTER.ACTIVE, label: "Activos", selected: statusFilter === STATUS_FILTER.ACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.ACTIVE); setPage(1); } },
      { id: STATUS_FILTER.INACTIVE, label: "Inactivos", selected: statusFilter === STATUS_FILTER.INACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.INACTIVE); setPage(1); } },
    ],
  }];

  return (
    <CatalogModuleLayout title="Tipos de Traslado" description="Catalogo de tipos de traslado." icon={<Map className="size-12" />}>
      {!canReadTipoTraslado ? <AdminReadOnlyNotice message={readOnlyCatalogMessage} /> : null}

      <TableHeaderBar
        search={<TableSearch value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Buscar en la tabla" disabled={!canReadTipoTraslado} />}
        actions={
          <>
            {canReadTipoTraslado ? <TableFilterMenu sections={filterSections} appliedCount={appliedFiltersCount} onClear={handleClearFilters} /> : null}
            {canReadTipoTraslado ? <TableColumnVisibility columns={visibilityOptions} visibility={columnVisibility} onVisibilityChange={setColumnVisibility} /> : null}
            {canReadTipoTraslado ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreateTipoTraslado ? (
              <TablePrimaryAction permission="admin:catalogos:tipos_traslado:create" dependencyAware label="Nuevo" icon={<Plus className="size-4" />} onClick={() => setCreateOpen(true)} />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canReadTipoTraslado && Boolean(error)}
        errorTitle="No se pudo cargar el catalogo"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadTipoTraslado ? handleOpenDetails : undefined}
        onRetry={() => { void refetch(); }}
        onClearFilters={handleClearFilters}
        pagination={{
          page, pageSize, total: data?.total ?? 0, totalPages: data?.totalPages ?? 1,
          onPageChange: setPage,
          onPageSizeChange: (value) => { setPageSize(value); setPage(1); },
        }}
        getRowKey={(row) => row.id.toString()}
        emptyTitle="Sin registros"
        emptyDescription="Cuando existan registros se listaran aqui."
      />

      <TipoTrasladoDetailsDialog open={detailsOpen} onOpenChange={setDetailsOpen} onClose={handleCloseDetails} tipoTrasladoSummary={selectedTipoTraslado} canEdit={canUpdateTipoTraslado} />
      <TipoTrasladoCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => { setDeleteOpen(nextOpen); if (!nextOpen) setTipoTrasladoToDelete(null); }}
        title="Eliminar registro"
        description="Esta accion dara de baja el registro y lo quitara del catalogo."
        onConfirm={() => { void handleDeleteTipoTraslado(); }}
        confirmDisabled={deleteTipoTraslado.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default TipoTrasladoPage;
