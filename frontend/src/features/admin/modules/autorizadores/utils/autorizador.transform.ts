import type {
  AutorizadorAltaRequest,
  AutorizadorEdicionRequest,
  AutorizadorItem,
  ClaveTipoAutorizacion,
  TipoAsignadoRequest,
} from "@api/types/autorizaciones/autorizadores.types";
import type {
  AutorizadorFormValues,
  TipoFormValue,
} from "@features/admin/modules/autorizadores/domain/autorizador.schemas";

const hoyIso = () => {
  const ahora = new Date();
  const mes = String(ahora.getMonth() + 1).padStart(2, "0");
  const dia = String(ahora.getDate()).padStart(2, "0");
  return `${ahora.getFullYear()}-${mes}-${dia}`;
};

const tipoVacio = (clave: ClaveTipoAutorizacion): TipoFormValue => ({
  clave,
  seleccionado: false,
  alcance: { centros: [], tiposCentro: [], global: false },
});

/** `claves`: tipos del catalogo, en el orden en que se muestran. */
export const buildEmptyAutorizadorValues = (claves: ClaveTipoAutorizacion[]): AutorizadorFormValues => ({
  usuarioId: 0,
  cargo: "",
  numeroOficio: "",
  fechaInicioVigencia: hoyIso(),
  fechaFinVigencia: "",
  tipos: claves.map(tipoVacio),
});

export const mapAutorizadorToFormValues = (
  item: AutorizadorItem,
  claves: ClaveTipoAutorizacion[],
): AutorizadorFormValues => ({
  usuarioId: item.usuario.id,
  cargo: item.cargo ?? "",
  numeroOficio: item.numeroOficio ?? "",
  fechaInicioVigencia: item.fechaInicioVigencia,
  fechaFinVigencia: item.fechaFinVigencia,
  tipos: claves.map((clave) => {
    const asignado = item.tipos.find((tipo) => tipo.clave === clave);
    if (!asignado) return tipoVacio(clave);
    return {
      clave,
      seleccionado: true,
      alcance: {
        centros: asignado.alcance.centros.map((centro) => centro.id),
        tiposCentro: [...asignado.alcance.tiposCentro],
        global: asignado.alcance.global,
      },
    };
  }),
});

const textoONulo = (valor: string) => valor.trim() || null;

/** Solo los tipos elegidos. "Todos los centros" es exclusivo: va sin centros ni tipos. */
const buildTiposRequest = (tipos: TipoFormValue[]): TipoAsignadoRequest[] =>
  tipos
    .filter((tipo) => tipo.seleccionado)
    .map((tipo) => ({
      claveTipo: tipo.clave,
      alcance: tipo.alcance.global
        ? { centros: [], tiposCentro: [], global: true }
        : {
            centros: [...tipo.alcance.centros],
            tiposCentro: [...tipo.alcance.tiposCentro],
            global: false,
          },
    }));

export const buildAltaPayload = (valores: AutorizadorFormValues): AutorizadorAltaRequest => ({
  usuarioId: valores.usuarioId,
  cargo: textoONulo(valores.cargo),
  numeroOficio: textoONulo(valores.numeroOficio),
  fechaInicioVigencia: valores.fechaInicioVigencia,
  fechaFinVigencia: valores.fechaFinVigencia,
  tipos: buildTiposRequest(valores.tipos),
});

export const buildEdicionPayload = (
  valores: AutorizadorFormValues,
  version: number,
): AutorizadorEdicionRequest => ({
  cargo: textoONulo(valores.cargo),
  numeroOficio: textoONulo(valores.numeroOficio),
  tipos: buildTiposRequest(valores.tipos),
  version,
});
