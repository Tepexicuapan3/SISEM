/**
 * NavMain.tsx
 *
 * Componente que renderiza las secciones principales de navegación.
 * Implementa renderizado recursivo para soportar N niveles de anidamiento.
 * Persistencia de estado de menús abiertos vía Zustand.
 */

import { useState } from "react";
import { ChevronRight, Circle, Search } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useShallow } from "zustand/react/shallow";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@shared/ui/collapsible";
import { Badge } from "@shared/ui/badge";
import { Input } from "@shared/ui/input";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@shared/ui/sidebar";
import { useSidebar } from "@shared/ui/sidebar-context";
import { Tooltip, TooltipContent, TooltipTrigger } from "@shared/ui/tooltip";
import { TruncatedTooltip } from "@shared/ui/truncated-tooltip";
import { cn } from "@shared/utils/styling/cn";
import { normalizeSearchText } from "@shared/utils/text/normalizeSearchText";
import { useSidebarStore } from "@app/state/ui/sidebarStore";
import type { NavItem, NavSection } from "@app/navigation/nav-config";

interface NavMainProps {
  sections: NavSection[];
}

const BADGE_LABELS = {
  Dev: "Dev",
  New: "Nvo",
  Mantenimiento: "Mtto",
} as const;

type BadgeKey = keyof typeof BADGE_LABELS;

const BADGE_VARIANTS = {
  Dev: "alert",
  New: "info",
  Mantenimiento: "critical",
} as const;

const BADGE_DOT_STYLES: Record<BadgeKey, string> = {
  Dev: "bg-status-alert",
  New: "bg-status-info",
  Mantenimiento: "bg-status-critical",
};

const BADGE_TEXT_CLASSES = "max-w-[4rem] truncate";
// Sin tope de ancho fijo: el titulo usa todo el espacio de la columna y
// parte hasta en 2 lineas antes de cortar con "...". `whitespace-normal!`
// le gana al `[&>span:last-child]:truncate` del boton base.
const TITLE_TEXT_CLASSES =
  "line-clamp-2 break-words leading-snug whitespace-normal!";

const resolveBadgeKey = (badge: string): BadgeKey =>
  badge in BADGE_LABELS ? (badge as BadgeKey) : "Dev";

const getBadgeVariant = (badge: string) =>
  BADGE_VARIANTS[resolveBadgeKey(badge)];
const BADGE_TOOLTIPS: Record<BadgeKey, string> = {
  Dev: "En desarrollo",
  New: "Nuevo",
  Mantenimiento: "Mantenimiento",
};

const getBadgeLabel = (badge: string) => BADGE_LABELS[resolveBadgeKey(badge)];
const getBadgeTooltip = (badge: string) =>
  BADGE_TOOLTIPS[resolveBadgeKey(badge)];

const renderBadge = (badge: string, withTooltip: boolean) => {
  const badgeNode = (
    <Badge
      variant={getBadgeVariant(badge)}
      className={cn(
        "shrink-0 whitespace-nowrap px-2 py-0.5 text-[10px] font-semibold tracking-wide",
        BADGE_TEXT_CLASSES,
        getBadgeRingClass(badge),
      )}
    >
      {getBadgeLabel(badge)}
    </Badge>
  );

  if (!withTooltip) return badgeNode;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{badgeNode}</TooltipTrigger>
      <TooltipContent side="top" align="end">
        {getBadgeTooltip(badge)}
      </TooltipContent>
    </Tooltip>
  );
};

const getBadgePriority = (items?: NavItem[]): BadgeKey | null => {
  if (!items?.length) return null;

  const counts: Record<BadgeKey, number> = {
    Dev: 0,
    New: 0,
    Mantenimiento: 0,
  };

  const walk = (nodes?: NavItem[]) => {
    nodes?.forEach((node) => {
      if (node.badge) {
        counts[resolveBadgeKey(node.badge)] += 1;
      }
      if (node.items?.length) walk(node.items);
    });
  };

  walk(items);

  const maxCount = Math.max(counts.New, counts.Mantenimiento, counts.Dev);
  if (maxCount === 0) return null;
  if (counts.New === maxCount) return "New";
  if (counts.Mantenimiento === maxCount) return "Mantenimiento";
  return "Dev";
};

// A partir de esta cantidad de items, una carpeta (a CUALQUIER
// profundidad, no solo secciones raiz) arranca colapsada y suma un
// buscador propio arriba de su lista -- ej. "Catalogos" con ~29 items,
// viva como seccion raiz o anidada dentro de "Administracion". Carpetas
// chicas (la mayoria: 1-6 items) no cambian de comportamiento.
const SECTION_COLLAPSE_THRESHOLD = 8;

