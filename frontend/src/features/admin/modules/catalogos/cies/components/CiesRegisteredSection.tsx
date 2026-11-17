import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { useDebounce } from "@shared/hooks/useDebounce";
import { DataTable } from "@features/admin/shared/components/DataTable";
import { TableFilterMenu } from "@features/admin/shared/components/TableFilterMenu";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import {
  TableOptionsMenu,
  type TableOptionItem,
} from "@features/admin/shared/components/TableOptionsMenu";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CIES_TABLE_COLUMNS } from "@features/admin/modules/catalogos/cies/components/CiesTableColumns";
import { useCiesList } from "@features/admin/modules/catalogos/cies/queries/useCiesList";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";

const STATUS_FILTER = {
  ALL: "all",
  ACTIVE: "active",
  INACTIVE: "inactive",
} as const;

type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

/**
 * Claves CIE ya guardadas en el catalogo. La busqueda va al servidor: el
 * CIE-10 oficial ronda 14 mil claves y filtrar solo la pagina cargada no
 * encontraria nada fuera de ella.
 */
export function CiesRegisteredSection() {
  const { hasCapability } = usePermissionDependencies();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(
    STATUS_FILTER.ALL,
  );

  const canReadCies = hasCapability("admin.catalogs.cies.read", {
    allOf: ["admin:catalogos:cies:read"],
  });

  const debouncedSearch = useDebounce(search, 400);
  const normalizedSearch = debouncedSearch.trim();

  const { data, isLoading, isFetching, error, refetch } = useCiesList(
    {
      page,
      pageSize,
      sortBy: "code",
      search: normalizedSearch || undefined,
      isActive:
        statusFilter === STATUS_FILTER.ALL
          ? undefined
          : statusFilter === STATUS_FILTER.ACTIVE,
    },
    { enabled: canReadCies },
  );

  const appliedFiltersCount = statusFilter !== STATUS_FILTER.ALL ? 1 : 0;
  const hasFilters =
    canReadCies && (normalizedSearch.length > 0 || appliedFiltersCount > 0);

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(STATUS_FILTER.ALL);
    setPage(1);
  };

  const selectStatus = (next: StatusFilter) => {
    setStatusFilter(next);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    {
      id: "refresh-cies",
      label: "Actualizar",
      icon: RotateCcw,
      isLoading: isFetching,
      disabled: isFetching,
      onSelect: () => {
        if (isFetching) return;
        void refetch();
      },
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
          onSelect: () => selectStatus(STATUS_FILTER.ACTIVE),
        },
        {
          id: STATUS_FILTER.INACTIVE,
          label: "Inactivos",
          selected: statusFilter === STATUS_FILTER.INACTIVE,
          onSelect: () => selectStatus(STATUS_FILTER.INACTIVE),
        },
      ],
    },
  ];

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-txt-body">
          Claves registradas
        </h2>
        <p className="text-sm text-txt-muted">
          Diagnósticos guardados en el catálogo, los que usa la consulta.
        </p>
      </div>

      {!canReadCies ? (
        <AdminReadOnlyNotice message="No tienes acceso para consultar las claves registradas." />
      ) : null}

      <TableHeaderBar
        search={
          <TableSearch
            value={search}
            onChange={(value) => {
              setSearch(value);
              setPage(1);
            }}
            placeholder="Buscar por clave o descripción"
            disabled={!canReadCies}
          />
        }
        actions={
          canReadCies ? (
            <>
              <TableFilterMenu
                sections={filterSections}
                appliedCount={appliedFiltersCount}
                onClear={handleClearFilters}
              />
              <TableOptionsMenu options={tableOptions} />
            </>
          ) : null
        }
      />

      <DataTable
        columns={CIES_TABLE_COLUMNS}
        rows={canReadCies ? (data?.items ?? []) : []}
        isLoading={canReadCies && (isLoading || search.trim() !== normalizedSearch)}
        isError={canReadCies && Boolean(error)}
        errorTitle="No se pudo cargar el catálogo CIE"
        errorDescription="Intenta nuevamente en unos momentos."
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
        getRowKey={(row) => row.code}
        emptyTitle="Sin claves CIE"
        emptyDescription="Cuando cargues el catálogo con el formulario de arriba, las claves se listarán aquí."
        noResultsTitle="Sin coincidencias"
        noResultsDescription="Prueba con otra clave o parte de la descripción."
      />
    </section>
  );
}
