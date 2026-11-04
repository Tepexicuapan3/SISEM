import { Building2 } from "lucide-react";
import { useAuthSession } from "@/domains/auth-access/hooks/useAuthSession";

/**
 * Alcance por centro: sin centro de atención asignado el backend no devuelve
 * visitas ni citas, y una lista vacía se confunde con "no hay pacientes".
 * Este aviso lo explica. Es solo UX: el backend es quien filtra.
 */
export const SinCentroAviso = () => {
  const { data: user } = useAuthSession();
  const alcance = user?.alcanceCentros;
  if (!alcance || alcance.todos || alcance.centros.length > 0) return null;

  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-xl border border-status-alert/40 bg-status-alert/10 px-3 py-2.5 text-sm text-status-alert"
    >
      <Building2 className="mt-0.5 size-4 shrink-0" />
      <p>
        No tienes un centro de atención asignado, por eso no ves pacientes, citas ni fichas. Pide a un
        administrador que te asigne tu centro en Administración → Usuarios.
      </p>
    </div>
  );
};
