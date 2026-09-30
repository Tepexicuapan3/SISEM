import type { ComponentProps, ReactNode } from "react";
import type { Button } from "@shared/ui/button";
import type { Permission } from "@api/types";

export type ButtonVariant = ComponentProps<typeof Button>["variant"];

export const PERMISSION_TREE_ROW_TYPE = {
  GROUP: "group",
  MODULE: "module",
  SUBMODULE: "submodule",
  ACTION: "action",
} as const;

export type PermissionTreeRowType =
  (typeof PERMISSION_TREE_ROW_TYPE)[keyof typeof PERMISSION_TREE_ROW_TYPE];

export const PERMISSION_ROW_HEIGHT: Record<PermissionTreeRowType, number> = {
  [PERMISSION_TREE_ROW_TYPE.GROUP]: 52,
  [PERMISSION_TREE_ROW_TYPE.MODULE]: 48,
  [PERMISSION_TREE_ROW_TYPE.SUBMODULE]: 46,
  [PERMISSION_TREE_ROW_TYPE.ACTION]: 68,
};

export const VIRTUALIZATION_THRESHOLD = 100;
export const VIRTUALIZATION_OVERSCAN_PX = 320;
export const DEFAULT_SUBMODULE_KEY = "general";

export interface PermissionExplorerItem {
  id: number;
  code: string;
  description: string;
  isSystem?: boolean;
}

export interface PermissionHierarchyExplorerProps<
  TPermission extends PermissionExplorerItem = Permission,
> {
  permissions: TPermission[];
  isLoading?: boolean;
  className?: string;
  selectedPermissionCode?: string | null;
  onSelectPermission?: (permission: TPermission) => void;
  title?: string;
  description?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  noResultsMessage?: string;
  viewportHeightClassName?: string;
  actionLabel?: string;
  actionIcon?: ReactNode;
  actionVariant?: ButtonVariant;
  actionDisplay?: "button" | "icon";
  isActionPending?: boolean;
  isActionDisabled?: (permission: TPermission) => boolean;
  actionAriaLabel?: (permission: TPermission) => string;
  actionClassName?: string;
  onAction?: (permission: TPermission) => void;
  renderMeta?: (permission: TPermission) => ReactNode;
  metaDisplay?: "inline" | "footer";
  showCodeBadge?: boolean;
}

export interface PermissionCodeSegments {
  groupKey: string;
  moduleKey: string;
  submoduleKey: string;
  actionKey: string;
}

export interface PermissionActionNode<TPermission extends PermissionExplorerItem> {
  id: string;
  label: string;
  permission: TPermission;
}

export interface PermissionSubmoduleNode<TPermission extends PermissionExplorerItem> {
  id: string;
  key: string;
  label: string;
  permissionsCount: number;
  actions: PermissionActionNode<TPermission>[];
}

export interface PermissionModuleNode<TPermission extends PermissionExplorerItem> {
  id: string;
  key: string;
  label: string;
  permissionsCount: number;
  submodulesCount: number;
  submodules: PermissionSubmoduleNode<TPermission>[];
}

export interface PermissionGroupNode<TPermission extends PermissionExplorerItem> {
  id: string;
  key: string;
  label: string;
  permissionsCount: number;
  modulesCount: number;
  modules: PermissionModuleNode<TPermission>[];
}

export interface PermissionTreeBuildResult<
  TPermission extends PermissionExplorerItem,
> {
  groups: PermissionGroupNode<TPermission>[];
  expandableIds: string[];
}

export interface PermissionTreeRowBase {
  id: string;
  depth: number;
}

export interface PermissionTreeGroupRow<
  TPermission extends PermissionExplorerItem,
> extends PermissionTreeRowBase {
  type: typeof PERMISSION_TREE_ROW_TYPE.GROUP;
  node: PermissionGroupNode<TPermission>;
  isExpanded: boolean;
}

export interface PermissionTreeModuleRow<
  TPermission extends PermissionExplorerItem,
> extends PermissionTreeRowBase {
  type: typeof PERMISSION_TREE_ROW_TYPE.MODULE;
  node: PermissionModuleNode<TPermission>;
  isExpanded: boolean;
}

export interface PermissionTreeSubmoduleRow<
  TPermission extends PermissionExplorerItem,
> extends PermissionTreeRowBase {
  type: typeof PERMISSION_TREE_ROW_TYPE.SUBMODULE;
  node: PermissionSubmoduleNode<TPermission>;
  isExpanded: boolean;
}

export interface PermissionTreeActionRow<
  TPermission extends PermissionExplorerItem,
> extends PermissionTreeRowBase {
  type: typeof PERMISSION_TREE_ROW_TYPE.ACTION;
  node: PermissionActionNode<TPermission>;
}

export type PermissionTreeRow<TPermission extends PermissionExplorerItem> =
  | PermissionTreeGroupRow<TPermission>
  | PermissionTreeModuleRow<TPermission>
  | PermissionTreeSubmoduleRow<TPermission>
  | PermissionTreeActionRow<TPermission>;

