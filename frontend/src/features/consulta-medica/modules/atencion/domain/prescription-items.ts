import type { PrescriptionItem } from "@api/types";

/** Dosis, via, frecuencia y duracion de un renglon; los previos solo traen dosis. */
export const administrationText = (item: PrescriptionItem): string =>
  [item.dose, item.routeLabel, item.frequency, item.duration].filter(Boolean).join(" · ");

/** Renglones vigentes: los cancelados no cuentan ni se muestran. */
export const activePrescriptionItems = (items: PrescriptionItem[] | undefined) =>
  (items ?? []).filter((item) => item.status === "activo");
