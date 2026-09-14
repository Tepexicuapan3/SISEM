import type { DestinoAmbulanciaDetail, CreateDestinoAmbulanciaRequest, UpdateDestinoAmbulanciaRequest } from "@api/types";
import type {
  DestinoAmbulanciaDetailsFormValues,
  CreateDestinoAmbulanciaFormValues,
} from "@features/admin/modules/catalogos/destinos-ambulancia/domain/destinos-ambulancia.schemas";

export const mapDestinoAmbulanciaDetailToFormValues = (
  detail?: DestinoAmbulanciaDetail | null,
): DestinoAmbulanciaDetailsFormValues => ({
  name: detail?.name ?? "",
  street: detail?.street ?? "",
  zipCode: detail?.zipCode ?? "",
  neighborhood: detail?.neighborhood ?? "",
  borough: detail?.borough ?? "",
  phone: detail?.phone ?? "",
  reference: detail?.reference ?? "",
});

const trimOrUndefined = (value?: string) => {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
};

export const buildCreateDestinoAmbulanciaPayload = (
  values: CreateDestinoAmbulanciaFormValues,
): CreateDestinoAmbulanciaRequest => ({
  name: values.name.trim(),
  street: trimOrUndefined(values.street),
  zipCode: trimOrUndefined(values.zipCode),
  neighborhood: trimOrUndefined(values.neighborhood),
  borough: trimOrUndefined(values.borough),
  phone: trimOrUndefined(values.phone),
  reference: trimOrUndefined(values.reference),
});

const FIELDS = ["name", "street", "zipCode", "neighborhood", "borough", "phone", "reference"] as const;

export const buildUpdateDestinoAmbulanciaPayload = (
  values: DestinoAmbulanciaDetailsFormValues,
  dirtyFields: Partial<Record<keyof DestinoAmbulanciaDetailsFormValues, boolean>>,
): UpdateDestinoAmbulanciaRequest => {
  const payload: UpdateDestinoAmbulanciaRequest = {};

  for (const field of FIELDS) {
    if (!dirtyFields[field] || values[field] === undefined) continue;
    if (field === "name") {
      payload.name = values.name.trim();
    } else {
      payload[field] = trimOrUndefined(values[field]) ?? "";
    }
  }

  return payload;
};
