import { http, HttpResponse, passthrough } from "msw";
import { authHandlers } from "./handlers/auth";
import { usersHandlers } from "./handlers/users";
import { centrosAtencionHandlers } from "./handlers/centros-atencion";
import { areasHandlers } from "./handlers/areas";
import { consultoriosHandlers } from "./handlers/consultorios";
import { rolesHandlers } from "./handlers/roles";
import { permissionsHandlers } from "./handlers/permissions";
import { visitsHandlers } from "./handlers/visits";
import { padronesHandlers } from "./handlers/padrones";
import { getApiUrl } from "./urls";

export const handlers = [
  // 1. REGLAS DE EXCLUSIÓN (Passthrough)
  // Dejar pasar archivos estáticos y de código fuente para no romper Vite/Lazy Loading
  http.get("**/*.ts", () => passthrough()),
  http.get("**/*.tsx", () => passthrough()),
  http.get("**/*.js", () => passthrough()),
  http.get("**/*.jsx", () => passthrough()),
  http.get("**/*.css", () => passthrough()),
  http.get("**/*.svg", () => passthrough()),
  http.get("**/*.png", () => passthrough()),
  http.get("**/*.json", ({ request }) => {
    // Solo dejar pasar JSON si NO es de la API (es decir, si viene de src/ o node_modules)
    if (
      request.url.includes("/src/") ||
      request.url.includes("/node_modules/")
    ) {
      return passthrough();
    }
    // Si es una llamada a API que pide JSON, dejar que sigan los handlers de abajo
    return;
  }),

  // 2. Health Check (Base)
  http.get(getApiUrl("health"), () => {
    return HttpResponse.json({ status: "ok", mode: "test" });
  }),

  // 3. Módulos de Negocio
  ...authHandlers,
  ...usersHandlers,
  ...centrosAtencionHandlers,
  ...areasHandlers,
  ...consultoriosHandlers,
  ...rolesHandlers,
  ...permissionsHandlers,
  ...visitsHandlers,
  ...padronesHandlers,
];
