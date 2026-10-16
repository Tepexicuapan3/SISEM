import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  impresionAPI,
  type PrintableDocument,
  type PrintErrorBody,
} from "@api/resources/impresion.api";

const REVOKE_DELAY_MS = 60_000;

const ERROR_MESSAGES: Record<string, string> = {
  ROLE_NOT_ALLOWED: "No tienes permiso para imprimir este documento.",
  DOCUMENT_TYPE_NOT_FOUND: "Tipo de documento no disponible.",
  VISIT_NOT_FOUND: "No se encontró la visita.",
  DOCUMENT_NOT_PRINTABLE: "Este documento todavía no se puede imprimir.",
  PRINT_BUSY:
    "El servicio de impresión está ocupado. Intenta de nuevo en unos segundos.",
  PRINT_RENDER_ERROR: "No se pudo generar el PDF. Intenta de nuevo.",
  PRINT_AUDIT_ERROR:
    "No se pudo registrar la impresión. No se generó el documento.",
};

const FALLBACK_MESSAGE = "No se pudo generar el PDF.";

/** Extrae `{code, message}` del Blob JSON que devuelve axios con responseType blob. */
async function readErrorBody(error: unknown): Promise<PrintErrorBody | null> {
  const data = (error as { response?: { data?: unknown } })?.response?.data;
  try {
    if (data instanceof Blob) {
      return JSON.parse(await data.text()) as PrintErrorBody;
    }
    if (data && typeof data === "object") return data as PrintErrorBody;
  } catch {
    /* cuerpo no JSON */
  }
  return null;
}

export async function resolvePrintErrorMessage(
  error: unknown,
): Promise<string> {
  const body = await readErrorBody(error);
  if (body?.code && ERROR_MESSAGES[body.code]) return ERROR_MESSAGES[body.code];
  return body?.message || FALLBACK_MESSAGE;
}

function triggerDownload(url: string, filename: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/**
 * Imprime un documento via `/impresion/<documento>/<id>`.
 *
 * La pestania se abre de forma SINCRONA dentro del click handler (antes de
 * cualquier await) para esquivar el bloqueador de popups; luego se le asigna
 * la URL del blob. Si el navegador igual la bloquea, se descarga el PDF.
 */
export function usePrintDocument(documento: PrintableDocument) {
  const [isPrinting, setIsPrinting] = useState(false);
  const inFlight = useRef(false);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
    },
    [],
  );

  const print = useCallback(
    async (resourceId: number): Promise<boolean> => {
      if (inFlight.current) return false;
      inFlight.current = true;
      setIsPrinting(true);

      // Sincrono: debe ocurrir en el mismo tick del click del usuario.
      const tab = window.open("", "_blank");

      try {
        const result = await impresionAPI.print(documento, resourceId);
        const url = URL.createObjectURL(result.blob);
        if (tab && !tab.closed) {
          tab.location.href = url;
        } else {
          triggerDownload(
            url,
            result.filename ?? `${documento}_${resourceId}.pdf`,
          );
        }
        timers.current.push(
          setTimeout(() => URL.revokeObjectURL(url), REVOKE_DELAY_MS),
        );
        return true;
      } catch (error) {
        tab?.close();
        toast.error(await resolvePrintErrorMessage(error));
        return false;
      } finally {
        inFlight.current = false;
        setIsPrinting(false);
      }
    },
    [documento],
  );

  return { print, isPrinting };
}
