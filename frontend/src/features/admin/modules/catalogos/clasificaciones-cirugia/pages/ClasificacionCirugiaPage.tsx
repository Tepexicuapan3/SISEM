import { useState } from "react";
import { toast } from "sonner";
import { ListChecks, Download, Plus, RotateCcw } from "lucide-react";
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
import { useDeleteClasificacionCirugia } from "@features/admin/modules/catalogos/clasificaciones-cirugia/mutations/useDeleteClasificacionCirugia";
import { useUpdateClasificacionCirugia } from "@features/admin/modules/catalogos/clasificaciones-cirugia/mutations/useUpdateClasificacionCirugia";
import { useClasificacionCirugiaList } from "@features/admin/modules/catalogos/clasificaciones-cirugia/queries/useClasificacionCirugiaList";
import {
  buildClasificacionCirugiaTableColumns,
  buildClasificacionCirugiaVisibilityOptions,
} from "@features/admin/modules/catalogos/clasificaciones-cirugia/components/ClasificacionCirugiaTableColumns";
import { ClasificacionCirugiaCreateDialog } from "@features/admin/modules/catalogos/clasificaciones-cirugia/components/ClasificacionCirugiaCreateDialog";
import { ClasificacionCirugiaDetailsDialog } from "@features/admin/modules/catalogos/clasificaciones-cirugia/components/ClasificacionCirugiaDetailsDialog";
import { getClasificacionCirugiaErrorMessage } from "@features/admin/modules/catalogos/clasificaciones-cirugia/utils/clasificaciones-cirugia.feedback";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { ClasificacionCirugiaListItem } from "@api/types";

const STATUS_FILTER = { ALL: "all", ACTIVE: "active", INACTIVE: "inactive" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) => String(value ?? "").toLowerCase();

