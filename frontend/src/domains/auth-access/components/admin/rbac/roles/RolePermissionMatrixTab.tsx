import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Checkbox } from "@shared/ui/checkbox";
import { Skeleton } from "@shared/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@shared/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@shared/ui/tooltip";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import {
  ModuleImpactDialog,
  type ModuleImpactAction,
} from "@/domains/auth-access/components/admin/rbac/roles/ModuleImpactDialog";
import { PermissionMatrixRow } from "@/domains/auth-access/components/admin/rbac/roles/PermissionMatrixRow";
import {
  TriStateCheckbox,
  type TriState,
} from "@/domains/auth-access/components/admin/rbac/roles/TriStateCheckbox";
import {
  buildPermissionModuleIndex,
  type ModuleRef,
} from "@/domains/auth-access/adapters/rbac/roles/roles.module-tree";
import {
  MATRIX_ACTIONS,
  buildDependencyIndex,
  buildPermissionMatrix,
  buildResourceIndex,
  getActionLabel,
  getDependencyClosure,
  getMissingDependencies,
  planBatchToggle,
  planToggle,
  resolveCodesToIds,
  type MatrixCell,
  type MatrixRow,
  type TogglePlan,
} from "@/domains/auth-access/adapters/rbac/roles/roles.permission-matrix";
import type { ModuleCatalogNodeDTO, Permission, RolePermission } from "@api/types";

/** Leyenda especifica para roles admin -- distinta del mensaje generico de
 * "es de sistema" o "no tienes permisos": el rol admin SI tiene acceso,
 * solo que no se administra via RelRolPermiso. */
const ADMIN_ACCESS_MESSAGE =
  "Este rol tiene acceso total automatico a todos los permisos y modulos -- no depende de asignaciones individuales.";

const OTHER_PERMISSIONS_TITLE = "Otros permisos";

interface PendingChange {
  plan: TogglePlan;
  requested: string[];
  nextChecked: boolean;
  title: string;
  collateral: ModuleRef[];
}

interface RolePermissionMatrixTabProps {
  modules: ModuleCatalogNodeDTO[];
  isLoadingModules: boolean;
  workingPermissions: RolePermission[];
  permissionCatalog: Permission[];
  actorPermissions: string[];
  isEditable?: boolean;
  /**
   * Rol con `is_admin=true`. El RBACResolver le da acceso total dinamico
   * (wildcard) sin depender de RelRolPermiso, asi que esta tab ignora el
   * estado real de `workingPermissions` y muestra todo tildado, en modo
   * solo lectura.
   */
  isAdmin?: boolean;
  readOnlyMessage?: string;
  catalogAccessMessage?: string | null;
  isSaving?: boolean;
  moduleCatalogErrorMessage?: string | null;
  onRetryModuleCatalog?: () => void;
  onToggleModule: (permissionIds: number[], nextChecked: boolean) => void;
}

const computeState = (
  cells: MatrixCell[],
  isChecked: (code: string) => boolean,
): TriState => {
  const checked = cells.filter((cell) => isChecked(cell.code)).length;
  if (checked === 0) return "unchecked";
  return checked === cells.length ? "checked" : "indeterminate";
};

const rowCells = (row: MatrixRow): MatrixCell[] => [
  ...MATRIX_ACTIONS.flatMap((action) => {
    const cell = row.cells[action];
    return cell ? [cell] : [];
  }),
  ...row.other,
];

