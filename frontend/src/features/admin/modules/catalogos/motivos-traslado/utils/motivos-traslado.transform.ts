import type { MotivoTrasladoDetail, CreateMotivoTrasladoRequest, UpdateMotivoTrasladoRequest } from "@api/types";
import type {
  MotivoTrasladoDetailsFormValues,
  CreateMotivoTrasladoFormValues,
} from "@features/admin/modules/catalogos/motivos-traslado/domain/motivos-traslado.schemas";

export const mapMotivoTrasladoDetailToFormValues = (
  detail?: MotivoTrasladoDetail | null,
): MotivoTrasladoDetailsFormValues => ({
  name: detail?.name ?? "",
  requiresNotes: detail?.requiresNotes ?? false,
});

export const buildCreateMotivoTrasladoPayload = (
  values: CreateMotivoTrasladoFormValues,
): CreateMotivoTrasladoRequest => ({
  name: values.name.trim(),
  requiresNotes: values.requiresNotes,
});

export const buildUpdateMotivoTrasladoPayload = (
  values: MotivoTrasladoDetailsFormValues,
  dirtyFields: Partial<Record<keyof MotivoTrasladoDetailsFormValues, boolean>>,
): UpdateMotivoTrasladoRequest => {
  const payload: UpdateMotivoTrasladoRequest = {};
  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }
  if (dirtyFields.requiresNotes && values.requiresNotes !== undefined) {
    payload.requiresNotes = values.requiresNotes;
  }
  return payload;
};
