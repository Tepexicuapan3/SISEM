import type { CiesListItem } from "@api/resources/catalogos/cies.api";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";

export const CIES_TABLE_COLUMNS: DataTableColumn<CiesListItem>[] = [
  {
    key: "code",
    header: "Clave",
    accessorKey: "code",
    className: "w-[120px]",
  },
  {
    key: "name",
    header: "Descripción",
    accessorKey: "name",
    className: "w-[480px]",
    cellContentClassName: "max-w-[480px]",
  },
  {
    key: "version",
    header: "Versión",
    accessorKey: "version",
    className: "w-[120px]",
  },
  {
    key: "isActive",
    header: "Estado",
    align: "center",
    accessorKey: "isActive",
    className: "w-[130px]",
    render: (row) => (
      <CatalogStatusBadge
        isActive={row.isActive}
        activeLabel="Activo"
        inactiveLabel="Inactivo"
      />
    ),
  },
];
