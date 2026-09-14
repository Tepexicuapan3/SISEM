import { useState } from "react";
import { toast } from "sonner";
import { Truck, Download, Plus, RotateCcw } from "lucide-react";
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
import { useDeleteTipoServicioAmbulancia } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/mutations/useDeleteTipoServicioAmbulancia";
import { useUpdateTipoServicioAmbulancia } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/mutations/useUpdateTipoServicioAmbulancia";
import { useTipoServicioAmbulanciaList } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/queries/useTipoServicioAmbulanciaList";
import {
  buildTipoServicioAmbulanciaTableColumns,
  buildTipoServicioAmbulanciaVisibilityOptions,
} from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/components/TipoServicioAmbulanciaTableColumns";
import { TipoServicioAmbulanciaCreateDialog } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/components/TipoServicioAmbulanciaCreateDialog";
import { TipoServicioAmbulanciaDetailsDialog } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/components/TipoServicioAmbulanciaDetailsDialog";
import { getTipoServicioAmbulanciaErrorMessage } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/utils/tipos-servicio-ambulancia.feedback";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { TipoServicioAmbulanciaListItem } from "@api/types";

const STATUS_FILTER = { ALL: "all", ACTIVE: "active", INACTIVE: "inactive" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) => String(value ?? "").toLowerCase();

