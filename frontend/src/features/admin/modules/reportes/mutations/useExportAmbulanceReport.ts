import { useState } from "react";
import { ambulanciasReportAPI } from "@api/resources/reportes/ambulancias.api";
import type { AmbulanceReportParams } from "@api/types";

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

export const useExportAmbulanceReport = () => {
  const [isExporting, setIsExporting] = useState(false);

  const exportReport = async (params: AmbulanceReportParams) => {
    if (isExporting) return;
    setIsExporting(true);
    try {
      const blob = await ambulanciasReportAPI.exportXlsx(params);
      const filename = `informe_ambulancias_${params.fechaInicio ?? "hoy"}_${params.fechaFin ?? "hoy"}.xlsx`;
      triggerDownload(blob, filename);
    } finally {
      setIsExporting(false);
    }
  };

  return { exportReport, isExporting };
};
