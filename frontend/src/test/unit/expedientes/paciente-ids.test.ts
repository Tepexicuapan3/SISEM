import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "@api/client";
import { conIdPaciente, registrarIdsPaciente, rutaPaciente } from "@api/paciente-ids";

vi.mock("@api/client", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

/**
 * Plan contraer la llave vieja: las rutas de datos del paciente se arman con
 * su idPaciente; la llave vieja (expediente + pkNum) solo queda para quien
 * nunca se atendió.
 */
describe("rutaPaciente", () => {
  const mockedGet = (apiClient as unknown as { get: ReturnType<typeof vi.fn> }).get;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("con el idPaciente conocido usa /pacientes/<id> y no manda pkNum", async () => {
    registrarIdsPaciente([{ noExp: "40041", pkNum: 3, idPaciente: 25 }]);

    await expect(rutaPaciente("040041", 3, "allergies")).resolves.toEqual({
      url: "/pacientes/25/allergies",
      params: {},
    });
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it("el provisional va por su idPaciente, nunca con su clave en pkNum", async () => {
    registrarIdsPaciente([{ noExp: "40041", pkNum: 100000001, idPaciente: 10 }]);

    const ruta = await rutaPaciente("40041", 100000001, "profile");
    expect(ruta).toEqual({ url: "/pacientes/10/profile", params: {} });
  });

  it("si no lo conoce, busca el expediente una vez y usa el id que devuelve", async () => {
    mockedGet.mockResolvedValueOnce({
      data: { titular: { noExp: "77001", pkNum: 0, idPaciente: 7 }, dependientes: [] },
    });

    await expect(rutaPaciente("77001", 0, "clinical-history")).resolves.toEqual({
      url: "/pacientes/7/clinical-history",
      params: {},
    });
    expect(mockedGet).toHaveBeenCalledTimes(1);
  });

  it("el miembro que nunca se atendió usa la ruta vieja", async () => {
    mockedGet.mockResolvedValueOnce({
      data: { titular: { noExp: "88001", pkNum: 0, idPaciente: null }, dependientes: [] },
    });

    await expect(rutaPaciente("88001", 0, "allergies")).resolves.toEqual({
      url: "/patients/88001/allergies",
      params: { pkNum: 0 },
    });
  });
});

describe("conIdPaciente", () => {
  it("cambia expediente + pkNum por idPaciente cuando lo conoce", async () => {
    registrarIdsPaciente([{ noExp: "50050", pkNum: 2, idPaciente: 31 }]);

    await expect(conIdPaciente({ noExp: "50050", pkNum: 2, surgeonId: 9 })).resolves.toEqual({
      surgeonId: 9,
      idPaciente: 31,
    });
    await expect(conIdPaciente({ expediente: "50050", pkNum: 2, nombre: "X" }, "expediente")).resolves.toEqual({
      nombre: "X",
      idPaciente: 31,
    });
  });

  it("si no lo conoce, lo abre en SIRES y manda solo el idPaciente", async () => {
    const cliente = apiClient as unknown as { get: ReturnType<typeof vi.fn>; post: ReturnType<typeof vi.fn> };
    cliente.get.mockResolvedValueOnce({ data: { titular: null, dependientes: [] } });
    cliente.post.mockResolvedValueOnce({ data: { idPaciente: 77 } });

    await expect(conIdPaciente({ noExp: "60060", pkNum: 0, itemId: "E11" })).resolves.toEqual({
      itemId: "E11",
      idPaciente: 77,
    });
    expect(cliente.post).toHaveBeenCalledWith("/visits/patient-open", { noExp: "60060", pkNum: 0 });
  });
});
