import { describe, expect, it } from "vitest";
import {
  describeSuggestion,
  followUpError,
  FOLLOW_UP_SHORTCUTS,
  followUpMonthRange,
  groupSlotsByShift,
  minFollowUpDate,
  shortcutStartDate,
  todayIso,
} from "@features/consulta-medica/modules/atencion/domain/consultation-morbidity";

const NOW = new Date(2026, 9, 9, 10, 30); // 9 de octubre de 2026, hora local

describe("atajos de seguimiento", () => {
  const byLabel = (label: string) => FOLLOW_UP_SHORTCUTS.find((s) => s.label === label)!;

  it("próximo disponible arranca mañana", () => {
    expect(shortcutStartDate(byLabel("Próximo disponible"), NOW)).toBe("2026-10-10");
  });

  it("si la consulta es de una fecha posterior a hoy, arranca el día siguiente a la consulta", () => {
    expect(shortcutStartDate(byLabel("Próximo disponible"), NOW, "2026-10-10")).toBe("2026-10-11");
    expect(shortcutStartDate(byLabel("2 semanas"), NOW, "2026-10-10")).toBe("2026-10-23");
  });

  it("semanas y meses se cuentan desde hoy", () => {
    expect(shortcutStartDate(byLabel("1 semana"), NOW)).toBe("2026-10-16");
    expect(shortcutStartDate(byLabel("2 semanas"), NOW)).toBe("2026-10-23");
    expect(shortcutStartDate(byLabel("1 mes"), NOW)).toBe("2026-11-09");
    expect(shortcutStartDate(byLabel("3 meses"), NOW)).toBe("2027-01-09");
  });

  it("un mes desde el 31 no se pasa al mes siguiente", () => {
    expect(shortcutStartDate(byLabel("1 mes"), new Date(2027, 0, 31))).toBe("2027-02-28");
  });
});

describe("horarios por turno", () => {
  const slot = (slotId: number, hora: string) => ({ slotId, hora, duracionMin: 20, consultorioNombre: null, disponible: true });

  it("agrupa en mañana, tarde y noche y omite los turnos vacíos", () => {
    const groups = groupSlotsByShift([slot(1, "08:00"), slot(2, "11:40"), slot(3, "18:20")]);
    expect(groups.map((g) => [g.shift, g.slots.map((s) => s.slotId)])).toEqual([
      ["Mañana", [1, 2]],
      ["Noche", [3]],
    ]);
  });

  it("las 12:00 ya son tarde", () => {
    expect(groupSlotsByShift([slot(1, "12:00")])[0].shift).toBe("Tarde");
  });
});

describe("rango del calendario de seguimiento", () => {
  it("va de mañana al fin del mes visible si el mes es el actual", () => {
    expect(followUpMonthRange(new Date(2026, 9, 1), NOW)).toEqual({ desde: "2026-10-10", hasta: "2026-10-31" });
  });

  it("cubre el mes completo si es un mes futuro", () => {
    expect(followUpMonthRange(new Date(2026, 10, 15), NOW)).toEqual({ desde: "2026-11-01", hasta: "2026-11-30" });
  });

  it("no hay rango para un mes que ya pasó", () => {
    expect(followUpMonthRange(new Date(2026, 8, 1), NOW)).toBeNull();
  });
});

describe("fechas de seguimiento", () => {
  it("hoy y mañana en formato aaaa-mm-dd", () => {
    expect(todayIso(NOW)).toBe("2026-10-09");
    expect(minFollowUpDate(NOW)).toBe("2026-10-10");
  });

  it("el mínimo es el día siguiente a la consulta (la regla del backend)", () => {
    expect(minFollowUpDate(NOW, "2026-10-10")).toBe("2026-10-11");
    // Una consulta de días anteriores no adelanta el mínimo: sigue siendo mañana.
    expect(minFollowUpDate(NOW, "2026-10-01")).toBe("2026-10-10");
    expect(minFollowUpDate(NOW, null)).toBe("2026-10-10");
  });

  it("la fecha tiene que ser posterior a la consulta", () => {
    expect(followUpError(true, "2026-10-10", NOW, "2026-10-10")).toContain("posterior");
    expect(followUpError(true, "2026-10-11", NOW, "2026-10-10")).toBeNull();
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
