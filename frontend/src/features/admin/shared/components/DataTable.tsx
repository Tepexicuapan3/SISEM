import { type ReactNode } from "react";
import { AlertTriangle, Inbox, RotateCcw, SearchX } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardFooter } from "@shared/ui/card";
import { Skeleton } from "@shared/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@shared/ui/table";
import { TruncatedTooltip } from "@shared/ui/truncated-tooltip";
import { cn } from "@shared/utils/styling/cn";
import {
  TablePagination,
  type TablePaginationProps,
} from "@features/admin/shared/components/TablePagination";

const COLUMN_ALIGN = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
} as const;

type ColumnAlign = keyof typeof COLUMN_ALIGN;

export interface DataTableColumn<T> {
  key: string;
  header: ReactNode;
  accessorKey?: keyof T & string;
  render?: (row: T) => ReactNode;
  skeleton?: ReactNode | ((rowIndex: number) => ReactNode);
  align?: ColumnAlign;
  className?: string;
  headerClassName?: string;
  cellContentClassName?: string;
  truncate?: boolean;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  isLoading?: boolean;
  isError?: boolean;
  loadingRows?: number;
  hasFilters?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  noResultsTitle?: string;
  noResultsDescription?: string;
  errorTitle?: string;
  errorDescription?: string;
  onRetry?: () => void;
  onClearFilters?: () => void;
  onRowClick?: (row: T) => void;
  pagination?: TablePaginationProps;
  footerNote?: ReactNode;
  getRowKey?: (row: T, index: number) => string;
  getRowClassName?: (row: T, index: number) => string | undefined;
  className?: string;
  /** Nombre accesible de la tabla (lectores de pantalla y tests por rol). */
  ariaLabel?: string;
  /**
   * Ancho minimo de la tabla (clase Tailwind, ej. "min-w-[900px]").
   * Ajustalo cuando la suma de los anchos explicitos de las columnas
   * supere el default: la tabla ya tiene scroll horizontal (ver
   * shared/ui/table.tsx), asi que un valor mayor es seguro.
   */
  minWidthClassName?: string;
}

const defaultEmptyTitle = "Sin registros";
const defaultEmptyDescription = "Todavia no hay registros para mostrar";
const defaultNoResultsTitle = "Sin resultados";
const defaultNoResultsDescription =
  "No encontramos coincidencias con los filtros actuales";
const defaultErrorTitle = "No se pudo cargar";
const defaultErrorDescription =
  "Ocurrio un error al obtener la informacion. Intenta nuevamente.";
const skeletonWidths = ["w-16", "w-24", "w-32", "w-40", "w-20"] as const;

