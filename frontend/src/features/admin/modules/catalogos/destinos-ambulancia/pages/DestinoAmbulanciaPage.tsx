import { useState } from "react";
import { toast } from "sonner";
import { MapPin, Download, Plus, RotateCcw } from "lucide-react";
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
import { useDeleteDestinoAmbulancia } from "@features/admin/modules/catalogos/destinos-ambulancia/mutations/useDeleteDestinoAmbulancia";
import { useUpdateDestinoAmbulancia } from "@features/admin/modules/catalogos/destinos-ambulancia/mutations/useUpdateDestinoAmbulancia";
import { useDestinoAmbulanciaList } from "@features/admin/modules/catalogos/destinos-ambulancia/queries/useDestinoAmbulanciaList";
import {
  buildDestinoAmbulanciaTableColumns,
  buildDestinoAmbulanciaVisibilityOptions,
} from "@features/admin/modules/catalogos/destinos-ambulancia/components/DestinoAmbulanciaTableColumns";
import { DestinoAmbulanciaCreateDialog } from "@features/admin/modules/catalogos/destinos-ambulancia/components/DestinoAmbulanciaCreateDialog";
import { DestinoAmbulanciaDetailsDialog } from "@features/admin/modules/catalogos/destinos-ambulancia/components/DestinoAmbulanciaDetailsDialog";
import { getDestinoAmbulanciaErrorMessage } from "@features/admin/modules/catalogos/destinos-ambulancia/utils/destinos-ambulancia.feedback";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { DestinoAmbulanciaListItem } from "@api/types";

const STATUS_FILTER = { ALL: "all", ACTIVE: "active", INACTIVE: "inactive" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) => String(value ?? "").toLowerCase();

