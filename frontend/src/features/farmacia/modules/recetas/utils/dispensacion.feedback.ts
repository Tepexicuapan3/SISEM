import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

const DISPENSACION_ERROR_MESSAGES: Record<string, string> = {
  PRESCRIPTION_NOT_FOUND: "La receta ya no existe.",
  PRESCRIPTION_NOT_AUTHORIZED: "La receta todavia no esta autorizada para dispensarse.",
  PRESCRIPTION_ITEM_NOT_FOUND: "Uno o mas items de receta no existen o fueron cancelados.",
  MEDICATION_NOT_MAPPED: "Uno o mas medicamentos no tienen insumo mapeado en farmacia.",
  FRACTIONAL_QUANTITY_NOT_ALLOWED: "La cantidad calculada no admite fracciones para este insumo.",
  INSUFFICIENT_STOCK: "No hay stock suficiente en el almacen seleccionado.",
  ALREADY_DISPENSED: "Este item de receta ya fue dispensado por completo.",
  DISPENSATION_EXCEEDS_PRESCRIBED: "La cantidad solicitada excede lo prescrito para este item.",
  ROLE_NOT_ALLOWED: "No tienes permiso para dispensar recetas.",
  VALIDATION_ERROR: "Revisa los datos capturados.",
  SESSION_EXPIRED: "Tu sesion expiro. Inicia sesion nuevamente.",
  NETWORK_ERROR: "No hay conexion con el servidor. Intenta nuevamente.",
};

export const getDispensacionErrorMessage = (error: unknown, fallback: string) => {
  return getCatalogErrorMessage(error, fallback, DISPENSACION_ERROR_MESSAGES);
};
