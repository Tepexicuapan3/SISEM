import { useState } from "react";
import { toast } from "sonner";
import { XCircle, Download, Plus, RotateCcw } from "lucide-react";
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
import { useDeleteMotivoBajaPadron } from "@features/admin/modules/catalogos/motivos-baja-padron/mutations/useDeleteMotivoBajaPadron";
import { useUpdateMotivoBajaPadron } from "@features/admin/modules/catalogos/motivos-baja-padron/mutations/useUpdateMotivoBajaPadron";
import { useMotivoBajaPadronList } from "@features/admin/modules/catalogos/motivos-baja-padron/queries/useMotivoBajaPadronList";
import {
  buildMotivoBajaPadronTableColumns,
  buildMotivoBajaPadronVisibilityOptions,
} from "@features/admin/modules/catalogos/motivos-baja-padron/components/MotivoBajaPadronTableColumns";
import { MotivoBajaPadronCreateDialog } from "@features/admin/modules/catalogos/motivos-baja-padron/components/MotivoBajaPadronCreateDialog";
import { MotivoBajaPadronDetailsDialog } from "@features/admin/modules/catalogos/motivos-baja-padron/components/MotivoBajaPadronDetailsDialog";
import { getMotivoBajaPadronErrorMessage } from "@features/admin/modules/catalogos/motivos-baja-padron/utils/motivos-baja-padron.feedback";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { MotivoBajaPadronListItem } from "@api/types";

const STATUS_FILTER = { ALL: "all", ACTIVE: "active", INACTIVE: "inactive" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) => String(value ?? "").toLowerCase();

