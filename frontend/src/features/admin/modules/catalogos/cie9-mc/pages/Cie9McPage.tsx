import { useState } from "react";
import { toast } from "sonner";
import { Download, FileText, Plus, RotateCcw, Upload } from "lucide-react";
import { useDebounce } from "@shared/hooks/useDebounce";
import { DataTable } from "@features/admin/shared/components/DataTable";
import {
  TableColumnVisibility,
  type ColumnVisibilityState,
} from "@features/admin/shared/components/TableColumnVisibility";
import { TableFilterMenu } from "@features/admin/shared/components/TableFilterMenu";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import {
  TableOptionsMenu,
  type TableOptionItem,
} from "@features/admin/shared/components/TableOptionsMenu";
import { TablePrimaryAction } from "@features/admin/shared/components/TablePrimaryAction";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { ConfirmDestructiveDialog } from "@features/admin/shared/components/ConfirmDestructiveDialog";
import { useTableDetailsDialog } from "@features/admin/shared/hooks/useTableDetailsDialog";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useDeleteCie9Mc } from "@features/admin/modules/catalogos/cie9-mc/mutations/useDeleteCie9Mc";
import { useUpdateCie9Mc } from "@features/admin/modules/catalogos/cie9-mc/mutations/useUpdateCie9Mc";
import { useCie9McList } from "@features/admin/modules/catalogos/cie9-mc/queries/useCie9McList";
import {
  buildCie9McTableColumns,
  buildCie9McVisibilityOptions,
} from "@features/admin/modules/catalogos/cie9-mc/components/Cie9McTableColumns";
import { Cie9McCreateDialog } from "@features/admin/modules/catalogos/cie9-mc/components/Cie9McCreateDialog";
import { Cie9McDetailsDialog } from "@features/admin/modules/catalogos/cie9-mc/components/Cie9McDetailsDialog";
import { getCie9McErrorMessage } from "@features/admin/modules/catalogos/cie9-mc/utils/cie9-mc.feedback";
import { CatalogImportDialog } from "@features/admin/modules/catalogos/shared/import/CatalogImportDialog";
import { CIE9_MC_IMPORT_CONFIG } from "@features/admin/modules/catalogos/shared/import/catalog-import.config";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { Cie9McListItem } from "@api/types";

const STATUS_FILTER = {
  ALL: "all",
  ACTIVE: "active",
  INACTIVE: "inactive",
} as const;

type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) =>
  String(value ?? "").toLowerCase();

