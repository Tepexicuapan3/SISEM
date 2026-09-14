import type { Cie9McDetail, CreateCie9McRequest, UpdateCie9McRequest } from "@api/types";
import type {
  Cie9McDetailsFormValues,
  CreateCie9McFormValues,
} from "@features/admin/modules/catalogos/cie9-mc/domain/cie9-mc.schemas";

export const mapCie9McDetailToFormValues = (
  detail?: Cie9McDetail | null,
): Cie9McDetailsFormValues => ({
  name: detail?.name ?? "",
  code: detail?.code ?? "",
});

export const buildCreateCie9McPayload = (
  values: CreateCie9McFormValues,
): CreateCie9McRequest => ({
  name: values.name.trim(),
  code: values.code.trim(),
});

export const buildUpdateCie9McPayload = (
  values: Cie9McDetailsFormValues,
  dirtyFields: Partial<Record<keyof Cie9McDetailsFormValues, boolean>>,
): UpdateCie9McRequest => {
  const payload: UpdateCie9McRequest = {};

  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }
  if (dirtyFields.code && values.code !== undefined) {
    payload.code = values.code.trim();
  }

  return payload;
};
