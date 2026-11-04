import { useAuthSession } from "@/domains/auth-access/hooks/useAuthSession";

const AGENDAR_OTROS_CENTROS = "recepcion:citas:agendar_otros_centros";

/**
 * Alcance por centro de atención para la UI: qué centros ofrecer en
 * selectores y listas. Es solo UX: el backend filtra y rechaza lo de otros
 * centros.
 *
 * - `permite`: trabajar en el centro (visitas, check-in).
 * - `puedeAgendarEn`: agendar citas; incluye el permiso de agendar en otros centros.
 * Si la sesión no trae `alcanceCentros` no se filtra nada.
 */
export const useAlcanceCentros = () => {
  const { data: user } = useAuthSession();
  const alcance = user?.alcanceCentros;
  const ids = new Set(alcance?.centros.map((centro) => centro.id) ?? []);
  const sinFiltro = !alcance || alcance.todos;
  const agendaEnOtros = Boolean(user?.capabilities?.[AGENDAR_OTROS_CENTROS]?.granted);

  const permite = (centroId: number | null | undefined) =>
    sinFiltro || (centroId != null && ids.has(centroId));

  return {
    permite,
    puedeAgendarEn: (centroId: number | null | undefined) => agendaEnOtros || permite(centroId),
    /** El centro cuando el usuario tiene uno solo; null si ve todos o tiene varios. */
    centroPrincipal: !sinFiltro && ids.size === 1 ? [...ids][0] : null,
  };
};
