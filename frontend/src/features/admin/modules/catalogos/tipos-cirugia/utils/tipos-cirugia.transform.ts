import type { TipoCirugiaDetail, CreateTipoCirugiaRequest, UpdateTipoCirugiaRequest } from "@api/types";
import type {
  TipoCirugiaDetailsFormValues,
  CreateTipoCirugiaFormValues,
} from "@features/admin/modules/catalogos/tipos-cirugia/domain/tipos-cirugia.schemas";

export const mapTipoCirugiaDetailToFormValues = (
  detail?: TipoCirugiaDetail | null,
): TipoCirugiaDetailsFormValues => ({
  name: detail?.name ?? "",
});

export const buildCreateTipoCirugiaPayload = (
  values: CreateTipoCirugiaFormValues,
): CreateTipoCirugiaRequest => ({
  name: values.name.trim(),
});

export const buildUpdateTipoCirugiaPayload = (
  values: TipoCirugiaDetailsFormValues,
  dirtyFields: Partial<Record<keyof TipoCirugiaDetailsFormValues, boolean>>,
): UpdateTipoCirugiaRequest => {
  const payload: UpdateTipoCirugiaRequest = {};
  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }
  return payload;
};
