import { useState } from "react";
import { toast } from "sonner";
import { Download, Plus, RotateCcw, UserCog } from "lucide-react";
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
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { DesignacionFormDialog } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionFormDialog";
import {
  buildDesignacionTableColumns,
  buildDesignacionVisibilityOptions,
} from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionTableColumns";
import { useRevokeDesignacion } from "@features/admin/modules/catalogos/designacion-autorizadores/mutations/useRevokeDesignacion";
import { useDesignacionesList } from "@features/admin/modules/catalogos/designacion-autorizadores/queries/useDesignacionesList";
import { getDesignacionErrorMessage } from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.feedback";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { DesignacionItem } from "@api/types";

const STATUS_FILTER = {
  ALL: "all",
  ACTIVE: "active",
  INACTIVE: "inactive",
} as const;

type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

export function DesignacionAutorizadoresPage() {
  const { hasCapability } = usePermissionDependencies();

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(STATUS_FILTER.ALL);

  const [columnVisibility, setColumnVisibility] = useState<ColumnVisibilityState>({
    user: true,
    tipo: true,
    cargo: true,
    alcance: true,
    vigencia: true,
    vigente: true,
    actions: true,
  });

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<DesignacionItem | null>(null);
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [itemToRevoke, setItemToRevoke] = useState<DesignacionItem | null>(null);

  const debouncedSearch = useDebounce(search, 400);
  const revokeDesignacion = useRevokeDesignacion();

  const canRead = hasCapability("admin.catalogs.designacionAutorizadores.read", {
    allOf: ["admin:autorizadores:designacion:read"],
  });
  const canWrite = hasCapability("admin.catalogs.designacionAutorizadores.write", {
    allOf: ["admin:autorizadores:designacion:write"],
  });
  const canGrantGlobal = hasCapability("admin.catalogs.designacionAutorizadores.global", {
    allOf: ["admin:autorizadores:designacion:global"],
  });

  const { data, isLoading, isFetching, error, refetch } = useDesignacionesList(
    {
      page,
      pageSize,
      search: debouncedSearch.trim() || undefined,
      isActive:
        statusFilter === STATUS_FILTER.ALL ? undefined : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canRead },
  );

  const rows = data?.items ?? [];

  const handleOpenCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const handleOpenEdit = (item: DesignacionItem) => {
    setEditing(item);
    setFormOpen(true);
  };

  const handleRevoke = async () => {
    if (!itemToRevoke) return;

    try {
      await revokeDesignacion.mutateAsync({ id: itemToRevoke.id });
      toast.success("Designación dada de baja", {
        description: `La designación de ${itemToRevoke.user.name} se dio de baja correctamente.`,
      });
      setRevokeOpen(false);
      setItemToRevoke(null);
    } catch (mutationError) {
      toast.error("No se pudo dar de baja", {
        description: getDesignacionErrorMessage(mutationError, "Error al dar de baja la designación"),
      });
    }
  };

  const columns = buildDesignacionTableColumns({
    canWrite,
    onEdit: handleOpenEdit,
    onRequestRevoke: (item) => {
      setItemToRevoke(item);
      setRevokeOpen(true);
    },
  });
  const visibilityOptions = buildDesignacionVisibilityOptions(canWrite);
  const visibleColumns = columns.filter((column) => columnVisibility[column.key] ?? true);

  const appliedFiltersCount = [statusFilter !== STATUS_FILTER.ALL].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters = canRead && (Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0);

  const tableErrorDescription =
    canRead && error
      ? getDesignacionErrorMessage(
          error,
          "No se pudo obtener el listado de designaciones. Intenta nuevamente.",
        )
      : undefined;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    {
      id: "refresh-designaciones",
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
      id: "export-designaciones",
      label: "Exportar",
      icon: Download,
      loadingAnimation: "pulse",
    },
  ];

  const selectStatus = (next: StatusFilter) => () => {
    setStatusFilter(next);
    setPage(1);
  };

  const filterSections = [
    {
      id: "status",
      label: "Estado",
      options: [
        {
          id: STATUS_FILTER.ACTIVE,
          label: "Activas",
          selected: statusFilter === STATUS_FILTER.ACTIVE,
          onSelect: selectStatus(STATUS_FILTER.ACTIVE),
        },
        {
          id: STATUS_FILTER.INACTIVE,
          label: "Inactivas",
          selected: statusFilter === STATUS_FILTER.INACTIVE,
          onSelect: selectStatus(STATUS_FILTER.INACTIVE),
        },
        {
          id: STATUS_FILTER.ALL,
          label: "Todas",
          selected: statusFilter === STATUS_FILTER.ALL,
          onSelect: selectStatus(STATUS_FILTER.ALL),
        },
      ],
    },
  ];

  return (
    <CatalogModuleLayout
      title="Designación de autorizadores"
      description="Define quién puede autorizar cada tipo de acción, en qué centros y por cuánto tiempo."
      icon={<UserCog className="size-12" />}
    >
      {!canRead ? (
        <AdminReadOnlyNotice message="No tienes acceso para consultar las designaciones de autorizadores." />
      ) : null}

      <TableHeaderBar
        search={
          <TableSearch
            value={search}
            onChange={(value) => {
              setSearch(value);
              setPage(1);
            }}
            placeholder="Buscar por usuario o cargo"
            disabled={!canRead}
          />
        }
        actions={
          <>
            {canRead ? (
              <TableFilterMenu
                sections={filterSections}
                appliedCount={appliedFiltersCount}
                onClear={handleClearFilters}
              />
            ) : null}

            {canRead ? (
              <TableColumnVisibility
                columns={visibilityOptions}
                visibility={columnVisibility}
                onVisibilityChange={setColumnVisibility}
              />
            ) : null}

            {canRead ? <TableOptionsMenu options={tableOptions} /> : null}

            {canWrite ? (
              <TablePrimaryAction
                permission="admin:autorizadores:designacion:write"
                dependencyAware
                label="Nueva"
                icon={<Plus className="size-4" />}
                onClick={handleOpenCreate}
              />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading || isSearchPending}
        isError={canRead && Boolean(error)}
        errorTitle="No se pudo cargar las designaciones"
        errorDescription={tableErrorDescription}
        hasFilters={hasFilters}
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
        emptyTitle="Sin designaciones"
        emptyDescription="Cuando existan designaciones de autorizadores se listarán aquí."
      />

      <DesignacionFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        designation={editing}
        canGrantGlobal={canGrantGlobal}
      />

      <ConfirmDestructiveDialog
        open={revokeOpen}
        onOpenChange={(nextOpen) => {
          setRevokeOpen(nextOpen);
          if (!nextOpen) setItemToRevoke(null);
        }}
        title="Dar de baja designación"
        description="El usuario dejará de poder autorizar con esta designación. Se conserva el historial."
        onConfirm={() => {
          void handleRevoke();
        }}
        confirmDisabled={revokeDesignacion.isPending}
      />
    </CatalogModuleLayout>
  );
}

export default DesignacionAutorizadoresPage;
