import type { Location } from "react-router-dom";

// Rutas a las que no tiene sentido volver despues de iniciar sesion.
const NON_RETURNABLE_PATHS = new Set(["/", "/login", "/onboarding"]);

/**
 * Ruta interna a la que volver tras re-autenticarse, tomada del
 * `location.state.from` que dejan ProtectedRoute y SessionObserver.
 *
 * Solo acepta paths internos ("/..."): nunca URLs absolutas ni "//host".
 */
export const resolvePostLoginRedirect = (state: unknown): string | null => {
  const from = (state as { from?: Partial<Location> } | null | undefined)
    ?.from;
  const pathname = from?.pathname;

  if (typeof pathname !== "string") return null;
  if (!pathname.startsWith("/") || pathname.startsWith("//")) return null;
  if (NON_RETURNABLE_PATHS.has(pathname)) return null;

  const search = typeof from?.search === "string" ? from.search : "";
  const hash = typeof from?.hash === "string" ? from.hash : "";

  return `${pathname}${search}${hash}`;
};