export interface PermissionTreeRowsResult<TPermission extends PermissionExplorerItem> {
  rows: PermissionTreeRow<TPermission>[];
  actionsCount: number;
}

interface DraftSubmoduleNode<TPermission extends PermissionExplorerItem> {
  id: string;
  key: string;
  label: string;
  actions: PermissionActionNode<TPermission>[];
}

interface DraftModuleNode<TPermission extends PermissionExplorerItem> {
  id: string;
  key: string;
  label: string;
  submodules: Map<string, DraftSubmoduleNode<TPermission>>;
}

interface DraftGroupNode<TPermission extends PermissionExplorerItem> {
  id: string;
  key: string;
  label: string;
  modules: Map<string, DraftModuleNode<TPermission>>;
}

export const compareByLabel = <T extends { label: string }>(a: T, b: T) =>
  a.label.localeCompare(b.label, "es");

export const normalizeSearchText = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();

export const parsePermissionCode = (code: string): PermissionCodeSegments => {
  const segments = code
    .split(":")
    .map((segment) => segment.trim())
    .filter(Boolean);

  if (segments.length >= 4) {
    return {
      groupKey: segments[0],
      moduleKey: segments[1],
      submoduleKey: segments[2],
      actionKey: segments.slice(3).join(":"),
    };
  }

  if (segments.length === 3) {
    return {
      groupKey: segments[0],
      moduleKey: segments[1],
      submoduleKey: DEFAULT_SUBMODULE_KEY,
      actionKey: segments[2],
    };
  }

  if (segments.length === 2) {
    return {
      groupKey: segments[0],
      moduleKey: segments[1],
      submoduleKey: DEFAULT_SUBMODULE_KEY,
      actionKey: "read",
    };
  }

  return {
    groupKey: segments[0] ?? "sin-grupo",
    moduleKey: segments[1] ?? "general",
    submoduleKey: DEFAULT_SUBMODULE_KEY,
    actionKey: segments[2] ?? "read",
  };
};

export const formatHierarchyLabel = (value: string) =>
  value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());

export const pluralize = (count: number, singular: string, plural: string) =>
  `${count} ${count === 1 ? singular : plural}`;

const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export const renderHighlightedText = (text: string, query: string): ReactNode => {
  const cleanQuery = query.trim();
  if (!cleanQuery) {
    return text;
  }

  const matcher = new RegExp(`(${escapeRegExp(cleanQuery)})`, "ig");
  const segments = text.split(matcher);

  if (segments.length === 1) {
    return text;
  }

  return segments.map((segment, index) => {
    const isMatch = segment.toLowerCase() === cleanQuery.toLowerCase();

    return isMatch ? (
      <mark
        key={`${segment}-${index}`}
        className="rounded bg-brand/15 px-0.5 text-txt-body"
      >
        {segment}
      </mark>
    ) : (
      <span key={`${segment}-${index}`}>{segment}</span>
    );
  });
};

export const permissionMatchesSearch = (
  permission: PermissionExplorerItem,
  query: string,
) => {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) {
    return true;
  }

  const queryTokens = normalizedQuery.split(/\s+/).filter(Boolean);
  const hierarchy = parsePermissionCode(permission.code);

  const searchableFields = [
    permission.code,
    permission.description,
    hierarchy.groupKey,
    hierarchy.moduleKey,
    hierarchy.submoduleKey,
    hierarchy.actionKey,
    formatHierarchyLabel(hierarchy.groupKey),
    formatHierarchyLabel(hierarchy.moduleKey),
    formatHierarchyLabel(hierarchy.submoduleKey),
    formatHierarchyLabel(hierarchy.actionKey),
  ].map(normalizeSearchText);

  return queryTokens.every((token) =>
    searchableFields.some((field) => field.includes(token)),
  );
};

