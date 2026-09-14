import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

/**
 * Sesion del Portal de Citas (autoservicio del paciente) -- INDEPENDIENTE
 * de la sesion de staff (que usa cookie HttpOnly, ver @api/client.ts). El
 * portal se autentica con Bearer token (backend: PortalTokenAuthentication,
 * apps/portal_citas/authentication.py), asi que el token vive acá y se
 * inyecta a mano en cada request (ver portalClient.ts).
 *
 * sessionStorage (no localStorage): un paciente puede usar un dispositivo
 * compartido/kiosco -- no queremos que la sesion sobreviva a cerrar la
 * pestaña.
 */
interface PortalSessionState {
  accessToken: string | null;
  expiraEn: string | null;
  setSession: (accessToken: string, expiraEn: string) => void;
  clearSession: () => void;
  isExpired: () => boolean;
}

export const usePortalSessionStore = create<PortalSessionState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      expiraEn: null,
      setSession: (accessToken, expiraEn) => set({ accessToken, expiraEn }),
      clearSession: () => set({ accessToken: null, expiraEn: null }),
      isExpired: () => {
        const { expiraEn } = get();
        if (!expiraEn) return true;
        return new Date(expiraEn).getTime() <= Date.now();
      },
    }),
    {
      name: "sires-portal-citas-session",
      storage: createJSONStorage(() => sessionStorage),
    },
  ),
);
