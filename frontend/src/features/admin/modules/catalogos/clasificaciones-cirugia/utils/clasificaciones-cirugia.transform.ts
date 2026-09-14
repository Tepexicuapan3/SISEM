import type { ClasificacionCirugiaDetail, CreateClasificacionCirugiaRequest, UpdateClasificacionCirugiaRequest } from "@api/types";
import type {
  ClasificacionCirugiaDetailsFormValues,
  CreateClasificacionCirugiaFormValues,
} from "@features/admin/modules/catalogos/clasificaciones-cirugia/domain/clasificaciones-cirugia.schemas";

export const mapClasificacionCirugiaDetailToFormValues = (
  detail?: ClasificacionCirugiaDetail | null,
): ClasificacionCirugiaDetailsFormValues => ({
  name: detail?.name ?? "",
});

export const buildCreateClasificacionCirugiaPayload = (
  values: CreateClasificacionCirugiaFormValues,
): CreateClasificacionCirugiaRequest => ({
  name: values.name.trim(),
});

export const buildUpdateClasificacionCirugiaPayload = (
  values: ClasificacionCirugiaDetailsFormValues,
  dirtyFields: Partial<Record<keyof ClasificacionCirugiaDetailsFormValues, boolean>>,
): UpdateClasificacionCirugiaRequest => {
  const payload: UpdateClasificacionCirugiaRequest = {};
  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }
  return payload;
};
