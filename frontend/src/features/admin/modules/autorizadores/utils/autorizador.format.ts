import type {
  AlcanceAutorizador,
  EstadoVigencia,
  EstatusAutorizador,
  MovimientoAutorizador,
} from "@api/types/autorizaciones/autorizadores.types";
import { formatCatalogDate } from "@features/admin/modules/catalogos/shared/utils/catalog-format";

export const formatFecha = formatCatalogDate;

type VarianteBadge = "stable" | "alert" | "critical" | "info" | "outline";

interface Etiqueta {
  etiqueta: string;
  variante: VarianteBadge;
}

const VIGENCIA: Record<EstadoVigencia, Etiqueta> = {
  VIGENTE: { etiqueta: "Vigente", variante: "stable" },
  POR_VENCER: { etiqueta: "Por vencer", variante: "alert" },
  VENCIDO: { etiqueta: "Vencido", variante: "critical" },
  PENDIENTE_INICIO: { etiqueta: "Por iniciar", variante: "info" },
};

const ESTATUS: Record<EstatusAutorizador, Etiqueta> = {
  ACTIVO: { etiqueta: "Activo", variante: "stable" },
  SUSPENDIDO: { etiqueta: "Suspendido", variante: "alert" },
  INACTIVO: { etiqueta: "Inactivo", variante: "outline" },
};

export const describirVigencia = (estado: EstadoVigencia): Etiqueta => VIGENCIA[estado];
export const describirEstatus = (estatus: EstatusAutorizador): Etiqueta => ESTATUS[estatus];

export const OPCIONES_VIGENCIA = Object.entries(VIGENCIA).map(([valor, { etiqueta }]) => ({
  valor: valor as EstadoVigencia,
  etiqueta,
}));
export const OPCIONES_ESTATUS = Object.entries(ESTATUS).map(([valor, { etiqueta }]) => ({
  valor: valor as EstatusAutorizador,
  etiqueta,
}));

const TIPO_CENTRO = {
  CLINICA: "Todas las clínicas",
  HOSPITAL: "Todos los hospitales",
  INSTITUTO: "Todos los institutos",
} as const;

export const describirAlcance = (alcance: AlcanceAutorizador): string[] => {
  if (alcance.global) return ["Todos los centros"];
  return [
    ...alcance.tiposCentro.map((tipo) => TIPO_CENTRO[tipo]),
    ...alcance.centros.map((centro) => centro.nombre),
  ];
};

export const MOVIMIENTOS: Record<MovimientoAutorizador["tipoMovimiento"], string> = {
  ALTA: "Alta",
  EDICION: "Edición",
  RENOVACION: "Renovación de vigencia",
  SUSPENSION: "Suspensión",
  REACTIVACION: "Reactivación",
  BAJA: "Baja",
  ALTA_TIPO: "Tipo asignado",
  BAJA_TIPO: "Tipo retirado",
  ALTA_CENTRO: "Centro asignado",
  BAJA_CENTRO: "Centro retirado",
  VENCIMIENTO: "Vencimiento",
};
