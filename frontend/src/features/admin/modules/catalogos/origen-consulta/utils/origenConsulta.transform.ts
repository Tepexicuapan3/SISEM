import type { CreateOrigenConsultaRequest } from "@api/types";
import type { CreateOrigenConsultaFormValues } from "@features/admin/modules/catalogos/origen-consulta/domain/origenConsulta.schemas";

// =============================================================================
// FORM -> API
// =============================================================================

export const buildCreateOrigenConsultaPayload = (
  values: CreateOrigenConsultaFormValues,
): CreateOrigenConsultaRequest => ({
  id: values.id.trim(),
  name: values.name.trim(),
});
