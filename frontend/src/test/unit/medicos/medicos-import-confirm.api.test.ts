import { beforeEach, describe, expect, it, vi } from "vitest";
import apiClient from "@api/client";
import { medicosAPI } from "@api/resources/medicos.api";
import { ApiError } from "@api/utils/errors";
import type { MedicoImportJob, MedicoImportResult } from "@api/types/medicos.types";

vi.mock("@api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

const RESULT: MedicoImportResult = {
  totalRecords: 2,
  totalErrores: 0,
  totalWarnings: 0,
  inserted: 2,
  rows: [],
};

const buildJob = (overrides: Partial<MedicoImportJob> = {}): MedicoImportJob => ({
  jobId: "job-1",
  status: "PENDING",
  phase: "QUEUED",
  processed: 0,
  phaseTotal: 0,
  totalRecords: 0,
  inserted: 0,
  errorCode: null,
  errorMessage: null,
  createdAt: null,
  startedAt: null,
  finishedAt: null,
  result: null,
  ...overrides,
});

const file = new File(["x"], "medicos.xlsx");

describe("medicosAPI.import.confirm (import en segundo plano)", () => {
  const mockedApiClient = apiClient as unknown as {
    get: ReturnType<typeof vi.fn>;
    post: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("encola, consulta el job hasta SUCCESS y reporta el avance", async () => {
    mockedApiClient.post.mockResolvedValueOnce({ data: buildJob() });
    mockedApiClient.get
      .mockResolvedValueOnce({
        data: buildJob({ status: "RUNNING", phase: "SAVING", processed: 1, phaseTotal: 2 }),
      })
      .mockResolvedValueOnce({
        data: buildJob({ status: "SUCCESS", phase: "DONE", inserted: 2, result: RESULT }),
      });
    const onProgress = vi.fn();

    const result = await medicosAPI.import.confirm(file, { onProgress, pollIntervalMs: 0 });

    expect(result).toEqual(RESULT);
    expect(mockedApiClient.post).toHaveBeenCalledWith(
      "/medicos/import/confirm",
      expect.any(FormData),
      expect.anything(),
    );
    expect(mockedApiClient.get).toHaveBeenCalledWith("/medicos/import/jobs/job-1");
    expect(onProgress).toHaveBeenCalledTimes(3);
    expect(onProgress).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ phase: "SAVING", processed: 1, phaseTotal: 2 }),
    );
  });

  it("devuelve las filas con error cuando el job termina en VALIDATION_FAILED", async () => {
    const failed = { ...RESULT, totalErrores: 1, inserted: 0 };
    mockedApiClient.post.mockResolvedValueOnce({ data: buildJob() });
    mockedApiClient.get.mockResolvedValueOnce({
      data: buildJob({ status: "VALIDATION_FAILED", phase: "DONE", result: failed }),
    });

    const result = await medicosAPI.import.confirm(file, { pollIntervalMs: 0 });

    expect(result.totalErrores).toBe(1);
    expect(result.inserted).toBe(0);
  });

  it("lanza ApiError con el mensaje del backend cuando el job termina en ERROR", async () => {
    mockedApiClient.post.mockResolvedValueOnce({ data: buildJob() });
    mockedApiClient.get.mockResolvedValueOnce({
      data: buildJob({
        status: "ERROR",
        phase: "DONE",
        errorCode: "MEDICO_IMPORT_RACE",
        errorMessage: "El usuario ya no existe.",
      }),
    });

    await expect(
      medicosAPI.import.confirm(file, { pollIntervalMs: 0 }),
    ).rejects.toMatchObject({ code: "MEDICO_IMPORT_RACE", message: "El usuario ya no existe." });
  });

  it("tolera fallos de red transitorios durante el polling", async () => {
    mockedApiClient.post.mockResolvedValueOnce({ data: buildJob() });
    mockedApiClient.get
      .mockRejectedValueOnce(new ApiError("NETWORK_ERROR", "sin red", 0))
      .mockResolvedValueOnce({
        data: buildJob({ status: "SUCCESS", phase: "DONE", result: RESULT }),
      });

    const result = await medicosAPI.import.confirm(file, { pollIntervalMs: 0 });

    expect(result).toEqual(RESULT);
    expect(mockedApiClient.get).toHaveBeenCalledTimes(2);
  });
});
