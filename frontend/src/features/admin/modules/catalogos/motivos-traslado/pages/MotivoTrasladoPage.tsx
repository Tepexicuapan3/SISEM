import { useState } from "react";
import { toast } from "sonner";
import { Route, Download, Plus, RotateCcw } from "lucide-react";
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
import { useDeleteMotivoTraslado } from "@features/admin/modules/catalogos/motivos-traslado/mutations/useDeleteMotivoTraslado";
import { useUpdateMotivoTraslado } from "@features/admin/modules/catalogos/motivos-traslado/mutations/useUpdateMotivoTraslado";
import { useMotivoTrasladoList } from "@features/admin/modules/catalogos/motivos-traslado/queries/useMotivoTrasladoList";
import {
  buildMotivoTrasladoTableColumns,
  buildMotivoTrasladoVisibilityOptions,
} from "@features/admin/modules/catalogos/motivos-traslado/components/MotivoTrasladoTableColumns";
import { MotivoTrasladoCreateDialog } from "@features/admin/modules/catalogos/motivos-traslado/components/MotivoTrasladoCreateDialog";
import { MotivoTrasladoDetailsDialog } from "@features/admin/modules/catalogos/motivos-traslado/components/MotivoTrasladoDetailsDialog";
import { getMotivoTrasladoErrorMessage } from "@features/admin/modules/catalogos/motivos-traslado/utils/motivos-traslado.feedback";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { MotivoTrasladoListItem } from "@api/types";

const STATUS_FILTER = { ALL: "all", ACTIVE: "active", INACTIVE: "inactive" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) => String(value ?? "").toLowerCase();

