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
import { useDeleteMotivoCancelacionNota } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/mutations/useDeleteMotivoCancelacionNota";
import { useUpdateMotivoCancelacionNota } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/mutations/useUpdateMotivoCancelacionNota";
import { useMotivoCancelacionNotaList } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/queries/useMotivoCancelacionNotaList";
import {
  buildMotivoCancelacionNotaTableColumns,
  buildMotivoCancelacionNotaVisibilityOptions,
} from "@features/admin/modules/catalogos/motivos-cancelacion-nota/components/MotivoCancelacionNotaTableColumns";
import { MotivoCancelacionNotaCreateDialog } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/components/MotivoCancelacionNotaCreateDialog";
import { MotivoCancelacionNotaDetailsDialog } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/components/MotivoCancelacionNotaDetailsDialog";
import { getMotivoCancelacionNotaErrorMessage } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/utils/motivos-cancelacion-nota.feedback";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { MotivoCancelacionNotaListItem } from "@api/types";

const STATUS_FILTER = { ALL: "all", ACTIVE: "active", INACTIVE: "inactive" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) => String(value ?? "").toLowerCase();

export function MotivoCancelacionNotaPage() {
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
  const [motivoCancelacionNotaToDelete, setMotivoCancelacionNotaToDelete] = useState<MotivoCancelacionNotaListItem | null>(null);

  const {
    open: detailsOpen, selectedItem: selectedMotivoCancelacionNota, openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails, setOpen: setDetailsOpen,
  } = useTableDetailsDialog<MotivoCancelacionNotaListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateMotivoCancelacionNota = useUpdateMotivoCancelacionNota();
  const deleteMotivoCancelacionNota = useDeleteMotivoCancelacionNota();

  const canReadMotivoCancelacionNota = hasCapability("admin.catalogs.motivoscancelacionnota.read", { allOf: ["admin:catalogos:motivos_cancelacion_nota:read"] });
  const canCreateMotivoCancelacionNota = hasCapability("admin.catalogs.motivoscancelacionnota.create", { allOf: ["admin:catalogos:motivos_cancelacion_nota:create"] });
  const canUpdateMotivoCancelacionNota = hasCapability("admin.catalogs.motivoscancelacionnota.update", { allOf: ["admin:catalogos:motivos_cancelacion_nota:update"] });
  const canDeleteMotivoCancelacionNota = hasCapability("admin.catalogs.motivoscancelacionnota.delete", { allOf: ["admin:catalogos:motivos_cancelacion_nota:delete"] });
  const readOnlyCatalogMessage = "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useMotivoCancelacionNotaList(
    {
      page, pageSize,
      isActive: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadMotivoCancelacionNota },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows = normalizedSearch.length === 0
    ? allRows
    : allRows.filter((item) => normalizeSearchValue(item.name).includes(normalizedSearch));

  const showActions = canReadMotivoCancelacionNota || canUpdateMotivoCancelacionNota || canDeleteMotivoCancelacionNota;
  const isStatusPending = updateMotivoCancelacionNota.isPending;

  const handleToggleStatus = async (item: MotivoCancelacionNotaListItem) => {
    const nextStatus = !item.isActive;
    try {
      await updateMotivoCancelacionNota.mutateAsync({ id: item.id, data: { isActive: nextStatus } });
      toast.success(nextStatus ? "Registro activado" : "Registro desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", { description: getMotivoCancelacionNotaErrorMessage(mutationError, "Error al actualizar estado") });
    }
  };

  const handleDeleteMotivoCancelacionNota = async () => {
    if (!motivoCancelacionNotaToDelete) return;
    try {
      await deleteMotivoCancelacionNota.mutateAsync({ id: motivoCancelacionNotaToDelete.id });
      toast.success("Registro eliminado", { description: `${motivoCancelacionNotaToDelete.name} se elimino correctamente.` });
      setDeleteOpen(false);
      setMotivoCancelacionNotaToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", { description: getMotivoCancelacionNotaErrorMessage(mutationError, "Error al eliminar registro") });
    }
  };

  const columns = buildMotivoCancelacionNotaTableColumns({
    canReadMotivoCancelacionNota, canUpdateMotivoCancelacionNota, canDeleteMotivoCancelacionNota, isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (item) => { void handleToggleStatus(item); },
    onRequestDelete: (item) => { setMotivoCancelacionNotaToDelete(item); setDeleteOpen(true); },
  });
  const visibilityOptions = buildMotivoCancelacionNotaVisibilityOptions(showActions);
  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters = canReadMotivoCancelacionNota && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription = canReadMotivoCancelacionNota && error
    ? getMotivoCancelacionNotaErrorMessage(error, "No se pudo obtener el listado. Intenta nuevamente.")
    : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    { id: "refresh-motivos-cancelacion-nota", label: "Actualizar", icon: RotateCcw, isLoading: isFetching, disabled: isFetching, onSelect: () => { if (!isFetching) void refetch(); } },
    { id: "export-motivos-cancelacion-nota", label: "Exportar", icon: Download, loadingAnimation: "pulse" },
  ];

  const filterSections = [{
    id: "status", label: "Estado",
    options: [
      { id: STATUS_FILTER.ACTIVE, label: "Activos", selected: statusFilter === STATUS_FILTER.ACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.ACTIVE); setPage(1); } },
      { id: STATUS_FILTER.INACTIVE, label: "Inactivos", selected: statusFilter === STATUS_FILTER.INACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.INACTIVE); setPage(1); } },
    ],
  }];

  return (
    <CatalogModuleLayout title="Motivos de Cancelación de Nota" description="Catalogo de motivos de cancelación de nota." icon={<XCircle className="size-12" />}>
      {!canReadMotivoCancelacionNota ? <AdminReadOnlyNotice message={readOnlyCatalogMessage} /> : null}

      <TableHeaderBar
        search={<TableSearch value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Buscar en la tabla" disabled={!canReadMotivoCancelacionNota} />}
        actions={
          <>
            {canReadMotivoCancelacionNota ? <TableFilterMenu sections={filterSections} appliedCount={appliedFiltersCount} onClear={handleClearFilters} /> : null}
            {canReadMotivoCancelacionNota ? <TableColumnVisibility columns={visibilityOptions} visibility={columnVisibility} onVisibilityChange={setColumnVisibility} /> : null}
            {canReadMotivoCancelacionNota ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreateMotivoCancelacionNota ? (
              <TablePrimaryAction permission="admin:catalogos:motivos_cancelacion_nota:create" dependencyAware label="Nuevo" icon={<Plus className="size-4" />} onClick={() => setCreateOpen(true)} />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canReadMotivoCancelacionNota && Boolean(error)}
        errorTitle="No se pudo cargar el catalogo"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadMotivoCancelacionNota ? handleOpenDetails : undefined}
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

      <MotivoCancelacionNotaDetailsDialog open={detailsOpen} onOpenChange={setDetailsOpen} onClose={handleCloseDetails} motivoCancelacionNotaSummary={selectedMotivoCancelacionNota} canEdit={canUpdateMotivoCancelacionNota} />
      <MotivoCancelacionNotaCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => { setDeleteOpen(nextOpen); if (!nextOpen) setMotivoCancelacionNotaToDelete(null); }}
        title="Eliminar registro"
        description="Esta accion dara de baja el registro y lo quitara del catalogo."
        onConfirm={() => { void handleDeleteMotivoCancelacionNota(); }}
        confirmDisabled={deleteMotivoCancelacionNota.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default MotivoCancelacionNotaPage;
