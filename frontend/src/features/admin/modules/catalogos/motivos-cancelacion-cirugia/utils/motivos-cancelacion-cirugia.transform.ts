import type { MotivoCancelacionCirugiaDetail, CreateMotivoCancelacionCirugiaRequest, UpdateMotivoCancelacionCirugiaRequest } from "@api/types";
import type {
  MotivoCancelacionCirugiaDetailsFormValues,
  CreateMotivoCancelacionCirugiaFormValues,
} from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/domain/motivos-cancelacion-cirugia.schemas";

export const mapMotivoCancelacionCirugiaDetailToFormValues = (
  detail?: MotivoCancelacionCirugiaDetail | null,
): MotivoCancelacionCirugiaDetailsFormValues => ({
  name: detail?.name ?? "",
});

export const buildCreateMotivoCancelacionCirugiaPayload = (
  values: CreateMotivoCancelacionCirugiaFormValues,
): CreateMotivoCancelacionCirugiaRequest => ({
  name: values.name.trim(),
});

export const buildUpdateMotivoCancelacionCirugiaPayload = (
  values: MotivoCancelacionCirugiaDetailsFormValues,
  dirtyFields: Partial<Record<keyof MotivoCancelacionCirugiaDetailsFormValues, boolean>>,
): UpdateMotivoCancelacionCirugiaRequest => {
  const payload: UpdateMotivoCancelacionCirugiaRequest = {};
  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }
  return payload;
};
