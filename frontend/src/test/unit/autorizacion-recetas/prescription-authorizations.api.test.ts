import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "@api/client";
import { prescriptionAuthorizationsAPI } from "@api/resources/prescription-authorizations.api";

vi.mock("@api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe("prescriptionAuthorizationsAPI", () => {
  const mockedApiClient = apiClient as unknown as {
    get: ReturnType<typeof vi.fn>;
    post: ReturnType<typeof vi.fn>;
    patch: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getPending calls GET on the pending endpoint", async () => {
    mockedApiClient.get.mockResolvedValueOnce({ data: { items: [], total: 0 } });

    await prescriptionAuthorizationsAPI.getPending();

    expect(apiClient.get).toHaveBeenCalledWith("/prescriptions/authorizations/pending");
  });

  it("getHistory calls GET with params", async () => {
    mockedApiClient.get.mockResolvedValueOnce({ data: { items: [], total: 0 } });

    await prescriptionAuthorizationsAPI.getHistory({ estatus: "rechazada" });

    expect(apiClient.get).toHaveBeenCalledWith("/prescriptions/authorizations", {
      params: { estatus: "rechazada" },
    });
  });

  // Riesgo D5 (design): authorize/reject son POST en este backend, a
  // diferencia de ambulancias que usa PATCH -- este test caza un
  // copy-paste accidental del metodo equivocado.
  it("authorize sends POST (not PATCH) with no body", async () => {
    mockedApiClient.post.mockResolvedValueOnce({ data: { id: 1 } });

    await prescriptionAuthorizationsAPI.authorize(1);

    expect(apiClient.post).toHaveBeenCalledWith("/prescriptions/authorizations/1/authorize");
    expect(mockedApiClient.patch).not.toHaveBeenCalled();
  });

  // Riesgo D6 (design): el campo del body de reject es `reason`, no
  // `notes` (que es el campo que usa ambulancias) -- este test caza un
  // copy-paste accidental del nombre de campo equivocado.
  it("reject sends POST with exact path and reason field", async () => {
    mockedApiClient.post.mockResolvedValueOnce({ data: { id: 1 } });

    await prescriptionAuthorizationsAPI.reject(1, { reason: "Dosis incorrecta" });

    expect(apiClient.post).toHaveBeenCalledWith("/prescriptions/authorizations/1/reject", {
      reason: "Dosis incorrecta",
    });
    expect(mockedApiClient.patch).not.toHaveBeenCalled();
  });
});