export function MotivoBajaPadronPage() {
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
  const [motivoBajaPadronToDelete, setMotivoBajaPadronToDelete] = useState<MotivoBajaPadronListItem | null>(null);

  const {
    open: detailsOpen, selectedItem: selectedMotivoBajaPadron, openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails, setOpen: setDetailsOpen,
  } = useTableDetailsDialog<MotivoBajaPadronListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateMotivoBajaPadron = useUpdateMotivoBajaPadron();
  const deleteMotivoBajaPadron = useDeleteMotivoBajaPadron();

  const canReadMotivoBajaPadron = hasCapability("admin.catalogs.motivosbajapadron.read", { allOf: ["admin:catalogos:motivos_baja_padron:read"] });
  const canCreateMotivoBajaPadron = hasCapability("admin.catalogs.motivosbajapadron.create", { allOf: ["admin:catalogos:motivos_baja_padron:create"] });
  const canUpdateMotivoBajaPadron = hasCapability("admin.catalogs.motivosbajapadron.update", { allOf: ["admin:catalogos:motivos_baja_padron:update"] });
  const canDeleteMotivoBajaPadron = hasCapability("admin.catalogs.motivosbajapadron.delete", { allOf: ["admin:catalogos:motivos_baja_padron:delete"] });
  const readOnlyCatalogMessage = "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useMotivoBajaPadronList(
    {
      page, pageSize,
      isActive: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadMotivoBajaPadron },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows = normalizedSearch.length === 0
    ? allRows
    : allRows.filter((item) => normalizeSearchValue(item.name).includes(normalizedSearch));

  const showActions = canReadMotivoBajaPadron || canUpdateMotivoBajaPadron || canDeleteMotivoBajaPadron;
  const isStatusPending = updateMotivoBajaPadron.isPending;

  const handleToggleStatus = async (item: MotivoBajaPadronListItem) => {
    const nextStatus = !item.isActive;
    try {
      await updateMotivoBajaPadron.mutateAsync({ id: item.id, data: { isActive: nextStatus } });
      toast.success(nextStatus ? "Registro activado" : "Registro desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", { description: getMotivoBajaPadronErrorMessage(mutationError, "Error al actualizar estado") });
    }
  };

  const handleDeleteMotivoBajaPadron = async () => {
    if (!motivoBajaPadronToDelete) return;
    try {
      await deleteMotivoBajaPadron.mutateAsync({ id: motivoBajaPadronToDelete.id });
      toast.success("Registro eliminado", { description: `${motivoBajaPadronToDelete.name} se elimino correctamente.` });
      setDeleteOpen(false);
      setMotivoBajaPadronToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", { description: getMotivoBajaPadronErrorMessage(mutationError, "Error al eliminar registro") });
    }
  };

  const columns = buildMotivoBajaPadronTableColumns({
    canReadMotivoBajaPadron, canUpdateMotivoBajaPadron, canDeleteMotivoBajaPadron, isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (item) => { void handleToggleStatus(item); },
    onRequestDelete: (item) => { setMotivoBajaPadronToDelete(item); setDeleteOpen(true); },
  });
  const visibilityOptions = buildMotivoBajaPadronVisibilityOptions(showActions);
  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters = canReadMotivoBajaPadron && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription = canReadMotivoBajaPadron && error
    ? getMotivoBajaPadronErrorMessage(error, "No se pudo obtener el listado. Intenta nuevamente.")
    : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    { id: "refresh-motivos-baja-padron", label: "Actualizar", icon: RotateCcw, isLoading: isFetching, disabled: isFetching, onSelect: () => { if (!isFetching) void refetch(); } },
    { id: "export-motivos-baja-padron", label: "Exportar", icon: Download, loadingAnimation: "pulse" },
  ];

  const filterSections = [{
    id: "status", label: "Estado",
    options: [
      { id: STATUS_FILTER.ACTIVE, label: "Activos", selected: statusFilter === STATUS_FILTER.ACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.ACTIVE); setPage(1); } },
      { id: STATUS_FILTER.INACTIVE, label: "Inactivos", selected: statusFilter === STATUS_FILTER.INACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.INACTIVE); setPage(1); } },
    ],
  }];

  return (
    <CatalogModuleLayout title="Motivos de Baja de Padrón" description="Catalogo de motivos de baja de padrón." icon={<XCircle className="size-12" />}>
      {!canReadMotivoBajaPadron ? <AdminReadOnlyNotice message={readOnlyCatalogMessage} /> : null}

      <TableHeaderBar
        search={<TableSearch value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Buscar en la tabla" disabled={!canReadMotivoBajaPadron} />}
        actions={
          <>
            {canReadMotivoBajaPadron ? <TableFilterMenu sections={filterSections} appliedCount={appliedFiltersCount} onClear={handleClearFilters} /> : null}
            {canReadMotivoBajaPadron ? <TableColumnVisibility columns={visibilityOptions} visibility={columnVisibility} onVisibilityChange={setColumnVisibility} /> : null}
            {canReadMotivoBajaPadron ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreateMotivoBajaPadron ? (
              <TablePrimaryAction permission="admin:catalogos:motivos_baja_padron:create" dependencyAware label="Nuevo" icon={<Plus className="size-4" />} onClick={() => setCreateOpen(true)} />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canReadMotivoBajaPadron && Boolean(error)}
        errorTitle="No se pudo cargar el catalogo"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadMotivoBajaPadron ? handleOpenDetails : undefined}
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

      <MotivoBajaPadronDetailsDialog open={detailsOpen} onOpenChange={setDetailsOpen} onClose={handleCloseDetails} motivoBajaPadronSummary={selectedMotivoBajaPadron} canEdit={canUpdateMotivoBajaPadron} />
      <MotivoBajaPadronCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => { setDeleteOpen(nextOpen); if (!nextOpen) setMotivoBajaPadronToDelete(null); }}
        title="Eliminar registro"
        description="Esta accion dara de baja el registro y lo quitara del catalogo."
        onConfirm={() => { void handleDeleteMotivoBajaPadron(); }}
        confirmDisabled={deleteMotivoBajaPadron.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default MotivoBajaPadronPage;
