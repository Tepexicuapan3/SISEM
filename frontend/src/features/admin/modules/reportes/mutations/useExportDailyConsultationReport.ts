import { useState } from "react";
import { consultasDiarioReportAPI } from "@api/resources/reportes/consultasDiario.api";
import type { DailyConsultationReportParams } from "@api/types";

const triggerDownload = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

export const useExportDailyConsultationReport = () => {
  const [isExporting, setIsExporting] = useState(false);

  const exportReport = async (params: DailyConsultationReportParams) => {
    if (isExporting) return;
    setIsExporting(true);
    try {
      const blob = await consultasDiarioReportAPI.exportXlsx(params);
      const filename = `informe_diario_consulta_${params.fechaInicio ?? "hoy"}_${params.fechaFin ?? "hoy"}.xlsx`;
      triggerDownload(blob, filename);
    } finally {
      setIsExporting(false);
    }
  };

  return { exportReport, isExporting };
};
