import { Eye, Pencil, ToggleLeft, ToggleRight, Trash2 } from "lucide-react";
import type { MedicamentoListItem } from "@api/types";
import { Badge } from "@shared/ui/badge";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import { CUADRO_BASICO_LABEL } from "@features/admin/modules/catalogos/medicamentos/domain/medicamentos.schemas";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { type TableColumnVisibilityItem } from "@features/admin/shared/components/TableColumnVisibility";
import {
  TableActionsHeader,
  TableToolbar,
  type TableAction,
} from "@features/admin/shared/components/TableToolbar";

interface BuildMedicamentosTableColumnsOptions {
  canReadMedicamento: boolean;
  canUpdateMedicamento: boolean;
  canDeleteMedicamento: boolean;
  isStatusPending: boolean;
  onOpenDetails: (medicamento: MedicamentoListItem) => void;
  onToggleStatus: (medicamento: MedicamentoListItem) => void;
  onRequestDelete: (medicamento: MedicamentoListItem) => void;
}

export const buildMedicamentosTableColumns = ({
  canReadMedicamento,
  canUpdateMedicamento,
  canDeleteMedicamento,
  isStatusPending,
  onOpenDetails,
  onToggleStatus,
  onRequestDelete,
}: BuildMedicamentosTableColumnsOptions): DataTableColumn<MedicamentoListItem>[] => {
  const baseColumns: DataTableColumn<MedicamentoListItem>[] = [
    {
      key: "code",
      header: "Clave",
      className: "w-[150px]",
      cellContentClassName: "max-w-[140px]",
      render: (row) => row.code ?? "—",
    },
    {
      key: "name",
      header: "Medicamento",
      accessorKey: "name",
      className: "w-[260px]",
      cellContentClassName: "max-w-[260px]",
    },
    {
      key: "genericName",
      header: "Genérico",
      className: "w-[200px]",
      cellContentClassName: "max-w-[200px]",
      render: (row) => row.genericName ?? "—",
    },
    {
      key: "cuadroBasico",
      header: "Cuadro",
      className: "w-[120px]",
      render: (row) => CUADRO_BASICO_LABEL[row.cuadroBasico] ?? row.cuadroBasico,
    },
    {
      key: "isControlled",
      header: "Control",
      align: "center",
      className: "w-[120px]",
      render: (row) =>
        row.isControlled ? <Badge variant="outline">Controlado</Badge> : "—",
    },
    {
      key: "maxQuantity",
      header: "Máx. cajas",
      align: "center",
      className: "w-[110px]",
      render: (row) => row.maxQuantity ?? "—",
    },
    {
      key: "isActive",
      header: "Estado",
      align: "center",
      accessorKey: "isActive",
      className: "w-[130px]",
      render: (row) => <CatalogStatusBadge isActive={row.isActive} />,
    },
  ];

  const showActions = canReadMedicamento || canUpdateMedicamento || canDeleteMedicamento;

  if (!showActions) {
    return baseColumns;
  }

  const actionColumn: DataTableColumn<MedicamentoListItem> = {
    key: "actions",
    header: <TableActionsHeader />,
    align: "center",
    className: "w-9 px-0",
    headerClassName: "w-9 px-0",
    render: (row) => {
      const actions: TableAction[] = [];

      if (canReadMedicamento) {
        actions.push({
          id: `view-${row.id}`,
          label: "Ver detalles",
          icon: Eye,
          onSelect: () => onOpenDetails(row),
        });
      }

      if (canUpdateMedicamento) {
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

      if (canDeleteMedicamento) {
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

export const buildMedicamentosVisibilityOptions = (
  showActions: boolean,
): TableColumnVisibilityItem[] => {
  const options: TableColumnVisibilityItem[] = [
    { key: "code", label: "Clave" },
    { key: "name", label: "Medicamento" },
    { key: "genericName", label: "Genérico" },
    { key: "cuadroBasico", label: "Cuadro" },
    { key: "isControlled", label: "Control" },
    { key: "maxQuantity", label: "Máx. cajas" },
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