/**
 * Componente recursivo para renderizar items de navegación
 * Soporta profundidad infinita usando SidebarMenuSub
 */
function NavRecursiveItem({
  item,
  level = 0,
  openGroups,
  onToggle,
  badgeSeenGroups,
  showInlineTooltips,
  sectionSearch,
  onSectionSearchChange,
}: {
  item: NavItem;
  level?: number;
  openGroups: Record<string, boolean>;
  onToggle: (title: string, isOpen: boolean) => void;
  badgeSeenGroups: Record<string, boolean>;
  showInlineTooltips: boolean;
  sectionSearch: Record<string, string>;
  onSectionSearchChange: (key: string, value: string) => void;
}) {
  const location = useLocation();
  // Active si la URL exacta coincide
  const isActive = location.pathname === item.url;

  // Auto-expand si algun hijo coincide con la ruta actual.
  const hasActiveChild = (items?: NavItem[]): boolean => {
    if (!items) return false;
    return items.some(
      (i) => i.url === location.pathname || hasActiveChild(i.items),
    );
  };

  // Prioridad: Estado persistido > Auto-expand por ruta activa.
  const isOpen = openGroups[item.title] ?? hasActiveChild(item.items);

  const hasSubItems = item.items && item.items.length > 0;
  const childBadgePriority = getBadgePriority(item.items);
  const showBadgeChevron =
    Boolean(childBadgePriority) && !isOpen && !badgeSeenGroups[item.title];

  // Carpeta grande (a cualquier profundidad): suma buscador propio arriba
  // de su lista de hijos -- mismo criterio que las secciones raiz grandes.
  const isSearchableFolder =
    Boolean(hasSubItems) && item.items!.length > SECTION_COLLAPSE_THRESHOLD;
  const searchQuery = sectionSearch[item.title] ?? "";
  const normalizedSearchQuery = normalizeSearchText(searchQuery);
  const visibleChildren =
    isSearchableFolder && normalizedSearchQuery
      ? item.items!.filter((child) =>
          normalizeSearchText(child.title).includes(normalizedSearchQuery),
        )
      : item.items;

  // CASO 1: Item con submenú (Carpeta)
  if (hasSubItems) {
    return (
      <Collapsible
        asChild
        open={isOpen}
        onOpenChange={(open) => onToggle(item.title, open)}
        className="group/collapsible"
      >
        <SidebarMenuItem>
          <CollapsibleTrigger asChild>
            <SidebarMenuButton tooltip={item.title} isActive={isActive}>
              <span className="grid w-full min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2">
                <span className="flex h-4 w-4 items-center justify-center">
                  {/* Ícono: Si es nivel 0 usa el ícono configurado, si no, usa Circle pequeño */}
                  {item.icon ? (
                    <item.icon />
                  ) : (
                    level > 0 && <Circle className="h-2 w-2" />
                  )}
                </span>
                {showInlineTooltips ? (
                  <TruncatedTooltip
                    label={item.title}
                    side="top"
                    align="start"
                    className={`min-w-0 ${TITLE_TEXT_CLASSES}`}
                  >
                    {item.title}
                  </TruncatedTooltip>
                ) : (
                  <span className={`min-w-0 ${TITLE_TEXT_CLASSES}`}>
                    {item.title}
                  </span>
                )}

                <span className="flex items-center gap-2">
                  {item.badge && renderBadge(item.badge, showInlineTooltips)}
                  <span className="flex items-center gap-1.5">
                    {showBadgeChevron && childBadgePriority && (
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          BADGE_DOT_STYLES[childBadgePriority],
                        )}
                      />
                    )}
                    <ChevronRight className="shrink-0 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                  </span>
                </span>
              </span>
            </SidebarMenuButton>
          </CollapsibleTrigger>
          <CollapsibleContent>
            {isSearchableFolder && showInlineTooltips ? (
              <div className="px-2 pb-1.5 pt-1">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-txt-muted" />
                  <Input
                    type="search"
                    value={searchQuery}
                    onChange={(event) =>
                      onSectionSearchChange(item.title, event.target.value)
                    }
                    placeholder={`Buscar en ${item.title.toLowerCase()}`}
                    className="h-7 rounded-md bg-subtle pl-7 text-xs focus-visible:ring-1 focus-visible:ring-line-struct/50 focus-visible:ring-offset-0"
                    aria-label={`Buscar en ${item.title}`}
                  />
                </div>
              </div>
            ) : null}
            {isSearchableFolder && visibleChildren?.length === 0 ? (
              <p className="px-4 pb-1.5 text-xs text-txt-muted">
                Sin resultados para &quot;{searchQuery}&quot;.
              </p>
            ) : (
              <SidebarMenuSub>
                {visibleChildren?.map((subItem) => (
                  <NavRecursiveItem
                    key={subItem.title}
                    item={subItem}
                    level={level + 1}
                    openGroups={openGroups}
                    onToggle={onToggle}
                    badgeSeenGroups={badgeSeenGroups}
                    showInlineTooltips={showInlineTooltips}
                    sectionSearch={sectionSearch}
                    onSectionSearchChange={onSectionSearchChange}
                  />
                ))}
              </SidebarMenuSub>
            )}
          </CollapsibleContent>
        </SidebarMenuItem>
      </Collapsible>
    );
  }

  // CASO 2: Item hoja (Link)
  // Si estamos en nivel 0 (raíz), usamos SidebarMenuButton.
  // Si estamos en nivel > 0 (anidado), usamos SidebarMenuSubButton para correcta indentación.

  if (level === 0) {
    return (
      <SidebarMenuItem>
        <SidebarMenuButton asChild isActive={isActive} tooltip={item.title}>
          <Link
            to={item.url || "#"}
            className="grid w-full min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2"
          >
            <span className="flex h-4 w-4 items-center justify-center">
              {item.icon && <item.icon />}
            </span>
            {showInlineTooltips ? (
              <TruncatedTooltip
                label={item.title}
                side="top"
                align="start"
                className={`min-w-0 ${TITLE_TEXT_CLASSES}`}
              >
                {item.title}
              </TruncatedTooltip>
            ) : (
              <span className={`min-w-0 ${TITLE_TEXT_CLASSES}`}>
                {item.title}
              </span>
            )}
            {item.badge && (
              <span className="flex items-center gap-2">
                {renderBadge(item.badge, showInlineTooltips)}
              </span>
            )}
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  }

  return (
    <SidebarMenuSubItem>
      <SidebarMenuSubButton asChild isActive={isActive}>
        <Link
          to={item.url || "#"}
          className="grid w-full min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-2"
        >
          {showInlineTooltips ? (
            <TruncatedTooltip
              label={item.title}
              side="top"
              align="start"
              className={`min-w-0 ${TITLE_TEXT_CLASSES}`}
            >
              {item.title}
            </TruncatedTooltip>
          ) : (
            <span className={`min-w-0 ${TITLE_TEXT_CLASSES}`}>
              {item.title}
            </span>
          )}
          {item.badge && (
            <span className="flex items-center gap-2">
              {renderBadge(item.badge, showInlineTooltips)}
            </span>
          )}
        </Link>
      </SidebarMenuSubButton>
    </SidebarMenuSubItem>
  );
}

