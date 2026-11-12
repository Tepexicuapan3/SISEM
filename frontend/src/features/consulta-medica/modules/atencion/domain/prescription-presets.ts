/**
 * Atajos para capturar frecuencia y duracion de un medicamento. Solo llenan
 * el campo: siguen siendo texto libre y el medico puede escribir otro valor.
 */
export const FREQUENCY_PRESETS = [
  "Cada 6 horas",
  "Cada 8 horas",
  "Cada 12 horas",
  "Cada 24 horas",
  "Dosis única",
] as const;

export const DURATION_PRESETS = ["3 días", "5 días", "7 días", "10 días", "30 días"] as const;