export function RolePermissionMatrixTab({
  modules,
  isLoadingModules,
  workingPermissions,
  permissionCatalog,
  actorPermissions,
  isEditable = true,
  isAdmin = false,
  readOnlyMessage = "Solo lectura: no puedes actualizar este rol porque no tienes permisos.",
  catalogAccessMessage = null,
  isSaving = false,
  moduleCatalogErrorMessage = null,
  onRetryModuleCatalog,
  onToggleModule,
}: RolePermissionMatrixTabProps) {
  const [pending, setPending] = useState<PendingChange | null>(null);

  const matrix = useMemo(
    () => buildPermissionMatrix(modules, permissionCatalog),
    [modules, permissionCatalog],
  );
  const dependencyIndex = useMemo(
    () => buildDependencyIndex(permissionCatalog),
    [permissionCatalog],
  );
  const resourceIndex = useMemo(
    () => buildResourceIndex(permissionCatalog),
    [permissionCatalog],
  );
  const permissionIndex = useMemo(
    () => buildPermissionModuleIndex(modules),
    [modules],
  );
  const draftCodes = useMemo(
    () => new Set(workingPermissions.map((permission) => permission.code)),
    [workingPermissions],
  );
  const actorPermissionSet = useMemo(
    () => new Set(actorPermissions),
    [actorPermissions],
  );
  const hasWildcard = actorPermissionSet.has("*");

  // Sin catalogo de permisos no se pueden traducir codigos -> ids, asi que
  // la tab se muestra igual pero sin permitir tildar/destildar.
  const canToggle = isEditable && !catalogAccessMessage && !isAdmin;
  const isReadOnly = !canToggle || isSaving;

  const isChecked = useCallback(
    (code: string) => isAdmin || draftCodes.has(code),
    [isAdmin, draftCodes],
  );

  const getDisabledReason = useCallback(
    (code: string): string | null => {
      if (hasWildcard) return null;
      const missing = [...getDependencyClosure([code], dependencyIndex)].filter(
        (required) =>
          dependencyIndex.deps.has(required) && !actorPermissionSet.has(required),
      );
      return missing.length > 0
        ? `No puedes asignar permisos que no tienes. Requiere: ${missing.join(", ")}`
        : null;
    },
    [hasWildcard, dependencyIndex, actorPermissionSet],
  );

  const getMissing = useCallback(
    (code: string) => getMissingDependencies(code, dependencyIndex),
    [dependencyIndex],
  );

  const commit = useCallback(
    (plan: TogglePlan, requested: string[]) => {
      const nextChecked = plan.add.length > 0;
      const codes = nextChecked ? plan.add : plan.remove;
      const { ids } = resolveCodesToIds(codes, permissionCatalog);
      if (ids.length === 0) return;

      // Una sola direccion por accion: ver `addPermissionsToDraft`, varias
      // llamadas sincronicas pisarian el draft entre si.
      onToggleModule(ids, nextChecked);

      const extras = codes.filter((code) => !requested.includes(code));
      if (extras.length > 0) {
        toast.info(
          nextChecked
            ? `También se agregaron por dependencia: ${extras.join(", ")}`
            : `También se quitaron: ${extras.join(", ")}`,
        );
      }
    },
    [permissionCatalog, onToggleModule],
  );

  const applyChange = useCallback(
    (
      plan: TogglePlan,
      requested: string[],
      excludeModuleKeys: Set<string>,
      title: string,
    ) => {
      const changed = [...plan.add, ...plan.remove];
      if (changed.length === 0) return;

      const collateral = new Map<string, ModuleRef>();
      for (const code of changed) {
        for (const ref of permissionIndex.get(code) ?? []) {
          if (!excludeModuleKeys.has(ref.key)) collateral.set(ref.key, ref);
        }
      }

      if (collateral.size > 0) {
        setPending({
          plan,
          requested,
          nextChecked: plan.add.length > 0,
          title,
          collateral: [...collateral.values()],
        });
        return;
      }

      commit(plan, requested);
    },
    [permissionIndex, commit],
  );

  const planContext = useMemo(
    () => ({ draftCodes, dependencyIndex, resourceIndex }),
    [draftCodes, dependencyIndex, resourceIndex],
  );

  const toggleCode = useCallback(
    (code: string, nextChecked: boolean, excludeModuleKeys: Set<string>, title: string) => {
      if (isReadOnly) return;
      applyChange(planToggle(code, nextChecked, planContext), [code], excludeModuleKeys, title);
    },
    [isReadOnly, applyChange, planContext],
  );

  const toggleMany = useCallback(
    (
      cells: MatrixCell[],
      nextChecked: boolean,
      excludeModuleKeys: Set<string>,
      title: string,
    ) => {
      if (isReadOnly) return;
      const codes = cells
        .filter((cell) => getDisabledReason(cell.code) === null)
        .map((cell) => cell.code);
      applyChange(
        planBatchToggle(codes, nextChecked, planContext),
        codes,
        excludeModuleKeys,
        title,
      );
    },
    [isReadOnly, getDisabledReason, applyChange, planContext],
  );

  const handleToggleCell = useCallback(
    (row: MatrixRow, code: string, nextChecked: boolean) =>
      toggleCode(code, nextChecked, new Set([row.module.key]), row.module.title),
    [toggleCode],
  );

  const handleToggleRow = useCallback(
    (row: MatrixRow, nextChecked: boolean) =>
      toggleMany(rowCells(row), nextChecked, new Set([row.module.key]), row.module.title),
    [toggleMany],
  );

  const handleConfirmImpact = () => {
    if (!pending) return;
    commit(pending.plan, pending.requested);
    setPending(null);
  };

  const impactAction: ModuleImpactAction = pending?.nextChecked
    ? "check"
    : "uncheck";

  const renderState = (cells: MatrixCell[]): TriState => {
    if (isAdmin) return "checked";
    const enabled = cells.filter((cell) => getDisabledReason(cell.code) === null);
    return computeState(enabled, isChecked);
  };

  const hasContent = matrix.groups.length > 0 || matrix.orphans.length > 0;

  return (
    <div className="space-y-6">
      {isAdmin ? (
        <AdminReadOnlyNotice message={ADMIN_ACCESS_MESSAGE} />
      ) : !isEditable ? (
        <AdminReadOnlyNotice message={readOnlyMessage} />
      ) : null}
      {isEditable && !isAdmin && catalogAccessMessage ? (
        <AdminReadOnlyNotice message={catalogAccessMessage} />
      ) : null}

      {isEditable && !isAdmin && !catalogAccessMessage && moduleCatalogErrorMessage ? (
        <div className="rounded-xl border border-status-critical/30 bg-status-critical/5 px-4 py-3 text-xs text-status-critical">
          <p>{moduleCatalogErrorMessage}</p>
          {onRetryModuleCatalog ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={onRetryModuleCatalog}
            >
              Reintentar
            </Button>
          ) : null}
        </div>
      ) : null}

      <div>
        <p className="text-sm font-semibold text-txt-body">
          Permisos por modulo
        </p>
        <p className="text-xs text-txt-muted">
          Asigna ver, crear, editar y eliminar por modulo. Al marcar un
          permiso se agregan sus dependencias (por ejemplo, Ver) y al quitar
          Ver se quita todo el recurso. Algunos permisos se comparten entre
          modulos: cambiarlos puede afectar a otros.
        </p>
      </div>

      {isLoadingModules ? (
        <div className="space-y-2 rounded-xl border border-line-struct/60 bg-subtle/20 p-3">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton
              key={`permission-matrix-skeleton-${index}`}
              className="h-9 w-full"
            />
          ))}
        </div>
      ) : !hasContent ? (
        <div className="rounded-xl border border-dashed border-line-struct/70 bg-subtle/20 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-txt-body">
            No hay modulos ni permisos disponibles.
          </p>
        </div>
      ) : (
        <div className="max-h-[480px] overflow-auto rounded-xl border border-line-struct/60 bg-subtle/20">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Modulo</TableHead>
                {MATRIX_ACTIONS.map((action) => (
                  <TableHead key={action} scope="col" className="text-center">
                    {getActionLabel(action)}
                  </TableHead>
                ))}
                <TableHead scope="col">Otras</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {matrix.groups.map((group) => {
                const groupCells = group.rows.flatMap(rowCells);
                const groupKeys = new Set(group.rows.map((row) => row.module.key));
                const state = renderState(groupCells);
                const hasEnabled = groupCells.some(
                  (cell) => getDisabledReason(cell.code) === null,
                );
                return [
                  <TableRow key={`group-${group.key}`} className="bg-subtle/50">
                    <TableCell colSpan={6}>
                      <div className="flex items-center gap-2.5">
                        <TriStateCheckbox
                          state={state}
                          disabled={isReadOnly || !hasEnabled}
                          onToggle={() =>
                            toggleMany(groupCells, state !== "checked", groupKeys, group.title)
                          }
                          aria-label={`Todos los permisos de ${group.title}`}
                        />
                        <span className="text-sm font-semibold text-txt-body">
                          {group.title}
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>,
                  ...group.rows.map((row) => (
                    <PermissionMatrixRow
                      key={row.key}
                      row={row}
                      draftCodes={draftCodes}
                      isAdmin={isAdmin}
                      isReadOnly={isReadOnly}
                      getDisabledReason={getDisabledReason}
                      getMissingDependencies={getMissing}
                      onToggleCell={handleToggleCell}
                      onToggleRow={handleToggleRow}
                    />
                  )),
                ];
              })}

              {matrix.orphans.length > 0
                ? [
                    <TableRow key="group-orphans" className="bg-subtle/50">
                      <TableCell colSpan={6}>
                        <div className="flex items-center gap-2.5">
                          <TriStateCheckbox
                            state={renderState(matrix.orphans)}
                            disabled={
                              isReadOnly ||
                              matrix.orphans.every(
                                (cell) => getDisabledReason(cell.code) !== null,
                              )
                            }
                            onToggle={() =>
                              toggleMany(
                                matrix.orphans,
                                renderState(matrix.orphans) !== "checked",
                                new Set(),
                                OTHER_PERMISSIONS_TITLE,
                              )
                            }
                            aria-label={`Todos los permisos de ${OTHER_PERMISSIONS_TITLE}`}
                          />
                          <span className="text-sm font-semibold text-txt-body">
                            {OTHER_PERMISSIONS_TITLE}
                          </span>
                          <span className="text-xs text-txt-muted">
                            Sin modulo asociado
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>,
                    ...matrix.orphans.map((cell) => {
                      const reason = isReadOnly ? null : getDisabledReason(cell.code);
                      const checkbox = (
                        <Checkbox
                          checked={isChecked(cell.code)}
                          disabled={isReadOnly || reason !== null}
                          onCheckedChange={(value) =>
                            toggleCode(
                              cell.code,
                              value === true,
                              new Set(),
                              OTHER_PERMISSIONS_TITLE,
                            )
                          }
                          aria-label={`${cell.code} en ${OTHER_PERMISSIONS_TITLE}`}
                        />
                      );
                      return (
                        <TableRow key={`orphan-${cell.code}`}>
                          <TableCell colSpan={6}>
                            <div className="flex items-center gap-2.5 pl-3">
                              {reason ? (
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <span className="inline-flex" tabIndex={0}>
                                      {checkbox}
                                    </span>
                                  </TooltipTrigger>
                                  <TooltipContent>{reason}</TooltipContent>
                                </Tooltip>
                              ) : (
                                checkbox
                              )}
                              <span className="font-mono text-xs text-txt-body">
                                {cell.code}
                              </span>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    }),
                  ]
                : null}
            </TableBody>
          </Table>
        </div>
      )}

      <ModuleImpactDialog
        open={pending !== null}
        onOpenChange={(open) => {
          if (!open) setPending(null);
        }}
        action={impactAction}
        nodeTitle={pending?.title ?? ""}
        collateralModules={pending?.collateral ?? []}
        onConfirm={handleConfirmImpact}
      />
    </div>
  );
}
