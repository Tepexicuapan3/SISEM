import { useState } from "react";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import type { AdscritosParams } from "@api/types";

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

export const useExportAdscripcionReport = () => {
  const [isExporting, setIsExporting] = useState(false);

  const exportReport = async (params: Omit<AdscritosParams, "page" | "pageSize">) => {
    if (isExporting) return;
    setIsExporting(true);
    try {
      const blob = await adscripcionAPI.exportReporteAdscritos(params);
      triggerDownload(blob, `padron_adscripcion_${new Date().toISOString().slice(0, 10)}.xlsx`);
    } finally {
      setIsExporting(false);
    }
  };

  return { exportReport, isExporting };
};
