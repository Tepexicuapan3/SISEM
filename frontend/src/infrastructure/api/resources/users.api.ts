/**
 * Users API Resource
 *
 * Gestión completa de usuarios dividida en sub-recursos lógicos.
 *
 * ESTRUCTURA:
 * - Core: CRUD básico de perfil y estados.
 * - Roles: Gestión de roles asignados.
 * - Overrides: Gestión de excepciones de permisos.
 *
 * PERMISOS:
 * Patrón: ADMIN:GESTION:USUARIOS:{ACCION}
 */

import apiClient from "@api/client";
import { ApiError } from "@api/utils/errors";
import type {
  CreateUserRequest,
  CreateUserResponse,
  UpdateUserRequest,
  UpdateUserResponse,
  UserStatusResponse,
  ResetUserPasswordRequest,
  ResetUserPasswordResponse,
  ForceLogoutUserResponse,
  UnlockUserResponse,
  UsersListParams,
  UsersListResponse,
  UserDetailResponse,
  AssignRolesRequest,
  AssignRolesResponse,
  SetPrimaryRoleRequest,
  SetPrimaryRoleResponse,
  RevokeRoleResponse,
  AddUserOverrideRequest,
  AddUserOverrideResponse,
  RemoveUserOverrideResponse,
  EmpleadoSermedResponse,
  NotifyUsersRequest,
  NotifyUsersResponse,
  NotifyUsersPreviewResponse,
  UserImportResult,
  UserImportJob,
  UserImportJobStatus,
} from "@api/types";

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
const FINAL_IMPORT_STATUSES: ReadonlyArray<UserImportJobStatus> = [
  "SUCCESS",
  "VALIDATION_FAILED",
  "ERROR",
];

const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

export interface UserImportConfirmOptions {
  /** Se llama con cada estado consultado del job (para la barra de avance). */
  onProgress?: (job: UserImportJob) => void;
  pollIntervalMs?: number;
}

