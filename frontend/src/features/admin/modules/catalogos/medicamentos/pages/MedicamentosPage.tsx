import { useState } from "react";
import { toast } from "sonner";
import { Download, Pill, Plus, RotateCcw, Upload } from "lucide-react";
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
import { useDeleteMedicamento } from "@features/admin/modules/catalogos/medicamentos/mutations/useDeleteMedicamento";
import { useUpdateMedicamento } from "@features/admin/modules/catalogos/medicamentos/mutations/useUpdateMedicamento";
import { useMedicamentosList } from "@features/admin/modules/catalogos/medicamentos/queries/useMedicamentosList";
import {
  buildMedicamentosTableColumns,
  buildMedicamentosVisibilityOptions,
} from "@features/admin/modules/catalogos/medicamentos/components/MedicamentosTableColumns";
import { MedicamentoCreateDialog } from "@features/admin/modules/catalogos/medicamentos/components/MedicamentoCreateDialog";
import { MedicamentoDetailsDialog } from "@features/admin/modules/catalogos/medicamentos/components/MedicamentoDetailsDialog";
import { getMedicamentoErrorMessage } from "@features/admin/modules/catalogos/medicamentos/utils/medicamentos.feedback";
import { CatalogImportDialog } from "@features/admin/modules/catalogos/shared/import/CatalogImportDialog";
import { MEDICAMENTOS_IMPORT_CONFIG } from "@features/admin/modules/catalogos/shared/import/catalog-import.config";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { MedicamentoListItem } from "@api/types";

const STATUS_FILTER = {
  ALL: "all",
  ACTIVE: "active",
  INACTIVE: "inactive",
} as const;

type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const normalizeSearchValue = (value: string | number | null | undefined) =>
  String(value ?? "").toLowerCase();