export function MotivoTrasladoPage() {
  const { hasCapability } = usePermissionDependencies();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(STATUS_FILTER.ALL);
  const [columnVisibility, setColumnVisibility] = useState<ColumnVisibilityState>({
    name: true, requiresNotes: true, isActive: true, actions: true,
  });
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [motivoTrasladoToDelete, setMotivoTrasladoToDelete] = useState<MotivoTrasladoListItem | null>(null);

  const {
    open: detailsOpen, selectedItem: selectedMotivoTraslado, openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails, setOpen: setDetailsOpen,
  } = useTableDetailsDialog<MotivoTrasladoListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateMotivoTraslado = useUpdateMotivoTraslado();
  const deleteMotivoTraslado = useDeleteMotivoTraslado();

  const canReadMotivoTraslado = hasCapability("admin.catalogs.motivostraslado.read", { allOf: ["admin:catalogos:motivos_traslado:read"] });
  const canCreateMotivoTraslado = hasCapability("admin.catalogs.motivostraslado.create", { allOf: ["admin:catalogos:motivos_traslado:create"] });
  const canUpdateMotivoTraslado = hasCapability("admin.catalogs.motivostraslado.update", { allOf: ["admin:catalogos:motivos_traslado:update"] });
  const canDeleteMotivoTraslado = hasCapability("admin.catalogs.motivostraslado.delete", { allOf: ["admin:catalogos:motivos_traslado:delete"] });
  const readOnlyCatalogMessage = "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useMotivoTrasladoList(
    {
      page, pageSize,
      isActive: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadMotivoTraslado },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows = normalizedSearch.length === 0
    ? allRows
    : allRows.filter((item) => normalizeSearchValue(item.name).includes(normalizedSearch));

  const showActions = canReadMotivoTraslado || canUpdateMotivoTraslado || canDeleteMotivoTraslado;
  const isStatusPending = updateMotivoTraslado.isPending;

  const handleToggleStatus = async (item: MotivoTrasladoListItem) => {
    const nextStatus = !item.isActive;
    try {
      await updateMotivoTraslado.mutateAsync({ id: item.id, data: { isActive: nextStatus } });
      toast.success(nextStatus ? "Registro activado" : "Registro desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", { description: getMotivoTrasladoErrorMessage(mutationError, "Error al actualizar estado") });
    }
  };

  const handleDeleteMotivoTraslado = async () => {
    if (!motivoTrasladoToDelete) return;
    try {
      await deleteMotivoTraslado.mutateAsync({ id: motivoTrasladoToDelete.id });
      toast.success("Registro eliminado", { description: `${motivoTrasladoToDelete.name} se elimino correctamente.` });
      setDeleteOpen(false);
      setMotivoTrasladoToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", { description: getMotivoTrasladoErrorMessage(mutationError, "Error al eliminar registro") });
    }
  };

  const columns = buildMotivoTrasladoTableColumns({
    canReadMotivoTraslado, canUpdateMotivoTraslado, canDeleteMotivoTraslado, isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (item) => { void handleToggleStatus(item); },
    onRequestDelete: (item) => { setMotivoTrasladoToDelete(item); setDeleteOpen(true); },
  });
  const visibilityOptions = buildMotivoTrasladoVisibilityOptions(showActions);
  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters = canReadMotivoTraslado && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription = canReadMotivoTraslado && error
    ? getMotivoTrasladoErrorMessage(error, "No se pudo obtener el listado. Intenta nuevamente.")
    : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    { id: "refresh-motivos-traslado", label: "Actualizar", icon: RotateCcw, isLoading: isFetching, disabled: isFetching, onSelect: () => { if (!isFetching) void refetch(); } },
    { id: "export-motivos-traslado", label: "Exportar", icon: Download, loadingAnimation: "pulse" },
  ];

  const filterSections = [{
    id: "status", label: "Estado",
    options: [
      { id: STATUS_FILTER.ACTIVE, label: "Activos", selected: statusFilter === STATUS_FILTER.ACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.ACTIVE); setPage(1); } },
      { id: STATUS_FILTER.INACTIVE, label: "Inactivos", selected: statusFilter === STATUS_FILTER.INACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.INACTIVE); setPage(1); } },
    ],
  }];

  return (
    <CatalogModuleLayout title="Motivos de Traslado" description="Catalogo de motivos de traslado en ambulancia." icon={<Route className="size-12" />}>
      {!canReadMotivoTraslado ? <AdminReadOnlyNotice message={readOnlyCatalogMessage} /> : null}

      <TableHeaderBar
        search={<TableSearch value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Buscar en la tabla" disabled={!canReadMotivoTraslado} />}
        actions={
          <>
            {canReadMotivoTraslado ? <TableFilterMenu sections={filterSections} appliedCount={appliedFiltersCount} onClear={handleClearFilters} /> : null}
            {canReadMotivoTraslado ? <TableColumnVisibility columns={visibilityOptions} visibility={columnVisibility} onVisibilityChange={setColumnVisibility} /> : null}
            {canReadMotivoTraslado ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreateMotivoTraslado ? (
              <TablePrimaryAction permission="admin:catalogos:motivos_traslado:create" dependencyAware label="Nuevo" icon={<Plus className="size-4" />} onClick={() => setCreateOpen(true)} />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canReadMotivoTraslado && Boolean(error)}
        errorTitle="No se pudo cargar el catalogo"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadMotivoTraslado ? handleOpenDetails : undefined}
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

      <MotivoTrasladoDetailsDialog open={detailsOpen} onOpenChange={setDetailsOpen} onClose={handleCloseDetails} motivoTrasladoSummary={selectedMotivoTraslado} canEdit={canUpdateMotivoTraslado} />
      <MotivoTrasladoCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => { setDeleteOpen(nextOpen); if (!nextOpen) setMotivoTrasladoToDelete(null); }}
        title="Eliminar registro"
        description="Esta accion dara de baja el registro y lo quitara del catalogo."
        onConfirm={() => { void handleDeleteMotivoTraslado(); }}
        confirmDisabled={deleteMotivoTraslado.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default MotivoTrasladoPage;
