import { toast } from "sonner";
import { ApiError } from "@api/utils/errors";

export const avisarError = (titulo: string, error: unknown) =>
  toast.error(titulo, {
    description: error instanceof ApiError ? error.message : "Intenta nuevamente en unos segundos.",
  });

/** Capacidad escrita a mano: vacía = sin tope (null); si no, entero positivo. */
export const leerCapacidad = (texto: string): number | null | "invalida" => {
  const limpio = texto.trim();
  if (limpio === "") return null;
  const valor = Number(limpio);
  return Number.isInteger(valor) && valor > 0 ? valor : "invalida";
};
