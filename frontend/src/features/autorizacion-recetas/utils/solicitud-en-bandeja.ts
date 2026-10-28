import { ApiError } from "@api/utils/errors";
import { RUTA_BANDEJA, rutaDetalle } from "@features/autorizaciones/domain/solicitud.format";

export const CODIGO_GESTIONADA_EN_BANDEJA = "AUTHORIZATION_MANAGED_BY_INBOX";

/**
 * Con AUTORIZACIONES_RECETAS_V2 la receta se decide en la bandeja del motor:
 * ruta a su solicitud (o a la bandeja si el backend no mando el uuid).
 * null si el error es otro.
 */
export const rutaSolicitudEnBandeja = (error: unknown): string | null => {
  if (!(error instanceof ApiError) || error.code !== CODIGO_GESTIONADA_EN_BANDEJA) return null;
  const uuid = error.details?.solicitudUuid;
  return typeof uuid === "string" && uuid ? rutaDetalle(uuid) : RUTA_BANDEJA;
};
