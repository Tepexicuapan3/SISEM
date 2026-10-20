import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "@api/client";
import { parametersAPI } from "@api/resources/catalogos/parameters.api";
import {
  describeLimits,
  formatParametroValue,
  validateParametroValue,
} from "@features/admin/modules/catalogos/parametros/domain/parametro.value";

vi.mock("@api/client", () => ({
  default: { get: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const entero = { valueType: "ENTERO" as const, minValue: 1, maxValue: 365 };

describe("validateParametroValue", () => {
  it("acepta enteros dentro de los límites", () => {
    expect(validateParametroValue(entero, " 60 ")).toBeNull();
  });

  it.each([
    ["0", "No puede ser menor que 1."],
    ["366", "No puede ser mayor que 365."],
    ["2.5", "Debe ser un número entero."],
    ["abc", "Debe ser un número."],
    ["", "Debe ser un número."],
  ])("rechaza %s", (raw, message) => {
    expect(validateParametroValue(entero, raw)).toBe(message);
  });

  it("acepta decimales y booleanos como el backend", () => {
    expect(validateParametroValue({ valueType: "DECIMAL", minValue: null, maxValue: null }, "3000.50")).toBeNull();
    const bool = { valueType: "BOOLEANO" as const, minValue: null, maxValue: null };
    expect(validateParametroValue(bool, "true")).toBeNull();
    expect(validateParametroValue(bool, "tal vez")).toBe("Debe ser verdadero o falso.");
  });

  it("el texto libre siempre es válido", () => {
    expect(validateParametroValue({ valueType: "TEXTO", minValue: null, maxValue: null }, "")).toBeNull();
  });
});

describe("formato", () => {
  it("muestra booleanos como Sí/No y describe límites", () => {
    expect(formatParametroValue("BOOLEANO", "true")).toBe("Sí");
    expect(formatParametroValue("BOOLEANO", "false")).toBe("No");
    expect(formatParametroValue("ENTERO", "60")).toBe("60");
    expect(describeLimits(entero)).toBe("Entre 1 y 365");
    expect(describeLimits({ valueType: "TEXTO", minValue: null, maxValue: null })).toBeNull();
  });
});

describe("parametersAPI", () => {
  const mocked = apiClient as unknown as {
    get: ReturnType<typeof vi.fn>;
    put: ReturnType<typeof vi.fn>;
    delete: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mocked.get.mockResolvedValue({ data: { items: [] } });
    mocked.put.mockResolvedValue({ data: { parameter: {} } });
    mocked.delete.mockResolvedValue({ data: { parameter: {} } });
  });

  it("usa las rutas del backend con la clave codificada", async () => {
    await parametersAPI.getAll();
    expect(mocked.get).toHaveBeenCalledWith("/parameters/");

    await parametersAPI.updateGeneral("incapacidad.max_dias", "45");
    expect(mocked.put).toHaveBeenCalledWith("/parameters/incapacidad.max_dias/", { value: "45" });

    await parametersAPI.setCenterValue("incapacidad.max_dias", 7, "20");
    expect(mocked.put).toHaveBeenCalledWith("/parameters/incapacidad.max_dias/centers/7/", { value: "20" });

    await parametersAPI.deleteCenterValue("incapacidad.max_dias", 7);
    expect(mocked.delete).toHaveBeenCalledWith("/parameters/incapacidad.max_dias/centers/7/");
  });
});
