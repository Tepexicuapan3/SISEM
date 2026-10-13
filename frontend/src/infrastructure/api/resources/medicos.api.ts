import apiClient from "@api/client";
import { ApiError } from "@api/utils/errors";
import type {
  MedicosListResponse,
  MedicoDetailResponse,
  MedicoListItem,
  MedicoDetail,
  CreateMedicoRequest,
  UpdateMedicoRequest,
  AsignarUsuarioRequest,
  AsignarUsuarioResponse,
  AddEspecialidadRequest,
  AddCentroRequest,
  AddConsultorioRequest,
  SaveHorarioRequest,
  CreateExcepcionRequest,
  CreateCoberturaRequest,
  MedicoExcepcionesResponse,
  MedicoCoberturaItem,
  MedicoCoberturasResponse,
  MedicosDisponiblesResponse,
  MedicoDisponible,
  MedicoImportResult,
  MedicoImportJob,
  MedicoImportJobStatus,
} from "@api/types/medicos.types";

// Duplicados a propósito de `infrastructure/api/resources/users.api.ts`
// (helpers locales, no exportados ahi -- extraerlos a un módulo compartido
// queda fuera de alcance de este change, ver Engram, topic_key
// sdd/medicos-legacy-field-bulk-import/design, "Open Questions").
const waitForTokenRefresh = (): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, 800));

const isApiError = (error: unknown): error is ApiError =>
  error instanceof ApiError;

const buildImportFormData = (file: File): FormData => {
  const formData = new FormData();
  formData.append("file", file);
  return formData;
};

const IMPORT_POLL_INTERVAL_MS = 2000;
// Errores de red seguidos tolerados durante el polling: el job sigue
// corriendo en el worker aunque se caiga un request de consulta.
const IMPORT_POLL_MAX_CONSECUTIVE_FAILURES = 15;
const FINAL_IMPORT_STATUSES: ReadonlyArray<MedicoImportJobStatus> = [
  "SUCCESS",
  "VALIDATION_FAILED",
  "ERROR",
];

const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

export interface MedicoImportConfirmOptions {
  /** Se llama con cada estado consultado del job (para la barra de avance). */
  onProgress?: (job: MedicoImportJob) => void;
  pollIntervalMs?: number;
}

