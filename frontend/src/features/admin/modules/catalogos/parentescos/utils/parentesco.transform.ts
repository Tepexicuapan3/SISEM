import type { CreateParentescoRequest } from "@api/types";
import type { CreateParentescoFormValues } from "@features/admin/modules/catalogos/parentescos/domain/parentesco.schemas";

// =============================================================================
// FORM -> API
// =============================================================================

export const buildCreateParentescoPayload = (
  values: CreateParentescoFormValues,
): CreateParentescoRequest => ({
  id: values.id.trim(),
  name: values.name.trim(),
});