const sectionHasActiveRoute = (items: NavItem[], pathname: string): boolean =>
  items.some(
    (item) =>
      item.url === pathname ||
      (item.items ? sectionHasActiveRoute(item.items, pathname) : false),
  );

export function NavMain({ sections }: NavMainProps) {
  // Usar el store global de Zustand para persistencia
  const { openGroups, toggleGroup, badgeSeenGroups } = useSidebarStore(
    useShallow((state) => ({
      openGroups: state.openGroups,
      toggleGroup: state.toggleGroup,
      badgeSeenGroups: state.badgeSeenGroups,
    })),
  );
  const { state } = useSidebar();
  const showInlineTooltips = state !== "collapsed";
  const location = useLocation();
  // Busqueda por seccion grande (ej. "Catalogos" con ~29 items) -- vive
  // aca, no en un store persistido: es un filtro de "estoy buscando ahora
  // mismo", no una preferencia que deba sobrevivir a un F5.
  const [sectionSearch, setSectionSearch] = useState<Record<string, string>>(
    {},
  );
  const handleSectionSearchChange = (key: string, value: string) => {
    setSectionSearch((current) => ({ ...current, [key]: value }));
  };

  return (
    <>
      {sections.map((section) => {
        if (section.items.length <= SECTION_COLLAPSE_THRESHOLD) {
          return (
            <SidebarGroup key={section.title}>
              <SidebarGroupLabel>{section.title}</SidebarGroupLabel>
              <SidebarMenu>
                {section.items.map((item) => (
                  <NavRecursiveItem
                    key={item.title}
                    item={item}
                    level={0}
                    openGroups={openGroups}
                    onToggle={toggleGroup}
                    badgeSeenGroups={badgeSeenGroups}
                    showInlineTooltips={showInlineTooltips}
                    sectionSearch={sectionSearch}
                    onSectionSearchChange={handleSectionSearchChange}
                  />
                ))}
              </SidebarMenu>
            </SidebarGroup>
          );
        }

        // Seccion grande: se pliega como una carpeta comun -- sus items
        // van a nivel 1 (SidebarMenuSub), igual que los hijos de "Panel" o
        // cualquier otra carpeta con `NavRecursiveItem`. Ademas, arriba de
        // la lista se agrega un buscador que filtra por titulo (normalizado
        // -- sin acentos/mayusculas), parte del propio desplegable.
        const query = sectionSearch[section.title] ?? "";
        const normalizedQuery = normalizeSearchText(query);
        const visibleItems = normalizedQuery
          ? section.items.filter((item) =>
              normalizeSearchText(item.title).includes(normalizedQuery),
            )
          : section.items;

        const nestedItems = (
          <>
            {showInlineTooltips ? (
              <div className="px-2 pb-1.5 pt-1">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-txt-muted" />
                  <Input
                    type="search"
                    value={query}
                    onChange={(event) =>
                      setSectionSearch((current) => ({
                        ...current,
                        [section.title]: event.target.value,
                      }))
                    }
                    placeholder={`Buscar en ${section.title.toLowerCase()}`}
                    className="h-7 rounded-md bg-subtle pl-7 text-xs focus-visible:ring-1 focus-visible:ring-line-struct/50 focus-visible:ring-offset-0"
                    aria-label={`Buscar en ${section.title}`}
                  />
                </div>
              </div>
            ) : null}
            {visibleItems.length === 0 ? (
              <p className="px-4 pb-1.5 text-xs text-txt-muted">
                Sin resultados para &quot;{query}&quot;.
              </p>
            ) : (
              <SidebarMenuSub>
                {visibleItems.map((item) => (
                  <NavRecursiveItem
                    key={item.title}
                    item={item}
                    level={1}
                    openGroups={openGroups}
                    onToggle={toggleGroup}
                    badgeSeenGroups={badgeSeenGroups}
                    showInlineTooltips={showInlineTooltips}
                    sectionSearch={sectionSearch}
                    onSectionSearchChange={handleSectionSearchChange}
                  />
                ))}
              </SidebarMenuSub>
            )}
          </>
        );

        const isOpen =
          openGroups[section.title] ??
          sectionHasActiveRoute(section.items, location.pathname);

        return (
          <Collapsible
            key={section.title}
            open={isOpen}
            onOpenChange={(open) => toggleGroup(section.title, open)}
            className="group/collapsible"
          >
            {/* Sin SidebarGroupLabel: el trigger de abajo usa el MISMO
             * componente/estilo que una carpeta comun (ver "Panel" en
             * NavRecursiveItem) -- un heading aparte diria lo mismo que el
             * trigger y quedaria redundante. */}
            <SidebarGroup>
              <SidebarMenu>
                <SidebarMenuItem>
                  <CollapsibleTrigger asChild>
                    <SidebarMenuButton tooltip={section.title}>
                      <span className="grid w-full min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2">
                        <span className="flex h-4 w-4 items-center justify-center">
                          {section.icon ? <section.icon /> : null}
                        </span>
                        {showInlineTooltips ? (
                          <TruncatedTooltip
                            label={section.title}
                            side="top"
                            align="start"
                            className={`min-w-0 ${TITLE_TEXT_CLASSES}`}
                          >
                            {section.title}
                          </TruncatedTooltip>
                        ) : (
                          <span className={`min-w-0 ${TITLE_TEXT_CLASSES}`}>
                            {section.title}
                          </span>
                        )}
                        <ChevronRight className="shrink-0 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                      </span>
                    </SidebarMenuButton>
                  </CollapsibleTrigger>
                </SidebarMenuItem>
              </SidebarMenu>
              <CollapsibleContent>{nestedItems}</CollapsibleContent>
            </SidebarGroup>
          </Collapsible>
        );
      })}
    </>
  );
}
const BADGE_RING_STYLES: Record<BadgeKey, string> = {
  Dev: "ring-1 ring-inset ring-status-alert/20",
  New: "ring-1 ring-inset ring-status-info/20",
  Mantenimiento: "ring-1 ring-inset ring-status-critical/20",
};

const getBadgeRingClass = (badge: string) =>
  BADGE_RING_STYLES[resolveBadgeKey(badge)];
