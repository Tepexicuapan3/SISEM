import type { AreaClinicaDetail, UpdateAreaClinicaRequest } from "@api/types";
import type { AreaClinicaDetailsFormValues } from "@features/admin/modules/catalogos/areas-clinicas/domain/areas-clinicas.schemas";

export const mapAreaClinicaDetailToFormValues = (
  detail?: AreaClinicaDetail | null,
): AreaClinicaDetailsFormValues => ({
  name: detail?.name ?? "",
});

export const buildUpdateAreaClinicaPayload = (
  values: AreaClinicaDetailsFormValues,
  dirtyFields: Partial<Record<keyof AreaClinicaDetailsFormValues, boolean>>,
): UpdateAreaClinicaRequest => {
  const payload: UpdateAreaClinicaRequest = {};

  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }

  return payload;
};