export function TipoServicioAmbulanciaPage() {
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
  const [tipoServicioAmbulanciaToDelete, setTipoServicioAmbulanciaToDelete] = useState<TipoServicioAmbulanciaListItem | null>(null);

  const {
    open: detailsOpen, selectedItem: selectedTipoServicioAmbulancia, openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails, setOpen: setDetailsOpen,
  } = useTableDetailsDialog<TipoServicioAmbulanciaListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateTipoServicioAmbulancia = useUpdateTipoServicioAmbulancia();
  const deleteTipoServicioAmbulancia = useDeleteTipoServicioAmbulancia();

  const canReadTipoServicioAmbulancia = hasCapability("admin.catalogs.tiposservicioambulancia.read", { allOf: ["admin:catalogos:tipos_servicio_ambulancia:read"] });
  const canCreateTipoServicioAmbulancia = hasCapability("admin.catalogs.tiposservicioambulancia.create", { allOf: ["admin:catalogos:tipos_servicio_ambulancia:create"] });
  const canUpdateTipoServicioAmbulancia = hasCapability("admin.catalogs.tiposservicioambulancia.update", { allOf: ["admin:catalogos:tipos_servicio_ambulancia:update"] });
  const canDeleteTipoServicioAmbulancia = hasCapability("admin.catalogs.tiposservicioambulancia.delete", { allOf: ["admin:catalogos:tipos_servicio_ambulancia:delete"] });
  const readOnlyCatalogMessage = "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useTipoServicioAmbulanciaList(
    {
      page, pageSize,
      isActive: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadTipoServicioAmbulancia },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows = normalizedSearch.length === 0
    ? allRows
    : allRows.filter((item) => normalizeSearchValue(item.name).includes(normalizedSearch));

  const showActions = canReadTipoServicioAmbulancia || canUpdateTipoServicioAmbulancia || canDeleteTipoServicioAmbulancia;
  const isStatusPending = updateTipoServicioAmbulancia.isPending;

  const handleToggleStatus = async (item: TipoServicioAmbulanciaListItem) => {
    const nextStatus = !item.isActive;
    try {
      await updateTipoServicioAmbulancia.mutateAsync({ id: item.id, data: { isActive: nextStatus } });
      toast.success(nextStatus ? "Registro activado" : "Registro desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", { description: getTipoServicioAmbulanciaErrorMessage(mutationError, "Error al actualizar estado") });
    }
  };

  const handleDeleteTipoServicioAmbulancia = async () => {
    if (!tipoServicioAmbulanciaToDelete) return;
    try {
      await deleteTipoServicioAmbulancia.mutateAsync({ id: tipoServicioAmbulanciaToDelete.id });
      toast.success("Registro eliminado", { description: `${tipoServicioAmbulanciaToDelete.name} se elimino correctamente.` });
      setDeleteOpen(false);
      setTipoServicioAmbulanciaToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", { description: getTipoServicioAmbulanciaErrorMessage(mutationError, "Error al eliminar registro") });
    }
  };

  const columns = buildTipoServicioAmbulanciaTableColumns({
    canReadTipoServicioAmbulancia, canUpdateTipoServicioAmbulancia, canDeleteTipoServicioAmbulancia, isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (item) => { void handleToggleStatus(item); },
    onRequestDelete: (item) => { setTipoServicioAmbulanciaToDelete(item); setDeleteOpen(true); },
  });
  const visibilityOptions = buildTipoServicioAmbulanciaVisibilityOptions(showActions);
  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters = canReadTipoServicioAmbulancia && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription = canReadTipoServicioAmbulancia && error
    ? getTipoServicioAmbulanciaErrorMessage(error, "No se pudo obtener el listado. Intenta nuevamente.")
    : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    { id: "refresh-tipos-servicio-ambulancia", label: "Actualizar", icon: RotateCcw, isLoading: isFetching, disabled: isFetching, onSelect: () => { if (!isFetching) void refetch(); } },
    { id: "export-tipos-servicio-ambulancia", label: "Exportar", icon: Download, loadingAnimation: "pulse" },
  ];

  const filterSections = [{
    id: "status", label: "Estado",
    options: [
      { id: STATUS_FILTER.ACTIVE, label: "Activos", selected: statusFilter === STATUS_FILTER.ACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.ACTIVE); setPage(1); } },
      { id: STATUS_FILTER.INACTIVE, label: "Inactivos", selected: statusFilter === STATUS_FILTER.INACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.INACTIVE); setPage(1); } },
    ],
  }];

  return (
    <CatalogModuleLayout title="Tipos de Servicio de Ambulancia" description="Catalogo de tipos de servicio de ambulancia." icon={<Truck className="size-12" />}>
      {!canReadTipoServicioAmbulancia ? <AdminReadOnlyNotice message={readOnlyCatalogMessage} /> : null}

      <TableHeaderBar
        search={<TableSearch value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Buscar en la tabla" disabled={!canReadTipoServicioAmbulancia} />}
        actions={
          <>
            {canReadTipoServicioAmbulancia ? <TableFilterMenu sections={filterSections} appliedCount={appliedFiltersCount} onClear={handleClearFilters} /> : null}
            {canReadTipoServicioAmbulancia ? <TableColumnVisibility columns={visibilityOptions} visibility={columnVisibility} onVisibilityChange={setColumnVisibility} /> : null}
            {canReadTipoServicioAmbulancia ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreateTipoServicioAmbulancia ? (
              <TablePrimaryAction permission="admin:catalogos:tipos_servicio_ambulancia:create" dependencyAware label="Nuevo" icon={<Plus className="size-4" />} onClick={() => setCreateOpen(true)} />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canReadTipoServicioAmbulancia && Boolean(error)}
        errorTitle="No se pudo cargar el catalogo"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadTipoServicioAmbulancia ? handleOpenDetails : undefined}
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

      <TipoServicioAmbulanciaDetailsDialog open={detailsOpen} onOpenChange={setDetailsOpen} onClose={handleCloseDetails} tipoServicioAmbulanciaSummary={selectedTipoServicioAmbulancia} canEdit={canUpdateTipoServicioAmbulancia} />
      <TipoServicioAmbulanciaCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => { setDeleteOpen(nextOpen); if (!nextOpen) setTipoServicioAmbulanciaToDelete(null); }}
        title="Eliminar registro"
        description="Esta accion dara de baja el registro y lo quitara del catalogo."
        onConfirm={() => { void handleDeleteTipoServicioAmbulancia(); }}
        confirmDisabled={deleteTipoServicioAmbulancia.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default TipoServicioAmbulanciaPage;
