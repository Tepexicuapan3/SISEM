import { Eye, Pencil, ToggleLeft, ToggleRight, Trash2 } from "lucide-react";
import type { MotivoCancelacionCirugiaListItem } from "@api/types";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { type TableColumnVisibilityItem } from "@features/admin/shared/components/TableColumnVisibility";
import {
  TableActionsHeader,
  TableToolbar,
  type TableAction,
} from "@features/admin/shared/components/TableToolbar";

interface BuildMotivoCancelacionCirugiaTableColumnsOptions {
  canReadMotivoCancelacionCirugia: boolean;
  canUpdateMotivoCancelacionCirugia: boolean;
  canDeleteMotivoCancelacionCirugia: boolean;
  isStatusPending: boolean;
  onOpenDetails: (item: MotivoCancelacionCirugiaListItem) => void;
  onToggleStatus: (item: MotivoCancelacionCirugiaListItem) => void;
  onRequestDelete: (item: MotivoCancelacionCirugiaListItem) => void;
}

export const buildMotivoCancelacionCirugiaTableColumns = ({
  canReadMotivoCancelacionCirugia,
  canUpdateMotivoCancelacionCirugia,
  canDeleteMotivoCancelacionCirugia,
  isStatusPending,
  onOpenDetails,
  onToggleStatus,
  onRequestDelete,
}: BuildMotivoCancelacionCirugiaTableColumnsOptions): DataTableColumn<MotivoCancelacionCirugiaListItem>[] => {
  const baseColumns: DataTableColumn<MotivoCancelacionCirugiaListItem>[] = [
    {
      key: "name",
      header: "Nombre",
      accessorKey: "name",
      className: "w-[320px]",
      cellContentClassName: "max-w-[320px]",
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

  const showActions = canReadMotivoCancelacionCirugia || canUpdateMotivoCancelacionCirugia || canDeleteMotivoCancelacionCirugia;
  if (!showActions) return baseColumns;

  const actionColumn: DataTableColumn<MotivoCancelacionCirugiaListItem> = {
    key: "actions",
    header: <TableActionsHeader />,
    align: "center",
    className: "w-9 px-0",
    headerClassName: "w-9 px-0",
    render: (row) => {
      const actions: TableAction[] = [];

      if (canReadMotivoCancelacionCirugia) {
        actions.push({ id: `view-${row.id}`, label: "Ver detalles", icon: Eye, onSelect: () => onOpenDetails(row) });
      }
      if (canUpdateMotivoCancelacionCirugia) {
        actions.push({ id: `edit-${row.id}`, label: "Editar", icon: Pencil, onSelect: () => onOpenDetails(row) });
        actions.push({
          id: `status-${row.id}`,
          label: row.isActive ? "Desactivar" : "Activar",
          icon: row.isActive ? ToggleLeft : ToggleRight,
          disabled: isStatusPending,
          onSelect: () => onToggleStatus(row),
        });
      }
      if (canDeleteMotivoCancelacionCirugia) {
        if (actions.length > 0) actions.push({ id: `divider-${row.id}`, type: "separator" });
        actions.push({ id: `delete-${row.id}`, label: "Eliminar", icon: Trash2, variant: "destructive", onSelect: () => onRequestDelete(row) });
      }

      return actions.length > 0 ? (
        <div onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
          <TableToolbar actions={actions} />
        </div>
      ) : null;
    },
  };

  return [...baseColumns, actionColumn];
};

export const buildMotivoCancelacionCirugiaVisibilityOptions = (
  showActions: boolean,
): TableColumnVisibilityItem[] => {
  const options: TableColumnVisibilityItem[] = [
    { key: "name", label: "Nombre" },
    { key: "isActive", label: "Estado" },
  ];
  if (showActions) options.push({ key: "actions", label: "Acciones", canHide: false });
  return options;
};
