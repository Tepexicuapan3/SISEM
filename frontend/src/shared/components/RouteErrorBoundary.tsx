import { isRouteErrorResponse, useRouteError } from "react-router-dom";
import { RefreshCwIcon } from "lucide-react";

import { cn } from "@shared/utils/styling/cn";

/**
 * RouteErrorBoundary - errorElement del router.
 *
 * Atrapa errores de render no controlados (ej. desajustes del DOM
 * provocados por el traductor automático del navegador en mobile) para
 * no exponer la pantalla de debug default de React Router en producción.
 */
export const RouteErrorBoundary = () => {
  const error = useRouteError();

  const status = isRouteErrorResponse(error) ? error.status : undefined;
  const title = status === 404 ? "Página no encontrada" : "Algo salió mal";
  const description =
    status === 404
      ? "La ruta que buscás no existe o fue movida."
      : "Ocurrió un error inesperado. Recargá la página para continuar.";

  return (
    <main className="min-h-screen w-full bg-app flex items-center justify-center p-4">
      <div className="max-w-sm w-full flex flex-col items-center text-center gap-4">
        <h1 className="text-xl font-semibold text-fg">{title}</h1>
        <p className="text-sm text-muted">{description}</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className={cn(
            "inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium",
            "bg-brand text-white hover:bg-brand/90 transition-colors",
          )}
        >
          <RefreshCwIcon className="size-4" />
          Recargar página
        </button>
      </div>
    </main>
  );
};
