import type { CentroTipoDesignacion } from "@api/types";

export interface ScopeSelection {
  centros: number[];
  tiposCentro: CentroTipoDesignacion[];
  global: boolean;
}

/**
 * GLOBAL es exclusivo: al marcarlo se limpian centros y tipos; al desmarcarlo
 * se parte de un alcance vacio (nunca se infiere GLOBAL de la ausencia de datos).
 */
export const setGlobalScope = (checked: boolean): ScopeSelection => ({
  centros: [],
  tiposCentro: [],
  global: checked,
});

export const toggleTipoCentro = (
  current: ScopeSelection,
  tipo: CentroTipoDesignacion,
  checked: boolean,
): ScopeSelection => {
  if (current.global) return current;
  const tipos = checked
    ? Array.from(new Set([...current.tiposCentro, tipo]))
    : current.tiposCentro.filter((t) => t !== tipo);
  return { ...current, tiposCentro: tipos };
};

export const toggleCentro = (
  current: ScopeSelection,
  centerId: number,
  checked: boolean,
): ScopeSelection => {
  if (current.global) return current;
  const centros = checked
    ? Array.from(new Set([...current.centros, centerId]))
    : current.centros.filter((id) => id !== centerId);
  return { ...current, centros };
};
