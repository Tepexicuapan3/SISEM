import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Eye,
  EyeOff,
  FolderInput,
  MoreVertical,
  Pencil,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@shared/ui/dropdown-menu";
import { cn } from "@shared/utils/styling/cn";
import { resolveNavIcon } from "@/app/navigation/nav-icons";
import type { ModuleCatalogNodeDTO } from "@api/types";

interface ModuleTreeRowProps {
  node: ModuleCatalogNodeDTO;
  depth: number;
  canMoveUp: boolean;
  canMoveDown: boolean;
  canUpdate: boolean;
  canDelete: boolean;
  isBusy: boolean;
  /** Si el nodo tiene hijos, controla si se muestran o quedan colapsados. */
  isExpanded: boolean;
  onToggleExpand: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onMoveToFolder: () => void;
  onEdit: () => void;
  onToggleVisibility: () => void;
}

/**
 * Fila de un nodo del arbol editable (`ModuleTreeEditor`). Muestra icono,
 * titulo y un resumen de estado en texto plano; toda la fila es el
 * disparador de un menu desplegable con la info completa y las acciones
 * (subir/bajar/mover/editar/ocultar) -- reemplaza el cluster de botones de
 * icono que antes vivia siempre visible en la fila (decision de diseño:
 * un solo punto de entrada por fila en vez de 5 iconos sin etiqueta).
 *
 * `es_sistema=True` deshabilita "Mover"/"Ocultar" (marcado como
 * "protegido" en el menu) pero NO deshabilita "Editar": el
 * titulo/icono/destino de un nodo de sistema se puede seguir editando,
 * solo su posicion y visibilidad estan protegidas (mismo alcance que
 * `assert_not_system` en el backend, invocado solo desde
 * `HideModuleUseCase`/`MoveModuleUseCase`).
 */
export function ModuleTreeRow({
  node,
  depth,
  canMoveUp,
  canMoveDown,
  canUpdate,
  canDelete,
  isBusy,
  isExpanded,
  onToggleExpand,
  onMoveUp,
  onMoveDown,
  onMoveToFolder,
  onEdit,
  onToggleVisibility,
}: ModuleTreeRowProps) {
  const isUnmanaged = node.permissions.length === 0;
  const protectedNode = node.isSystem;
  const hasActions = canUpdate || canDelete;
  const hasChildren = node.items.length > 0;
  // Ver comentario en `NavMain.tsx`: se envuelve en un objeto
  // para no romper react-hooks/static-components con `resolveNavIcon`.
  const icon = { Component: resolveNavIcon(node.icon) };

  const infoLine = [
    node.isSection ? "Carpeta" : "Acceso directo",
    hasChildren && !isExpanded
      ? `${node.items.length} elemento${node.items.length === 1 ? "" : "s"} adentro`
      : null,
    !node.isActive ? "oculto del menú" : null,
    protectedNode ? "protegido (elemento de sistema)" : null,
    isUnmanaged && !node.isSection ? "visible para todos" : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const rowContent = (
    <div
      className={cn(
        "flex min-w-0 flex-1 items-center gap-2.5 rounded-lg border px-3 py-2 text-left",
        node.isActive
          ? "border-line-struct/45 bg-paper/50"
          : "border-dashed border-line-struct/45 bg-subtle/30 opacity-70",
        hasActions && "cursor-pointer transition-colors hover:bg-surface-hover",
      )}
    >
      <icon.Component className="size-4 shrink-0 text-txt-muted" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-txt-body">
          {node.title}
        </p>
        <p className="truncate text-xs text-txt-muted">{infoLine}</p>
      </div>
      {hasActions ? (
        <MoreVertical className="size-4 shrink-0 text-txt-muted" />
      ) : null}
    </div>
  );

  return (
    <div
      className="flex items-center gap-1"
      style={{ marginLeft: depth * 20 }}
    >
      {hasChildren ? (
        <button
          type="button"
          onClick={onToggleExpand}
          className="flex size-6 shrink-0 items-center justify-center rounded-md text-txt-muted transition-colors hover:bg-surface-hover hover:text-txt-body"
          aria-label={isExpanded ? `Contraer ${node.title}` : `Expandir ${node.title}`}
          aria-expanded={isExpanded}
        >
          {isExpanded ? (
            <ChevronDown className="size-4" />
          ) : (
            <ChevronRight className="size-4" />
          )}
        </button>
      ) : (
        <span className="size-6 shrink-0" />
      )}

      {!hasActions ? (
        rowContent
      ) : (
        <DropdownMenu>
          <DropdownMenuTrigger asChild disabled={isBusy}>
            <button
              type="button"
              className="w-full disabled:pointer-events-none disabled:opacity-60"
              disabled={isBusy}
              aria-label={`Ver información y acciones de ${node.title}`}
            >
              {rowContent}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="min-w-56">
            <DropdownMenuLabel className="font-normal text-txt-muted">
              {node.title}
              <br />
              <span className="text-xs">{infoLine}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />

            {canUpdate ? (
              <DropdownMenuItem
                disabled={!canMoveUp}
                onSelect={(event) => {
                  event.preventDefault();
                  onMoveUp();
                }}
              >
                <ChevronUp className="size-4" />
                Subir de posición
              </DropdownMenuItem>
            ) : null}
            {canUpdate ? (
              <DropdownMenuItem
                disabled={!canMoveDown}
                onSelect={(event) => {
                  event.preventDefault();
                  onMoveDown();
                }}
              >
                <ChevronDown className="size-4" />
                Bajar de posición
              </DropdownMenuItem>
            ) : null}
            {canUpdate ? (
              <DropdownMenuItem
                disabled={protectedNode}
                onSelect={onMoveToFolder}
              >
                <FolderInput className="size-4" />
                Mover a otra carpeta
                {protectedNode ? (
                  <span className="ml-auto text-[10px] text-txt-muted">
                    protegido
                  </span>
                ) : null}
              </DropdownMenuItem>
            ) : null}
            {canUpdate ? (
              <DropdownMenuItem onSelect={onEdit}>
                <Pencil className="size-4" />
                Editar
              </DropdownMenuItem>
            ) : null}
            {canDelete ? (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant={node.isActive ? "destructive" : "default"}
                  disabled={protectedNode && node.isActive}
                  onSelect={onToggleVisibility}
                >
                  {node.isActive ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                  {node.isActive ? "Ocultar del menú" : "Restaurar al menú"}
                  {protectedNode && node.isActive ? (
                    <span className="ml-auto text-[10px] text-txt-muted">
                      protegido
                    </span>
                  ) : null}
                </DropdownMenuItem>
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
