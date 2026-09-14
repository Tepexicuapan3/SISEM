import { useState } from "react";
import { incapacidadesReportAPI } from "@api/resources/reportes/incapacidades.api";
import type { MedicalLeaveReportParams } from "@api/types";

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

export const useExportMedicalLeaveReport = () => {
  const [isExporting, setIsExporting] = useState(false);

  const exportReport = async (params: MedicalLeaveReportParams) => {
    if (isExporting) return;
    setIsExporting(true);
    try {
      const blob = await incapacidadesReportAPI.exportXlsx(params);
      const filename = `informe_incapacidades_${params.fechaInicio ?? "hoy"}_${params.fechaFin ?? "hoy"}.xlsx`;
      triggerDownload(blob, filename);
    } finally {
      setIsExporting(false);
    }
  };

  return { exportReport, isExporting };
};
