import { useEffect, useRef, useState } from "react";
import {
  Boxes,
  ChevronDown,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  FolderTree,
  KeyRound,
  Layers,
} from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Skeleton } from "@shared/ui/skeleton";
import { TruncatedTooltip } from "@shared/ui/truncated-tooltip";
import { cn } from "@shared/utils/styling/cn";
import type { Permission } from "@api/types";
import { PermissionSearchField } from "@/domains/auth-access/components/admin/rbac/shared/PermissionSearchField";

import { buildPermissionTree, buildTreeRows, findStartIndex, PERMISSION_ROW_HEIGHT, PERMISSION_TREE_ROW_TYPE, permissionMatchesSearch, pluralize, renderHighlightedText, rowPaddingLeft, VIRTUALIZATION_OVERSCAN_PX, VIRTUALIZATION_THRESHOLD, type PermissionExplorerItem, type PermissionHierarchyExplorerProps, type PermissionTreeRow } from "./permission-hierarchy-explorer.tree";

export function PermissionsHierarchyExplorer<
  TPermission extends PermissionExplorerItem = Permission,
>({
  permissions,
  isLoading = false,
  className,
  selectedPermissionCode,
  onSelectPermission,
  title,
  description,
  searchPlaceholder = "Buscar por codigo, descripcion o jerarquia",
  emptyMessage = "Sin permisos disponibles",
  noResultsMessage = "No se encontraron permisos",
  viewportHeightClassName = "h-[560px]",
  actionLabel = "Agregar",
  actionIcon,
  actionVariant = "outline",
  actionDisplay = "button",
  isActionPending = false,
  isActionDisabled,
  actionAriaLabel,
  actionClassName,
  onAction,
  renderMeta,
  metaDisplay = "inline",
  showCodeBadge = true,
}: PermissionHierarchyExplorerProps<TPermission>) {
  const [searchValue, setSearchValue] = useState("");
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(
    () => new Set<string>(),
  );
  const [hasExpansionOverride, setHasExpansionOverride] = useState(false);
  const [internalSelectedCode, setInternalSelectedCode] = useState<
    string | null
  >(null);
  const [viewportHeight, setViewportHeight] = useState(560);
  const [scrollTop, setScrollTop] = useState(0);

  const viewportRef = useRef<HTMLDivElement | null>(null);

  const normalizedSearchValue = searchValue.trim();
  const isSearching = normalizedSearchValue.length > 0;

  const fullTree = buildPermissionTree(permissions);
  const filteredPermissions = isSearching
    ? permissions.filter((permission) =>
        permissionMatchesSearch(permission, normalizedSearchValue),
      )
    : permissions;
  const visibleTree = isSearching
    ? buildPermissionTree(filteredPermissions)
    : fullTree;

  const effectiveExpandedIds = isSearching
    ? new Set<string>(visibleTree.expandableIds)
    : hasExpansionOverride
      ? expandedNodeIds
      : new Set<string>(fullTree.expandableIds);

  const rowsData = buildTreeRows(visibleTree.groups, effectiveExpandedIds);
  const shouldVirtualize = rowsData.actionsCount > VIRTUALIZATION_THRESHOLD;
  const actionRowHeight =
    renderMeta && metaDisplay === "footer"
      ? 92
      : PERMISSION_ROW_HEIGHT[PERMISSION_TREE_ROW_TYPE.ACTION];

  const getRowHeight = (row: PermissionTreeRow<TPermission>) =>
    row.type === PERMISSION_TREE_ROW_TYPE.ACTION
      ? actionRowHeight
      : PERMISSION_ROW_HEIGHT[row.type];

  const rowOffsets: number[] = [];
  let totalHeight = 0;
  rowsData.rows.forEach((row) => {
    rowOffsets.push(totalHeight);
    totalHeight += getRowHeight(row);
  });

  let startIndex = 0;
  let endIndex = rowsData.rows.length;

  if (shouldVirtualize && rowsData.rows.length > 0) {
    const startOffset = Math.max(scrollTop - VIRTUALIZATION_OVERSCAN_PX, 0);
    const endOffset = scrollTop + viewportHeight + VIRTUALIZATION_OVERSCAN_PX;

    startIndex = findStartIndex(rowOffsets, startOffset);
    endIndex = startIndex;

    while (
      endIndex < rowsData.rows.length &&
      rowOffsets[endIndex] < endOffset
    ) {
      endIndex += 1;
    }
  }

  const visibleRows = shouldVirtualize
    ? rowsData.rows.slice(startIndex, endIndex)
    : rowsData.rows;

  const selectedCode = selectedPermissionCode ?? internalSelectedCode;
  const canSelectPermission = Boolean(onSelectPermission);

  useEffect(() => {
    if (!shouldVirtualize) {
      return;
    }

    const viewportElement = viewportRef.current;
    if (!viewportElement) {
      return;
    }

    const syncViewportHeight = () => {
      setViewportHeight(viewportElement.clientHeight);
    };

    syncViewportHeight();

    if (typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver(syncViewportHeight);
    observer.observe(viewportElement);

    return () => {
      observer.disconnect();
    };
  }, [shouldVirtualize, rowsData.rows.length]);

  const handleToggleNode = (nodeId: string) => {
    if (isSearching) {
      return;
    }

    setHasExpansionOverride(true);
    setExpandedNodeIds((previous) => {
      const next = new Set(previous);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const handleExpandAll = () => {
    setHasExpansionOverride(true);
    setExpandedNodeIds(new Set<string>(fullTree.expandableIds));
  };

  const handleCollapseAll = () => {
    setHasExpansionOverride(true);
    setExpandedNodeIds(new Set<string>());
  };

  const handleSelectPermission = (permission: TPermission) => {
    setInternalSelectedCode(permission.code);
    onSelectPermission?.(permission);
  };

  const resetViewportScroll = () => {
    const viewportElement = viewportRef.current;
    if (viewportElement) {
      viewportElement.scrollTop = 0;
    }
    setScrollTop(0);
  };

  const handleSearchChange = (value: string) => {
    setSearchValue(value);
    resetViewportScroll();
  };

  const renderChevron = (isExpanded: boolean) =>
    isExpanded ? (
      <ChevronDown className="size-4 text-txt-muted" />
    ) : (
      <ChevronRight className="size-4 text-txt-muted" />
    );

  const renderActionControl = (permission: TPermission) => {
    if (!onAction) {
      return null;
    }

    const isDisabled =
      isActionPending || Boolean(isActionDisabled?.(permission));
    const label =
      actionAriaLabel?.(permission) ?? `${actionLabel} ${permission.code}`;

    if (actionDisplay === "icon") {
      return (
        <Button
          type="button"
          size="icon-sm"
          variant={actionVariant}
          onClick={() => onAction(permission)}
          disabled={isDisabled}
          aria-label={label}
          className={cn(actionClassName)}
        >
          {actionIcon}
        </Button>
      );
    }

    return (
      <Button
        type="button"
        size="sm"
        variant={actionVariant}
        onClick={() => onAction(permission)}
        disabled={isDisabled}
        aria-label={label}
        className={cn(actionClassName)}
      >
        {actionIcon}
        {actionLabel}
      </Button>
    );
  };

  const renderRow = (row: PermissionTreeRow<TPermission>) => {
    if (row.type === PERMISSION_TREE_ROW_TYPE.GROUP) {
      return (
        <button
          type="button"
          onClick={() => handleToggleNode(row.id)}
          className="flex h-full w-full items-center justify-between gap-3 rounded-xl border border-line-struct/60 bg-paper/70 px-3 text-left transition-colors hover:bg-subtle/40"
          style={{ paddingLeft: rowPaddingLeft(row.depth) }}
        >
          <span className="inline-flex min-w-0 items-center gap-2.5">
            {renderChevron(row.isExpanded)}
            <FolderTree className="size-4 shrink-0 text-brand" />
            <span className="truncate text-sm font-semibold text-txt-body">
              {renderHighlightedText(row.node.label, normalizedSearchValue)}
            </span>
          </span>
          <span className="inline-flex shrink-0 items-center gap-1.5">
            <Badge variant="secondary" className="text-[11px]">
              {pluralize(row.node.modulesCount, "modulo", "modulos")}
            </Badge>
            <Badge variant="outline" className="text-[11px]">
              {pluralize(row.node.permissionsCount, "permiso", "permisos")}
            </Badge>
          </span>
        </button>
      );
    }

    if (row.type === PERMISSION_TREE_ROW_TYPE.MODULE) {
      return (
        <button
          type="button"
          onClick={() => handleToggleNode(row.id)}
          className="flex h-full w-full items-center justify-between gap-3 rounded-xl border border-line-struct/50 bg-paper/60 px-3 text-left transition-colors hover:bg-subtle/35"
          style={{ paddingLeft: rowPaddingLeft(row.depth) }}
        >
          <span className="inline-flex min-w-0 items-center gap-2.5">
            {renderChevron(row.isExpanded)}
            <Boxes className="size-4 shrink-0 text-status-info" />
            <span className="truncate text-sm font-medium text-txt-body">
              {renderHighlightedText(row.node.label, normalizedSearchValue)}
            </span>
          </span>
          <span className="inline-flex shrink-0 items-center gap-1.5">
            <Badge variant="secondary" className="text-[11px]">
              {pluralize(row.node.submodulesCount, "submodulo", "submodulos")}
            </Badge>
            <Badge variant="outline" className="text-[11px]">
              {pluralize(row.node.permissionsCount, "permiso", "permisos")}
            </Badge>
          </span>
        </button>
      );
    }

    if (row.type === PERMISSION_TREE_ROW_TYPE.SUBMODULE) {
      return (
        <button
          type="button"
          onClick={() => handleToggleNode(row.id)}
          className="flex h-full w-full items-center justify-between gap-3 rounded-lg border border-line-struct/45 bg-paper/50 px-3 text-left transition-colors hover:bg-subtle/30"
          style={{ paddingLeft: rowPaddingLeft(row.depth) }}
        >
          <span className="inline-flex min-w-0 items-center gap-2.5">
            {renderChevron(row.isExpanded)}
            <Layers className="size-4 shrink-0 text-status-alert" />
            <span className="truncate text-sm font-medium text-txt-body">
              {renderHighlightedText(row.node.label, normalizedSearchValue)}
            </span>
          </span>
          <Badge variant="outline" className="text-[11px]">
            {pluralize(row.node.permissionsCount, "permiso", "permisos")}
          </Badge>
        </button>
      );
    }

    const permission = row.node.permission;
    const isSelected = selectedCode === permission.code;
    const isMetaFooter = Boolean(renderMeta && metaDisplay === "footer");
    const summaryTitle = permission.description?.trim() || row.node.label;

    const summaryContent = isMetaFooter ? (
      <div className="flex min-w-0 items-center gap-2">
        <KeyRound
          className={cn(
            "size-4 shrink-0",
            isSelected ? "text-brand" : "text-status-stable",
          )}
        />
        <p className="truncate text-sm font-medium text-txt-body">
          {renderHighlightedText(summaryTitle, normalizedSearchValue)}
        </p>
      </div>
    ) : (
      <div className="flex min-w-0 items-start gap-2">
        <KeyRound
          className={cn(
            "mt-0.5 size-4 shrink-0",
            isSelected ? "text-brand" : "text-status-stable",
          )}
        />

        <div className="min-w-0 space-y-0">
          <p className="truncate text-sm font-medium text-txt-body">
            {renderHighlightedText(row.node.label, normalizedSearchValue)}
          </p>

          <p className="truncate text-xs leading-snug text-txt-muted">
            {renderHighlightedText(
              permission.description,
              normalizedSearchValue,
            )}
          </p>

          {renderMeta && !isMetaFooter ? (
            <div className="text-[11px] leading-snug text-txt-muted">
              {renderMeta(permission)}
            </div>
          ) : null}
        </div>
      </div>
    );

    const actionSummary = canSelectPermission ? (
      <button
        type="button"
        onClick={() => handleSelectPermission(permission)}
        className="min-w-0 flex-1 text-left"
      >
        {summaryContent}
      </button>
    ) : (
      <div className="min-w-0 flex-1">{summaryContent}</div>
    );

    const actionControls = (
      <div className="flex shrink-0 items-center gap-2">
        {showCodeBadge ? (
          <Badge
            variant="outline"
            className="max-w-65 px-2 py-0.5 font-mono text-[11px]"
          >
            <TruncatedTooltip
              label={permission.code}
              className="block min-w-0 max-w-full truncate"
              align="end"
            >
              {renderHighlightedText(permission.code, normalizedSearchValue)}
            </TruncatedTooltip>
          </Badge>
        ) : null}

        {renderActionControl(permission)}
      </div>
    );

    if (isMetaFooter) {
      return (
        <div
          className={cn(
            "h-full w-full overflow-hidden rounded-xl border transition-colors",
            isSelected
              ? "border-brand/50 bg-brand/5"
              : "border-line-struct/60 bg-paper/80 hover:bg-subtle/25",
          )}
          style={{ paddingLeft: rowPaddingLeft(row.depth) }}
        >
          <div className="flex items-center justify-between gap-3 px-3 py-2.5">
            {actionSummary}
            {actionControls}
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line-struct/50 px-3 py-2 text-xs text-txt-muted">
            {renderMeta?.(permission)}
          </div>
        </div>
      );
    }

    return (
      <div
        className={cn(
          "flex h-full w-full items-center justify-between gap-2 rounded-lg border px-2.5 py-1.5",
          isSelected
            ? "border-brand/50 bg-brand/5"
            : "border-line-struct/45 bg-paper/45 hover:bg-subtle/25",
        )}
        style={{ paddingLeft: rowPaddingLeft(row.depth) }}
      >
        {actionSummary}
        {actionControls}
      </div>
    );
  };

  return (
    <section
      className={cn(
        "flex min-h-0 w-full flex-col gap-3 rounded-2xl border border-line-struct bg-paper p-4",
        className,
      )}
    >
      {title || description ? (
        <div>
          {title ? (
            <p className="text-sm font-semibold text-txt-body">{title}</p>
          ) : null}
          {description ? (
            <p className="text-xs text-txt-muted">{description}</p>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <PermissionSearchField
          value={searchValue}
          onValueChange={handleSearchChange}
          placeholder={searchPlaceholder}
          ariaLabel="Buscar permisos"
          className="flex-1"
        />

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleExpandAll}
          >
            <ChevronsUpDown className="size-4" />
            Expandir todo
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleCollapseAll}
          >
            <ChevronsDownUp className="size-4" />
            Colapsar todo
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-txt-muted">
        <Badge variant="outline">
          {pluralize(permissions.length, "permiso", "permisos")}
        </Badge>
        {isSearching ? (
          <Badge variant="info">
            {pluralize(filteredPermissions.length, "resultado", "resultados")}{" "}
            encontrados
          </Badge>
        ) : null}
        {shouldVirtualize ? (
          <Badge variant="secondary">Scroll virtual activo</Badge>
        ) : null}
      </div>

      {isLoading ? (
        <div className="space-y-2 rounded-xl border border-line-struct/60 bg-subtle/20 p-3">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton
              key={`permission-tree-skeleton-${index}`}
              className={cn("h-10", index % 3 === 0 ? "w-full" : "w-[94%]")}
            />
          ))}
        </div>
      ) : permissions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line-struct/70 bg-subtle/20 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-txt-body">{emptyMessage}</p>
        </div>
      ) : filteredPermissions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line-struct/70 bg-subtle/20 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-txt-body">
            {noResultsMessage}
          </p>
          <p className="mt-1 text-xs text-txt-muted">
            Ajusta el texto o limpia la busqueda para ver todo el catalogo.
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={() => handleSearchChange("")}
          >
            Limpiar busqueda
          </Button>
        </div>
      ) : (
        <div
          ref={viewportRef}
          className={cn(
            "overflow-y-auto rounded-xl border border-line-struct/60 bg-subtle/20 p-2",
            viewportHeightClassName,
          )}
          onScroll={
            shouldVirtualize
              ? (event) => {
                  setScrollTop(event.currentTarget.scrollTop);
                }
              : undefined
          }
        >
          {shouldVirtualize ? (
            <div style={{ height: `${totalHeight}px`, position: "relative" }}>
              {visibleRows.map((row, index) => {
                const rowIndex = startIndex + index;
                const rowOffsetTop = rowOffsets[rowIndex] ?? 0;

                return (
                  <div
                    key={row.id}
                    className="absolute inset-x-0 px-1"
                    style={{
                      top: `${rowOffsetTop}px`,
                      height: `${getRowHeight(row)}px`,
                    }}
                  >
                    {renderRow(row)}
                  </div>
                );
              })}
            </div>
          ) : (
            <div>
              {visibleRows.map((row) => (
                <div
                  key={row.id}
                  className="px-1"
                  style={{ height: `${getRowHeight(row)}px` }}
                >
                  {renderRow(row)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
