import type { CreateCalidadLaboralRequest } from "@api/types";
import type { CreateCalidadLaboralFormValues } from "@features/admin/modules/catalogos/calidad-laboral/domain/calidadLaboral.schemas";

// =============================================================================
// FORM -> API
// =============================================================================

export const buildCreateCalidadLaboralPayload = (
  values: CreateCalidadLaboralFormValues,
): CreateCalidadLaboralRequest => ({
  id: values.id.trim(),
  name: values.name.trim(),
});
