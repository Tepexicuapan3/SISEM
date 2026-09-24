import apiClient from "@api/client";
import { ApiError } from "@api/utils/errors";
import type {
  MedicosListResponse,
  MedicoDetailResponse,
  MedicoListItem,
  MedicoDetail,
  CreateMedicoRequest,
  UpdateMedicoRequest,
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

  getById: async (userId: number): Promise<MedicoDetailResponse> => {
    const r = await apiClient.get<MedicoDetailResponse>(`/medicos/${userId}`);
    return r.data;
  },

  update: async (userId: number, data: UpdateMedicoRequest): Promise<MedicoDetail> => {
    const r = await apiClient.patch<MedicoDetail>(`/medicos/${userId}`, data);
    return r.data;
  },

  // ── Especialidades ────────────────────────────────────────────────────────

  addEspecialidad: async (userId: number, data: AddEspecialidadRequest) => {
    const r = await apiClient.post(`/medicos/${userId}/especialidades`, data);
    return r.data;
  },

  removeEspecialidad: async (userId: number, especialidadId: number) => {
    const r = await apiClient.delete(`/medicos/${userId}/especialidades/${especialidadId}`);
    return r.data;
  },

  // ── Centros ───────────────────────────────────────────────────────────────

  addCentro: async (userId: number, data: AddCentroRequest) => {
    const r = await apiClient.post(`/medicos/${userId}/centros`, data);
    return r.data;
  },

  removeCentro: async (userId: number, relId: number) => {
    const r = await apiClient.delete(`/medicos/${userId}/centros/${relId}`);
    return r.data;
  },

  // ── Consultorios ──────────────────────────────────────────────────────────

  addConsultorio: async (userId: number, data: AddConsultorioRequest) => {
    const r = await apiClient.post(`/medicos/${userId}/consultorios`, data);
    return r.data;
  },

  updateConsultorio: async (userId: number, rmcId: number, data: { consultorioId?: number; tipoAsignacion?: string }) => {
    const r = await apiClient.patch(`/medicos/${userId}/consultorios/${rmcId}`, data);
    return r.data;
  },

  removeConsultorio: async (userId: number, rmcId: number) => {
    const r = await apiClient.delete(`/medicos/${userId}/consultorios/${rmcId}`);
    return r.data;
  },

  saveHorario: async (userId: number, rmcId: number, data: SaveHorarioRequest) => {
    const r = await apiClient.put(`/medicos/${userId}/consultorios/${rmcId}/horario`, data);
    return r.data;
  },

  // ── Excepciones ───────────────────────────────────────────────────────────

  getExcepciones: async (userId: number): Promise<MedicoExcepcionesResponse> => {
    const r = await apiClient.get<MedicoExcepcionesResponse>(`/medicos/${userId}/excepciones`);
    return r.data;
  },

  createExcepcion: async (userId: number, data: CreateExcepcionRequest) => {
    const r = await apiClient.post(`/medicos/${userId}/excepciones`, data);
    return r.data;
  },

  deleteExcepcion: async (userId: number, excId: number) => {
    const r = await apiClient.delete(`/medicos/${userId}/excepciones/${excId}`);
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

  getDisponibilidad: async (userId: number, fecha?: string): Promise<MedicoDisponible> => {
    const r = await apiClient.get<MedicoDisponible>(`/medicos/${userId}/disponibilidad`, {
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
     * PASO 2 - Confirm: crea todos los médicos SOLO SI no hay ningún error
     * (todo-o-nada). Reenvía el MISMO archivo; el servidor re-valida como
     * única autoridad.
     *
     * NOTA SOBRE CONFIRM Y 409:
     * El backend responde 409 con `{ totalRecords, totalErrores, inserted: 0,
     * rows, code: "IMPORT_HAS_ERRORS" }` cuando el todo-o-nada rechaza el
     * lote. El interceptor global normaliza cualquier error 4xx/5xx a
     * `ApiError` (solo conserva code/message/status/details) y ese cuerpo
     * (rows) se pierde. Como preview y confirm validan el MISMO archivo,
     * ante un 409 reconstruimos las filas re-llamando a `preview` en vez de
     * propagar un error vacío de contenido (mismo patrón que `users.api.ts`).
     *
     * @endpoint POST /api/v1/medicos/import/confirm
     * @permission admin:gestion:medicos:create
     */
    confirm: async (file: File, _retry = false): Promise<MedicoImportResult> => {
      try {
        const response = await apiClient.post<MedicoImportResult>(
          "/medicos/import/confirm",
          buildImportFormData(file),
          {
            headers: { "Content-Type": undefined },
          },
        );
        return response.data;
      } catch (err: unknown) {
        if (!_retry && isApiError(err) && err.status === 401) {
          await waitForTokenRefresh();
          return medicosAPI.import.confirm(file, true);
        }
        if (isApiError(err) && err.status === 409) {
          return medicosAPI.import.preview(file);
        }
        throw err;
      }
    },
  },
};
