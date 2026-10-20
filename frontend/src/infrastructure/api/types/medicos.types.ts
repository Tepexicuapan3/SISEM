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
  /** CatMedico.id = No. Médico. Es el único id válido para URLs y payloads de médico. */
  id: number;
  /** SyUsuario asociado (siempre presente). NUNCA usarlo como id de médico. */
  usuarioId: number;
  username: string;
  nombreCompleto: string;
  nombre: string;
  paterno: string;
  materno: string;
  cedulaProfesional: string | null;
  email: string | null;
  telefono: string | null;
  direccion: string | null;
  sexo: "M" | "F" | "O" | null;
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
  /** CatMedico.id (No. Médico): espacio MÉDICO (agenda, slots, citas). */
  medicoId: number;
  /** SyUsuario del médico: espacio USUARIO (Visit.doctorId). */
  usuarioId: number;
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

/** Cita ya agendada dentro de una ausencia: NO se cancela, recepción la reprograma. */
export interface CitaAfectadaPorExcepcion {
  id: number;
  folio: string;
  noExp: string;
  pkNum: number;
  fechaHora: string; // ISO 8601
  consultorioNombre: string | null;
  estatus: string;
  origenCanal: string;
}

export interface CreateExcepcionResponse {
  id: number;
  tipo: TipoExcepcion;
  fechaInicio: string;
  fechaFin: string;
  /** Horarios libres que quedaron sin habilitar por la ausencia. */
  horariosBloqueados: number;
  citasAfectadas: CitaAfectadaPorExcepcion[];
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

// ─── ARCHIVO LEGADO (solo lectura) ───────────────────────────────────────────

export interface LegacyMedicoClaveDescripcion {
  clave: number | null;
  descripcion: string | null;
}

export interface LegacyMedicoActual {
  id: number;
  nombreCompleto: string;
}

export interface LegacyMedicoItem {
  noMedico: number;
  claveRh: string;
  nombreCompleto: string;
  paterno: string | null;
  materno: string | null;
  nombre: string | null;
  cedula: string | null;
  sexo: string | null;
  clinica: LegacyMedicoClaveDescripcion | null;
  especialidad: LegacyMedicoClaveDescripcion | null;
  estatus: string;
  usuarioLegado: string | null;
  medicoActual: LegacyMedicoActual | null;
}

export interface LegacyMedicosParams {
  search?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}

export interface LegacyMedicosListResponse {
  items: LegacyMedicoItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
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
