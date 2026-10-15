import type { MotivoCancelacionNotaDetail, CreateMotivoCancelacionNotaRequest, UpdateMotivoCancelacionNotaRequest } from "@api/types";
import type {
  MotivoCancelacionNotaDetailsFormValues,
  CreateMotivoCancelacionNotaFormValues,
} from "@features/admin/modules/catalogos/motivos-cancelacion-nota/domain/motivos-cancelacion-nota.schemas";

export const mapMotivoCancelacionNotaDetailToFormValues = (
  detail?: MotivoCancelacionNotaDetail | null,
): MotivoCancelacionNotaDetailsFormValues => ({
  name: detail?.name ?? "",
});

export const buildCreateMotivoCancelacionNotaPayload = (
  values: CreateMotivoCancelacionNotaFormValues,
): CreateMotivoCancelacionNotaRequest => ({
  name: values.name.trim(),
});

export const buildUpdateMotivoCancelacionNotaPayload = (
  values: MotivoCancelacionNotaDetailsFormValues,
  dirtyFields: Partial<Record<keyof MotivoCancelacionNotaDetailsFormValues, boolean>>,
): UpdateMotivoCancelacionNotaRequest => {
  const payload: UpdateMotivoCancelacionNotaRequest = {};
  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }
  return payload;
};
