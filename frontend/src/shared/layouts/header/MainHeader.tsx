import { SidebarTrigger } from "@shared/ui/sidebar";
import { Separator } from "@shared/ui/separator";
import { SidebarBreadcrumbs } from "@shared/layouts/header/SidebarBreadcrumbs";
import { ModuleSearch } from "@shared/layouts/header/ModuleSearch";
import { ClockDisplay } from "@shared/layouts/header/ClockDisplay";
import { NotificacionesBell } from "@features/notificaciones/components/NotificacionesBell";

/**
 * Header principal del layout.
 *
 * Razon industria:
 * - Centraliza acciones de navegacion (breadcrumbs + buscador).
 * - Mantiene el layout limpio y permite evolucionar el header sin tocar el layout.
 */
export const MainHeader = () => {
  return (
    <header
      role="banner"
      className="relative flex h-16 shrink-0 items-center gap-3 rounded-t-3xl border-b border-line-hairline bg-app/95 px-4 backdrop-blur-sm"
    >
      <div className="flex min-w-0 items-center gap-2">
        <SidebarTrigger
          className="-ml-1"
          aria-label="Abrir/cerrar menú de navegación"
        />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <div className="min-w-0">
          <SidebarBreadcrumbs />
        </div>
      </div>

      <ClockDisplay />

      <div className="ml-auto flex shrink-0 items-center gap-2">
        <NotificacionesBell />
        <div className="w-48 shrink-0 sm:w-56 md:w-72 lg:w-96">
          <ModuleSearch />
        </div>
      </div>
    </header>
  );
};