export const usersAPI = {
  // ==========================================
  // 1. CORE: PERFIL Y ESTADOS
  // ==========================================

  /**
   * Listar usuarios con paginación.
   * @endpoint GET /api/v1/users
   * @permission admin:gestion:usuarios:read
   */
  getAll: async (params?: UsersListParams): Promise<UsersListResponse> => {
    const response = await apiClient.get<UsersListResponse>("/users", {
      params,
    });
    return response.data;
  },

  /**
   * Compat: alias legacy.
   */
  getUsers: async (params?: UsersListParams): Promise<UsersListResponse> => {
    const response = await apiClient.get<UsersListResponse>("/users", {
      params,
    });
    return response.data;
  },

  /**
   * Obtener detalle completo (Perfil + Roles + Overrides).
   * @endpoint GET /api/v1/users/:id
   * @permission admin:gestion:usuarios:read
   */
  getById: async (userId: number): Promise<UserDetailResponse> => {
    const response = await apiClient.get<UserDetailResponse>(
      `/users/${userId}`,
    );
    return response.data;
  },

  /**
   * Crear usuario.
   * @endpoint POST /api/v1/users
   * @permission admin:gestion:usuarios:create
   */
  create: async (data: CreateUserRequest): Promise<CreateUserResponse> => {
    const response = await apiClient.post<CreateUserResponse>("/users", data);
    return response.data;
  },

  /**
   * Actualizar perfil básico.
   * @endpoint PATCH /api/v1/users/:id
   * @permission admin:gestion:usuarios:update
   */
  update: async (
    userId: number,
    data: UpdateUserRequest,
  ): Promise<UpdateUserResponse> => {
    const response = await apiClient.patch<UpdateUserResponse>(
      `/users/${userId}`,
      data,
    );
    return response.data;
  },

  /**
   * Activar usuario.
   * @endpoint PATCH /api/v1/users/:id/activate
   * @permission admin:gestion:usuarios:update
   */
  activate: async (userId: number): Promise<UserStatusResponse> => {
    const response = await apiClient.patch<UserStatusResponse>(
      `/users/${userId}/activate`,
    );
    return response.data;
  },

  /**
   * Desactivar usuario.
   * @endpoint PATCH /api/v1/users/:id/deactivate
   * @permission admin:gestion:usuarios:update
   */
  deactivate: async (userId: number): Promise<UserStatusResponse> => {
    const response = await apiClient.patch<UserStatusResponse>(
      `/users/${userId}/deactivate`,
    );
    return response.data;
  },

  /**
   * Restablecer contraseña: genera una temporal y la devuelve en texto plano
   * (solo en esta respuesta, transitoria). El usuario debera cambiarla al
   * iniciar sesion (mustChangePassword: true).
   * Con `sendEmail: true` la temporal se envia por correo y la respuesta no la
   * incluye (409/400/502: SELF_PASSWORD_RESET_NOT_ALLOWED, USER_EMAIL_MISSING,
   * EMAIL_SEND_FAILED).
   * @endpoint POST /api/v1/users/:id/reset-password
   * @permission admin:gestion:usuarios:credenciales
   */
  resetPassword: async (
    userId: number,
    data: ResetUserPasswordRequest = {},
  ): Promise<ResetUserPasswordResponse> => {
    const response = await apiClient.post<ResetUserPasswordResponse>(
      `/users/${userId}/reset-password`,
      data,
    );
    return response.data;
  },

  /**
   * Forzar el cierre de sesion de otro usuario (revoca su sesion activa y
   * corta sus WebSockets). 409 SELF_FORCE_LOGOUT_NOT_ALLOWED si es uno mismo.
   * @endpoint POST /api/v1/users/:id/force-logout
   * @permission admin:gestion:usuarios:update
   */
  forceLogout: async (userId: number): Promise<ForceLogoutUserResponse> => {
    const response = await apiClient.post<ForceLogoutUserResponse>(
      `/users/${userId}/force-logout`,
    );
    return response.data;
  },

  /**
   * Desbloquear el login de una cuenta bloqueada por intentos fallidos.
   * @endpoint POST /api/v1/users/:id/unlock
   * @permission admin:gestion:usuarios:update
   */
  unlock: async (userId: number): Promise<UnlockUserResponse> => {
    const response = await apiClient.post<UnlockUserResponse>(
      `/users/${userId}/unlock`,
    );
    return response.data;
  },

  /**
   * Buscar empleado en SERMED por número de expediente.
   * @endpoint GET /api/v1/users/empleados-sermed/:noExp
   * @permission admin:gestion:usuarios:read
   */
  lookupEmpleadoSermed: async (
    noExp: string,
  ): Promise<EmpleadoSermedResponse> => {
    const response = await apiClient.get<EmpleadoSermedResponse>(
      `/users/empleados-sermed/${encodeURIComponent(noExp)}`,
    );
    return response.data;
  },

  /**
   * Valores distintos de cd_laboral registrados en el sistema.
   * @endpoint GET /api/v1/users/cd-laborales
   */
  getCdLaborales: async (): Promise<{ items: string[] }> => {
    const response = await apiClient.get<{ items: string[] }>("/users/cd-laborales");
    return response.data;
  },

  /**
   * Exportar usuarios a Excel con los filtros actuales.
   * @endpoint GET /api/v1/users/export
   * @permission admin:gestion:usuarios:read
   */
  export: async (params?: UsersListParams): Promise<Blob> => {
    const response = await apiClient.get("/users/export", {
      params,
      responseType: "blob",
    });
    return response.data as Blob;
  },

  /**
   * Vista previa: cuántos usuarios recibirían la notificación.
   * @endpoint POST /api/v1/users/notify?preview=true
   */
  notifyPreview: async (data: NotifyUsersRequest): Promise<NotifyUsersPreviewResponse> => {
    const response = await apiClient.post<NotifyUsersPreviewResponse>(
      "/users/notify?preview=true",
      data,
    );
    return response.data;
  },

  /**
   * Enviar notificación masiva con adjuntos opcionales.
   * - Sin adjuntos → JSON
   * - Con adjuntos  → multipart/form-data (DRF acepta ambos)
   * @endpoint POST /api/v1/users/notify
   * @permission admin:gestion:usuarios:update
   */
  notify: async (data: NotifyUsersRequest, files?: File[]): Promise<NotifyUsersResponse> => {
    if (files && files.length > 0) {
      const formData = new FormData();
      formData.append("subject", data.subject);
      formData.append("message", data.message);
      if (data.category) formData.append("category", data.category);
      if (data.cdLaboral) formData.append("cdLaboral", data.cdLaboral);
      if (data.userId != null) formData.append("userId", String(data.userId));
      if (data.clinicId != null) formData.append("clinicId", String(data.clinicId));
      files.forEach((file) => formData.append("attachments", file));
      // Eliminar Content-Type del default (application/json) para que el browser
      // genere automáticamente "multipart/form-data; boundary=..." con el FormData.
      // Sin esto DRF recibe Content-Type: application/json → usa JSONParser → request.FILES vacío.
      const response = await apiClient.post<NotifyUsersResponse>("/users/notify", formData, {
        headers: { "Content-Type": undefined },
      });
      return response.data;
    }
    const response = await apiClient.post<NotifyUsersResponse>("/users/notify", data);
    return response.data;
  },

  // ==========================================
  // 2. SUB-RECURSO: IMPORTACION MASIVA (EXCEL)
  // ==========================================
  import: {
    /**
     * Descargar plantilla .xlsx para carga masiva de usuarios.
     * @endpoint GET /api/v1/users/import/template
     * @permission admin:gestion:usuarios:create
     */
    downloadTemplate: async (): Promise<Blob> => {
      const response = await apiClient.get("/users/import/template", {
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
     * cada intento (mismo patron que `catalog-import.api.ts`).
     *
     * @endpoint POST /api/v1/users/import/preview
     * @permission admin:gestion:usuarios:create
     */
    preview: async (file: File, _retry = false): Promise<UserImportResult> => {
      try {
        const response = await apiClient.post<UserImportResult>(
          "/users/import/preview",
          buildImportFormData(file),
          {
            // Elimina Content-Type: application/json del cliente base.
            // Axios genera multipart/form-data con boundary correcto.
            headers: { "Content-Type": undefined },
            timeout: 60000,
          },
        );
        return response.data;
      } catch (err: unknown) {
        if (!_retry && isApiError(err) && err.status === 401) {
          await waitForTokenRefresh();
          return usersAPI.import.preview(file, true);
        }
        throw err;
      }
    },

    /**
     * PASO 2 - Confirm ASINCRONO: encola el import en el backend (202 +
     * `jobId`) y consulta el job hasta que termina. Devuelve el mismo
     * `UserImportResult` que el confirm sincrono de antes, asi el dialogo
     * no cambia su manejo de resultado:
     * - SUCCESS            -> resultado con `inserted` y `emailFailures`.
     * - VALIDATION_FAILED  -> resultado con `totalErrores > 0` y las filas
     *                         (todo-o-nada: no se creo ningun usuario).
     * - ERROR              -> lanza `ApiError` con el mensaje del backend.
     *
     * Por que asincrono: cada alta hashea su contrasena (~0.5 s) y un lote
     * de miles de filas excede cualquier timeout HTTP.
     *
     * @endpoint POST /api/v1/users/import/confirm
     * @endpoint GET  /api/v1/users/import/jobs/:jobId
     * @permission admin:gestion:usuarios:create
     */
    confirm: async (
      file: File,
      options: UserImportConfirmOptions = {},
    ): Promise<UserImportResult> => {
      const { onProgress, pollIntervalMs = IMPORT_POLL_INTERVAL_MS } = options;

      let job = await usersAPI.import.enqueue(file);
      onProgress?.(job);

      let consecutiveFailures = 0;
      while (!FINAL_IMPORT_STATUSES.includes(job.status)) {
        await sleep(pollIntervalMs);
        try {
          job = await usersAPI.import.getJob(job.jobId);
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
     * import corriendo.
     * @endpoint POST /api/v1/users/import/confirm
     */
    enqueue: async (file: File, _retry = false): Promise<UserImportJob> => {
      try {
        const response = await apiClient.post<UserImportJob>(
          "/users/import/confirm",
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
          return usersAPI.import.enqueue(file, true);
        }
        throw err;
      }
    },

    /**
     * Estado/avance de un import en segundo plano.
     * @endpoint GET /api/v1/users/import/jobs/:jobId
     */
    getJob: async (jobId: string): Promise<UserImportJob> => {
      const response = await apiClient.get<UserImportJob>(
        `/users/import/jobs/${jobId}`,
      );
      return response.data;
    },
  },

  // ==========================================
  // 3. SUB-RECURSO: ROLES
  // ==========================================
  roles: {
    /**
     * Asignar roles adicionales.
     * @endpoint POST /api/v1/users/:id/roles
     * @permission admin:gestion:usuarios:update
     */
    assign: async (
      userId: number,
      data: AssignRolesRequest,
    ): Promise<AssignRolesResponse> => {
      const response = await apiClient.post<AssignRolesResponse>(
        `/users/${userId}/roles`,
        data,
      );
      return response.data;
    },

    /**
     * Establecer rol primario.
     * @endpoint PUT /api/v1/users/:id/roles/primary
     * @permission admin:gestion:usuarios:update
     */
    setPrimary: async (
      userId: number,
      data: SetPrimaryRoleRequest,
    ): Promise<SetPrimaryRoleResponse> => {
      const response = await apiClient.put<SetPrimaryRoleResponse>(
        `/users/${userId}/roles/primary`,
        data,
      );
      return response.data;
    },

    /**
     * Revocar rol secundario.
     * @endpoint DELETE /api/v1/users/:id/roles/:roleId
     * @permission admin:gestion:usuarios:update
     */
    revoke: async (
      userId: number,
      roleId: number,
    ): Promise<RevokeRoleResponse> => {
      const response = await apiClient.delete<RevokeRoleResponse>(
        `/users/${userId}/roles/${roleId}`,
      );
      return response.data;
    },
  },

  // ==========================================
  // 3. SUB-RECURSO: OVERRIDES (Permisos)
  // ==========================================
  overrides: {
    /**
     * Agregar excepción (Allow/Deny).
     * @endpoint POST /api/v1/users/:id/overrides
     * @permission admin:gestion:usuarios:update
     */
    add: async (
      userId: number,
      data: AddUserOverrideRequest,
    ): Promise<AddUserOverrideResponse> => {
      const response = await apiClient.post<AddUserOverrideResponse>(
        `/users/${userId}/overrides`,
        data,
      );
      return response.data;
    },

    /**
     * Eliminar excepción.
     * @endpoint DELETE /api/v1/users/:id/overrides/:code
     * @permission admin:gestion:usuarios:update
     */
    remove: async (
      userId: number,
      permissionCode: string,
    ): Promise<RemoveUserOverrideResponse> => {
      const response = await apiClient.delete<RemoveUserOverrideResponse>(
        `/users/${userId}/overrides/${permissionCode}`,
      );
      return response.data;
    },
  },
};
