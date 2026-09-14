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
import { useDeleteMotivoCancelacionCirugia } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/mutations/useDeleteMotivoCancelacionCirugia";
import { useUpdateMotivoCancelacionCirugia } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/mutations/useUpdateMotivoCancelacionCirugia";
import { useMotivoCancelacionCirugiaList } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/queries/useMotivoCancelacionCirugiaList";
import {
  buildMotivoCancelacionCirugiaTableColumns,
  buildMotivoCancelacionCirugiaVisibilityOptions,
} from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/components/MotivoCancelacionCirugiaTableColumns";
import { MotivoCancelacionCirugiaCreateDialog } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/components/MotivoCancelacionCirugiaCreateDialog";
import { MotivoCancelacionCirugiaDetailsDialog } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/components/MotivoCancelacionCirugiaDetailsDialog";
import { getMotivoCancelacionCirugiaErrorMessage } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/utils/motivos-cancelacion-cirugia.feedback";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { MotivoCancelacionCirugiaListItem } from "@api/types";

const STATUS_FILTER = { ALL: "all", ACTIVE: "active", INACTIVE: "inactive" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) => String(value ?? "").toLowerCase();

export function MotivoCancelacionCirugiaPage() {
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
  const [motivoCancelacionCirugiaToDelete, setMotivoCancelacionCirugiaToDelete] = useState<MotivoCancelacionCirugiaListItem | null>(null);

  const {
    open: detailsOpen, selectedItem: selectedMotivoCancelacionCirugia, openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails, setOpen: setDetailsOpen,
  } = useTableDetailsDialog<MotivoCancelacionCirugiaListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateMotivoCancelacionCirugia = useUpdateMotivoCancelacionCirugia();
  const deleteMotivoCancelacionCirugia = useDeleteMotivoCancelacionCirugia();

  const canReadMotivoCancelacionCirugia = hasCapability("admin.catalogs.motivoscancelacioncirugia.read", { allOf: ["admin:catalogos:motivos_cancelacion_cirugia:read"] });
  const canCreateMotivoCancelacionCirugia = hasCapability("admin.catalogs.motivoscancelacioncirugia.create", { allOf: ["admin:catalogos:motivos_cancelacion_cirugia:create"] });
  const canUpdateMotivoCancelacionCirugia = hasCapability("admin.catalogs.motivoscancelacioncirugia.update", { allOf: ["admin:catalogos:motivos_cancelacion_cirugia:update"] });
  const canDeleteMotivoCancelacionCirugia = hasCapability("admin.catalogs.motivoscancelacioncirugia.delete", { allOf: ["admin:catalogos:motivos_cancelacion_cirugia:delete"] });
  const readOnlyCatalogMessage = "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useMotivoCancelacionCirugiaList(
    {
      page, pageSize,
      isActive: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadMotivoCancelacionCirugia },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows = normalizedSearch.length === 0
    ? allRows
    : allRows.filter((item) => normalizeSearchValue(item.name).includes(normalizedSearch));

  const showActions = canReadMotivoCancelacionCirugia || canUpdateMotivoCancelacionCirugia || canDeleteMotivoCancelacionCirugia;
  const isStatusPending = updateMotivoCancelacionCirugia.isPending;

  const handleToggleStatus = async (item: MotivoCancelacionCirugiaListItem) => {
    const nextStatus = !item.isActive;
    try {
      await updateMotivoCancelacionCirugia.mutateAsync({ id: item.id, data: { isActive: nextStatus } });
      toast.success(nextStatus ? "Registro activado" : "Registro desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", { description: getMotivoCancelacionCirugiaErrorMessage(mutationError, "Error al actualizar estado") });
    }
  };

  const handleDeleteMotivoCancelacionCirugia = async () => {
    if (!motivoCancelacionCirugiaToDelete) return;
    try {
      await deleteMotivoCancelacionCirugia.mutateAsync({ id: motivoCancelacionCirugiaToDelete.id });
      toast.success("Registro eliminado", { description: `${motivoCancelacionCirugiaToDelete.name} se elimino correctamente.` });
      setDeleteOpen(false);
      setMotivoCancelacionCirugiaToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", { description: getMotivoCancelacionCirugiaErrorMessage(mutationError, "Error al eliminar registro") });
    }
  };

  const columns = buildMotivoCancelacionCirugiaTableColumns({
    canReadMotivoCancelacionCirugia, canUpdateMotivoCancelacionCirugia, canDeleteMotivoCancelacionCirugia, isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (item) => { void handleToggleStatus(item); },
    onRequestDelete: (item) => { setMotivoCancelacionCirugiaToDelete(item); setDeleteOpen(true); },
  });
  const visibilityOptions = buildMotivoCancelacionCirugiaVisibilityOptions(showActions);
  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters = canReadMotivoCancelacionCirugia && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription = canReadMotivoCancelacionCirugia && error
    ? getMotivoCancelacionCirugiaErrorMessage(error, "No se pudo obtener el listado. Intenta nuevamente.")
    : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    { id: "refresh-motivos-cancelacion-cirugia", label: "Actualizar", icon: RotateCcw, isLoading: isFetching, disabled: isFetching, onSelect: () => { if (!isFetching) void refetch(); } },
    { id: "export-motivos-cancelacion-cirugia", label: "Exportar", icon: Download, loadingAnimation: "pulse" },
  ];

  const filterSections = [{
    id: "status", label: "Estado",
    options: [
      { id: STATUS_FILTER.ACTIVE, label: "Activos", selected: statusFilter === STATUS_FILTER.ACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.ACTIVE); setPage(1); } },
      { id: STATUS_FILTER.INACTIVE, label: "Inactivos", selected: statusFilter === STATUS_FILTER.INACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.INACTIVE); setPage(1); } },
    ],
  }];

  return (
    <CatalogModuleLayout title="Motivos de Cancelación de Cirugía" description="Catalogo de motivos de cancelación de cirugía." icon={<XCircle className="size-12" />}>
      {!canReadMotivoCancelacionCirugia ? <AdminReadOnlyNotice message={readOnlyCatalogMessage} /> : null}

      <TableHeaderBar
        search={<TableSearch value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Buscar en la tabla" disabled={!canReadMotivoCancelacionCirugia} />}
        actions={
          <>
            {canReadMotivoCancelacionCirugia ? <TableFilterMenu sections={filterSections} appliedCount={appliedFiltersCount} onClear={handleClearFilters} /> : null}
            {canReadMotivoCancelacionCirugia ? <TableColumnVisibility columns={visibilityOptions} visibility={columnVisibility} onVisibilityChange={setColumnVisibility} /> : null}
            {canReadMotivoCancelacionCirugia ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreateMotivoCancelacionCirugia ? (
              <TablePrimaryAction permission="admin:catalogos:motivos_cancelacion_cirugia:create" dependencyAware label="Nuevo" icon={<Plus className="size-4" />} onClick={() => setCreateOpen(true)} />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canReadMotivoCancelacionCirugia && Boolean(error)}
        errorTitle="No se pudo cargar el catalogo"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadMotivoCancelacionCirugia ? handleOpenDetails : undefined}
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

      <MotivoCancelacionCirugiaDetailsDialog open={detailsOpen} onOpenChange={setDetailsOpen} onClose={handleCloseDetails} motivoCancelacionCirugiaSummary={selectedMotivoCancelacionCirugia} canEdit={canUpdateMotivoCancelacionCirugia} />
      <MotivoCancelacionCirugiaCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => { setDeleteOpen(nextOpen); if (!nextOpen) setMotivoCancelacionCirugiaToDelete(null); }}
        title="Eliminar registro"
        description="Esta accion dara de baja el registro y lo quitara del catalogo."
        onConfirm={() => { void handleDeleteMotivoCancelacionCirugia(); }}
        confirmDisabled={deleteMotivoCancelacionCirugia.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default MotivoCancelacionCirugiaPage;
