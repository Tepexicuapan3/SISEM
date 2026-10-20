import type { Parametro, ParametroTipo } from "@api/types/catalogos/parameters.types";

/**
 * Reglas de valor de un parametro. Espejo de `parametro_service.parse_value`
 * del backend: el frontend valida para dar feedback inmediato, pero la regla
 * que manda es la del servidor (que tambien valida).
 */

type ValueRules = Pick<Parametro, "valueType" | "minValue" | "maxValue">;

const TRUE_VALUES = new Set(["true", "1", "s", "si", "sí"]);
const FALSE_VALUES = new Set(["false", "0", "n", "no"]);
const NUMBER_RE = /^-?\d+(\.\d+)?$/;

export const TIPO_LABELS: Record<ParametroTipo, string> = {
  ENTERO: "Entero",
  DECIMAL: "Decimal",
  BOOLEANO: "Sí / No",
  TEXTO: "Texto",
};

export const MODULE_LABELS: Record<string, string> = {
  citas: "Citas",
  incapacidad: "Incapacidad",
  receta: "Receta",
};

export const moduleLabel = (module: string) => MODULE_LABELS[module] ?? module;

/** Devuelve el mensaje de error o null si el valor es valido. */
export function validateParametroValue(rules: ValueRules, raw: string): string | null {
  const text = raw.trim();
  if (rules.valueType === "TEXTO") return null;
  if (rules.valueType === "BOOLEANO") {
    const lowered = text.toLowerCase();
    return TRUE_VALUES.has(lowered) || FALSE_VALUES.has(lowered)
      ? null
      : "Debe ser verdadero o falso.";
  }
  if (!NUMBER_RE.test(text)) return "Debe ser un número.";
  const number = Number(text);
  if (rules.valueType === "ENTERO" && !Number.isInteger(number)) {
    return "Debe ser un número entero.";
  }
  if (rules.minValue !== null && number < rules.minValue) {
    return `No puede ser menor que ${rules.minValue}.`;
  }
  if (rules.maxValue !== null && number > rules.maxValue) {
    return `No puede ser mayor que ${rules.maxValue}.`;
  }
  return null;
}

/** Texto legible para tablas (los booleanos guardados como "true"/"false"). */
export function formatParametroValue(valueType: ParametroTipo, value: string): string {
  if (valueType === "BOOLEANO") return TRUE_VALUES.has(value.toLowerCase()) ? "Sí" : "No";
  return value;
}

export function describeLimits(rules: ValueRules): string | null {
  const { minValue, maxValue } = rules;
  if (minValue !== null && maxValue !== null) return `Entre ${minValue} y ${maxValue}`;
  if (minValue !== null) return `Mínimo ${minValue}`;
  if (maxValue !== null) return `Máximo ${maxValue}`;
  return null;
}
