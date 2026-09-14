import type { TipoTrasladoDetail, CreateTipoTrasladoRequest, UpdateTipoTrasladoRequest } from "@api/types";
import type {
  TipoTrasladoDetailsFormValues,
  CreateTipoTrasladoFormValues,
} from "@features/admin/modules/catalogos/tipos-traslado/domain/tipos-traslado.schemas";

export const mapTipoTrasladoDetailToFormValues = (
  detail?: TipoTrasladoDetail | null,
): TipoTrasladoDetailsFormValues => ({
  name: detail?.name ?? "",
});

export const buildCreateTipoTrasladoPayload = (
  values: CreateTipoTrasladoFormValues,
): CreateTipoTrasladoRequest => ({
  name: values.name.trim(),
});

export const buildUpdateTipoTrasladoPayload = (
  values: TipoTrasladoDetailsFormValues,
  dirtyFields: Partial<Record<keyof TipoTrasladoDetailsFormValues, boolean>>,
): UpdateTipoTrasladoRequest => {
  const payload: UpdateTipoTrasladoRequest = {};
  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }
  return payload;
};
