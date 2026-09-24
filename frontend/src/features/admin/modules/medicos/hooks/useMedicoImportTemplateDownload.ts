import { useState } from "react";
import { medicosAPI } from "@api/resources/medicos.api";

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

/**
 * Descarga la plantilla .xlsx de importación masiva de médicos.
 */
export function useMedicoImportTemplateDownload() {
  const [isDownloading, setIsDownloading] = useState(false);

  const download = async () => {
    if (isDownloading) return;
    setIsDownloading(true);
    try {
      const blob = await medicosAPI.import.downloadTemplate();
      triggerDownload(blob, "plantilla_medicos.xlsx");
    } finally {
      setIsDownloading(false);
    }
  };

  return { download, isDownloading };
}
