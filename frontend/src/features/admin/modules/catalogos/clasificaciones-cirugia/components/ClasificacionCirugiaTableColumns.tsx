import { Eye, Pencil, ToggleLeft, ToggleRight, Trash2 } from "lucide-react";
import type { ClasificacionCirugiaListItem } from "@api/types";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { type TableColumnVisibilityItem } from "@features/admin/shared/components/TableColumnVisibility";
import {
  TableActionsHeader,
  TableToolbar,
  type TableAction,
} from "@features/admin/shared/components/TableToolbar";

interface BuildClasificacionCirugiaTableColumnsOptions {
  canReadClasificacionCirugia: boolean;
  canUpdateClasificacionCirugia: boolean;
  canDeleteClasificacionCirugia: boolean;
  isStatusPending: boolean;
  onOpenDetails: (item: ClasificacionCirugiaListItem) => void;
  onToggleStatus: (item: ClasificacionCirugiaListItem) => void;
  onRequestDelete: (item: ClasificacionCirugiaListItem) => void;
}

export const buildClasificacionCirugiaTableColumns = ({
  canReadClasificacionCirugia,
  canUpdateClasificacionCirugia,
  canDeleteClasificacionCirugia,
  isStatusPending,
  onOpenDetails,
  onToggleStatus,
  onRequestDelete,
}: BuildClasificacionCirugiaTableColumnsOptions): DataTableColumn<ClasificacionCirugiaListItem>[] => {
  const baseColumns: DataTableColumn<ClasificacionCirugiaListItem>[] = [
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

  const showActions = canReadClasificacionCirugia || canUpdateClasificacionCirugia || canDeleteClasificacionCirugia;
  if (!showActions) return baseColumns;

  const actionColumn: DataTableColumn<ClasificacionCirugiaListItem> = {
    key: "actions",
    header: <TableActionsHeader />,
    align: "center",
    className: "w-9 px-0",
    headerClassName: "w-9 px-0",
    render: (row) => {
      const actions: TableAction[] = [];

      if (canReadClasificacionCirugia) {
        actions.push({ id: `view-${row.id}`, label: "Ver detalles", icon: Eye, onSelect: () => onOpenDetails(row) });
      }
      if (canUpdateClasificacionCirugia) {
        actions.push({ id: `edit-${row.id}`, label: "Editar", icon: Pencil, onSelect: () => onOpenDetails(row) });
        actions.push({
          id: `status-${row.id}`,
          label: row.isActive ? "Desactivar" : "Activar",
          icon: row.isActive ? ToggleLeft : ToggleRight,
          disabled: isStatusPending,
          onSelect: () => onToggleStatus(row),
        });
      }
      if (canDeleteClasificacionCirugia) {
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

export const buildClasificacionCirugiaVisibilityOptions = (
  showActions: boolean,
): TableColumnVisibilityItem[] => {
  const options: TableColumnVisibilityItem[] = [
    { key: "name", label: "Nombre" },
    { key: "isActive", label: "Estado" },
  ];
  if (showActions) options.push({ key: "actions", label: "Acciones", canHide: false });
  return options;
};
