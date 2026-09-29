import type { AccessLogAction, AccessLogEventType, AccessLogSection } from "@api/types";

export const ACCESS_LOG_SECTION_LABELS: Record<AccessLogSection, string> = {
  historia_clinica: "Historia clínica",
  estomatologia: "Estomatología",
  alergias: "Alergias",
  consultas: "Consultas",
  consultas_legado: "Consultas previas (legado)",
  odontograma: "Odontograma",
  incapacidades: "Incapacidades",
  estudios: "Estudios",
  antecedentes_personales: "Antecedentes personales",
  antecedentes_familiares: "Antecedentes familiares",
  antecedentes_quirurgicos: "Antecedentes quirúrgicos",
  habitos: "Hábitos",
  tratamientos_dentales: "Tratamientos dentales",
  notas_historicas: "Notas históricas",
  ficha_paciente: "Ficha del paciente",
  reporte_consultas_diario: "Reporte diario de consultas",
  reporte_incapacidades: "Reporte de incapacidades",
  reporte_pases: "Reporte de pases",
  reporte_ambulancias: "Reporte de ambulancias",
};

export const ACCESS_LOG_ACTION_LABELS: Record<AccessLogAction, string> = {
  ver: "Ver",
  imprimir: "Imprimir",
  exportar: "Exportar",
  modificar: "Modificar",
};

export const ACCESS_LOG_EVENT_TYPE_LABELS: Record<AccessLogEventType, string> = {
  acceso: "Consulta de expediente",
  diagnostico_restringido: "Diagnóstico restringido",
};

const DATE_TIME_FORMAT = new Intl.DateTimeFormat("es-MX", {
  dateStyle: "short",
  timeStyle: "medium",
});

export function formatAccessLogDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : DATE_TIME_FORMAT.format(date);
}
