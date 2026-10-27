import type { ClaveTipoAutorizacion } from "@api/types/autorizaciones/autorizadores.types";
import type { ScopeSelection } from "@features/admin/modules/catalogos/designacion-autorizadores/domain/designacion.scope";
import type { TipoFormValue } from "@features/admin/modules/autorizadores/domain/autorizador.schemas";

interface Opciones {
  /** "Usar los mismos centros en todos los tipos": los cambios se replican en los tipos elegidos. */
  mismosCentros: boolean;
}

const copiar = (alcance: ScopeSelection): ScopeSelection => ({
  centros: [...alcance.centros],
  tiposCentro: [...alcance.tiposCentro],
  global: alcance.global,
});

const vacio = (): ScopeSelection => ({ centros: [], tiposCentro: [], global: false });

/** Marcar o desmarcar un tipo. Al desmarcarlo su alcance se limpia (nunca queda oculto con datos). */
export const alternarTipo = (
  tipos: TipoFormValue[],
  clave: ClaveTipoAutorizacion,
  seleccionado: boolean,
  { mismosCentros }: Opciones,
): TipoFormValue[] => {
  const referencia = tipos.find((tipo) => tipo.seleccionado && tipo.clave !== clave);
  return tipos.map((tipo) => {
    if (tipo.clave !== clave) return tipo;
    if (!seleccionado) return { ...tipo, seleccionado: false, alcance: vacio() };
    return {
      ...tipo,
      seleccionado: true,
      alcance: mismosCentros && referencia ? copiar(referencia.alcance) : vacio(),
    };
  });
};

export const cambiarAlcance = (
  tipos: TipoFormValue[],
  clave: ClaveTipoAutorizacion,
  alcance: ScopeSelection,
  { mismosCentros }: Opciones,
): TipoFormValue[] =>
  tipos.map((tipo) => {
    const aplica = tipo.clave === clave || (mismosCentros && tipo.seleccionado);
    return aplica ? { ...tipo, alcance: copiar(alcance) } : tipo;
  });

/** Copia el alcance del tipo de origen a todos los tipos elegidos. */
export const unificarAlcance = (
  tipos: TipoFormValue[],
  claveOrigen: ClaveTipoAutorizacion,
): TipoFormValue[] => {
  const origen = tipos.find((tipo) => tipo.clave === claveOrigen);
  if (!origen) return tipos;
  return tipos.map((tipo) => (tipo.seleccionado ? { ...tipo, alcance: copiar(origen.alcance) } : tipo));
};
