import { memo } from "react";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Checkbox } from "@shared/ui/checkbox";
import { TableCell, TableRow } from "@shared/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@shared/ui/tooltip";
import { cn } from "@shared/utils/styling/cn";
import {
  MATRIX_ACTIONS,
  formatResourceLabel,
  getActionLabel,
  type MatrixCell,
  type MatrixRow,
} from "@/domains/auth-access/adapters/rbac/roles/roles.permission-matrix";
import {
  TriStateCheckbox,
  type TriState,
} from "@/domains/auth-access/components/admin/rbac/roles/TriStateCheckbox";

interface PermissionMatrixRowProps {
  row: MatrixRow;
  draftCodes: Set<string>;
  /** Rol admin: todo se muestra marcado (el estado real del draft se ignora). */
  isAdmin: boolean;
  isReadOnly: boolean;
  /** Motivo por el que el actor no puede tocar el codigo, o `null` si puede. */
  getDisabledReason: (code: string) => string | null;
  /** Dependencias del cierre que no existen en el catalogo. */
  getMissingDependencies: (code: string) => string[];
  onToggleCell: (row: MatrixRow, code: string, nextChecked: boolean) => void;
  onToggleRow: (row: MatrixRow, nextChecked: boolean) => void;
}

const rowCells = (row: MatrixRow): MatrixCell[] => [
  ...MATRIX_ACTIONS.flatMap((action) => {
    const cell = row.cells[action];
    return cell ? [cell] : [];
  }),
  ...row.other,
];

function PermissionMatrixRowComponent({
  row,
  draftCodes,
  isAdmin,
  isReadOnly,
  getDisabledReason,
  getMissingDependencies,
  onToggleCell,
  onToggleRow,
}: PermissionMatrixRowProps) {
  const resourceLabel = formatResourceLabel(row.resource);
  const isChecked = (code: string) => isAdmin || draftCodes.has(code);

  const cells = rowCells(row);
  const editableCells = cells.filter(
    (cell) => !isReadOnly && getDisabledReason(cell.code) === null,
  );
  const checkedEditable = editableCells.filter((cell) => isChecked(cell.code)).length;
  const rowState: TriState = isAdmin
    ? "checked"
    : checkedEditable === 0
      ? "unchecked"
      : checkedEditable === editableCells.length
        ? "checked"
        : "indeterminate";
  const sharedRefs = cells.flatMap((cell) => cell.sharedWith);
  const sharedTitles = [...new Set(sharedRefs.map((ref) => ref.title))];

  const renderCell = (cell: MatrixCell, showLabel: boolean) => {
    const disabledReason = isReadOnly ? null : getDisabledReason(cell.code);
    const missing = getMissingDependencies(cell.code);
    const actionLabel = getActionLabel(cell.action);
    const ariaLabel = `${actionLabel} ${resourceLabel} en ${row.module.title}`;

    const checkbox = (
      <Checkbox
        checked={isChecked(cell.code)}
        disabled={isReadOnly || disabledReason !== null}
        onCheckedChange={(value) => onToggleCell(row, cell.code, value === true)}
        aria-label={ariaLabel}
      />
    );

    return (
      <span key={cell.code} className="inline-flex items-center gap-1.5">
        {disabledReason ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex" tabIndex={0}>
                {checkbox}
              </span>
            </TooltipTrigger>
            <TooltipContent>{disabledReason}</TooltipContent>
          </Tooltip>
        ) : (
          checkbox
        )}
        {showLabel ? (
          <span className="text-xs text-txt-body">{actionLabel}</span>
        ) : null}
        {missing.length > 0 ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span
                className="inline-flex text-status-warning"
                role="img"
                aria-label={`Dependencia que no existe en el catalogo: ${missing.join(", ")}`}
              >
                <AlertTriangle className="size-3.5" />
              </span>
            </TooltipTrigger>
            <TooltipContent>
              Dependencia que no existe en el catalogo: {missing.join(", ")}
            </TooltipContent>
          </Tooltip>
        ) : null}
      </span>
    );
  };

  return (
    <TableRow>
      <TableCell style={{ paddingLeft: 12 + row.depth * 12 }}>
        <div className="flex items-center gap-2.5">
          <TriStateCheckbox
            state={rowState}
            disabled={isReadOnly || editableCells.length === 0}
            onToggle={() => onToggleRow(row, rowState !== "checked")}
            aria-label={`Todos los permisos de ${resourceLabel} en ${row.module.title}`}
          />
          <div className="min-w-0">
            <p
              className={cn(
                "truncate text-sm text-txt-body",
                row.isOwner ? "font-medium" : "font-normal",
              )}
            >
              {row.module.title}
            </p>
            <p className="truncate text-xs text-txt-muted">{resourceLabel}</p>
          </div>
          {sharedTitles.length > 0 ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="outline" className="shrink-0 text-[10px] text-txt-muted">
                  Compartido
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                Algunos permisos de esta fila tambien los usan: {sharedTitles.join(", ")}.
              </TooltipContent>
            </Tooltip>
          ) : null}
        </div>
      </TableCell>

      {MATRIX_ACTIONS.map((action) => {
        const cell = row.cells[action];
        return (
          <TableCell key={action} className="text-center">
            {cell ? (
              renderCell(cell, false)
            ) : (
              <span className="text-txt-muted" aria-label="No disponible">
                —
              </span>
            )}
          </TableCell>
        );
      })}

      <TableCell>
        {row.other.length > 0 ? (
          <div className="flex flex-wrap gap-x-3 gap-y-1.5">
            {row.other.map((cell) => renderCell(cell, true))}
          </div>
        ) : (
          <span className="text-txt-muted" aria-label="No disponible">
            —
          </span>
        )}
      </TableCell>
    </TableRow>
  );
}

export const PermissionMatrixRow = memo(PermissionMatrixRowComponent);
