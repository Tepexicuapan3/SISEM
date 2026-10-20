import { useEffect, useState } from "react";
import { useDebounce } from "@shared/hooks/useDebounce";
import { DataTable } from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { useLegacyMedicosList } from "@features/admin/modules/medicos/hooks/useMedicos";
import { buildLegacyMedicosColumns } from "@features/admin/modules/medicos/components/legado/LegacyMedicoTableColumns";

const DEFAULT_PAGE_SIZE = 20;

interface LegacyMedicosTabProps {
  canRead: boolean;
}

/** Archivo legado de médicos: listado de solo lectura con búsqueda y paginación en servidor. */
export function LegacyMedicosTab({ canRead }: LegacyMedicosTabProps) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const debouncedSearch = useDebounce(search, 400);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  const { data, isLoading, error, refetch } = useLegacyMedicosList(
    { search: debouncedSearch.trim() || undefined, page, pageSize },
    { enabled: canRead },
  );

  const rows = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasSearch = Boolean(debouncedSearch.trim());
  const columns = buildLegacyMedicosColumns();

  return (
    <div className="space-y-4">
      <TableHeaderBar
        search={
          <TableSearch
            value={search}
            onChange={setSearch}
            placeholder="Buscar por nombre, clave RH, cédula o No. Médico"
            disabled={!canRead}
          />
        }
      />
      <DataTable
        columns={columns}
        rows={rows}
        isLoading={isLoading}
        isError={canRead && Boolean(error)}
        errorTitle="No se pudo cargar el archivo legado"
        hasFilters={hasSearch}
        onRetry={() => void refetch()}
        onClearFilters={() => setSearch("")}
        getRowKey={(row) => row.noMedico.toString()}
        emptyTitle="Aún no se ha cargado el padrón del legado"
        emptyDescription="El archivo legado se carga por SQL; cuando exista, aparecerá aquí en modo solo lectura."
        minWidthClassName="min-w-[1100px]"
        pagination={
          total > 0
            ? {
                page: data?.page ?? page,
                pageSize: data?.pageSize ?? pageSize,
                total,
                totalPages: data?.totalPages ?? 1,
                onPageChange: setPage,
                onPageSizeChange: (size) => {
                  setPageSize(size);
                  setPage(1);
                },
              }
            : undefined
        }
      />
    </div>
  );
}

export default LegacyMedicosTab;
