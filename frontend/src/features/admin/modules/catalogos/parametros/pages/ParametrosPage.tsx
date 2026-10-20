import { useMemo, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { ParametroDetailsDialog } from "@features/admin/modules/catalogos/parametros/components/ParametroDetailsDialog";
import {
  formatParametroValue,
  moduleLabel,
} from "@features/admin/modules/catalogos/parametros/domain/parametro.value";
import { useParametrosList } from "@features/admin/modules/catalogos/parametros/queries/useParametros";
import { getParametroErrorMessage } from "@features/admin/modules/catalogos/parametros/utils/parametro.feedback";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { Parametro } from "@api/types/catalogos/parameters.types";

const normalize = (text: string) =>
  text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

const columns: DataTableColumn<Parametro>[] = [
  {
    key: "description",
    header: "Parámetro",
    className: "w-[360px]",
    render: (row) => (
      <div className="min-w-0">
        <p className="font-medium text-txt-body">{row.description}</p>
        <p className="font-mono text-xs text-txt-muted">{row.key}</p>
      </div>
    ),
  },
  {
    key: "module",
    header: "Módulo",
    className: "w-[140px]",
    render: (row) => moduleLabel(row.module),
  },
  {
    key: "generalValue",
    header: "Valor general",
    className: "w-[260px]",
    render: (row) => (
      <span className="line-clamp-2">{formatParametroValue(row.valueType, row.generalValue)}</span>
    ),
  },
  {
    key: "centers",
    header: "Por centro",
    className: "w-[180px]",
    render: (row) =>
      !row.allowsCenterOverride ? (
        <Badge variant="outline">Solo general</Badge>
      ) : row.centerValues.length > 0 ? (
        <Badge variant="outline">
          {row.centerValues.length} {row.centerValues.length === 1 ? "centro" : "centros"}
        </Badge>
      ) : (
        <span className="text-sm text-txt-muted">Todos usan el general</span>
      ),
  },
];

export function ParametrosPage() {
  const { hasCapability } = usePermissionDependencies();
  const canRead = hasCapability("admin.catalogs.parametros.read", {
    allOf: ["admin:catalogos:parametros:read"],
  });
  const canEdit = hasCapability("admin.catalogs.parametros.update", {
    allOf: ["admin:catalogos:parametros:update"],
  });

  const [search, setSearch] = useState("");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useParametrosList({ enabled: canRead });
  const items = useMemo(() => data?.items ?? [], [data]);

  const rows = useMemo(() => {
    const term = normalize(search.trim());
    if (!term) return items;
    return items.filter((p) =>
      [p.description, p.key, moduleLabel(p.module)].some((field) => normalize(field).includes(term)),
    );
  }, [items, search]);

  // Se toma del listado (que se invalida tras cada cambio) para mostrar siempre lo vigente.
  const selected = items.find((p) => p.key === selectedKey) ?? null;

  return (
    <CatalogModuleLayout
      title="Parámetros por centro"
      description="Topes y valores operativos de SIRES. Cada parámetro tiene un valor general y, si lo admite, valores propios por centro."
      icon={<SlidersHorizontal className="size-12" />}
    >
      {!canRead ? (
        <AdminReadOnlyNotice message="No tienes acceso para consultar los parámetros." />
      ) : null}

      <TableHeaderBar
        search={
          <TableSearch
            value={search}
            onChange={setSearch}
            placeholder="Buscar por parámetro o módulo"
            disabled={!canRead}
          />
        }
      />

      <DataTable
        columns={columns}
        rows={rows}
        isLoading={canRead && isLoading}
        isError={canRead && Boolean(error)}
        errorTitle="No se pudieron cargar los parámetros"
        errorDescription={
          error ? getParametroErrorMessage(error, "Intenta nuevamente en unos segundos.") : undefined
        }
        hasFilters={Boolean(search.trim())}
        onClearFilters={() => setSearch("")}
        onRetry={() => void refetch()}
        onRowClick={canRead ? (row) => setSelectedKey(row.key) : undefined}
        getRowKey={(row) => row.key}
        emptyTitle="Sin parámetros"
        emptyDescription="Los parámetros se agregan junto con la regla que los usa."
      />

      <ParametroDetailsDialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedKey(null);
        }}
        onClose={() => setSelectedKey(null)}
        parametro={selected}
        canEdit={canEdit}
      />
    </CatalogModuleLayout>
  );
}

export default ParametrosPage;
