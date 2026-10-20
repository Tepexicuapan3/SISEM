import * as z from "zod";
import type { Parametro } from "@api/types/catalogos/parameters.types";
import { validateParametroValue } from "@features/admin/modules/catalogos/parametros/domain/parametro.value";

type ValueRules = Pick<Parametro, "valueType" | "minValue" | "maxValue">;

/** El tipo y los limites dependen del parametro: el schema se arma por definicion. */
export const buildParametroValueSchema = (rules: ValueRules) =>
  z.object({
    value: z.string().superRefine((value, ctx) => {
      const message = validateParametroValue(rules, value);
      if (message) ctx.addIssue({ code: "custom", message });
    }),
  });

export type ParametroValueFormValues = z.infer<ReturnType<typeof buildParametroValueSchema>>;
