import { Eye, Pencil, Trash2 } from "lucide-react";
import type { DesignacionItem } from "@api/types";
import { Badge } from "@shared/ui/badge";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { type TableColumnVisibilityItem } from "@features/admin/shared/components/TableColumnVisibility";
import {
  TableActionsHeader,
  TableToolbar,
  type TableAction,
} from "@features/admin/shared/components/TableToolbar";
import {
  describeAlcance,
  formatDate,
} from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.format";

interface BuildDesignacionTableColumnsOptions {
  canRead: boolean;
  canWrite: boolean;
  onOpenDetails: (item: DesignacionItem) => void;
  onRequestRevoke: (item: DesignacionItem) => void;
}

export const buildDesignacionTableColumns = ({
  canRead,
  canWrite,
  onOpenDetails,
  onRequestRevoke,
}: BuildDesignacionTableColumnsOptions): DataTableColumn<DesignacionItem>[] => {
  const baseColumns: DataTableColumn<DesignacionItem>[] = [
    {
      key: "user",
      header: "Autorizador",
      className: "w-[220px]",
      render: (row) => row.user.name,
    },
    {
      key: "tipo",
      header: "Tipo",
      className: "w-[180px]",
      render: (row) => row.tipoAutorizacion.name,
    },
    { key: "cargo", header: "Cargo", accessorKey: "cargo", className: "w-[180px]" },
    {
      key: "alcance",
      header: "Alcance",
      className: "w-[300px]",
      render: (row) => (
        <div className="flex flex-wrap gap-1">
          {describeAlcance(row.alcance).map((label) => (
            <Badge key={label} variant="outline">
              {label}
            </Badge>
          ))}
        </div>
      ),
    },
    {
      key: "vigencia",
      header: "Vigencia",
      className: "w-[200px]",
      render: (row) =>
        `${formatDate(row.fechaInicio)} – ${row.fechaFin ? formatDate(row.fechaFin) : "Sin fin"}`,
    },
    {
      key: "vigente",
      header: "Estado",
      align: "center",
      className: "w-[120px]",
      render: (row) =>
        row.vigente ? (
          <Badge variant="stable">Vigente</Badge>
        ) : (
          <Badge variant="outline">No vigente</Badge>
        ),
    },
  ];

  const showActions = canRead || canWrite;

  if (!showActions) return baseColumns;

  const actionColumn: DataTableColumn<DesignacionItem> = {
    key: "actions",
    header: <TableActionsHeader />,
    align: "center",
    className: "w-9 px-0",
    headerClassName: "w-9 px-0",
    render: (row) => {
      const actions: TableAction[] = [];

      if (canRead) {
        actions.push({
          id: `view-${row.id}`,
          label: "Ver detalles",
          icon: Eye,
          onSelect: () => onOpenDetails(row),
        });
      }

      // Una designacion dada de baja no se edita ni se vuelve a revocar.
      if (canWrite && row.isActive) {
        actions.push({
          id: `edit-${row.id}`,
          label: "Editar",
          icon: Pencil,
          onSelect: () => onOpenDetails(row),
        });

        if (actions.length > 0) {
          actions.push({ id: `divider-${row.id}`, type: "separator" });
        }

        actions.push({
          id: `revoke-${row.id}`,
          label: "Dar de baja",
          icon: Trash2,
          variant: "destructive",
          onSelect: () => onRequestRevoke(row),
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

export const buildDesignacionVisibilityOptions = (
  showActions: boolean,
): TableColumnVisibilityItem[] => {
  const options: TableColumnVisibilityItem[] = [
    { key: "user", label: "Autorizador" },
    { key: "tipo", label: "Tipo" },
    { key: "cargo", label: "Cargo" },
    { key: "alcance", label: "Alcance" },
    { key: "vigencia", label: "Vigencia" },
    { key: "vigente", label: "Estado" },
  ];

  if (showActions) {
    options.push({ key: "actions", label: "Acciones", canHide: false });
  }

  return options;
};
