import apiClient from "@api/client";

/** Documentos imprimibles soportados por `GET /impresion/<documento>/<id>`. */
export type PrintableDocument = "ficha" | "receta" | "nota";

export interface PrintDocumentResult {
  blob: Blob;
  filename: string | null;
  /** Numero de copia (header `X-Print-Copy`). */
  copy: number | null;
  /** `ORIGINAL` | `REIMPRESION` (header `X-Print-Type`). */
  type: string | null;
  logId: number | null;
}

/** Forma del error JSON del backend (`error_response`). */
export interface PrintErrorBody {
  code?: string;
  message?: string;
  status?: number;
}

function parseFilename(disposition: unknown): string | null {
  if (typeof disposition !== "string") return null;
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  return match ? decodeURIComponent(match[1]) : null;
}

function parseIntHeader(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const n = Number.parseInt(value, 10);
  return Number.isNaN(n) ? null : n;
}

export const impresionAPI = {
  /**
   * Descarga el PDF como Blob. El backend registra la impresion (bitacora +
   * numero de copia) en cada llamada exitosa: NO reintentar automaticamente.
   */
  print: async (
    documento: PrintableDocument,
    resourceId: number,
  ): Promise<PrintDocumentResult> => {
    const response = await apiClient.get(
      `/impresion/${documento}/${resourceId}`,
      { responseType: "blob" },
    );
    const headers = (response.headers ?? {}) as Record<string, unknown>;
    return {
      blob: new Blob([response.data as Blob], { type: "application/pdf" }),
      filename: parseFilename(headers["content-disposition"]),
      copy: parseIntHeader(headers["x-print-copy"]),
      type:
        typeof headers["x-print-type"] === "string"
          ? (headers["x-print-type"] as string)
          : null,
      logId: parseIntHeader(headers["x-print-log-id"]),
    };
  },
};