export function DestinoAmbulanciaPage() {
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
  const [destinoAmbulanciaToDelete, setDestinoAmbulanciaToDelete] = useState<DestinoAmbulanciaListItem | null>(null);

  const {
    open: detailsOpen, selectedItem: selectedDestinoAmbulancia, openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails, setOpen: setDetailsOpen,
  } = useTableDetailsDialog<DestinoAmbulanciaListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateDestinoAmbulancia = useUpdateDestinoAmbulancia();
  const deleteDestinoAmbulancia = useDeleteDestinoAmbulancia();

  const canReadDestinoAmbulancia = hasCapability("admin.catalogs.destinosambulancia.read", { allOf: ["admin:catalogos:destinos_ambulancia:read"] });
  const canCreateDestinoAmbulancia = hasCapability("admin.catalogs.destinosambulancia.create", { allOf: ["admin:catalogos:destinos_ambulancia:create"] });
  const canUpdateDestinoAmbulancia = hasCapability("admin.catalogs.destinosambulancia.update", { allOf: ["admin:catalogos:destinos_ambulancia:update"] });
  const canDeleteDestinoAmbulancia = hasCapability("admin.catalogs.destinosambulancia.delete", { allOf: ["admin:catalogos:destinos_ambulancia:delete"] });
  const readOnlyCatalogMessage = "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useDestinoAmbulanciaList(
    {
      page, pageSize,
      isActive: statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadDestinoAmbulancia },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows = normalizedSearch.length === 0
    ? allRows
    : allRows.filter((item) => normalizeSearchValue(item.name).includes(normalizedSearch));

  const showActions = canReadDestinoAmbulancia || canUpdateDestinoAmbulancia || canDeleteDestinoAmbulancia;
  const isStatusPending = updateDestinoAmbulancia.isPending;

  const handleToggleStatus = async (item: DestinoAmbulanciaListItem) => {
    const nextStatus = !item.isActive;
    try {
      await updateDestinoAmbulancia.mutateAsync({ id: item.id, data: { isActive: nextStatus } });
      toast.success(nextStatus ? "Destino activado" : "Destino desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", { description: getDestinoAmbulanciaErrorMessage(mutationError, "Error al actualizar estado") });
    }
  };

  const handleDeleteDestinoAmbulancia = async () => {
    if (!destinoAmbulanciaToDelete) return;
    try {
      await deleteDestinoAmbulancia.mutateAsync({ id: destinoAmbulanciaToDelete.id });
      toast.success("Destino eliminado", { description: `${destinoAmbulanciaToDelete.name} se elimino correctamente.` });
      setDeleteOpen(false);
      setDestinoAmbulanciaToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", { description: getDestinoAmbulanciaErrorMessage(mutationError, "Error al eliminar destino") });
    }
  };

  const columns = buildDestinoAmbulanciaTableColumns({
    canReadDestinoAmbulancia, canUpdateDestinoAmbulancia, canDeleteDestinoAmbulancia, isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (item) => { void handleToggleStatus(item); },
    onRequestDelete: (item) => { setDestinoAmbulanciaToDelete(item); setDeleteOpen(true); },
  });
  const visibilityOptions = buildDestinoAmbulanciaVisibilityOptions(showActions);
  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters = canReadDestinoAmbulancia && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription = canReadDestinoAmbulancia && error
    ? getDestinoAmbulanciaErrorMessage(error, "No se pudo obtener el listado. Intenta nuevamente.")
    : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    { id: "refresh-destinos-ambulancia", label: "Actualizar", icon: RotateCcw, isLoading: isFetching, disabled: isFetching, onSelect: () => { if (!isFetching) void refetch(); } },
    { id: "export-destinos-ambulancia", label: "Exportar", icon: Download, loadingAnimation: "pulse" },
  ];

  const filterSections = [{
    id: "status", label: "Estado",
    options: [
      { id: STATUS_FILTER.ACTIVE, label: "Activos", selected: statusFilter === STATUS_FILTER.ACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.ACTIVE); setPage(1); } },
      { id: STATUS_FILTER.INACTIVE, label: "Inactivos", selected: statusFilter === STATUS_FILTER.INACTIVE, onSelect: () => { setStatusFilter(STATUS_FILTER.INACTIVE); setPage(1); } },
    ],
  }];

  return (
    <CatalogModuleLayout title="Destinos de Ambulancia" description="Catalogo de destinos internos para traslados en ambulancia." icon={<MapPin className="size-12" />}>
      {!canReadDestinoAmbulancia ? <AdminReadOnlyNotice message={readOnlyCatalogMessage} /> : null}

      <TableHeaderBar
        search={<TableSearch value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Buscar en la tabla" disabled={!canReadDestinoAmbulancia} />}
        actions={
          <>
            {canReadDestinoAmbulancia ? <TableFilterMenu sections={filterSections} appliedCount={appliedFiltersCount} onClear={handleClearFilters} /> : null}
            {canReadDestinoAmbulancia ? <TableColumnVisibility columns={visibilityOptions} visibility={columnVisibility} onVisibilityChange={setColumnVisibility} /> : null}
            {canReadDestinoAmbulancia ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreateDestinoAmbulancia ? (
              <TablePrimaryAction permission="admin:catalogos:destinos_ambulancia:create" dependencyAware label="Nuevo" icon={<Plus className="size-4" />} onClick={() => setCreateOpen(true)} />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canReadDestinoAmbulancia && Boolean(error)}
        errorTitle="No se pudo cargar el catalogo"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadDestinoAmbulancia ? handleOpenDetails : undefined}
        onRetry={() => { void refetch(); }}
        onClearFilters={handleClearFilters}
        pagination={{
          page, pageSize, total: data?.total ?? 0, totalPages: data?.totalPages ?? 1,
          onPageChange: setPage,
          onPageSizeChange: (value) => { setPageSize(value); setPage(1); },
        }}
        getRowKey={(row) => row.id.toString()}
        emptyTitle="Sin destinos"
        emptyDescription="Cuando existan destinos registrados se listaran aqui."
      />

      <DestinoAmbulanciaDetailsDialog open={detailsOpen} onOpenChange={setDetailsOpen} onClose={handleCloseDetails} destinoAmbulanciaSummary={selectedDestinoAmbulancia} canEdit={canUpdateDestinoAmbulancia} />
      <DestinoAmbulanciaCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => { setDeleteOpen(nextOpen); if (!nextOpen) setDestinoAmbulanciaToDelete(null); }}
        title="Eliminar destino"
        description="Esta accion dara de baja el destino y lo quitara del catalogo."
        onConfirm={() => { void handleDeleteDestinoAmbulancia(); }}
        confirmDisabled={deleteDestinoAmbulancia.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default DestinoAmbulanciaPage;
