import type { MotivoBajaPadronDetail, CreateMotivoBajaPadronRequest, UpdateMotivoBajaPadronRequest } from "@api/types";
import type {
  MotivoBajaPadronDetailsFormValues,
  CreateMotivoBajaPadronFormValues,
} from "@features/admin/modules/catalogos/motivos-baja-padron/domain/motivos-baja-padron.schemas";

export const mapMotivoBajaPadronDetailToFormValues = (
  detail?: MotivoBajaPadronDetail | null,
): MotivoBajaPadronDetailsFormValues => ({
  name: detail?.name ?? "",
});

export const buildCreateMotivoBajaPadronPayload = (
  values: CreateMotivoBajaPadronFormValues,
): CreateMotivoBajaPadronRequest => ({
  name: values.name.trim(),
});

export const buildUpdateMotivoBajaPadronPayload = (
  values: MotivoBajaPadronDetailsFormValues,
  dirtyFields: Partial<Record<keyof MotivoBajaPadronDetailsFormValues, boolean>>,
): UpdateMotivoBajaPadronRequest => {
  const payload: UpdateMotivoBajaPadronRequest = {};
  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }
  return payload;
};
