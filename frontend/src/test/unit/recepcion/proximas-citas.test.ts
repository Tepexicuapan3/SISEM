import { describe, expect, it } from "vitest";
import {
  PROXIMAS_RANGOS,
  groupCitasByDay,
  rangoProximas,
} from "@features/recepcion/modules/agenda/domain/proximas-citas";

const NOW = new Date(2026, 10, 9, 16, 0); // lunes 9 de noviembre de 2026, local

describe("rangos de próximas citas", () => {
  it("hoy, mañana, 7 y 30 días", () => {
    expect(rangoProximas("hoy", NOW)).toEqual({ fechaDesde: "2026-11-09", fechaHasta: "2026-11-09" });
    expect(rangoProximas("manana", NOW)).toEqual({ fechaDesde: "2026-11-10", fechaHasta: "2026-11-10" });
    expect(rangoProximas("7dias", NOW)).toEqual({ fechaDesde: "2026-11-09", fechaHasta: "2026-11-16" });
    expect(rangoProximas("30dias", NOW)).toEqual({ fechaDesde: "2026-11-09", fechaHasta: "2026-12-09" });
  });

  it("cada rango tiene su etiqueta", () => {
    expect(PROXIMAS_RANGOS.map((r) => r.label)).toEqual(["Hoy", "Mañana", "7 días", "30 días"]);
  });
});

describe("agrupar por día", () => {
  const cita = (id: number, iso: string) => ({ id, fechaHora: iso });

  it("agrupa por día local, en orden, con Hoy y Mañana", () => {
    const groups = groupCitasByDay(
      [
        cita(1, new Date(2026, 10, 9, 18, 0).toISOString()),
        cita(2, new Date(2026, 10, 10, 8, 0).toISOString()),
        cita(3, new Date(2026, 10, 10, 9, 0).toISOString()),
        cita(4, new Date(2026, 10, 12, 8, 0).toISOString()),
      ],
      NOW,
    );
    expect(groups.map((g) => [g.label, g.items.map((i) => i.id)])).toEqual([
      ["Hoy · lunes, 9 de noviembre", [1]],
      ["Mañana · martes, 10 de noviembre", [2, 3]],
      ["jueves, 12 de noviembre", [4]],
    ]);
  });
});
