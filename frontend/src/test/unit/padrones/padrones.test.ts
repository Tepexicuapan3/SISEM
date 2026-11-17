import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "@api/client";
import { padronesAPI } from "@api/resources/padrones.api";
import { registrarIdsPaciente } from "@api/paciente-ids";
import {
  dischargePadronSchema,
  enrollPadronSchema,
  todayLocalISO,
} from "@features/padrones/domain/padrones.schemas";

vi.mock("@api/client", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe("padrones schemas", () => {
  it("exige expediente y padecimiento", () => {
    const result = enrollPadronSchema.safeParse({ noExp: " ", itemId: "" });
    expect(result.success).toBe(false);
    const fields = result.success ? [] : result.error.issues.map((i) => i.path[0]);
    expect(fields).toEqual(expect.arrayContaining(["noExp", "itemId"]));
  });

  it("acepta fecha vacía o de hoy y rechaza futura", () => {
    // La persona se elige (docs/plans/cronicos-alta-padron.md): sin pkNum no hay alta.
    const base = { noExp: "123", pkNum: 0, itemId: "E11" };
    expect(enrollPadronSchema.safeParse({ noExp: "123", itemId: "E11" }).success).toBe(false);
    expect(enrollPadronSchema.safeParse({ ...base, enrolledOn: "" }).success).toBe(true);
    expect(enrollPadronSchema.safeParse({ ...base, enrolledOn: todayLocalISO() }).success).toBe(true);
    expect(enrollPadronSchema.safeParse({ ...base, enrolledOn: "2999-01-01" }).success).toBe(false);
    expect(dischargePadronSchema.safeParse({ reasonId: 1, dischargedOn: "2999-01-01" }).success).toBe(false);
  });

  it("la baja exige motivo", () => {
    expect(dischargePadronSchema.safeParse({ reasonId: 0 }).success).toBe(false);
    expect(dischargePadronSchema.safeParse({ reasonId: 3 }).success).toBe(true);
  });

  it("todayLocalISO usa la fecha local, no UTC", () => {
    const now = new Date();
    expect(todayLocalISO()).toBe(
      `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`,
    );
  });
});

describe("padronesAPI", () => {
  const mocked = apiClient as unknown as {
    get: ReturnType<typeof vi.fn>;
    post: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mocked.get.mockResolvedValue({ data: { items: [] } });
    mocked.post.mockResolvedValue({ data: {} });
  });

  it("usa las rutas del backend", async () => {
    await padronesAPI.list("cronicos", { status: "activo" });
    expect(mocked.get).toHaveBeenCalledWith("/padrones/cronicos", { params: { status: "activo" } });

    await padronesAPI.options("discapacidad", "mental");
    expect(mocked.get).toHaveBeenCalledWith("/padrones/discapacidad/opciones", { params: { search: "mental" } });

    // El alta viaja solo con el idPaciente, sin expediente ni pkNum (C7).
    registrarIdsPaciente([{ noExp: "1", pkNum: 0, idPaciente: 501 }]);
    await padronesAPI.enroll("cronicos", { noExp: "1", pkNum: 0, itemId: "E11" });
    expect(mocked.post).toHaveBeenCalledWith("/padrones/cronicos", { itemId: "E11", idPaciente: 501 });

    await padronesAPI.discharge("cronicos", 9, { reasonId: 2 });
    expect(mocked.post).toHaveBeenCalledWith("/padrones/cronicos/9/baja", { reasonId: 2 });
  });

  it("padrones del paciente: por idPaciente; sin id no pregunta (alerta del expediente)", async () => {
    registrarIdsPaciente([{ noExp: "40488", pkNum: 1, idPaciente: 777 }]);
    await padronesAPI.patientRegistries("40488", 1);
    expect(mocked.get).toHaveBeenCalledWith("/pacientes/777/padrones");

    // Un miembro que nunca se atendió no tiene registro, así que no está en ningún padrón.
    mocked.get.mockResolvedValueOnce({ data: { titular: null, dependientes: [] } });
    expect(await padronesAPI.patientRegistries("99999", 0)).toEqual({ cronicos: [], discapacidad: [] });
    expect(mocked.get).not.toHaveBeenCalledWith("/patients/99999/padrones", expect.anything());
  });
});
