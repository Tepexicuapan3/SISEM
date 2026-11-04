import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { ChevronDown, Plus, Search, ShieldAlert } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Skeleton } from "@shared/ui/skeleton";
import { Switch } from "@shared/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@shared/ui/tooltip";
import { cn } from "@shared/utils/styling/cn";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { PermissionCreateDialog } from "@/domains/auth-access/components/admin/rbac/permissions/PermissionCreateDialog";
import {
  TriStateCheckbox,
  type TriState,
} from "@/domains/auth-access/components/admin/rbac/roles/TriStateCheckbox";
import {
  buildPermissionAreas,
  type PermissionArea,
  type PermissionFilter,
} from "@/domains/auth-access/adapters/rbac/roles/roles.permission-areas";
import {
  buildDependencyIndex,
  buildResourceIndex,
  getDependencyClosure,
  planBatchToggle,
  planToggle,
  resolveCodesToIds,
  type TogglePlan,
} from "@/domains/auth-access/adapters/rbac/roles/roles.permission-matrix";
import type { Permission, RolePermission } from "@api/types";

/** Leyenda especifica para roles admin -- distinta del mensaje generico de
 * "es de sistema" o "no tienes permisos": el rol admin SI tiene acceso,
 * solo que no se administra via RelRolPermiso. */
const ADMIN_ACCESS_MESSAGE =
  "Este rol tiene acceso total automatico a todos los permisos y modulos -- no depende de asignaciones individuales.";

const FILTERS: { value: PermissionFilter; label: string }[] = [
  { value: "todos", label: "Todos" },
  { value: "asignados", label: "Asignados" },
  { value: "sin-asignar", label: "Sin asignar" },
];

interface RoleDetailsPermissionsTabProps {
  permissions: RolePermission[];
  permissionCatalog: Permission[];
  isLoadingPermissions: boolean;
  /** Permisos de quien edita: no puede dar lo que no tiene (el backend lo vuelve a validar). */
  actorPermissions: string[];
  isEditable?: boolean;
  /**
   * Rol con `is_admin=true`. El RBACResolver le da acceso total dinamico
   * (wildcard) sin depender de RelRolPermiso, asi que esta tab muestra todo
   * el catalogo prendido, en modo solo lectura.
   */
  isAdmin?: boolean;
  readOnlyMessage?: string;
  catalogAccessMessage?: string | null;
  isSaving?: boolean;
  catalogErrorMessage?: string | null;
  onRetryCatalog?: () => void;
  /** Una sola direccion por llamada (ver `addPermissionsToDraft`). */
  onTogglePermissions: (permissionIds: number[], nextChecked: boolean) => void;
}

