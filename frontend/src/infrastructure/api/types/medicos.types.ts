export type TipoMedico      = "CLINICA" | "HOSPITAL" | "AMBOS";
export type EstatusMedico   = "ACTIVO" | "VACACIONES" | "INCAPACIDAD" | "SUSPENDIDO" | "BAJA";
export type TipoAdscripcion = "DEFINITIVA" | "TEMPORAL";
export type TipoAsignacion  = "PERMANENTE" | "TEMPORAL";
export type CanalAtencion   = "PRESENCIAL" | "LINEA" | "AMBOS";
export type DiaSemana       = "LUNES" | "MARTES" | "MIERCOLES" | "JUEVES" | "VIERNES" | "SABADO" | "DOMINGO";
export type TipoExcepcion   = "VACACIONES" | "INCAPACIDAD" | "PERMISO" | "HORA_COMIDA" |
                              "CAPACITACION" | "AUSENCIA" | "SUSPENSION" | "CAMBIO_HORARIO";
export type MotivoCobertura = "VACACIONES" | "INCAPACIDAD" | "PERMISO" | "OTRO";

// ─── MÉDICO ──────────────────────────────────────────────────────────────────

export interface MedicoCedulaItem {
  id: number;
  numero: string;
  tipo: "PROFESIONAL" | "ESPECIALIDAD" | "SUBESPECIALIDAD";
  esPrincipal: boolean;
}

export interface MedicoEspecialidadItem {
  id: number;
  name: string;
  esPrincipal: boolean;
}

export interface MedicoCentroItem {
  id: number;
  centroId: number;
  centroNombre: string;
  centroDireccion: string | null;
  centroTelefono: string | null;
  tipoAdscripcion: TipoAdscripcion;
  fechaInicio: string;
  fechaFin: string | null;
}

export interface MedicoHorarioItem {
  id: number;
  diaSemana: DiaSemana;
  horaInicio: string;
  horaFin: string;
  intervaloCitaMin: number;
  canal: CanalAtencion;
}

export interface MedicoConsultorioItem {
  id: number;
  consultorioId: number;
  consultorioNumero: number;
  consultorioNombre: string;
  tipoAsignacion: TipoAsignacion;
  fechaInicio: string;
  fechaFin: string | null;
  isActive: boolean;
  horarios: MedicoHorarioItem[];
}

export interface MedicoEscuelaItem {
  id: number;
  code: string;
  name: string;
}

export interface MedicoConsultorioActivoItem {
  id: number;
  consultorioId: number;
  consultorioNumero: number;
  consultorioNombre: string;
  centroId: number;
  centroNombre: string;
}

export interface MedicoListItem {
  id: number;
  username: string;
  nombreCompleto: string;
  nombre: string;
  paterno: string;
  materno: string;
  email: string;
  telefono: string | null;
  direccion: string | null;
  sexo: "M" | "F" | null;
  fechaNac: string | null;
  isActive: boolean;
  tipoMedico: TipoMedico;
  servicio: string | null;
  estatusMedico: EstatusMedico;
  escuela: MedicoEscuelaItem | null;
  cedulas: MedicoCedulaItem[];
  especialidades: MedicoEspecialidadItem[];
  centros: MedicoCentroItem[];
  consultoriosActivos: MedicoConsultorioActivoItem[];
  createdAt: string | null;
}

export interface MedicoDetail extends MedicoListItem {
  observaciones: string | null;
  consultorios: MedicoConsultorioItem[];
}

// ─── EXCEPCIONES ─────────────────────────────────────────────────────────────

export interface MedicoExcepcionItem {
  id: number;
  tipo: TipoExcepcion;
  fechaInicio: string;
  fechaFin: string;
  horaInicio: string | null;
  horaFin: string | null;
  motivo: string | null;
  consultorioId: number | null;
}

// ─── COBERTURAS ──────────────────────────────────────────────────────────────

export interface MedicoCoberturaHorarioItem {
  id: number;
  diaSemana: DiaSemana;
  horaInicio: string;
  horaFin: string;
}

export interface MedicoCoberturaItem {
  id: number;
  medicoSuplenteId: number;
  medicoSuplenteNombre: string;
  medicoTitularId: number;
  medicoTitularNombre: string;
  consultorioId: number | null;
  consultorioNombre: string | null;
  centroId: number | null;
  centroNombre: string | null;
  fechaInicio: string;
  fechaFin: string | null;
  motivo: MotivoCobertura;
  isActive: boolean;
  horarios: MedicoCoberturaHorarioItem[];
  createdAt: string | null;
}

// ─── DISPONIBILIDAD ──────────────────────────────────────────────────────────

export interface MedicoDisponible {
  medicoId: number;
  nombreCompleto: string;
  servicio: string | null;
  tipoMedico: TipoMedico;
  disponible: boolean;
  consultorioId?: number;
  consultorioNumero?: number;
  consultorioNombre?: string;
  centroId?: number;
  origen?: "COBERTURA" | "REGULAR";
  horaInicio?: string;
  horaFin?: string;
  intervaloCitaMin?: number;
  motivo?: string;
}

export interface MedicosDisponiblesResponse {
  fecha: string;
  centroId: number;
  medicos: MedicoDisponible[];
}

// ─── REQUESTS ────────────────────────────────────────────────────────────────

export interface CreateMedicoRequest {
  usuarioId: number;
  tipoMedico?: TipoMedico;
  servicio?: string | null;
  observaciones?: string | null;
}

export interface UpdateMedicoRequest {
  tipoMedico?: TipoMedico;
  servicio?: string | null;
  observaciones?: string | null;
  estatusMedico?: EstatusMedico;
}

export interface AddEspecialidadRequest {
  especialidadId: number;
  esPrincipal?: boolean;
}

export interface AddCentroRequest {
  centroId: number;
  tipoAdscripcion?: TipoAdscripcion;
  fechaInicio: string;
  fechaFin?: string | null;
}

export interface AddConsultorioRequest {
  consultorioId: number;
  tipoAsignacion?: TipoAsignacion;
  fechaInicio: string;
  fechaFin?: string | null;
  horarios?: {
    diaSemana: DiaSemana;
    horaInicio: string;
    horaFin: string;
    intervaloCitaMin?: number;
    canal?: CanalAtencion;
  }[];
}

export interface SaveHorarioRequest {
  horarios: {
    diaSemana: DiaSemana;
    horaInicio: string;
    horaFin: string;
    intervaloCitaMin?: number;
    canal?: CanalAtencion;
  }[];
}

export interface CreateExcepcionRequest {
  tipo: TipoExcepcion;
  fechaInicio: string;
  fechaFin: string;
  horaInicio?: string | null;
  horaFin?: string | null;
  consultorioId?: number | null;
  motivo?: string | null;
}

export interface CreateCoberturaRequest {
  medicoSuplenteId: number;
  medicoTitularId: number;
  consultorioId: number;
  centroId: number;
  fechaInicio: string;
  fechaFin: string;
  motivo?: MotivoCobertura;
  horarios?: { diaSemana: DiaSemana; horaInicio: string; horaFin: string }[];
}

// ─── RESPONSES ───────────────────────────────────────────────────────────────

export interface MedicosListResponse {
  items: MedicoListItem[];
  total: number;
}

export interface MedicoDetailResponse {
  medico: MedicoDetail;
}

export interface MedicoExcepcionesResponse {
  items: MedicoExcepcionItem[];
}

export interface MedicoCoberturasResponse {
  items: MedicoCoberturaItem[];
}
