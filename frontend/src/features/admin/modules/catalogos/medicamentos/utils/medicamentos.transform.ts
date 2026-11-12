import type {
  CreateMedicamentoRequest,
  MedicamentoDetail,
  UpdateMedicamentoRequest,
} from "@api/types";
import type {
  CreateMedicamentoFormValues,
  MedicamentoDetailsFormValues,
} from "@features/admin/modules/catalogos/medicamentos/domain/medicamentos.schemas";

const textOrNull = (value: string) => value.trim() || null;
const quantityOrNull = (value: string) => (value.trim() ? Number(value) : null);

export const mapMedicamentoDetailToFormValues = (
  detail?: MedicamentoDetail | null,
): MedicamentoDetailsFormValues => ({
  name: detail?.name ?? "",
  code: detail?.code ?? "",
  genericName: detail?.genericName ?? "",
  presentation: detail?.presentation ?? "",
  cuadroBasico: detail?.cuadroBasico ?? "BASICO",
  isControlled: detail?.isControlled ?? false,
  maxQuantity: detail?.maxQuantity ? String(detail.maxQuantity) : "",
});

export const buildCreateMedicamentoPayload = (
  values: CreateMedicamentoFormValues,
): CreateMedicamentoRequest => ({
  name: values.name.trim(),
  code: textOrNull(values.code),
  genericName: textOrNull(values.genericName),
  presentation: textOrNull(values.presentation),
  cuadroBasico: values.cuadroBasico,
  isControlled: values.isControlled,
  maxQuantity: quantityOrNull(values.maxQuantity),
});

export const buildUpdateMedicamentoPayload = (
  values: MedicamentoDetailsFormValues,
  dirtyFields: Partial<Record<keyof MedicamentoDetailsFormValues, boolean>>,
): UpdateMedicamentoRequest => {
  const full = buildCreateMedicamentoPayload(values);
  const payload: UpdateMedicamentoRequest = {};

  (Object.keys(full) as (keyof CreateMedicamentoRequest)[]).forEach((key) => {
    if (dirtyFields[key as keyof MedicamentoDetailsFormValues]) {
      Object.assign(payload, { [key]: full[key] });
    }
  });

  return payload;
};