export function MedicamentosPage() {
  const { hasCapability } = usePermissionDependencies();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(STATUS_FILTER.ALL);
  const [columnVisibility, setColumnVisibility] = useState<ColumnVisibilityState>({
    code: true,
    name: true,
    genericName: true,
    cuadroBasico: true,
    isControlled: true,
    maxQuantity: true,
    isActive: true,
    actions: true,
  });
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [medicamentoToDelete, setMedicamentoToDelete] =
    useState<MedicamentoListItem | null>(null);

  const {
    open: detailsOpen,
    selectedItem: selectedMedicamento,
    openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails,
    setOpen: setDetailsOpen,
  } = useTableDetailsDialog<MedicamentoListItem>();

  const debouncedSearch = useDebounce(search, 400);
  const updateMedicamento = useUpdateMedicamento();
  const deleteMedicamento = useDeleteMedicamento();

  const canReadMedicamento = hasCapability("admin.catalogs.medicamentos.read", {
    allOf: ["admin:catalogos:medicamentos:read"],
  });
  const canCreateMedicamento = hasCapability("admin.catalogs.medicamentos.create", {
    allOf: ["admin:catalogos:medicamentos:create"],
  });
  const canUpdateMedicamento = hasCapability("admin.catalogs.medicamentos.update", {
    allOf: ["admin:catalogos:medicamentos:update"],
  });
  const canDeleteMedicamento = hasCapability("admin.catalogs.medicamentos.delete", {
    allOf: ["admin:catalogos:medicamentos:delete"],
  });
  const readOnlyCatalogMessage = "No tienes acceso para consultar este catalogo.";

  const { data, isLoading, isFetching, error, refetch } = useMedicamentosList(
    {
      page,
      pageSize,
      isActive:
        statusFilter === STATUS_FILTER.ALL
          ? undefined
          : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadMedicamento },
  );

  const allRows = data?.items ?? [];
  const normalizedSearch = debouncedSearch.trim().toLowerCase();
  const rows =
    normalizedSearch.length === 0
      ? allRows
      : allRows.filter((medicamento) =>
          [medicamento.name, medicamento.code, medicamento.genericName].some((value) =>
            normalizeSearchValue(value).includes(normalizedSearch),
          ),
        );

  const showActions = canReadMedicamento || canUpdateMedicamento || canDeleteMedicamento;
  const isStatusPending = updateMedicamento.isPending;

  const handleToggleStatus = async (medicamento: MedicamentoListItem) => {
    const nextStatus = !medicamento.isActive;

    try {
      await updateMedicamento.mutateAsync({
        id: medicamento.id,
        data: { isActive: nextStatus },
      });
      toast.success(nextStatus ? "Medicamento activado" : "Medicamento desactivado");
    } catch (mutationError) {
      toast.error("No se pudo actualizar el estado", {
        description: getMedicamentoErrorMessage(mutationError, "Error al actualizar estado"),
      });
    }
  };

  const handleDeleteMedicamento = async () => {
    if (!medicamentoToDelete) return;

    try {
      await deleteMedicamento.mutateAsync({ id: medicamentoToDelete.id });
      toast.success("Medicamento eliminado", {
        description: `El medicamento ${medicamentoToDelete.name} se elimino correctamente.`,
      });
      setDeleteOpen(false);
      setMedicamentoToDelete(null);
    } catch (mutationError) {
      toast.error("No se pudo eliminar", {
        description: getMedicamentoErrorMessage(mutationError, "Error al eliminar medicamento"),
      });
    }
  };

  const columns = buildMedicamentosTableColumns({
    canReadMedicamento,
    canUpdateMedicamento,
    canDeleteMedicamento,
    isStatusPending,
    onOpenDetails: handleOpenDetails,
    onToggleStatus: (medicamento) => {
      void handleToggleStatus(medicamento);
    },
    onRequestDelete: (medicamento) => {
      setMedicamentoToDelete(medicamento);
      setDeleteOpen(true);
    },
  });
  const visibilityOptions = buildMedicamentosVisibilityOptions(showActions);

  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;

  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters =
    canReadMedicamento && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);
  const tableErrorDescription =
    canReadMedicamento && error
      ? getMedicamentoErrorMessage(
          error,
          "No se pudo obtener el listado de medicamentos. Intenta nuevamente.",
        )
      : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    {
      id: "refresh-medicamentos",
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
      id: "export-medicamentos",
      label: "Exportar",
      icon: Download,
      loadingAnimation: "pulse",
    },
    {
      id: "import-medicamentos",
      label: "Importar Excel",
      icon: Upload,
      disabled: !canCreateMedicamento,
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
      title="Medicamentos"
      description="Catalogo de medicamentos que el medico puede recetar."
      icon={<Pill className="size-12" />}
    >
      {!canReadMedicamento ? <AdminReadOnlyNotice message={readOnlyCatalogMessage} /> : null}

      <TableHeaderBar
        search={
          <TableSearch
            value={search}
            onChange={(value) => {
              setSearch(value);
              setPage(1);
            }}
            placeholder="Buscar en la tabla"
            disabled={!canReadMedicamento}
          />
        }
        actions={
          <>
            {canReadMedicamento ? (
              <TableFilterMenu
                sections={filterSections}
                appliedCount={appliedFiltersCount}
                onClear={handleClearFilters}
              />
            ) : null}
            {canReadMedicamento ? (
              <TableColumnVisibility
                columns={visibilityOptions}
                visibility={columnVisibility}
                onVisibilityChange={setColumnVisibility}
              />
            ) : null}
            {canReadMedicamento ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreateMedicamento ? (
              <TablePrimaryAction
                permission="admin:catalogos:medicamentos:create"
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
        isError={canReadMedicamento && Boolean(error)}
        errorTitle="No se pudo cargar medicamentos"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
        onRowClick={canReadMedicamento ? handleOpenDetails : undefined}
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
        emptyTitle="Sin medicamentos"
        emptyDescription="Cuando existan medicamentos registrados se listaran aqui."
      />

      <MedicamentoDetailsDialog
        open={detailsOpen}
        onOpenChange={setDetailsOpen}
        onClose={handleCloseDetails}
        medicamentoSummary={selectedMedicamento}
        canEdit={canUpdateMedicamento}
      />

      <MedicamentoCreateDialog open={createOpen} onOpenChange={setCreateOpen} />

      <CatalogImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        config={MEDICAMENTOS_IMPORT_CONFIG}
        onImported={() => void refetch()}
      />

      <ConfirmDestructiveDialog
        open={deleteOpen}
        onOpenChange={(nextOpen) => {
          setDeleteOpen(nextOpen);
          if (!nextOpen) {
            setMedicamentoToDelete(null);
          }
        }}
        title="Eliminar medicamento"
        description="Esta accion dara de baja el medicamento y ya no se podra recetar."
        onConfirm={() => {
          void handleDeleteMedicamento();
        }}
        confirmDisabled={deleteMedicamento.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default MedicamentosPage;
