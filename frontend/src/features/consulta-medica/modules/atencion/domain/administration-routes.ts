/**
 * Vias de administracion de un medicamento de la receta (RIS art. 30).
 * Espejo de `VisitPrescriptionItem.Route` del backend, que es quien valida.
 */
export const ADMINISTRATION_ROUTES = [
  { value: "oral", label: "Oral" },
  { value: "sublingual", label: "Sublingual" },
  { value: "topica", label: "Tópica" },
  { value: "oftalmica", label: "Oftálmica" },
  { value: "otica", label: "Ótica" },
  { value: "nasal", label: "Nasal" },
  { value: "inhalada", label: "Inhalada" },
  { value: "rectal", label: "Rectal" },
  { value: "vaginal", label: "Vaginal" },
  { value: "intramuscular", label: "Intramuscular" },
  { value: "intravenosa", label: "Intravenosa" },
  { value: "subcutanea", label: "Subcutánea" },
  { value: "transdermica", label: "Transdérmica" },
] as const;

export type AdministrationRoute = (typeof ADMINISTRATION_ROUTES)[number]["value"];