export const medicosAPI = {
  // ── Catálogo ──────────────────────────────────────────────────────────────

  getAll: async (params?: {
    tipoMedico?: string;
    estatusMedico?: string;
    search?: string;
  }): Promise<MedicosListResponse> => {
    const r = await apiClient.get<MedicosListResponse>("/medicos", { params });
    return r.data;
  },

  create: async (data: CreateMedicoRequest): Promise<MedicoListItem> => {
    const r = await apiClient.post<MedicoListItem>("/medicos", data);
    return r.data;
  },

  getById: async (medicoId: number): Promise<MedicoDetailResponse> => {
    const r = await apiClient.get<MedicoDetailResponse>(`/medicos/${medicoId}`);
    return r.data;
  },

  update: async (medicoId: number, data: UpdateMedicoRequest): Promise<MedicoDetail> => {
    const r = await apiClient.patch<MedicoDetail>(`/medicos/${medicoId}`, data);
    return r.data;
  },

  /** Asigna un usuario (tipo Médico) a un médico sin usuario; mueve sus datos personales al usuario. */
  asignarUsuario: async (
    medicoId: number,
    data: AsignarUsuarioRequest,
  ): Promise<AsignarUsuarioResponse> => {
    const r = await apiClient.post<AsignarUsuarioResponse>(
      `/medicos/${medicoId}/asignar-usuario`,
      data,
    );
    return r.data;
  },

  // ── Especialidades ────────────────────────────────────────────────────────

  addEspecialidad: async (medicoId: number, data: AddEspecialidadRequest) => {
    const r = await apiClient.post(`/medicos/${medicoId}/especialidades`, data);
    return r.data;
  },

  removeEspecialidad: async (medicoId: number, especialidadId: number) => {
    const r = await apiClient.delete(`/medicos/${medicoId}/especialidades/${especialidadId}`);
    return r.data;
  },

  // ── Centros ───────────────────────────────────────────────────────────────

  addCentro: async (medicoId: number, data: AddCentroRequest) => {
    const r = await apiClient.post(`/medicos/${medicoId}/centros`, data);
    return r.data;
  },

  removeCentro: async (medicoId: number, relId: number) => {
    const r = await apiClient.delete(`/medicos/${medicoId}/centros/${relId}`);
    return r.data;
  },

  // ── Consultorios ──────────────────────────────────────────────────────────

  addConsultorio: async (medicoId: number, data: AddConsultorioRequest) => {
    const r = await apiClient.post(`/medicos/${medicoId}/consultorios`, data);
    return r.data;
  },

  updateConsultorio: async (medicoId: number, rmcId: number, data: { consultorioId?: number; tipoAsignacion?: string }) => {
    const r = await apiClient.patch(`/medicos/${medicoId}/consultorios/${rmcId}`, data);
    return r.data;
  },

  removeConsultorio: async (medicoId: number, rmcId: number) => {
    const r = await apiClient.delete(`/medicos/${medicoId}/consultorios/${rmcId}`);
    return r.data;
  },

  saveHorario: async (medicoId: number, rmcId: number, data: SaveHorarioRequest) => {
    const r = await apiClient.put(`/medicos/${medicoId}/consultorios/${rmcId}/horario`, data);
    return r.data;
  },

  // ── Excepciones ───────────────────────────────────────────────────────────

  getExcepciones: async (medicoId: number): Promise<MedicoExcepcionesResponse> => {
    const r = await apiClient.get<MedicoExcepcionesResponse>(`/medicos/${medicoId}/excepciones`);
    return r.data;
  },

  createExcepcion: async (medicoId: number, data: CreateExcepcionRequest) => {
    const r = await apiClient.post(`/medicos/${medicoId}/excepciones`, data);
    return r.data;
  },

  deleteExcepcion: async (medicoId: number, excId: number) => {
    const r = await apiClient.delete(`/medicos/${medicoId}/excepciones/${excId}`);
    return r.data;
  },

  // ── Coberturas ────────────────────────────────────────────────────────────

  createCobertura: async (data: CreateCoberturaRequest): Promise<MedicoCoberturaItem> => {
    const r = await apiClient.post<MedicoCoberturaItem>("/coberturas", data);
    return r.data;
  },

  getCoberturas: async (medicoId: number): Promise<MedicoCoberturasResponse> => {
    const r = await apiClient.get<MedicoCoberturasResponse>("/coberturas", {
      params: { medicoId },
    });
    return r.data;
  },

  deleteCobertura: async (coberturaId: number) => {
    const r = await apiClient.delete(`/coberturas/${coberturaId}`);
    return r.data;
  },

  // ── Disponibilidad (para recepción) ───────────────────────────────────────

  getDisponibles: async (centroId: number, fecha?: string): Promise<MedicosDisponiblesResponse> => {
    const r = await apiClient.get<MedicosDisponiblesResponse>("/medicos/disponibles", {
      params: { centroId, fecha },
    });
    return r.data;
  },

  getDisponibilidad: async (medicoId: number, fecha?: string): Promise<MedicoDisponible> => {
    const r = await apiClient.get<MedicoDisponible>(`/medicos/${medicoId}/disponibilidad`, {
      params: { fecha },
    });
    return r.data;
  },

  // ── Importación masiva (Excel) ────────────────────────────────────────────
  import: {
    /**
     * Descargar plantilla .xlsx para carga masiva de médicos.
     * @endpoint GET /api/v1/medicos/import/template
     * @permission admin:gestion:medicos:create
     */
    downloadTemplate: async (): Promise<Blob> => {
      const response = await apiClient.get("/medicos/import/template", {
        responseType: "blob",
      });
      return response.data as Blob;
    },

    /**
     * PASO 1 - Preview: valida el Excel y devuelve las filas con sus errores.
     * NO persiste nada en la base de datos.
     *
     * NOTA SOBRE UPLOAD Y FORMDATA:
     * El interceptor global refresca el token en 401 pero no puede reenviar
     * el mismo FormData (stream consumido). Reconstruimos el FormData en
     * cada intento (mismo patrón que `users.api.ts`).
     *
     * @endpoint POST /api/v1/medicos/import/preview
     * @permission admin:gestion:medicos:create
     */
    preview: async (file: File, _retry = false): Promise<MedicoImportResult> => {
      try {
        const response = await apiClient.post<MedicoImportResult>(
          "/medicos/import/preview",
          buildImportFormData(file),
          {
            headers: { "Content-Type": undefined },
            timeout: 60000,
          },
        );
        return response.data;
      } catch (err: unknown) {
        if (!_retry && isApiError(err) && err.status === 401) {
          await waitForTokenRefresh();
          return medicosAPI.import.preview(file, true);
        }
        throw err;
      }
    },

    /**
     * PASO 2 - Confirm ASÍNCRONO (mismo patrón que `usersAPI.import.confirm`):
     * encola el import en el backend (202 + `jobId`) y consulta el job hasta
     * que termina. Devuelve el mismo `MedicoImportResult` de siempre, así el
     * diálogo no cambia su manejo de resultado:
     * - SUCCESS            -> resultado con `inserted`.
     * - VALIDATION_FAILED  -> resultado con `totalErrores > 0` y las filas
     *                         (todo-o-nada: no se creó ningún médico).
     * - ERROR              -> lanza `ApiError` con el mensaje del backend.
     *
     * Por qué asíncrono: ~2700 médicos exceden el timeout HTTP (30 s front,
     * 60 s nginx).
     *
     * @endpoint POST /api/v1/medicos/import/confirm
     * @endpoint GET  /api/v1/medicos/import/jobs/:jobId
     * @permission admin:gestion:medicos:create
     */
    confirm: async (
      file: File,
      options: MedicoImportConfirmOptions = {},
    ): Promise<MedicoImportResult> => {
      const { onProgress, pollIntervalMs = IMPORT_POLL_INTERVAL_MS } = options;

      let job = await medicosAPI.import.enqueue(file);
      onProgress?.(job);

      let consecutiveFailures = 0;
      while (!FINAL_IMPORT_STATUSES.includes(job.status)) {
        await sleep(pollIntervalMs);
        try {
          job = await medicosAPI.import.getJob(job.jobId);
          consecutiveFailures = 0;
          onProgress?.(job);
        } catch (err: unknown) {
          consecutiveFailures += 1;
          if (consecutiveFailures >= IMPORT_POLL_MAX_CONSECUTIVE_FAILURES) {
            throw err;
          }
        }
      }

      if (job.status === "ERROR" || !job.result) {
        throw new ApiError(
          job.errorCode ?? "IMPORT_FAILED",
          job.errorMessage ?? "No se pudo completar la importacion.",
          500,
        );
      }
      return job.result;
    },

    /**
     * Encola el import (sin esperar). 409 IMPORT_IN_PROGRESS si ya hay otro
     * import de médicos corriendo.
     * @endpoint POST /api/v1/medicos/import/confirm
     */
    enqueue: async (file: File, _retry = false): Promise<MedicoImportJob> => {
      try {
        const response = await apiClient.post<MedicoImportJob>(
          "/medicos/import/confirm",
          buildImportFormData(file),
          {
            headers: { "Content-Type": undefined },
            timeout: 60000,
          },
        );
        return response.data;
      } catch (err: unknown) {
        if (!_retry && isApiError(err) && err.status === 401) {
          await waitForTokenRefresh();
          return medicosAPI.import.enqueue(file, true);
        }
        throw err;
      }
    },

    /**
     * Estado/avance de un import en segundo plano.
     * @endpoint GET /api/v1/medicos/import/jobs/:jobId
     */
    getJob: async (jobId: string): Promise<MedicoImportJob> => {
      const response = await apiClient.get<MedicoImportJob>(
        `/medicos/import/jobs/${jobId}`,
      );
      return response.data;
    },
  },
};
