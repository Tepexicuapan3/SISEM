import { useState } from "react";
import { pasesReportAPI } from "@api/resources/reportes/pases.api";
import type { ReferralReportParams } from "@api/types";

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

export const useExportReferralReport = () => {
  const [isExporting, setIsExporting] = useState(false);

  const exportReport = async (params: ReferralReportParams) => {
    if (isExporting) return;
    setIsExporting(true);
    try {
      const blob = await pasesReportAPI.exportXlsx(params);
      const filename = `informe_pases_${params.fechaInicio ?? "hoy"}_${params.fechaFin ?? "hoy"}.xlsx`;
      triggerDownload(blob, filename);
    } finally {
      setIsExporting(false);
    }
  };

  return { exportReport, isExporting };
};
