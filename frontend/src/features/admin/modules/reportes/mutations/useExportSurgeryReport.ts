import { useState } from "react";
import { cirugiasReportAPI } from "@api/resources/reportes/cirugias.api";
import type { SurgeryReportParams } from "@api/types";

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

export const useExportSurgeryReport = () => {
  const [isExporting, setIsExporting] = useState(false);

  const exportReport = async (params: SurgeryReportParams) => {
    if (isExporting) return;
    setIsExporting(true);
    try {
      const blob = await cirugiasReportAPI.exportXlsx(params);
      const filename = `informe_cirugias_${params.fechaInicio ?? "hoy"}_${params.fechaFin ?? "hoy"}.xlsx`;
      triggerDownload(blob, filename);
    } finally {
      setIsExporting(false);
    }
  };

  return { exportReport, isExporting };
};
