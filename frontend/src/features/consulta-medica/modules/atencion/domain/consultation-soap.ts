/**
 * Apartados de la nota SOAP (his_notas: subjetivo, objetivo, analisis, plan).
 * Cada apartado tiene su letra y su color para distinguirlo de un vistazo,
 * igual que en la nota impresa (consulta_medica/impresion/nota.html).
 */
export const SOAP_SECTIONS = [
  {
    name: "subjective",
    letter: "S",
    label: "Subjetivo",
    hint: "Lo que refiere el paciente: padecimiento actual e interrogatorio por aparatos y sistemas.",
    borderClass: "border-status-info",
    badgeClass: "bg-status-info",
  },
  {
    name: "objective",
    letter: "O",
    label: "Objetivo",
    hint: "Lo que observa y mide el médico: exploración física y hallazgos.",
    borderClass: "border-status-stable",
    badgeClass: "bg-status-stable",
  },
  {
    name: "assessment",
    letter: "A",
    label: "Análisis",
    hint: "Interpretación clínica: impresión diagnóstica y evolución.",
    borderClass: "border-area-gyn",
    badgeClass: "bg-area-gyn",
  },
  {
    name: "plan",
    letter: "P",
    label: "Plan",
    hint: "Qué sigue: plan diagnóstico (estudios) y terapéutico (tratamiento e indicaciones).",
    borderClass: "border-brand",
    badgeClass: "bg-brand",
  },
] as const;

export type SoapSectionName = (typeof SOAP_SECTIONS)[number]["name"];
