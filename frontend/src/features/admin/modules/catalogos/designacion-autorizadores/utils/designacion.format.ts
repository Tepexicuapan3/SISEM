import type { DesignacionAlcance } from "@api/types";
import { formatCatalogDate } from "@features/admin/modules/catalogos/shared/utils/catalog-format";

export const formatDate = formatCatalogDate;

const TIPO_LABELS = {
  CLINICA: "Todas las clínicas",
  HOSPITAL: "Todos los hospitales",
  INSTITUTO: "Todos los institutos",
} as const;

/** Etiquetas legibles del alcance para tabla (GLOBAL, tipos, centros). */
export const describeAlcance = (alcance: DesignacionAlcance): string[] => {
  if (alcance.global) return ["Todos los centros"];
  return [
    ...alcance.tiposCentro.map((tipo) => TIPO_LABELS[tipo]),
    ...alcance.centros.map((c) => c.name),
  ];
};