export function Cie9McPage() {
  const { hasCapability } = usePermissionDependencies();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(
    STATUS_FILTER.ALL,
  );
  const [columnVisibility, setColumnVisibility] =
    useState<ColumnVisibilityState>({
      code: true,
      name: true,
      isActive: true,
      actions: true,
    });
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [cie9McToDelete, setCie9McToDelete] =
    useState<Cie9McListItem | null>(null);

  const {
    open: detailsOpen,
    selectedItem: selectedCie9Mc,
    openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails,
    setOpen: setDetailsOpen,
  } = useTableDetailsDialog<Cie9McListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateCie9Mc = useUpdateCie9Mc();
  const deleteCie9Mc = useDeleteCie9Mc();

  const canReadCie9Mc = hasCapability("admin.catalogs.cie9mc.read", {
    allOf: ["admin:catalogos:cie9_mc:read"],
  });
  const canCreateCie9Mc = hasCapability("admin.catalogs.cie9mc.create", {
    allOf: ["admin:catalogos:cie9_mc:create"],
  });
  const canUpdateCie9Mc = hasCapability("admin.catalogs.cie9mc.update", {
    allOf: ["admin:catalogos:cie9_mc:update"],
  });
  const canDeleteCie9Mc = hasCapability("admin.catalogs.cie9mc.delete", {
    allOf: ["admin:catalogos:cie9_mc:delete"],
  });
  const readOnlyCatalogMessage =
    "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useCie9McList(
    {
      page,
      pageSize,
      isActive:
        statusFilter === STATUS_FILTER.ALL
          ? undefined
          : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadCie9Mc },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows =
    normalizedSearch.length === 0
      ? allRows
      : allRows.filter((cie9Mc) => {
          const matchesName = normalizeSearchValue(cie9Mc.name).includes(
            normalizedSearch,
          );
          const matchesCode = normalizeSearchValue(cie9Mc.code).includes(
            normalizedSearch,
          );
          return matchesName || matchesCode;
        });

  const showActions = canReadCie9Mc || canUpdateCie9Mc || canDeleteCie9Mc;
  const isStatusPending = updateCie9Mc.isPending;

  const handleToggleStatus = async (cie9Mc: Cie9McListItem) => {
    const nextStatus = !cie9Mc.isActive;

    try {
      await updateCie9Mc.mutateAsync({
        id: cie9Mc.id,
        data: { isActive: nextStatus },
      });
      toast.success(nextStatus ? "Código activado" : "Código desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", {
        description: getCie9McErrorMessage(
          mutationError,
          "Error al actualizar estado",
        ),
      });
    }
  };

  const handleDeleteCie9Mc = async () => {
    if (!cie9McToDelete) return;

    try {
      await deleteCie9Mc.mutateAsync({ id: cie9McToDelete.id });
      toast.success("Código eliminado", {
        description: `El código ${cie9McToDelete.code} se eliminó correctamente.`,
      });
      setDeleteOpen(false);
      setCie9McToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", {
        description: getCie9McErrorMessage(
          mutationError,
          "Error al eliminar código",
        ),
      });
    }
  };

  const columns = buildCie9McTableColumns({
    canReadCie9Mc,
    canUpdateCie9Mc,
    canDeleteCie9Mc,
    isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (cie9Mc) => {
      void handleToggleStatus(cie9Mc);
    },
    onRequestDelete: (cie9Mc) => {
      setCie9McToDelete(cie9Mc);
      setDeleteOpen(true);
    },
  });
  const visibilityOptions = buildCie9McVisibilityOptions(showActions);

  const visibleColumns = columns.filter(
    (column) => columnVisibility[column.key] ?? true,
  );

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(
    Boolean,
  ).length;

  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters =
    canReadCie9Mc &&
    (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription =
    canReadCie9Mc && error
      ? getCie9McErrorMessage(
          error,
          "No se pudo obtener el listado de CIE-9-MC. Intenta nuevamente.",
        )
      : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    {
      id: "refresh-cie9-mc",
      label: "Actualizar",
      icon: RotateCcw,
      isLoading: isFetching,
      disabled: isFetching,
      onSelect: () => {
        if (isFetching) return;
        void refetch();
      },
    },
    {
      id: "export-cie9-mc",
      label: "Exportar",
      icon: Download,
      loadingAnimation: "pulse",
    },
    {
      id: "import-cie9-mc",
      label: "Importar Excel",
      icon: Upload,
      disabled: !canCreateCie9Mc,
      onSelect: () => setImportOpen(true),
    },
  ];

  const filterSections = [
    {
      id: "status",
      label: "Estado",
      options: [
        {
          id: STATUS_FILTER.ACTIVE,
          label: "Activos",
          selected: statusFilter === STATUS_FILTER.ACTIVE,
          onSelect: () => {
            setStatusFilter(STATUS_FILTER.ACTIVE);
            setPage(1);
          },
        },
        {
          id: STATUS_FILTER.INACTIVE,
          label: "Inactivos",
          selected: statusFilter === STATUS_FILTER.INACTIVE,
          onSelect: () => {
            setStatusFilter(STATUS_FILTER.INACTIVE);
            setPage(1);
          },
        },
      ],
    },
  ];

  return (
    <CatalogModuleLayout
      title="Catálogo CIE-9-MC"
      description="Códigos de procedimientos CIE-9-MC (NOM-024), complementa al catálogo CIE-10 de diagnósticos."
      icon={<FileText className="size-12" />}
    >
      {!canReadCie9Mc ? (
        <AdminReadOnlyNotice message={readOnlyCatalogMessage} />
      ) : null}

      <TableHeaderBar
        search={
          <TableSearch
            value={search}
            onChange={(value) => {
              setSearch(value);
              setPage(1);
            }}
            placeholder="Buscar en la tabla"
            disabled={!canReadCie9Mc}
          />
        }
        actions={
          <>
            {canReadCie9Mc ? (
              <TableFilterMenu
                sections={filterSections}
                appliedCount={appliedFiltersCount}
                onClear={handleClearFilters}
              />
            ) : null}
            {canReadCie9Mc ? (
              <TableColumnVisibility
                columns={visibilityOptions}
                visibility={columnVisibility}
                onVisibilityChange={setColumnVisibility}
              />
            ) : null}
            {canReadCie9Mc ? (
              <TableOptionsMenu options={tableOptions} />
            ) : null}
            {canCreateCie9Mc ? (
              <TablePrimaryAction
                permission="admin:catalogos:cie9_mc:create"
                dependencyAware
                label="Nuevo"
                icon={<Plus className="size-4" />}
                onClick={() => setCreateOpen(true)}
              />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canReadCie9Mc && Boolean(error)}
        errorTitle="No se pudo cargar CIE-9-MC"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadCie9Mc ? handleOpenDetails : undefined}
        onRetry={() => {
          void refetch();
        }}
        onClearFilters={handleClearFilters}
        pagination={{
          page,
          pageSize,
          total: data?.total ?? 0,
          totalPages: data?.totalPages ?? 1,
          onPageChange: setPage,
          onPageSizeChange: (value) => {
            setPageSize(value);
            setPage(1);
          },
        }}
        getRowKey={(row) => row.id.toString()}
        emptyTitle="Sin códigos CIE-9-MC"
        emptyDescription="Cuando existan códigos registrados se listarán aquí. Usa 'Importar Excel' para cargar el catálogo oficial."
      />

      <Cie9McDetailsDialog
        open={detailsOpen}
        onOpenChange={setDetailsOpen}
        onClose={handleCloseDetails}
        cie9McSummary={selectedCie9Mc}
        canEdit={canUpdateCie9Mc}
      />

      <Cie9McCreateDialog open={createOpen} onOpenChange={setCreateOpen} />

      <CatalogImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        config={CIE9_MC_IMPORT_CONFIG}
        onImported={() => void refetch()}
      />

      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => {
          setDeleteOpen(nextOpen);
          if (!nextOpen) {
            setCie9McToDelete(null);
          }
        }}
        title="Eliminar código CIE-9-MC"
        description="Esta acción dará de baja el código y lo quitará del catálogo."
        onConfirm={() => {
          void handleDeleteCie9Mc();
        }}
        confirmDisabled={deleteCie9Mc.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default Cie9McPage;
