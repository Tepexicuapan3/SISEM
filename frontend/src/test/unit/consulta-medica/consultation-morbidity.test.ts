import { describe, expect, it } from "vitest";
import {
  describeSuggestion,
  followUpError,
  minFollowUpDate,
  todayIso,
} from "@features/consulta-medica/modules/atencion/domain/consultation-morbidity";

const NOW = new Date(2026, 9, 9, 10, 30); // 9 de octubre de 2026, hora local

describe("fechas de seguimiento", () => {
  it("hoy y mañana en formato aaaa-mm-dd", () => {
    expect(todayIso(NOW)).toBe("2026-10-09");
    expect(minFollowUpDate(NOW)).toBe("2026-10-10");
  });

  it("sin 'cita' marcada no hay nada que validar", () => {
    expect(followUpError(false, "", NOW)).toBeNull();
  });

  it("con 'cita' la fecha es obligatoria (regla del legado)", () => {
    expect(followUpError(true, "", NOW)).toContain("Indica");
  });

  it("la fecha tiene que ser posterior a hoy", () => {
    expect(followUpError(true, "2026-10-09", NOW)).toContain("posterior");
    expect(followUpError(true, "2026-10-01", NOW)).toContain("posterior");
    expect(followUpError(true, "2026-11-09", NOW)).toBeNull();
  });
});

describe("describeSuggestion", () => {
  it("primera vez cuando no hay consultas anteriores", () => {
    expect(describeSuggestion("1", 0, "I10")).toBe("Sugerido: primera vez (sin consultas anteriores con I10).");
  });

  it("subsecuente con singular y plural", () => {
    expect(describeSuggestion("2", 1, "I10")).toContain("1 consulta anterior con I10");
    expect(describeSuggestion("2", 3, "I10")).toContain("3 consultas anteriores con I10");
  });

  it("sin CIE no sugiere nada", () => {
    expect(describeSuggestion(null, 0, null)).toBeNull();
  });
});
