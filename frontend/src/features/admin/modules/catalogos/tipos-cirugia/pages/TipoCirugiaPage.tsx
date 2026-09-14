import { useState } from "react";
import { toast } from "sonner";
import { Scissors, Download, Plus, RotateCcw } from "lucide-react";
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
import { useDeleteTipoCirugia } from "@features/admin/modules/catalogos/tipos-cirugia/mutations/useDeleteTipoCirugia";
import { useUpdateTipoCirugia } from "@features/admin/modules/catalogos/tipos-cirugia/mutations/useUpdateTipoCirugia";
import { useTipoCirugiaList } from "@features/admin/modules/catalogos/tipos-cirugia/queries/useTipoCirugiaList";
import {
  buildTipoCirugiaTableColumns,
  buildTipoCirugiaVisibilityOptions,
} from "@features/admin/modules/catalogos/tipos-cirugia/components/TipoCirugiaTableColumns";
import { TipoCirugiaCreateDialog } from "@features/admin/modules/catalogos/tipos-cirugia/components/TipoCirugiaCreateDialog";
import { TipoCirugiaDetailsDialog } from "@features/admin/modules/catalogos/tipos-cirugia/components/TipoCirugiaDetailsDialog";
import { getTipoCirugiaErrorMessage } from "@features/admin/modules/catalogos/tipos-cirugia/utils/tipos-cirugia.feedback";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { TipoCirugiaListItem } from "@api/types";

const STATUS_FILTER = { ALL: "all", ACTIVE: "active", INACTIVE: "inactive" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) => String(value ?? "").toLowerCase();

export function TipoCirugiaPage() {
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
  const [tipoCirugiaToDelete, setTipoCirugiaToDelete] = useState<TipoCirugiaListItem | null>(null);

  const {
    open: detailsOpen, selectedItem: selectedTipoCirugia, openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails, setOpen: setDetailsOpen,
  } = useTableDetailsDialog<TipoCirugiaListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateTipoCirugia = useUpdateTipoCirugia();
  const deleteTipoCirugia = useDeleteTipoCirugia();

  const canReadTipoCirugia = hasCapability("admin.catalogs.tiposcirugia.read", { allOf: ["admin:catalogos:tipos_cirugia:read"] });
  const canCreateTipoCirugia = hasCapability("admin.catalogs.tiposcirugia.create", { allOf: ["admin:catalogos:tipos_cirugia:create"] });
  const canUpdateTipoCirugia = hasCapability("admin.catalogs.tiposcirugia.update", { allOf: ["admin:catalogos:tipos_cirugia:update"] });
  const canDeleteTipoCirugia = hasCapability("admin.catalogs.tiposcirugia.delete", { allOf: ["admin:catalogos:tipos_cirugia:delete"] });
  const readOnlyCatalogMessage = "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useTipoCirugiaList(
    {
      page, pageSize,
      isActive: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadTipoCirugia },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows = normalizedSearch.length === 0
    ? allRows
    : allRows.filter((item) => normalizeSearchValue(item.name).includes(normalizedSearch));

  const showActions = canReadTipoCirugia || canUpdateTipoCirugia || canDeleteTipoCirugia;
  const isStatusPending = updateTipoCirugia.isPending;

  const handleToggleStatus = async (item: TipoCirugiaListItem) => {
    const nextStatus = !item.isActive;
    try {
      await updateTipoCirugia.mutateAsync({ id: item.id, data: { isActive: nextStatus } });
      toast.success(nextStatus ? "Registro activado" : "Registro desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", { description: getTipoCirugiaErrorMessage(mutationError, "Error al actualizar estado") });
    }
  };

  const handleDeleteTipoCirugia = async () => {
    if (!tipoCirugiaToDelete) return;
    try {
      await deleteTipoCirugia.mutateAsync({ id: tipoCirugiaToDelete.id });
      toast.success("Registro eliminado", { description: `${tipoCirugiaToDelete.name} se elimino correctamente.` });
      setDeleteOpen(false);
      setTipoCirugiaToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", { description: getTipoCirugiaErrorMessage(mutationError, "Error al eliminar registro") });
    }
  };

  const columns = buildTipoCirugiaTableColumns({
    canReadTipoCirugia, canUpdateTipoCirugia, canDeleteTipoCirugia, isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (item) => { void handleToggleStatus(item); },
    onRequestDelete: (item) => { setTipoCirugiaToDelete(item); setDeleteOpen(true); },
  });
  const visibilityOptions = buildTipoCirugiaVisibilityOptions(showActions);
  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters = canReadTipoCirugia && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription = canReadTipoCirugia && error
    ? getTipoCirugiaErrorMessage(error, "No se pudo obtener el listado. Intenta nuevamente.")
    : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    { id: "refresh-tipos-cirugia", label: "Actualizar", icon: RotateCcw, isLoading: isFetching, disabled: isFetching, onSelect: () => { if (!isFetching) void refetch(); } },
    { id: "export-tipos-cirugia", label: "Exportar", icon: Download, loadingAnimation: "pulse" },
  ];

  const filterSections = [{
    id: "status", label: "Estado",
    options: [
      { id: STATUS_FILTER.ACTIVE, label: "Activos", selected: statusFilter === STATUS_FILTER.ACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.ACTIVE); setPage(1); } },
      { id: STATUS_FILTER.INACTIVE, label: "Inactivos", selected: statusFilter === STATUS_FILTER.INACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.INACTIVE); setPage(1); } },
    ],
  }];

  return (
    <CatalogModuleLayout title="Tipos de Cirugía" description="Catalogo de tipos de cirugía." icon={<Scissors className="size-12" />}>
      {!canReadTipoCirugia ? <AdminReadOnlyNotice message={readOnlyCatalogMessage} /> : null}

      <TableHeaderBar
        search={<TableSearch value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Buscar en la tabla" disabled={!canReadTipoCirugia} />}
        actions={
          <>
            {canReadTipoCirugia ? <TableFilterMenu sections={filterSections} appliedCount={appliedFiltersCount} onClear={handleClearFilters} /> : null}
            {canReadTipoCirugia ? <TableColumnVisibility columns={visibilityOptions} visibility={columnVisibility} onVisibilityChange={setColumnVisibility} /> : null}
            {canReadTipoCirugia ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreateTipoCirugia ? (
              <TablePrimaryAction permission="admin:catalogos:tipos_cirugia:create" dependencyAware label="Nuevo" icon={<Plus className="size-4" />} onClick={() => setCreateOpen(true)} />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canReadTipoCirugia && Boolean(error)}
        errorTitle="No se pudo cargar el catalogo"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadTipoCirugia ? handleOpenDetails : undefined}
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

      <TipoCirugiaDetailsDialog open={detailsOpen} onOpenChange={setDetailsOpen} onClose={handleCloseDetails} tipoCirugiaSummary={selectedTipoCirugia} canEdit={canUpdateTipoCirugia} />
      <TipoCirugiaCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => { setDeleteOpen(nextOpen); if (!nextOpen) setTipoCirugiaToDelete(null); }}
        title="Eliminar registro"
        description="Esta accion dara de baja el registro y lo quitara del catalogo."
        onConfirm={() => { void handleDeleteTipoCirugia(); }}
        confirmDisabled={deleteTipoCirugia.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default TipoCirugiaPage;