export function ClasificacionCirugiaPage() {
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
  const [clasificacionCirugiaToDelete, setClasificacionCirugiaToDelete] = useState<ClasificacionCirugiaListItem | null>(null);

  const {
    open: detailsOpen, selectedItem: selectedClasificacionCirugia, openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails, setOpen: setDetailsOpen,
  } = useTableDetailsDialog<ClasificacionCirugiaListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateClasificacionCirugia = useUpdateClasificacionCirugia();
  const deleteClasificacionCirugia = useDeleteClasificacionCirugia();

  const canReadClasificacionCirugia = hasCapability("admin.catalogs.clasificacionescirugia.read", { allOf: ["admin:catalogos:clasificaciones_cirugia:read"] });
  const canCreateClasificacionCirugia = hasCapability("admin.catalogs.clasificacionescirugia.create", { allOf: ["admin:catalogos:clasificaciones_cirugia:create"] });
  const canUpdateClasificacionCirugia = hasCapability("admin.catalogs.clasificacionescirugia.update", { allOf: ["admin:catalogos:clasificaciones_cirugia:update"] });
  const canDeleteClasificacionCirugia = hasCapability("admin.catalogs.clasificacionescirugia.delete", { allOf: ["admin:catalogos:clasificaciones_cirugia:delete"] });
  const readOnlyCatalogMessage = "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useClasificacionCirugiaList(
    {
      page, pageSize,
      isActive: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadClasificacionCirugia },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows = normalizedSearch.length === 0
    ? allRows
    : allRows.filter((item) => normalizeSearchValue(item.name).includes(normalizedSearch));

  const showActions = canReadClasificacionCirugia || canUpdateClasificacionCirugia || canDeleteClasificacionCirugia;
  const isStatusPending = updateClasificacionCirugia.isPending;

  const handleToggleStatus = async (item: ClasificacionCirugiaListItem) => {
    const nextStatus = !item.isActive;
    try {
      await updateClasificacionCirugia.mutateAsync({ id: item.id, data: { isActive: nextStatus } });
      toast.success(nextStatus ? "Registro activado" : "Registro desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", { description: getClasificacionCirugiaErrorMessage(mutationError, "Error al actualizar estado") });
    }
  };

  const handleDeleteClasificacionCirugia = async () => {
    if (!clasificacionCirugiaToDelete) return;
    try {
      await deleteClasificacionCirugia.mutateAsync({ id: clasificacionCirugiaToDelete.id });
      toast.success("Registro eliminado", { description: `${clasificacionCirugiaToDelete.name} se elimino correctamente.` });
      setDeleteOpen(false);
      setClasificacionCirugiaToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", { description: getClasificacionCirugiaErrorMessage(mutationError, "Error al eliminar registro") });
    }
  };

  const columns = buildClasificacionCirugiaTableColumns({
    canReadClasificacionCirugia, canUpdateClasificacionCirugia, canDeleteClasificacionCirugia, isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (item) => { void handleToggleStatus(item); },
    onRequestDelete: (item) => { setClasificacionCirugiaToDelete(item); setDeleteOpen(true); },
  });
  const visibilityOptions = buildClasificacionCirugiaVisibilityOptions(showActions);
  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters = canReadClasificacionCirugia && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription = canReadClasificacionCirugia && error
    ? getClasificacionCirugiaErrorMessage(error, "No se pudo obtener el listado. Intenta nuevamente.")
    : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    { id: "refresh-clasificaciones-cirugia", label: "Actualizar", icon: RotateCcw, isLoading: isFetching, disabled: isFetching, onSelect: () => { if (!isFetching) void refetch(); } },
    { id: "export-clasificaciones-cirugia", label: "Exportar", icon: Download, loadingAnimation: "pulse" },
  ];

  const filterSections = [{
    id: "status", label: "Estado",
    options: [
      { id: STATUS_FILTER.ACTIVE, label: "Activos", selected: statusFilter === STATUS_FILTER.ACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.ACTIVE); setPage(1); } },
      { id: STATUS_FILTER.INACTIVE, label: "Inactivos", selected: statusFilter === STATUS_FILTER.INACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.INACTIVE); setPage(1); } },
    ],
  }];

  return (
    <CatalogModuleLayout title="Clasificaciones de Cirugía" description="Catalogo de clasificaciones de cirugía." icon={<ListChecks className="size-12" />}>
      {!canReadClasificacionCirugia ? <AdminReadOnlyNotice message={readOnlyCatalogMessage} /> : null}

      <TableHeaderBar
        search={<TableSearch value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Buscar en la tabla" disabled={!canReadClasificacionCirugia} />}
        actions={
          <>
            {canReadClasificacionCirugia ? <TableFilterMenu sections={filterSections} appliedCount={appliedFiltersCount} onClear={handleClearFilters} /> : null}
            {canReadClasificacionCirugia ? <TableColumnVisibility columns={visibilityOptions} visibility={columnVisibility} onVisibilityChange={setColumnVisibility} /> : null}
            {canReadClasificacionCirugia ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreateClasificacionCirugia ? (
              <TablePrimaryAction permission="admin:catalogos:clasificaciones_cirugia:create" dependencyAware label="Nuevo" icon={<Plus className="size-4" />} onClick={() => setCreateOpen(true)} />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canReadClasificacionCirugia && Boolean(error)}
        errorTitle="No se pudo cargar el catalogo"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadClasificacionCirugia ? handleOpenDetails : undefined}
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

      <ClasificacionCirugiaDetailsDialog open={detailsOpen} onOpenChange={setDetailsOpen} onClose={handleCloseDetails} clasificacionCirugiaSummary={selectedClasificacionCirugia} canEdit={canUpdateClasificacionCirugia} />
      <ClasificacionCirugiaCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => { setDeleteOpen(nextOpen); if (!nextOpen) setClasificacionCirugiaToDelete(null); }}
        title="Eliminar registro"
        description="Esta accion dara de baja el registro y lo quitara del catalogo."
        onConfirm={() => { void handleDeleteClasificacionCirugia(); }}
        confirmDisabled={deleteClasificacionCirugia.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default ClasificacionCirugiaPage;