export function RoleDetailsPermissionsTab({
  permissions,
  permissionCatalog,
  isLoadingPermissions,
  actorPermissions,
  isEditable = true,
  isAdmin = false,
  readOnlyMessage = "Solo lectura: no puedes actualizar este rol porque no tienes permisos.",
  catalogAccessMessage = null,
  isSaving = false,
  catalogErrorMessage = null,
  onRetryCatalog,
  onTogglePermissions,
}: RoleDetailsPermissionsTabProps) {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<PermissionFilter>("todos");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  // Sin acceso al catalogo se gestionan solo los ya asignados: se suman al
  // catalogo para poder mostrarlos y traducir codigos a ids.
  const catalog = useMemo(() => {
    const byCode = new Map(permissionCatalog.map((permission) => [permission.code, permission]));
    for (const permission of permissions) {
      if (!byCode.has(permission.code)) {
        byCode.set(permission.code, {
          id: permission.id,
          code: permission.code,
          description: permission.description,
          isSystem: false,
        });
      }
    }
    return [...byCode.values()];
  }, [permissionCatalog, permissions]);

  const draftCodes = useMemo(
    () => new Set(permissions.map((permission) => permission.code)),
    [permissions],
  );
  const dependencyIndex = useMemo(() => buildDependencyIndex(catalog), [catalog]);
  const resourceIndex = useMemo(() => buildResourceIndex(catalog), [catalog]);
  const actorPermissionSet = useMemo(() => new Set(actorPermissions), [actorPermissions]);
  const descriptionByCode = useMemo(
    () => new Map(catalog.map((permission) => [permission.code, permission.description])),
    [catalog],
  );

  const showCatalogAccessNotice = Boolean(catalogAccessMessage) && isEditable && !isAdmin;
  const showCatalogErrorBanner =
    Boolean(catalogErrorMessage) && isEditable && !isAdmin && !showCatalogAccessNotice;
  const isReadOnly = !isEditable || isAdmin || isSaving || showCatalogErrorBanner;

  const isAssigned = useCallback(
    (code: string) => isAdmin || draftCodes.has(code),
    [isAdmin, draftCodes],
  );

  const getDisabledReason = useCallback(
    (code: string): string | null => {
      if (actorPermissionSet.has("*")) return null;
      const missing = [...getDependencyClosure([code], dependencyIndex)].filter(
        (required) => dependencyIndex.deps.has(required) && !actorPermissionSet.has(required),
      );
      return missing.length > 0
        ? `No puedes dar permisos que tú no tienes: ${missing
            .map((required) => descriptionByCode.get(required) ?? required)
            .join(", ")}.`
        : null;
    },
    [actorPermissionSet, dependencyIndex, descriptionByCode],
  );

  const areas = useMemo(
    () => buildPermissionAreas(catalog, { query, filter, isAssigned }),
    [catalog, query, filter, isAssigned],
  );
  const visibleAreas = areas.filter((area) => area.items.length > 0);
  const assignedTotal = isAdmin ? catalog.length : catalog.filter((p) => draftCodes.has(p.code)).length;

  const commit = useCallback(
    (plan: TogglePlan, requested: string[]) => {
      const nextChecked = plan.add.length > 0;
      const codes = nextChecked ? plan.add : plan.remove;
      const { ids } = resolveCodesToIds(codes, catalog);
      if (ids.length === 0) return;
      onTogglePermissions(ids, nextChecked);

      const extras = codes.filter((code) => !requested.includes(code));
      if (extras.length > 0) {
        const names = extras.map((code) => descriptionByCode.get(code) ?? code).join(", ");
        toast.info(nextChecked ? `También se agregó lo que necesita: ${names}` : `También se quitó: ${names}`);
      }
    },
    [catalog, onTogglePermissions, descriptionByCode],
  );

  const planContext = useMemo(
    () => ({ draftCodes, dependencyIndex, resourceIndex }),
    [draftCodes, dependencyIndex, resourceIndex],
  );

  const togglePermission = (code: string, nextChecked: boolean) => {
    if (isReadOnly) return;
    commit(planToggle(code, nextChecked, planContext), [code]);
  };

  const editableCodes = (area: PermissionArea) =>
    area.all.map((permission) => permission.code).filter((code) => getDisabledReason(code) === null);

  const areaState = (area: PermissionArea): TriState => {
    if (isAdmin) return "checked";
    const codes = editableCodes(area);
    const checked = codes.filter((code) => draftCodes.has(code)).length;
    if (checked === 0) return "unchecked";
    return checked === codes.length ? "checked" : "indeterminate";
  };

  const toggleArea = (area: PermissionArea) => {
    if (isReadOnly) return;
    const codes = editableCodes(area);
    commit(planBatchToggle(codes, areaState(area) !== "checked", planContext), codes);
  };

  const toggleCollapsed = (key: string) =>
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <div className="space-y-5">
      <PermissionCreateDialog open={isCreateOpen} onOpenChange={setIsCreateOpen} />
      {isAdmin ? (
        <AdminReadOnlyNotice message={ADMIN_ACCESS_MESSAGE} />
      ) : !isEditable ? (
        <AdminReadOnlyNotice message={readOnlyMessage} />
      ) : null}
      {showCatalogAccessNotice ? <AdminReadOnlyNotice message={catalogAccessMessage} /> : null}
      {showCatalogErrorBanner ? (
        <div className="rounded-xl border border-status-critical/30 bg-status-critical/5 px-4 py-3 text-xs text-status-critical">
          <p>{catalogErrorMessage}</p>
          {onRetryCatalog ? (
            <Button type="button" variant="outline" size="sm" className="mt-2" onClick={onRetryCatalog}>
              Reintentar catalogo
            </Button>
          ) : null}
        </div>
      ) : null}

      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <p className="text-sm font-semibold text-txt-body">Permisos del rol</p>
          <p className="text-xs text-txt-muted">
            Prende o apaga lo que este rol puede hacer. Al prender un permiso se agrega lo que necesita para
            funcionar; los cambios se guardan con el botón Guardar.
          </p>
        </div>
        {isEditable && !isAdmin ? (
          <Button type="button" variant="outline" size="sm" className="shrink-0" onClick={() => setIsCreateOpen(true)}>
            <Plus className="size-4" />
            Nuevo permiso
          </Button>
        ) : null}
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-line-struct/60 bg-subtle/20 p-3 md:flex-row md:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-txt-muted" />
          <Input
            type="search"
            aria-label="Buscar permiso"
            placeholder="Buscar por nombre o código..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="pl-9"
          />
        </div>
        <div className="inline-flex shrink-0 rounded-lg border border-line-struct/60 bg-paper p-0.5">
          {FILTERS.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={filter === option.value}
              onClick={() => setFilter(option.value)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                filter === option.value ? "bg-brand text-txt-inverse" : "text-txt-muted hover:text-txt-body",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
        <p className="shrink-0 text-xs text-txt-muted" aria-live="polite">
          {assignedTotal} de {catalog.length} asignados
        </p>
      </div>

      {isLoadingPermissions ? (
        <div className="space-y-2 rounded-xl border border-line-struct/60 bg-subtle/20 p-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={`permissions-skeleton-${index}`} className="h-12 w-full" />
          ))}
        </div>
      ) : visibleAreas.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line-struct/70 bg-subtle/20 px-6 py-10 text-center">
          <p className="text-sm font-semibold text-txt-body">
            {query ? `No hay permisos que coincidan con "${query}".` : "No hay permisos para mostrar."}
          </p>
          {query || filter !== "todos" ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="mt-2"
              onClick={() => {
                setQuery("");
                setFilter("todos");
              }}
            >
              Limpiar búsqueda
            </Button>
          ) : null}
        </div>
      ) : (
        <div className="max-h-[520px] space-y-3 overflow-auto pr-1">
          {visibleAreas.map((area) => {
            // Buscando, todo se despliega para no esconder resultados.
            const isOpen = Boolean(query) || !collapsed.has(area.key);
            const state = areaState(area);
            const contentId = `permission-area-${area.key}`;
            let previousSection = "";
            return (
              <section key={area.key} className="overflow-hidden rounded-xl border border-line-struct/60 bg-paper">
                <div className="flex items-center gap-3 bg-subtle/40 px-4 py-2.5">
                  <TriStateCheckbox
                    state={state}
                    disabled={isReadOnly || editableCodes(area).length === 0}
                    onToggle={() => toggleArea(area)}
                    aria-label={`Todos los permisos de ${area.label}`}
                  />
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={contentId}
                    onClick={() => toggleCollapsed(area.key)}
                    className="flex flex-1 items-center justify-between gap-2 text-left"
                  >
                    <span className="text-sm font-semibold text-txt-body">{area.label}</span>
                    <span className="inline-flex items-center gap-2">
                      <Badge variant="secondary" className="text-[11px]">
                        {isAdmin ? area.all.length : area.assignedCount}/{area.all.length}
                      </Badge>
                      <ChevronDown
                        className={cn("size-4 text-txt-muted transition-transform", isOpen ? "rotate-180" : "")}
                      />
                    </span>
                  </button>
                </div>
                {isOpen ? (
                  <ul id={contentId} className="divide-y divide-line-hairline">
                    {area.items.map(({ permission, section, sensitive }) => {
                      const showSection = section !== previousSection;
                      previousSection = section;
                      const reason = isReadOnly ? null : getDisabledReason(permission.code);
                      const switchControl = (
                        <Switch
                          checked={isAssigned(permission.code)}
                          disabled={isReadOnly || reason !== null}
                          onCheckedChange={(value) => togglePermission(permission.code, value)}
                          aria-label={permission.description || permission.code}
                        />
                      );
                      return (
                        <li key={permission.code}>
                          {showSection ? (
                            <p className="bg-subtle/20 px-4 pt-2.5 pb-1 text-[11px] font-medium tracking-wide text-txt-muted uppercase">
                              {section}
                            </p>
                          ) : null}
                          <div className="flex items-center gap-3 px-4 py-2.5">
                            <div className="min-w-0 flex-1">
                              <p className="flex flex-wrap items-center gap-2 text-sm text-txt-body">
                                {permission.description || permission.code}
                                {sensitive ? (
                                  <Badge
                                    variant="outline"
                                    className="gap-1 border-status-alert/40 text-[10px] text-status-alert"
                                  >
                                    <ShieldAlert className="size-3" />
                                    Sensible
                                  </Badge>
                                ) : null}
                              </p>
                              <p className="truncate font-mono text-[11px] text-txt-muted">{permission.code}</p>
                            </div>
                            {reason ? (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span className="inline-flex" tabIndex={0}>
                                    {switchControl}
                                  </span>
                                </TooltipTrigger>
                                <TooltipContent>{reason}</TooltipContent>
                              </Tooltip>
                            ) : (
                              switchControl
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
