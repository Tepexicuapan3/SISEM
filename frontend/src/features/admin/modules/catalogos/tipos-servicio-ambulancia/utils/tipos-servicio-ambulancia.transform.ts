import type { TipoServicioAmbulanciaDetail, CreateTipoServicioAmbulanciaRequest, UpdateTipoServicioAmbulanciaRequest } from "@api/types";
import type {
  TipoServicioAmbulanciaDetailsFormValues,
  CreateTipoServicioAmbulanciaFormValues,
} from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/domain/tipos-servicio-ambulancia.schemas";

export const mapTipoServicioAmbulanciaDetailToFormValues = (
  detail?: TipoServicioAmbulanciaDetail | null,
): TipoServicioAmbulanciaDetailsFormValues => ({
  name: detail?.name ?? "",
});

export const buildCreateTipoServicioAmbulanciaPayload = (
  values: CreateTipoServicioAmbulanciaFormValues,
): CreateTipoServicioAmbulanciaRequest => ({
  name: values.name.trim(),
});

export const buildUpdateTipoServicioAmbulanciaPayload = (
  values: TipoServicioAmbulanciaDetailsFormValues,
  dirtyFields: Partial<Record<keyof TipoServicioAmbulanciaDetailsFormValues, boolean>>,
): UpdateTipoServicioAmbulanciaRequest => {
  const payload: UpdateTipoServicioAmbulanciaRequest = {};
  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }
  return payload;
};
