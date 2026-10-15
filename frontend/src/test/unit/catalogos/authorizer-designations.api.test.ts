import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "@api/client";
import { authorizerDesignationsAPI } from "@api/resources/catalogos/authorizer-designations.api";

vi.mock("@api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe("authorizerDesignationsAPI", () => {
  const mocked = apiClient as unknown as {
    get: ReturnType<typeof vi.fn>;
    post: ReturnType<typeof vi.fn>;
    put: ReturnType<typeof vi.fn>;
    delete: ReturnType<typeof vi.fn>;
  };

  const payload = {
    userId: 7,
    tipoAutorizacionId: 3,
    cargo: "Director",
    fechaInicio: "2026-01-01",
    fechaFin: null,
    oficio: null,
    alcance: { centros: [1], tiposCentro: [], global: false },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getAll consulta authorizer-designations/ con params", async () => {
    mocked.get.mockResolvedValueOnce({ data: { items: [], total: 0 } });
    await authorizerDesignationsAPI.getAll({ page: 2, isActive: true });
    expect(mocked.get).toHaveBeenCalledWith("/authorizer-designations/", {
      params: { page: 2, isActive: true },
    });
  });

  it("create y update envian el payload y devuelven { designation }", async () => {
    mocked.post.mockResolvedValueOnce({ data: { designation: { id: 1 } } });
    mocked.put.mockResolvedValueOnce({ data: { designation: { id: 1 } } });

    const created = await authorizerDesignationsAPI.create(payload);
    const updated = await authorizerDesignationsAPI.update(1, payload);

    expect(mocked.post).toHaveBeenCalledWith("/authorizer-designations/", payload);
    expect(mocked.put).toHaveBeenCalledWith("/authorizer-designations/1/", payload);
    expect(created.designation.id).toBe(1);
    expect(updated.designation.id).toBe(1);
  });

  it("delete usa baja logica sobre /authorizer-designations/:id/", async () => {
    mocked.delete.mockResolvedValueOnce({ data: { success: true } });
    const result = await authorizerDesignationsAPI.delete(5);
    expect(mocked.delete).toHaveBeenCalledWith("/authorizer-designations/5/");
    expect(result.success).toBe(true);
  });
});
