import { Eye, Pencil, ToggleLeft, ToggleRight, Trash2 } from "lucide-react";
import type { Cie9McListItem } from "@api/types";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { type TableColumnVisibilityItem } from "@features/admin/shared/components/TableColumnVisibility";
import {
  TableActionsHeader,
  TableToolbar,
  type TableAction,
} from "@features/admin/shared/components/TableToolbar";

interface BuildCie9McTableColumnsOptions {
  canReadCie9Mc: boolean;
  canUpdateCie9Mc: boolean;
  canDeleteCie9Mc: boolean;
  isStatusPending: boolean;
  onOpenDetails: (cie9Mc: Cie9McListItem) => void;
  onToggleStatus: (cie9Mc: Cie9McListItem) => void;
  onRequestDelete: (cie9Mc: Cie9McListItem) => void;
}

export const buildCie9McTableColumns = ({
  canReadCie9Mc,
  canUpdateCie9Mc,
  canDeleteCie9Mc,
  isStatusPending,
  onOpenDetails,
  onToggleStatus,
  onRequestDelete,
}: BuildCie9McTableColumnsOptions): DataTableColumn<Cie9McListItem>[] => {
  const baseColumns: DataTableColumn<Cie9McListItem>[] = [
    {
      key: "code",
      header: "Clave",
      accessorKey: "code",
      className: "w-[140px]",
    },
    {
      key: "name",
      header: "Descripción",
      accessorKey: "name",
      className: "w-[420px]",
      cellContentClassName: "max-w-[420px]",
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

  const showActions = canReadCie9Mc || canUpdateCie9Mc || canDeleteCie9Mc;

  if (!showActions) {
    return baseColumns;
  }

  const actionColumn: DataTableColumn<Cie9McListItem> = {
    key: "actions",
    header: <TableActionsHeader />,
    align: "center",
    className: "w-9 px-0",
    headerClassName: "w-9 px-0",
    render: (row) => {
      const actions: TableAction[] = [];

      if (canReadCie9Mc) {
        actions.push({
          id: `view-${row.id}`,
          label: "Ver detalles",
          icon: Eye,
          onSelect: () => onOpenDetails(row),
        });
      }

      if (canUpdateCie9Mc) {
        actions.push({
          id: `edit-${row.id}`,
          label: "Editar",
          icon: Pencil,
          onSelect: () => onOpenDetails(row),
        });
        actions.push({
          id: `status-${row.id}`,
          label: row.isActive ? "Desactivar" : "Activar",
          icon: row.isActive ? ToggleLeft : ToggleRight,
          disabled: isStatusPending,
          onSelect: () => onToggleStatus(row),
        });
      }

      if (canDeleteCie9Mc) {
        if (actions.length > 0) {
          actions.push({ id: `divider-${row.id}`, type: "separator" });
        }

        actions.push({
          id: `delete-${row.id}`,
          label: "Eliminar",
          icon: Trash2,
          variant: "destructive",
          onSelect: () => onRequestDelete(row),
        });
      }

      return actions.length > 0 ? (
        <div
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          <TableToolbar actions={actions} />
        </div>
      ) : null;
    },
  };

  return [...baseColumns, actionColumn];
};

export const buildCie9McVisibilityOptions = (
  showActions: boolean,
): TableColumnVisibilityItem[] => {
  const options: TableColumnVisibilityItem[] = [
    { key: "code", label: "Clave" },
    { key: "name", label: "Descripción" },
    { key: "isActive", label: "Estado" },
  ];

  if (showActions) {
    options.push({
      key: "actions",
      label: "Acciones",
      canHide: false,
    });
  }

  return options;
};
