import { Eye, Pencil, ToggleLeft, ToggleRight, Trash2 } from "lucide-react";
import type { MotivoTrasladoListItem } from "@api/types";
import { Badge } from "@shared/ui/badge";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { type TableColumnVisibilityItem } from "@features/admin/shared/components/TableColumnVisibility";
import {
  TableActionsHeader,
  TableToolbar,
  type TableAction,
} from "@features/admin/shared/components/TableToolbar";

interface BuildMotivoTrasladoTableColumnsOptions {
  canReadMotivoTraslado: boolean;
  canUpdateMotivoTraslado: boolean;
  canDeleteMotivoTraslado: boolean;
  isStatusPending: boolean;
  onOpenDetails: (item: MotivoTrasladoListItem) => void;
  onToggleStatus: (item: MotivoTrasladoListItem) => void;
  onRequestDelete: (item: MotivoTrasladoListItem) => void;
}

export const buildMotivoTrasladoTableColumns = ({
  canReadMotivoTraslado,
  canUpdateMotivoTraslado,
  canDeleteMotivoTraslado,
  isStatusPending,
  onOpenDetails,
  onToggleStatus,
  onRequestDelete,
}: BuildMotivoTrasladoTableColumnsOptions): DataTableColumn<MotivoTrasladoListItem>[] => {
  const baseColumns: DataTableColumn<MotivoTrasladoListItem>[] = [
    {
      key: "name",
      header: "Nombre",
      accessorKey: "name",
      className: "w-[320px]",
      cellContentClassName: "max-w-[320px]",
    },
    {
      key: "requiresNotes",
      header: "Requiere notas",
      align: "center",
      accessorKey: "requiresNotes",
      className: "w-[150px]",
      render: (row) => (
        <Badge variant={row.requiresNotes ? "secondary" : "outline"} className="text-xs">
          {row.requiresNotes ? "Sí" : "No"}
        </Badge>
      ),
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

  const showActions = canReadMotivoTraslado || canUpdateMotivoTraslado || canDeleteMotivoTraslado;
  if (!showActions) return baseColumns;

  const actionColumn: DataTableColumn<MotivoTrasladoListItem> = {
    key: "actions",
    header: <TableActionsHeader />,
    align: "center",
    className: "w-9 px-0",
    headerClassName: "w-9 px-0",
    render: (row) => {
      const actions: TableAction[] = [];

      if (canReadMotivoTraslado) {
        actions.push({ id: `view-${row.id}`, label: "Ver detalles", icon: Eye, onSelect: () => onOpenDetails(row) });
      }
      if (canUpdateMotivoTraslado) {
        actions.push({ id: `edit-${row.id}`, label: "Editar", icon: Pencil, onSelect: () => onOpenDetails(row) });
        actions.push({
          id: `status-${row.id}`,
          label: row.isActive ? "Desactivar" : "Activar",
          icon: row.isActive ? ToggleLeft : ToggleRight,
          disabled: isStatusPending,
          onSelect: () => onToggleStatus(row),
        });
      }
      if (canDeleteMotivoTraslado) {
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

export const buildMotivoTrasladoVisibilityOptions = (
  showActions: boolean,
): TableColumnVisibilityItem[] => {
  const options: TableColumnVisibilityItem[] = [
    { key: "name", label: "Nombre" },
    { key: "requiresNotes", label: "Requiere notas" },
    { key: "isActive", label: "Estado" },
  ];
  if (showActions) options.push({ key: "actions", label: "Acciones", canHide: false });
  return options;
};
