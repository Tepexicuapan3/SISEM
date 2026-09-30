import type { CentroAtencionDetail, CreateCentroAtencionRequest, UpdateCentroAtencionRequest, CentroAtencionExcepcionDetail, CreateCentroAtencionExcepcionRequest, UpdateCentroAtencionExcepcionRequest, TipoExcepcion } from "@api/types";

import type { CentroAtencionDetailsFormValues, CreateCentroAtencionFormValues, UpdateCentroAtencionFormValues, CentroAtencionExcepcionFormValues, CreateCentroAtencionExcepcionFormValues } from "@features/admin/modules/catalogos/centros-atencion/domain/centros-atencion.schemas";

// =============================================================================
// HELPERS
// =============================================================================

const normalizeNullableText = (value?: string | null): string | null => {
  if (value == null) return null;
  const normalized = value.trim();
  return normalized === "" ? null : normalized;
};

const normalizeCode = (value: string) => value.trim().toUpperCase();
const normalizeCenterType = (value: string) => value.trim().toUpperCase();

const normalizeTime = (value?: string | null): string | null => {
  if (!value) return null;
  const normalized = value.trim();
  if (!normalized) return null;
  return normalized.length === 5 ? `${normalized}:00` : normalized;
};

// =============================================================================
// CENTROS DE ATENCION - API -> FORM
// =============================================================================

export const mapCentroAtencionDetailToFormValues = (
  detail?: CentroAtencionDetail | null,
): CentroAtencionDetailsFormValues => ({
  name: detail?.name ?? "",
  code: detail?.code ?? "",
  centerType: detail?.centerType ?? "CLINICA",
  legacyFolio: detail?.legacyFolio ?? null,
  isExternal: detail?.isExternal ?? false,

  address: detail?.address ?? null,
  postalCode: detail?.postalCode ?? null,
  neighborhood: detail?.neighborhood ?? null,
  municipality: detail?.municipality ?? null,
  state: detail?.state ?? null,
  city: detail?.city ?? null,
  phone: detail?.phone ?? null,

  isActive: detail?.isActive ?? true,
});

// =============================================================================
// CENTROS DE ATENCION - FORM -> API
// =============================================================================

export const buildCreateCentroAtencionPayload = (
  values: CreateCentroAtencionFormValues,
): CreateCentroAtencionRequest => ({
  name: values.name.trim(),
  code: normalizeCode(values.code),
  centerType: normalizeCenterType(values.centerType) as
    | "CLINICA"
    | "HOSPITAL"
    | "INSTITUTO",
  legacyFolio: normalizeNullableText(values.legacyFolio),
  isExternal: values.isExternal,

  address: normalizeNullableText(values.address),
  postalCode: normalizeNullableText(values.postalCode),
  neighborhood: normalizeNullableText(values.neighborhood),
  municipality: normalizeNullableText(values.municipality),
  state: normalizeNullableText(values.state),
  city: normalizeNullableText(values.city),
  phone: normalizeNullableText(values.phone),

  isActive: values.isActive,
});

export const buildUpdateCentroAtencionPayload = (
  values: UpdateCentroAtencionFormValues,
  dirtyFields: Partial<Record<keyof CentroAtencionDetailsFormValues, boolean>>,
): UpdateCentroAtencionRequest => {
  const payload: UpdateCentroAtencionRequest = {};

  if (dirtyFields.name && values.name !== undefined) {
    payload.name = values.name.trim();
  }

  if (dirtyFields.code && values.code !== undefined) {
    payload.code = normalizeCode(values.code);
  }

  if (dirtyFields.centerType && values.centerType !== undefined) {
    payload.centerType = normalizeCenterType(values.centerType) as
      | "CLINICA"
      | "HOSPITAL"
      | "INSTITUTO";
  }

  if (dirtyFields.legacyFolio) {
    payload.legacyFolio = normalizeNullableText(values.legacyFolio);
  }

  if (dirtyFields.isExternal && values.isExternal !== undefined) {
    payload.isExternal = values.isExternal;
  }

  if (dirtyFields.address) {
    payload.address = normalizeNullableText(values.address);
  }

  if (dirtyFields.postalCode) {
    payload.postalCode = normalizeNullableText(values.postalCode);
  }

  if (dirtyFields.neighborhood) {
    payload.neighborhood = normalizeNullableText(values.neighborhood);
  }

  if (dirtyFields.municipality) {
    payload.municipality = normalizeNullableText(values.municipality);
  }

  if (dirtyFields.state) {
    payload.state = normalizeNullableText(values.state);
  }

  if (dirtyFields.city) {
    payload.city = normalizeNullableText(values.city);
  }

  if (dirtyFields.phone) {
    payload.phone = normalizeNullableText(values.phone);
  }

  if (dirtyFields.isActive && values.isActive !== undefined) {
    payload.isActive = values.isActive;
  }

  return payload;
};

// =============================================================================
// EXCEPCIONES - API -> FORM
// =============================================================================

export const mapCentroAtencionExcepcionToFormValues = (
  detail?: CentroAtencionExcepcionDetail | null,
): CentroAtencionExcepcionFormValues => ({
  centerId: detail?.centerId ?? 0,
  date: detail?.date ?? "",
  tipo: detail?.tipo ?? "CERRADO",
  reason: detail?.reason ?? "",
  openingTime: detail?.openingTime ?? null,
  closingTime: detail?.closingTime ?? null,
  isActive: detail?.isActive ?? true,
});

// =============================================================================
// EXCEPCIONES - FORM -> API
// =============================================================================

export const buildCreateCentroAtencionExcepcionPayload = (
  values: CreateCentroAtencionExcepcionFormValues,
): CreateCentroAtencionExcepcionRequest => ({
  centerId: values.centerId,
  date: values.date,
  tipo: values.tipo as TipoExcepcion,
  reason: values.reason.trim(),
  openingTime: normalizeTime(values.openingTime),
  closingTime: normalizeTime(values.closingTime),
  isActive: values.isActive,
});

export const buildUpdateCentroAtencionExcepcionPayload = (
  values: Partial<CentroAtencionExcepcionFormValues>,
  dirtyFields: Partial<Record<keyof CentroAtencionExcepcionFormValues, boolean>>,
): UpdateCentroAtencionExcepcionRequest => {
  const payload: UpdateCentroAtencionExcepcionRequest = {};

  if (dirtyFields.centerId && values.centerId !== undefined) {
    payload.centerId = values.centerId;
  }

  if (dirtyFields.date && values.date !== undefined) {
    payload.date = values.date;
  }

  if (dirtyFields.tipo && values.tipo !== undefined) {
    payload.tipo = values.tipo as TipoExcepcion;
  }

  if (dirtyFields.reason && values.reason !== undefined) {
    payload.reason = values.reason.trim();
  }

  if (dirtyFields.openingTime) {
    payload.openingTime = normalizeTime(values.openingTime);
  }

  if (dirtyFields.closingTime) {
    payload.closingTime = normalizeTime(values.closingTime);
  }

  if (dirtyFields.isActive && values.isActive !== undefined) {
    payload.isActive = values.isActive;
  }

  return payload;
};