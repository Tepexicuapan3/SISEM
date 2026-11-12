import * as z from "zod";
import type { PrescriptionItem } from "@api/types";

/** Campos de un renglon de receta: los mismos al agregar y al editar. */
export const prescriptionItemFieldsSchema = z.object({
  dose: z.string().optional(),
  indications: z.string().trim().min(1, { error: "Ingresa las indicaciones" }),
  quantity: z.number().int().min(1, { error: "Minimo 1" }),
  // Via, frecuencia y duracion (RIS art. 30); el backend tambien las exige.
  route: z.string().min(1, { error: "Selecciona la vía de administración" }),
  frequency: z.string().trim().min(1, { error: "Ingresa la frecuencia" }).max(60),
  duration: z.string().trim().min(1, { error: "Ingresa la duración" }).max(60),
});

export const addPrescriptionItemSchema = prescriptionItemFieldsSchema.extend({
  medicationId: z.string().min(1, { error: "Selecciona un medicamento" }),
});

export type PrescriptionItemFieldsValues = z.infer<typeof prescriptionItemFieldsSchema>;
export type AddPrescriptionItemFormValues = z.infer<typeof addPrescriptionItemSchema>;

export const emptyPrescriptionItemFields = (): PrescriptionItemFieldsValues => ({
  dose: "",
  indications: "",
  quantity: 1,
  route: "",
  frequency: "",
  duration: "",
});

/** Valores del formulario a partir de un renglon guardado (los previos a D8 vienen sin via). */
export const prescriptionItemToFields = (item: PrescriptionItem): PrescriptionItemFieldsValues => ({
  dose: item.dose ?? "",
  indications: item.indications,
  quantity: item.quantity,
  route: item.route ?? "",
  frequency: item.frequency ?? "",
  duration: item.duration ?? "",
});

export const prescriptionItemFieldsToPayload = (values: PrescriptionItemFieldsValues) => ({
  quantity: values.quantity,
  indications: values.indications.trim(),
  dose: values.dose?.trim() || undefined,
  route: values.route,
  frequency: values.frequency.trim(),
  duration: values.duration.trim(),
});
