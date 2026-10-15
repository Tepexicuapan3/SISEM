import { describe, expect, it } from "vitest";
import type { DesignacionItem } from "@api/types";
import { buildDesignacionSchema } from "@features/admin/modules/catalogos/designacion-autorizadores/domain/designacion.schemas";
import {
  setGlobalScope,
  toggleCentro,
  toggleTipoCentro,
} from "@features/admin/modules/catalogos/designacion-autorizadores/domain/designacion.scope";
import {
  buildDesignacionPayload,
  mapDesignacionToFormValues,
} from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.transform";
import { describeAlcance } from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.format";

const baseValues = {
  userId: 7,
  tipoAutorizacionId: 3,
  cargo: "Director medico",
  fechaInicio: "2026-01-01",
  fechaFin: "",
  oficio: "",
  centros: [] as number[],
  tiposCentro: [] as ("CLINICA" | "HOSPITAL" | "INSTITUTO")[],
  global: false,
};

describe("designacion schema", () => {
  const schema = buildDesignacionSchema({ canGrantGlobal: true });

  it("acepta alcance con centros especificos", () => {
    expect(schema.safeParse({ ...baseValues, centros: [1, 2] }).success).toBe(true);
  });

  it("acepta alcance por tipo de centro", () => {
    expect(schema.safeParse({ ...baseValues, tiposCentro: ["CLINICA"] }).success).toBe(true);
  });

  it("rechaza alcance vacio (no equivale a GLOBAL)", () => {
    const result = schema.safeParse(baseValues);
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.path).toEqual(["centros"]);
  });

  it("S39: GLOBAL sin fecha fin bloquea el envio con mensaje", () => {
    const result = schema.safeParse({ ...baseValues, global: true });
    expect(result.success).toBe(false);
    const issue = result.error?.issues.find((i) => i.path[0] === "fechaFin");
    expect(issue?.message).toMatch(/obligatoria/i);
  });

  it("GLOBAL con fecha fin es valido", () => {
    expect(
      schema.safeParse({ ...baseValues, global: true, fechaFin: "2026-12-31" }).success,
    ).toBe(true);
  });

  it("GLOBAL combinado con centros o tipos es invalido (el backend responde 400)", () => {
    const withCenters = schema.safeParse({
      ...baseValues,
      global: true,
      fechaFin: "2026-12-31",
      centros: [1],
    });
    const withTypes = schema.safeParse({
      ...baseValues,
      global: true,
      fechaFin: "2026-12-31",
      tiposCentro: ["HOSPITAL"],
    });
    expect(withCenters.success).toBe(false);
    expect(withTypes.success).toBe(false);
  });

  it("S38: sin permiso global, GLOBAL es invalido", () => {
    const noGlobal = buildDesignacionSchema({ canGrantGlobal: false });
    expect(
      noGlobal.safeParse({ ...baseValues, global: true, fechaFin: "2026-12-31" }).success,
    ).toBe(false);
  });

  it("rechaza fecha fin anterior a fecha inicio", () => {
    const result = schema.safeParse({
      ...baseValues,
      centros: [1],
      fechaFin: "2025-12-31",
    });
    expect(result.success).toBe(false);
  });
});

describe("designacion scope helpers", () => {
  it("marcar GLOBAL limpia centros y tipos", () => {
    expect(setGlobalScope(true)).toEqual({ centros: [], tiposCentro: [], global: true });
  });

  it("desmarcar GLOBAL parte de alcance vacio", () => {
    expect(setGlobalScope(false)).toEqual({ centros: [], tiposCentro: [], global: false });
  });

  it("con GLOBAL activo no se agregan centros ni tipos", () => {
    const current = setGlobalScope(true);
    expect(toggleCentro(current, 5, true)).toBe(current);
    expect(toggleTipoCentro(current, "CLINICA", true)).toBe(current);
  });

  it("alterna centros y tipos sin duplicar", () => {
    let state = setGlobalScope(false);
    state = toggleCentro(state, 5, true);
    state = toggleCentro(state, 5, true);
    state = toggleTipoCentro(state, "HOSPITAL", true);
    expect(state).toEqual({ centros: [5], tiposCentro: ["HOSPITAL"], global: false });
    state = toggleCentro(state, 5, false);
    expect(state.centros).toEqual([]);
  });
});

describe("designacion transform", () => {
  const item: DesignacionItem = {
    id: 1,
    userId: 7,
    user: { id: 7, username: "jperez", name: "Juan Perez" },
    tipoAutorizacionId: 3,
    tipoAutorizacion: { id: 3, name: "Cancelar nota", code: "CN" },
    cargo: "Director medico",
    fechaInicio: "2026-01-01",
    fechaFin: null,
    oficio: null,
    imgFirma: null,
    alcance: { centros: [{ id: 4, name: "Clinica 4" }], tiposCentro: ["CLINICA"], global: false },
    isActive: true,
    vigente: true,
    createdAt: null,
  };

  it("mapea el detalle a valores de formulario", () => {
    expect(mapDesignacionToFormValues(item)).toMatchObject({
      userId: 7,
      fechaFin: "",
      oficio: "",
      centros: [4],
      tiposCentro: ["CLINICA"],
      global: false,
    });
  });

  it("construye el payload del backend (camelCase, fechaFin null si vacia)", () => {
    expect(buildDesignacionPayload({ ...baseValues, cargo: "  Director  ", centros: [1] })).toEqual({
      userId: 7,
      tipoAutorizacionId: 3,
      cargo: "Director",
      fechaInicio: "2026-01-01",
      fechaFin: null,
      oficio: null,
      alcance: { centros: [1], tiposCentro: [], global: false },
    });
  });

  it("con GLOBAL envia centros y tipos vacios", () => {
    const payload = buildDesignacionPayload({
      ...baseValues,
      global: true,
      fechaFin: "2026-12-31",
      centros: [1],
      tiposCentro: ["CLINICA"],
    });
    expect(payload.alcance).toEqual({ centros: [], tiposCentro: [], global: true });
    expect(payload.fechaFin).toBe("2026-12-31");
  });

  it("describe el alcance para la tabla", () => {
    expect(describeAlcance(item.alcance)).toEqual(["Todas las clínicas", "Clinica 4"]);
    expect(describeAlcance({ centros: [], tiposCentro: [], global: true })).toEqual([
      "Todos los centros",
    ]);
  });
});
