import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { medicosAPI } from "@api/resources/medicos.api";
import type {
  CreateMedicoRequest,
  UpdateMedicoRequest,
  AddEspecialidadRequest,
  AddCentroRequest,
  AddConsultorioRequest,
  SaveHorarioRequest,
  CreateExcepcionRequest,
  CreateCoberturaRequest,
} from "@api/types/medicos.types";

// ─── Keys ────────────────────────────────────────────────────────────────────

const keys = {
  all:          ["medicos"] as const,
  list:         (params?: object) => ["medicos", "list", params] as const,
  detail:       (id: number)      => ["medicos", "detail", id] as const,
  excepciones:  (id: number)      => ["medicos", id, "excepciones"] as const,
  coberturas:   (id: number)      => ["medicos", id, "coberturas"] as const,
  disponibles:  (centroId: number, fecha?: string) =>
                  ["medicos", "disponibles", centroId, fecha] as const,
};

// ─── Listado ──────────────────────────────────────────────────────────────────

export const useMedicosList = (
  params?: { tipoMedico?: string; estatusMedico?: string; search?: string },
  options?: { enabled?: boolean },
) =>
  useQuery({
    queryKey: keys.list(params),
    queryFn: () => medicosAPI.getAll(params),
    staleTime: 60_000,
    enabled: options?.enabled ?? true,
  });

// ─── Detalle ──────────────────────────────────────────────────────────────────

export const useMedicoDetail = (userId: number | undefined, enabled = true) =>
  useQuery({
    queryKey: keys.detail(userId!),
    queryFn: () => medicosAPI.getById(userId!),
    staleTime: 60_000,
    enabled: enabled && !!userId,
  });

// ─── Mutaciones CRUD ──────────────────────────────────────────────────────────

export const useCreateMedico = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateMedicoRequest) => medicosAPI.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
};

export const useUpdateMedico = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateMedicoRequest) => medicosAPI.update(userId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(userId) });
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
};

// ─── Especialidades ───────────────────────────────────────────────────────────

export const useAddEspecialidad = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AddEspecialidadRequest) => medicosAPI.addEspecialidad(userId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(userId) }),
  });
};

export const useRemoveEspecialidad = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (espId: number) => medicosAPI.removeEspecialidad(userId, espId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(userId) }),
  });
};

// ─── Centros ──────────────────────────────────────────────────────────────────

export const useAddCentro = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AddCentroRequest) => medicosAPI.addCentro(userId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(userId) }),
  });
};

export const useRemoveCentro = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (relId: number) => medicosAPI.removeCentro(userId, relId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(userId) }),
  });
};

// ─── Consultorios ─────────────────────────────────────────────────────────────

export const useAddConsultorio = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AddConsultorioRequest) => medicosAPI.addConsultorio(userId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(userId) }),
  });
};

export const useUpdateConsultorio = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ rmcId, data }: { rmcId: number; data: { consultorioId?: number; tipoAsignacion?: string } }) =>
      medicosAPI.updateConsultorio(userId, rmcId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(userId) }),
  });
};

export const useRemoveConsultorio = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rmcId: number) => medicosAPI.removeConsultorio(userId, rmcId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(userId) }),
  });
};

export const useSaveHorario = (userId: number, rmcId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SaveHorarioRequest) => medicosAPI.saveHorario(userId, rmcId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(userId) }),
  });
};

// ─── Excepciones ──────────────────────────────────────────────────────────────

export const useMedicoExcepciones = (userId: number, enabled = true) =>
  useQuery({
    queryKey: keys.excepciones(userId),
    queryFn: () => medicosAPI.getExcepciones(userId),
    staleTime: 30_000,
    enabled,
  });

export const useCreateExcepcion = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateExcepcionRequest) => medicosAPI.createExcepcion(userId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.excepciones(userId) });
      qc.invalidateQueries({ queryKey: keys.detail(userId) });
    },
  });
};

export const useDeleteExcepcion = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (excId: number) => medicosAPI.deleteExcepcion(userId, excId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.excepciones(userId) }),
  });
};

// ─── Coberturas ───────────────────────────────────────────────────────────────

export const useMedicoCoberturas = (userId: number, enabled = true) =>
  useQuery({
    queryKey: keys.coberturas(userId),
    queryFn: () => medicosAPI.getCoberturas(userId),
    staleTime: 30_000,
    enabled,
  });

export const useCreateCobertura = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateCoberturaRequest) => medicosAPI.createCobertura(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.coberturas(userId) });
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
};

export const useDeleteCobertura = (userId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (coberturaId: number) => medicosAPI.deleteCobertura(coberturaId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.coberturas(userId) }),
  });
};

// ─── Disponibilidad ───────────────────────────────────────────────────────────

export const useMedicosDisponibles = (
  centroId: number | undefined,
  fecha?: string,
  enabled = true,
) =>
  useQuery({
    queryKey: keys.disponibles(centroId!, fecha),
    queryFn: () => medicosAPI.getDisponibles(centroId!, fecha),
    staleTime: 30_000,
    enabled: enabled && !!centroId,
  });