export function DataTable<T>({
  columns,
  rows,
  isLoading = false,
  isError = false,
  loadingRows = 6,
  hasFilters = false,
  emptyTitle = defaultEmptyTitle,
  emptyDescription = defaultEmptyDescription,
  noResultsTitle = defaultNoResultsTitle,
  noResultsDescription = defaultNoResultsDescription,
  errorTitle = defaultErrorTitle,
  errorDescription = defaultErrorDescription,
  onRetry,
  onClearFilters,
  onRowClick,
  pagination,
  footerNote,
  getRowKey,
  getRowClassName,
  className,
  ariaLabel,
  minWidthClassName = "min-w-[720px]",
}: DataTableProps<T>) {
  const tableClassName = cn(minWidthClassName, "table-fixed");
  const shouldShowNoResults = hasFilters && rows.length === 0;
  const emptyStateTitle = shouldShowNoResults ? noResultsTitle : emptyTitle;
  const emptyStateDescription = shouldShowNoResults
    ? noResultsDescription
    : emptyDescription;
  const hasRowClick = Boolean(onRowClick);

  const renderSkeletonCell = (
    column: DataTableColumn<T>,
    rowIndex: number,
    columnIndex: number,
  ) => {
    if (column.skeleton) {
      return typeof column.skeleton === "function"
        ? column.skeleton(rowIndex)
        : column.skeleton;
    }

    const widthClass =
      column.key === "actions"
        ? "w-8"
        : skeletonWidths[(rowIndex + columnIndex) % skeletonWidths.length];
    const alignmentClass =
      column.align === "center"
        ? "justify-center"
        : column.align === "right"
          ? "justify-end"
          : "justify-start";

    return (
      <div className={cn("flex items-center", alignmentClass)}>
        <Skeleton className={cn("h-3", widthClass)} />
      </div>
    );
  };

  return (
    <Card className={className}>
      <CardContent>
        {isLoading ? (
          <Table className={tableClassName} aria-label={ariaLabel}>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                {columns.map((column) => (
                  <TableHead
                    key={column.key}
                    className={cn(
                      "bg-subtle text-xs font-semibold text-txt-muted tracking-wide first:rounded-tl-lg last:rounded-tr-lg",
                      COLUMN_ALIGN[column.align ?? "left"],
                      column.className,
                      column.headerClassName,
                    )}
                  >
                    {column.header}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: loadingRows }).map((_, rowIndex) => (
                <TableRow key={`loading-${rowIndex}`}>
                  {columns.map((column, columnIndex) => (
                    <TableCell key={`${column.key}-${rowIndex}`}>
                      {renderSkeletonCell(column, rowIndex, columnIndex)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : isError ? (
          <Alert variant="destructive" className="rounded-xl py-6">
            <div className="flex flex-col items-center gap-5 text-center">
              <div className="flex size-14 items-center justify-center rounded-full bg-status-critical/10 text-status-critical">
                <AlertTriangle className="size-8" />
              </div>
              <div className="space-y-2">
                <AlertTitle className="justify-center">{errorTitle}</AlertTitle>
                <AlertDescription className="mt-2 text-center">
                  {errorDescription}
                </AlertDescription>
              </div>
              {onRetry ? (
                <Button variant="outline" size="sm" onClick={onRetry}>
                  <RotateCcw className="size-4" />
                  Reintentar
                </Button>
              ) : null}
            </div>
          </Alert>
        ) : rows.length === 0 ? (
          <Alert variant="default" className="rounded-xl py-6">
            <div className="flex flex-col items-center gap-5 text-center">
              <div className="flex size-14 items-center justify-center rounded-full bg-subtle text-txt-muted">
                {shouldShowNoResults ? (
                  <SearchX className="size-8" />
                ) : (
                  <Inbox className="size-8" />
                )}
              </div>
              <div className="space-y-2">
                <AlertTitle className="justify-center">
                  {emptyStateTitle}
                </AlertTitle>
                <AlertDescription className="mt-2 text-center">
                  {emptyStateDescription}
                </AlertDescription>
              </div>
              {shouldShowNoResults && onClearFilters ? (
                <Button variant="outline" size="sm" onClick={onClearFilters}>
                  Limpiar filtros
                </Button>
              ) : null}
            </div>
          </Alert>
        ) : (
          <Table className={tableClassName} aria-label={ariaLabel}>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                {columns.map((column) => (
                  <TableHead
                    key={column.key}
                    className={cn(
                      "bg-subtle text-xs font-semibold text-txt-muted tracking-wide first:rounded-tl-lg last:rounded-tr-lg",
                      COLUMN_ALIGN[column.align ?? "left"],
                      column.className,
                      column.headerClassName,
                    )}
                  >
                    {column.header}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row, rowIndex) => {
                const rowKey = getRowKey
                  ? getRowKey(row, rowIndex)
                  : `row-${rowIndex}`;

                return (
                  <TableRow
                    key={rowKey}
                    onClick={() => onRowClick?.(row)}
                    className={cn(
                      hasRowClick && "cursor-pointer hover:bg-subtle/50",
                      getRowClassName?.(row, rowIndex),
                    )}
                  >
                    {columns.map((column) => {
                      const dataKey =
                        column.accessorKey ?? (column.key as keyof T);
                      const content = column.render
                        ? column.render(row)
                        : ((row[dataKey] as ReactNode) ?? "—");
                      const isTextValue =
                        typeof content === "string" ||
                        typeof content === "number";
                      const shouldTruncate = column.truncate ?? isTextValue;

                      const contentClassName = cn(
                        "min-w-0",
                        column.truncate === false &&
                          "whitespace-normal break-words",
                        column.cellContentClassName,
                      );

                      return (
                        <TableCell
                          key={`${column.key}-${rowKey}`}
                          className={cn(
                            "min-w-0",
                            COLUMN_ALIGN[column.align ?? "left"],
                            column.className,
                          )}
                        >
                          {shouldTruncate && isTextValue ? (
                            <TruncatedTooltip
                              label={String(content)}
                              className={cn(
                                "block max-w-full truncate",
                                contentClassName,
                              )}
                            >
                              {String(content)}
                            </TruncatedTooltip>
                          ) : (
                            <div className={cn("w-full", contentClassName)}>
                              {content}
                            </div>
                          )}
                        </TableCell>
                      );
                    })}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
      {pagination ? (
        <CardFooter
          className={cn(
            "flex flex-col gap-4 border-t border-line-struct md:flex-row md:items-center",
            footerNote ? "md:justify-between" : "md:justify-end",
          )}
        >
          <TablePagination
            {...pagination}
            className={cn(!footerNote && "md:ml-auto")}
          />
          {footerNote ? (
            <div className="text-xs text-txt-muted">{footerNote}</div>
          ) : null}
        </CardFooter>
      ) : null}
    </Card>
  );
}
