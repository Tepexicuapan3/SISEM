import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { medicosAPI } from "@api/resources/medicos.api";
import type {
  CreateMedicoRequest,
  UpdateMedicoRequest,
  AsignarUsuarioRequest,
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

export const useMedicoDetail = (medicoId: number | undefined, enabled = true) =>
  useQuery({
    queryKey: keys.detail(medicoId!),
    queryFn: () => medicosAPI.getById(medicoId!),
    staleTime: 60_000,
    enabled: enabled && !!medicoId,
  });

// ─── Mutaciones CRUD ──────────────────────────────────────────────────────────

export const useCreateMedico = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateMedicoRequest) => medicosAPI.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
};

export const useUpdateMedico = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateMedicoRequest) => medicosAPI.update(medicoId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(medicoId) });
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
};

export const useAsignarUsuario = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AsignarUsuarioRequest) => medicosAPI.asignarUsuario(medicoId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(medicoId) });
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
};

// ─── Especialidades ───────────────────────────────────────────────────────────

export const useAddEspecialidad = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AddEspecialidadRequest) => medicosAPI.addEspecialidad(medicoId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(medicoId) }),
  });
};

export const useRemoveEspecialidad = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (espId: number) => medicosAPI.removeEspecialidad(medicoId, espId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(medicoId) }),
  });
};

// ─── Centros ──────────────────────────────────────────────────────────────────

export const useAddCentro = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AddCentroRequest) => medicosAPI.addCentro(medicoId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(medicoId) }),
  });
};

export const useRemoveCentro = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (relId: number) => medicosAPI.removeCentro(medicoId, relId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(medicoId) }),
  });
};

// ─── Consultorios ─────────────────────────────────────────────────────────────

export const useAddConsultorio = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AddConsultorioRequest) => medicosAPI.addConsultorio(medicoId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(medicoId) }),
  });
};

export const useUpdateConsultorio = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ rmcId, data }: { rmcId: number; data: { consultorioId?: number; tipoAsignacion?: string } }) =>
      medicosAPI.updateConsultorio(medicoId, rmcId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(medicoId) }),
  });
};

export const useRemoveConsultorio = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rmcId: number) => medicosAPI.removeConsultorio(medicoId, rmcId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(medicoId) }),
  });
};

export const useSaveHorario = (medicoId: number, rmcId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SaveHorarioRequest) => medicosAPI.saveHorario(medicoId, rmcId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.detail(medicoId) }),
  });
};

// ─── Excepciones ──────────────────────────────────────────────────────────────

export const useMedicoExcepciones = (medicoId: number, enabled = true) =>
  useQuery({
    queryKey: keys.excepciones(medicoId),
    queryFn: () => medicosAPI.getExcepciones(medicoId),
    staleTime: 30_000,
    enabled,
  });

export const useCreateExcepcion = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateExcepcionRequest) => medicosAPI.createExcepcion(medicoId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.excepciones(medicoId) });
      qc.invalidateQueries({ queryKey: keys.detail(medicoId) });
    },
  });
};

export const useDeleteExcepcion = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (excId: number) => medicosAPI.deleteExcepcion(medicoId, excId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.excepciones(medicoId) }),
  });
};

// ─── Coberturas ───────────────────────────────────────────────────────────────

export const useMedicoCoberturas = (medicoId: number, enabled = true) =>
  useQuery({
    queryKey: keys.coberturas(medicoId),
    queryFn: () => medicosAPI.getCoberturas(medicoId),
    staleTime: 30_000,
    enabled,
  });

export const useCreateCobertura = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateCoberturaRequest) => medicosAPI.createCobertura(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.coberturas(medicoId) });
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
};

export const useDeleteCobertura = (medicoId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (coberturaId: number) => medicosAPI.deleteCobertura(coberturaId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.coberturas(medicoId) }),
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