export const buildPermissionTree = <TPermission extends PermissionExplorerItem>(
  permissions: TPermission[],
): PermissionTreeBuildResult<TPermission> => {
  const groups = new Map<string, DraftGroupNode<TPermission>>();

  permissions.forEach((permission) => {
    const hierarchy = parsePermissionCode(permission.code);
    const groupId = `group:${hierarchy.groupKey}`;
    const moduleId = `${groupId}/module:${hierarchy.moduleKey}`;
    const submoduleId = `${moduleId}/submodule:${hierarchy.submoduleKey}`;

    let groupNode = groups.get(hierarchy.groupKey);
    if (!groupNode) {
      groupNode = {
        id: groupId,
        key: hierarchy.groupKey,
        label: formatHierarchyLabel(hierarchy.groupKey),
        modules: new Map<string, DraftModuleNode<TPermission>>(),
      };
      groups.set(hierarchy.groupKey, groupNode);
    }

    let moduleNode = groupNode.modules.get(hierarchy.moduleKey);
    if (!moduleNode) {
      moduleNode = {
        id: moduleId,
        key: hierarchy.moduleKey,
        label: formatHierarchyLabel(hierarchy.moduleKey),
        submodules: new Map<string, DraftSubmoduleNode<TPermission>>(),
      };
      groupNode.modules.set(hierarchy.moduleKey, moduleNode);
    }

    let submoduleNode = moduleNode.submodules.get(hierarchy.submoduleKey);
    if (!submoduleNode) {
      submoduleNode = {
        id: submoduleId,
        key: hierarchy.submoduleKey,
        label: formatHierarchyLabel(hierarchy.submoduleKey),
        actions: [],
      };
      moduleNode.submodules.set(hierarchy.submoduleKey, submoduleNode);
    }

    submoduleNode.actions.push({
      id: `action:${permission.code}`,
      label: formatHierarchyLabel(hierarchy.actionKey),
      permission,
    });
  });

  const expandableIds: string[] = [];
  const normalizedGroups = Array.from(groups.values())
    .sort(compareByLabel)
    .map<PermissionGroupNode<TPermission>>((groupNode) => {
      const normalizedModules = Array.from(groupNode.modules.values())
        .sort(compareByLabel)
        .map<PermissionModuleNode<TPermission>>((moduleNode) => {
          const normalizedSubmodules = Array.from(
            moduleNode.submodules.values(),
          )
            .sort(compareByLabel)
            .map<PermissionSubmoduleNode<TPermission>>((submoduleNode) => {
              const sortedActions = [...submoduleNode.actions].sort((a, b) =>
                a.label.localeCompare(b.label, "es"),
              );

              if (sortedActions.length > 0) {
                expandableIds.push(submoduleNode.id);
              }

              return {
                id: submoduleNode.id,
                key: submoduleNode.key,
                label: submoduleNode.label,
                permissionsCount: sortedActions.length,
                actions: sortedActions,
              };
            });

          const permissionsCount = normalizedSubmodules.reduce(
            (total, submodule) => total + submodule.permissionsCount,
            0,
          );

          if (normalizedSubmodules.length > 0) {
            expandableIds.push(moduleNode.id);
          }

          return {
            id: moduleNode.id,
            key: moduleNode.key,
            label: moduleNode.label,
            permissionsCount,
            submodulesCount: normalizedSubmodules.length,
            submodules: normalizedSubmodules,
          };
        });

      const permissionsCount = normalizedModules.reduce(
        (total, module) => total + module.permissionsCount,
        0,
      );

      if (normalizedModules.length > 0) {
        expandableIds.push(groupNode.id);
      }

      return {
        id: groupNode.id,
        key: groupNode.key,
        label: groupNode.label,
        permissionsCount,
        modulesCount: normalizedModules.length,
        modules: normalizedModules,
      };
    });

  return {
    groups: normalizedGroups,
    expandableIds,
  };
};

export const buildTreeRows = <TPermission extends PermissionExplorerItem>(
  groups: PermissionGroupNode<TPermission>[],
  expandedIds: Set<string>,
): PermissionTreeRowsResult<TPermission> => {
  const rows: PermissionTreeRow<TPermission>[] = [];
  let actionsCount = 0;

  groups.forEach((groupNode) => {
    const groupExpanded = expandedIds.has(groupNode.id);

    rows.push({
      id: groupNode.id,
      depth: 0,
      type: PERMISSION_TREE_ROW_TYPE.GROUP,
      node: groupNode,
      isExpanded: groupExpanded,
    });

    if (!groupExpanded) {
      return;
    }

    groupNode.modules.forEach((moduleNode) => {
      const moduleExpanded = expandedIds.has(moduleNode.id);

      rows.push({
        id: moduleNode.id,
        depth: 1,
        type: PERMISSION_TREE_ROW_TYPE.MODULE,
        node: moduleNode,
        isExpanded: moduleExpanded,
      });

      if (!moduleExpanded) {
        return;
      }

      moduleNode.submodules.forEach((submoduleNode) => {
        const submoduleExpanded = expandedIds.has(submoduleNode.id);

        rows.push({
          id: submoduleNode.id,
          depth: 2,
          type: PERMISSION_TREE_ROW_TYPE.SUBMODULE,
          node: submoduleNode,
          isExpanded: submoduleExpanded,
        });

        if (!submoduleExpanded) {
          return;
        }

        submoduleNode.actions.forEach((actionNode) => {
          actionsCount += 1;
          rows.push({
            id: actionNode.id,
            depth: 3,
            type: PERMISSION_TREE_ROW_TYPE.ACTION,
            node: actionNode,
          });
        });
      });
    });
  });

  return {
    rows,
    actionsCount,
  };
};

export const findStartIndex = (offsets: number[], value: number) => {
  let low = 0;
  let high = offsets.length - 1;
  let result = 0;

  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    if (offsets[middle] <= value) {
      result = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }

  return result;
};

export const rowPaddingLeft = (depth: number) => `${depth * 20 + 8}px`;
