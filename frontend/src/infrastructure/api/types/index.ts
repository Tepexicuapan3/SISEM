/**
 * API Types - Barrel Export
 * Re-exports all API types from domain modules.
 *
 * @description Punto de entrada único para todos los tipos de la API SISEM.
 * Los tipos están organizados por dominio funcional.
 * Todos los campos usan camelCase en inglés según el estándar de la API.
 */

// =============================================================================
// COMMON TYPES (pagination, responses)
// =============================================================================
export type {
  PaginationParams,
  ListResponse,
  SuccessResponse,
  ErrorResponse,
} from "@api/types/common.types";

// =============================================================================
// AUTH TYPES (login, session, recovery)
// =============================================================================
export type {
  // Entidades
  AuthUser,
  AuthCapabilityState,
  AuthCapabilitiesResponse,
  // Requests
  LoginRequest,
  RequestResetCodeRequest,
  VerifyResetCodeRequest,
  ResetPasswordRequest,
  CompleteOnboardingRequest,
  ChangePasswordRequest,
  // Responses
  LoginResponse,
  RefreshTokenResponse,
  VerifyResetCodeResponse,
  VerifyTokenResponse,
  LogoutResponse,
  RequestResetCodeResponse,
  ResetPasswordResponse,
  CompleteOnboardingResponse,
  ChangePasswordResponse,
  MeResponse,
  CapabilitiesResponse,
} from "@api/types/auth.types";

// =============================================================================
// USERS TYPES (CRUD, roles assignment, overrides)
// =============================================================================
export type {
  // Objetos anidados (relaciones)
  UserRef,
  BaseUser,
  CedulaTipo,
  CedulaItem,
  EmpleadoSermedResult,
  EmpleadoSermedResponse,
  // Entidades
  UserListItem,
  UserDetail,
  UserRole,
  UserOverride,
  // CRUD Requests
  CreateUserRequest,
  UpdateUserRequest,
  // CRUD Responses
  CreateUserResponse,
  UpdateUserResponse,
  UserStatusResponse,
  ResetUserPasswordResponse,
  // Listados
  UsersListParams,
  UsersListResponse,
  // Detalle
  UserDetailResponse,
  // Sub-recurso: Roles
  AssignRolesRequest,
  AssignRolesResponse,
  SetPrimaryRoleRequest,
  SetPrimaryRoleResponse,
  RevokeRoleResponse,
  // Sub-recurso: Overrides
  AddUserOverrideRequest,
  AddUserOverrideResponse,
  RemoveUserOverrideResponse,
  // Notificaciones
  NotifyUsersRequest,
  NotifyUsersResponse,
  NotifyUsersPreviewResponse,
  NotifyFailedItem,
  // Importacion masiva (Excel)
  UserImportRowData,
  UserImportRow,
  UserImportResult,
  UserImportEmailFailure,
  // Refs
  EscolaridadRef,
  EscuelaRef,
  TipoPersonalRef,
  // Perfiles por tipo de personal
  TipoAdscripcionMedico,
  NivelEnfermeria,
  PerfilMedico,
  PerfilEnfermeria,
  PerfilAdministrativo,
} from "@api/types/users.types";

// =============================================================================
// SESSIONS TYPES (control de sesion unica, historial de conexiones)
// =============================================================================
export type {
  SessionListItem,
  SessionsListParams,
  SessionsListResponse,
  SessionEstado,
  SessionCerradaPor,
} from "@api/types/sessions.types";
export { SESSION_ESTADO, SESSION_CERRADA_POR } from "@api/types/sessions.types";

// =============================================================================
// ROLES TYPES (CRUD, permissions assignment)
// =============================================================================
export type {
  // Entidades
  RoleRef,
  RoleListItem,
  RoleDetail,
  RolePermission,
  // Requests
  CreateRoleRequest,
  UpdateRoleRequest,
  AssignPermissionsRequest,
  RevokePermissionsRequest,
  // Responses
  CreateRoleResponse,
  UpdateRoleResponse,
  DeleteRoleResponse,
  AssignPermissionsResponse,
  RevokePermissionsResponse,
  // Listados
  RolesListResponse,
  RolesListParams,
  // Detalle
  RoleDetailResponse,
} from "@api/types/roles.types";

// =============================================================================
// PERMISSIONS TYPES (catalogo: lectura + creacion)
// =============================================================================
export type {
  // Tipos comunes
  PermissionEffect,
  // Entidades
  Permission,
  // Responses
  PermissionCatalogResponse,
  CreatePermissionRequest,
  CreatePermissionResponse,
} from "@api/types/permissions.types";

// =============================================================================
// CLINICS TYPES (CRUD)
// =============================================================================
// =============================================================================
// CLINICS TYPES (CRUD + schedules + postal codes)
// =============================================================================
export type {
  // Refs y enums
  CentroAtencionRef,
  TurnoRef,
  DiaSemana,
  CentroAtencionType,
  TipoExcepcion,
  // Entidades - centro
  CentroAtencionListItem,
  CentroAtencionDetail,
  // CRUD Requests - centro
  CreateCentroAtencionRequest,
  UpdateCentroAtencionRequest,
  // CRUD Responses - centro
  CreateCentroAtencionResponse,
  UpdateCentroAtencionResponse,
  DeleteCentroAtencionResponse,
  // Listados - centro
  CentrosAtencionListParams,
  CentrosAtencionListResponse,
  // Detalle - centro
  CentroAtencionDetailResponse,
  // Entidades - horario
  CentroAtencionHorarioListItem,
  CentroAtencionHorarioDetail,
  // CRUD Requests - horario
  CreateCentroAtencionHorarioRequest,
  UpdateCentroAtencionHorarioRequest,
  // CRUD Responses - horario
  CreateCentroAtencionHorarioResponse,
  UpdateCentroAtencionHorarioResponse,
  DeleteCentroAtencionHorarioResponse,
  // Listados - horario
  CentrosAtencionHorariosListParams,
  CentrosAtencionHorariosListResponse,
  // Detalle - horario
  CentroAtencionHorarioDetailResponse,
  // Entidades - excepcion
  CentroAtencionExcepcionListItem,
  CentroAtencionExcepcionDetail,
  // CRUD Requests - excepcion
  CreateCentroAtencionExcepcionRequest,
  UpdateCentroAtencionExcepcionRequest,
  // CRUD Responses - excepcion
  CreateCentroAtencionExcepcionResponse,
  UpdateCentroAtencionExcepcionResponse,
  DeleteCentroAtencionExcepcionResponse,
  // Listados - excepcion
  CentrosAtencionExcepcionesListParams,
  CentrosAtencionExcepcionesListResponse,
  // Detalle - excepcion
  CentroAtencionExcepcionDetailResponse,
  // Codigos postales
  PostalCodeSearchItem,
  PostalCodeSearchResponse,
} from "@api/types/catalogos/centros-atencion.types";

// =============================================================================
// TURNOS TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  TurnoListItem,
  TurnoDetail,
  // CRUD Requests
  CreateTurnoRequest,
  UpdateTurnoRequest,
  // CRUD Responses
  CreateTurnoResponse,
  UpdateTurnoResponse,
  DeleteTurnoResponse,
  // Listados
  TurnosListParams,
  TurnosListResponse,
  // Detalle
  TurnoDetailResponse,
} from "@api/types/catalogos/turnos.types";

export type {
  // Entidades
  AreaRef,
  AreaListItem,
  AreaDetail,
  // CRUD Requests
  CreateAreaRequest,
  UpdateAreaRequest,
  // CRUD Responses
  CreateAreaResponse,
  UpdateAreaResponse,
  DeleteAreaResponse,
  // Listados
  AreasListParams,
  AreasListResponse,
  // Detalle
  AreaDetailResponse,
} from "@api/types/catalogos/areas.types";

export type {
  // Entidades
  ConsultorioRef,
  ConsultorioCatalogRef,
  ConsultorioListItem,
  ConsultorioDetail,
  // CRUD Requests
  CreateConsultorioRequest,
  UpdateConsultorioRequest,
  // CRUD Responses
  CreateConsultorioResponse,
  UpdateConsultorioResponse,
  DeleteConsultorioResponse,
  // Listados
  ConsultoriosListParams,
  ConsultoriosListResponse,
  // Detalle
  ConsultorioDetailResponse,
} from "@api/types/catalogos/consultorios.types";

// =============================================================================
// TIPOS DE AREAS TYPES (CRUD)
// =============================================================================
export type {
  TipoAreaListItem,
  TipoAreaDetail,
  CreateTipoAreaRequest,
  UpdateTipoAreaRequest,
  CreateTipoAreaResponse,
  UpdateTipoAreaResponse,
  DeleteTipoAreaResponse,
  TiposAreasListParams,
  TiposAreasListResponse,
  TipoAreaDetailResponse,
} from "@api/types/catalogos/tipos-areas.types";

// =============================================================================
// TIPOS DE AUTORIZACION TYPES (CRUD)
// =============================================================================
export type {
  TipoAutorizacionListItem,
  TipoAutorizacionDetail,
  CreateTipoAutorizacionRequest,
  UpdateTipoAutorizacionRequest,
  CreateTipoAutorizacionResponse,
  UpdateTipoAutorizacionResponse,
  DeleteTipoAutorizacionResponse,
  TiposAutorizacionListParams,
  TiposAutorizacionListResponse,
  TipoAutorizacionDetailResponse,
} from "@api/types/catalogos/tipos-autorizacion.types";

// =============================================================================
// TIPOS DE CITAS TYPES (CRUD)
// =============================================================================
export type {
  TipoCitaListItem,
  TipoCitaDetail,
  CreateTipoCitaRequest,
  UpdateTipoCitaRequest,
  CreateTipoCitaResponse,
  UpdateTipoCitaResponse,
  DeleteTipoCitaResponse,
  TiposCitasListParams,
  TiposCitasListResponse,
  TipoCitaDetailResponse,
} from "@api/types/catalogos/tipos-citas.types";

// =============================================================================
// TIPOS DE CONSULTA TYPES (CRUD)
// =============================================================================
export type {
  TipoConsultaListItem,
  TipoConsultaDetail,
  CreateTipoConsultaRequest,
  UpdateTipoConsultaRequest,
  CreateTipoConsultaResponse,
  UpdateTipoConsultaResponse,
  DeleteTipoConsultaResponse,
  TiposConsultaListParams,
  TiposConsultaListResponse,
  TipoConsultaDetailResponse,
} from "@api/types/catalogos/tipos-consulta.types";

// =============================================================================
// RELIGIONES TYPES (CRUD)
// =============================================================================
export type {
  ReligionListItem,
  ReligionDetail,
  CreateReligionRequest,
  UpdateReligionRequest,
  CreateReligionResponse,
  UpdateReligionResponse,
  DeleteReligionResponse,
  ReligionesListParams,
  ReligionesListResponse,
  ReligionDetailResponse,
} from "@api/types/catalogos/religiones.types";

// =============================================================================
// TIPOS DE RESIDENCIA TYPES (CRUD)
// =============================================================================
export type {
  TipoResidenciaListItem,
  TipoResidenciaDetail,
  CreateTipoResidenciaRequest,
  UpdateTipoResidenciaRequest,
  CreateTipoResidenciaResponse,
  UpdateTipoResidenciaResponse,
  DeleteTipoResidenciaResponse,
  TiposResidenciaListParams,
  TiposResidenciaListResponse,
  TipoResidenciaDetailResponse,
} from "@api/types/catalogos/tipos-residencia.types";

// =============================================================================
// HISTORIA CLINICA GENERAL (ClinicalHistory)
// =============================================================================
export type {
  ClinicalHistory,
  UpdateClinicalHistoryRequest,
} from "@api/types/clinical-history.types";

// =============================================================================
// HISTORIAL DE CONSULTAS DEL PACIENTE
// =============================================================================
export type {
  PatientConsultationHistoryItem,
  PatientConsultationsHistoryResponse,
} from "@api/types/patient-consultations.types";

// =============================================================================
// LICENCIAS MEDICAS (MedicalLeave)
// =============================================================================
export type {
  MedicalLeaveItem,
  PatientMedicalLeavesResponse,
  CreateMedicalLeaveRequest,
} from "@api/types/medical-leave.types";

// =============================================================================
// PASES / REFERENCIAS (Referral)
// =============================================================================
export type {
  ReferralType,
  ReferralVisitType,
  ReferralStatus,
  ReferralStudyItem,
  ReferralItem,
  PatientReferralsResponse,
  CreateReferralStudyRequest,
  CreateReferralRequest,
  CancelReferralRequest,
} from "@api/types/referral.types";

// =============================================================================
// REPORTES - CONSULTA MEDICA DIARIA
// =============================================================================
export type {
  DailyConsultationReportParams,
  DailyConsultationReportItem,
  DailyConsultationReportResponse,
} from "@api/types/reportes-consultas-diario.types";

// =============================================================================
// REPORTES - PASES
// =============================================================================
export type {
  ReferralReportParams,
  ReferralReportItem,
  ReferralReportResponse,
} from "@api/types/reportes-pases.types";

// =============================================================================
// DIAGNOSTICOS SECUNDARIOS (VisitDiagnosis)
// =============================================================================
export type {
  SecondaryDiagnosisStatus,
  SecondaryDiagnosisItem,
  VisitSecondaryDiagnosesResponse,
  AddSecondaryDiagnosisRequest,
} from "@api/types/visit-diagnosis.types";

// =============================================================================
// RECETA ESTRUCTURADA (VisitPrescriptionItem)
// =============================================================================
export type {
  PrescriptionItemStatus,
  PrescriptionItem,
  VisitPrescriptionItemsResponse,
  AddPrescriptionItemRequest,
} from "@api/types/prescription-item.types";

export type {
  CuadroBasico,
  MedicamentoListItem,
  MedicamentosListResponse,
  MedicamentosListParams,
} from "@api/types/catalogos/medicamentos.types";

// =============================================================================
// RESULTADOS DE ESTUDIOS (StudyResult)
// =============================================================================
export type {
  StudyResultItem,
  PatientStudyResultsResponse,
  CreateStudyResultRequest,
} from "@api/types/study-result.types";

// =============================================================================
// HISTORIA CLINICA DE ESTOMATOLOGIA (StomatologyHistory)
// =============================================================================
export type {
  StomatologyHistory,
  UpdateStomatologyHistoryRequest,
} from "@api/types/stomatology-history.types";

// =============================================================================
// ODONTOGRAMA (OdontogramTooth)
// =============================================================================
export type {
  ToothCondition,
  OdontogramToothItem,
  PatientOdontogramResponse,
  UpdateOdontogramToothRequest,
  OdontogramDentition,
} from "@api/types/odontogram.types";

// =============================================================================
// TIPO PERSONAL TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  TipoPersonalListItem,
  TipoPersonalDetail,
  // CRUD Requests
  CreateTipoPersonalRequest,
  UpdateTipoPersonalRequest,
  // CRUD Responses
  CreateTipoPersonalResponse,
  UpdateTipoPersonalResponse,
  DeleteTipoPersonalResponse,
  // Listados
  TipoPersonalListParams,
  TipoPersonalListResponse,
  // Detalle
  TipoPersonalDetailResponse,
} from "@api/types/catalogos/tipo-personal.types";

// =============================================================================
// ENFERMEDADES TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  EnfermedadListItem,
  EnfermedadDetail,
  // CRUD Requests
  CreateEnfermedadRequest,
  UpdateEnfermedadRequest,
  // CRUD Responses
  CreateEnfermedadResponse,
  UpdateEnfermedadResponse,
  DeleteEnfermedadResponse,
  // Listados
  EnfermedadesListParams,
  EnfermedadesListResponse,
  // Detalle
  EnfermedadDetailResponse,
} from "@api/types/catalogos/enfermedades.types";

// =============================================================================
// ESCOLARIDAD TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  EscolaridadListItem,
  EscolaridadDetail,
  // CRUD Requests
  CreateEscolaridadRequest,
  UpdateEscolaridadRequest,
  // CRUD Responses
  CreateEscolaridadResponse,
  UpdateEscolaridadResponse,
  DeleteEscolaridadResponse,
  // Listados
  EscolaridadListParams,
  EscolaridadListResponse,
  // Detalle
  EscolaridadDetailResponse,
} from "@api/types/catalogos/escolaridad.types";

// =============================================================================
// BAJAS TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  BajaListItem,
  BajaDetail,
  // CRUD Requests
  CreateBajaRequest,
  UpdateBajaRequest,
  // CRUD Responses
  CreateBajaResponse,
  UpdateBajaResponse,
  DeleteBajaResponse,
  // Listados
  BajasListParams,
  BajasListResponse,
  // Detalle
  BajaDetailResponse,
} from "@api/types/catalogos/bajas.types";

// =============================================================================
// PASES TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  PaseListItem,
  PaseDetail,
  // CRUD Requests
  CreatePaseRequest,
  UpdatePaseRequest,
  // CRUD Responses
  CreatePaseResponse,
  UpdatePaseResponse,
  DeletePaseResponse,
  // Listados
  PasesListParams,
  PasesListResponse,
  // Detalle
  PaseDetailResponse,
} from "@api/types/catalogos/pases.types";

// =============================================================================
// TIPOS SANGUINEO TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  TipoSanguineoListItem,
  TipoSanguineoDetail,
  // CRUD Requests
  CreateTipoSanguineoRequest,
  UpdateTipoSanguineoRequest,
  // CRUD Responses
  CreateTipoSanguineoResponse,
  UpdateTipoSanguineoResponse,
  DeleteTipoSanguineoResponse,
  // Listados
  TiposSanguineoListParams,
  TiposSanguineoListResponse,
  // Detalle
  TipoSanguineoDetailResponse,
} from "@api/types/catalogos/tipos-sanguineo.types";

// =============================================================================
// GRUPOS DE MEDICAMENTOS TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  GrupoMedicamentosListItem,
  GrupoMedicamentosDetail,
  // CRUD Requests
  CreateGrupoMedicamentosRequest,
  UpdateGrupoMedicamentosRequest,
  // CRUD Responses
  CreateGrupoMedicamentosResponse,
  UpdateGrupoMedicamentosResponse,
  DeleteGrupoMedicamentosResponse,
  // Listados
  GruposMedicamentosListParams,
  GruposMedicamentosListResponse,
  // Detalle
  GrupoMedicamentosDetailResponse,
} from "@api/types/catalogos/grupos-medicamentos.types";

// =============================================================================
// OCUPACIONES TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  OcupacionListItem,
  OcupacionDetail,
  // CRUD Requests
  CreateOcupacionRequest,
  UpdateOcupacionRequest,
  // CRUD Responses
  CreateOcupacionResponse,
  UpdateOcupacionResponse,
  DeleteOcupacionResponse,
  // Listados
  OcupacionesListParams,
  OcupacionesListResponse,
  // Detalle
  OcupacionDetailResponse,
} from "@api/types/catalogos/ocupaciones.types";

// =============================================================================
// LICENCIAS TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  LicenciaListItem,
  LicenciaDetail,
  // CRUD Requests
  CreateLicenciaRequest,
  UpdateLicenciaRequest,
  // CRUD Responses
  CreateLicenciaResponse,
  UpdateLicenciaResponse,
  DeleteLicenciaResponse,
  // Listados
  LicenciasListParams,
  LicenciasListResponse,
  // Detalle
  LicenciaDetailResponse,
} from "@api/types/catalogos/licencias.types";

// =============================================================================
// AUTORIZADORES TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  AutorizadorListItem,
  AutorizadorDetail,
  // CRUD Requests
  CreateAutorizadorRequest,
  UpdateAutorizadorRequest,
  // CRUD Responses
  CreateAutorizadorResponse,
  UpdateAutorizadorResponse,
  DeleteAutorizadorResponse,
  // Listados
  AutorizadoresListParams,
  AutorizadoresListResponse,
  // Detalle
  AutorizadorDetailResponse,
} from "@api/types/catalogos/autorizadores.types";

// =============================================================================
// CALIDAD LABORAL TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  CalidadLaboralListItem,
  CalidadLaboralDetail,
  // CRUD Requests
  CreateCalidadLaboralRequest,
  UpdateCalidadLaboralRequest,
  // CRUD Responses
  CreateCalidadLaboralResponse,
  UpdateCalidadLaboralResponse,
  DeleteCalidadLaboralResponse,
  // Listados
  CalidadLaboralListParams,
  CalidadLaboralListResponse,
  // Detalle
  CalidadLaboralDetailResponse,
} from "@api/types/catalogos/calidadLaboral.types";

// =============================================================================
// ORIGEN CONSULTA TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  OrigenConsultaListItem,
  OrigenConsultaDetail,
  // CRUD Requests
  CreateOrigenConsultaRequest,
  UpdateOrigenConsultaRequest,
  // CRUD Responses
  CreateOrigenConsultaResponse,
  UpdateOrigenConsultaResponse,
  DeleteOrigenConsultaResponse,
  // Listados
  OrigenConsultaListParams,
  OrigenConsultaListResponse,
  // Detalle
  OrigenConsultaDetailResponse,
} from "@api/types/catalogos/origenConsulta.types";

// =============================================================================
// PARENTESCO TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  ParentescoListItem,
  ParentescoDetail,
  // CRUD Requests
  CreateParentescoRequest,
  UpdateParentescoRequest,
  // CRUD Responses
  CreateParentescoResponse,
  UpdateParentescoResponse,
  DeleteParentescoResponse,
  // Listados
  ParentescoListParams,
  ParentescoListResponse,
  // Detalle
  ParentescoDetailResponse,
} from "@api/types/catalogos/parentesco.types";

// =============================================================================
// DISCAPACIDADES TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  DiscapacidadListItem,
  DiscapacidadDetail,
  // CRUD Requests
  CreateDiscapacidadRequest,
  UpdateDiscapacidadRequest,
  // CRUD Responses
  CreateDiscapacidadResponse,
  UpdateDiscapacidadResponse,
  DeleteDiscapacidadResponse,
  // Listados
  DiscapacidadesListParams,
  DiscapacidadesListResponse,
  // Detalle
  DiscapacidadDetailResponse,
} from "@api/types/catalogos/discapacidades.types";

// =============================================================================
// ESCUELAS TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  EscuelaListItem,
  EscuelaDetail,
  // CRUD Requests
  CreateEscuelaRequest,
  UpdateEscuelaRequest,
  // CRUD Responses
  CreateEscuelaResponse,
  UpdateEscuelaResponse,
  DeleteEscuelaResponse,
  // Listados
  EscuelasListParams,
  EscuelasListResponse,
  // Detalle
  EscuelaDetailResponse,
} from "@api/types/catalogos/escuelas.types";

// =============================================================================
// ESTUDIOS MEDICOS TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  EstudioMedicoListItem,
  EstudioMedicoDetail,
  // CRUD Requests
  CreateEstudioMedicoRequest,
  UpdateEstudioMedicoRequest,
  // CRUD Responses
  CreateEstudioMedicoResponse,
  UpdateEstudioMedicoResponse,
  DeleteEstudioMedicoResponse,
  // Listados
  EstudiosMedicosListParams,
  EstudiosMedicosListResponse,
  // Detalle
  EstudioMedicoDetailResponse,
} from "@api/types/catalogos/estudios-medicos.types";

// =============================================================================
// CATÁLOGO ESTADO CIVIL
// =============================================================================
export type {
  // Entidades
  EdoCivilListItem,
  EdoCivilDetail,
  // CRUD Requests
  CreateEdoCivilRequest,
  UpdateEdoCivilRequest,
  // CRUD Responses
  CreateEdoCivilResponse,
  UpdateEdoCivilResponse,
  DeleteEdoCivilResponse,
  // Listados
  EdoCivilListParams,
  EdoCivilListResponse,
  // Detalle
  EdoCivilDetailResponse,
} from "@api/types/catalogos/edoCivil.types";

// =============================================================================
// CATÁLOGO SUCURSALES
// =============================================================================
export type {
  SucursalListItem,
  SucursalDetail,
  SucursalesListParams,
  SucursalesListResponse,
  CreateSucursalRequest,
  CreateSucursalResponse,
  UpdateSucursalRequest,
  UpdateSucursalResponse,
  DeleteSucursalResponse,
  SucursalDetailResponse,
} from "@api/types/catalogos/sucursales.types";

// =============================================================================
// ESPECIALIDADES TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  EspecialidadListItem,
  EspecialidadDetail,
  // CRUD Requests
  CreateEspecialidadRequest,
  UpdateEspecialidadRequest,
  // CRUD Responses
  CreateEspecialidadResponse,
  UpdateEspecialidadResponse,
  DeleteEspecialidadResponse,
  // Listados
  EspecialidadesListParams,
  EspecialidadesListResponse,
  // Detalle
  EspecialidadDetailResponse,
} from "@api/types/catalogos/especialidades.types";

// =============================================================================
// VACUNAS TYPES (CRUD)
// =============================================================================
export type {
  // Entidades
  VacunaListItem,
  VacunaDetail,
  // CRUD Requests
  CreateVacunaRequest,
  UpdateVacunaRequest,
  // CRUD Responses
  CreateVacunaResponse,
  UpdateVacunaResponse,
  DeleteVacunaResponse,
  // Listados
  VacunasListParams,
  VacunasListResponse,
  // Detalle
  VacunaDetailResponse,
} from "@api/types/catalogos/vacunas.types";

// =============================================================================
// ÁREAS CLÍNICAS TYPES (CRUD catálogo + relación por centro)
// =============================================================================
export type {
  // Refs
  AreaClinicaRef,
  // Catálogo cat_areas_clinicas
  AreaClinicaListItem,
  AreaClinicaDetail,
  CreateAreaClinicaRequest,
  UpdateAreaClinicaRequest,
  AreasClinicasListResponse,
  AreaClinicaDetailResponse,
  CreateAreaClinicaResponse,
  UpdateAreaClinicaResponse,
  DeleteAreaClinicaResponse,
  AreasClinicasListParams,
  // Relación centro_area_clinica
  CentroAreaClinicaListItem,
  CentroAreaClinicaDetail,
  CreateCentroAreaClinicaRequest,
  UpdateCentroAreaClinicaRequest,
  CentrosAreasClinicasListResponse,
  CentroAreaClinicaDetailResponse,
  CreateCentroAreaClinicaResponse,
  UpdateCentroAreaClinicaResponse,
  DeleteCentroAreaClinicaResponse,
  CentrosAreasClinicasListParams,
} from "@api/types/catalogos/areas-clinicas.types";

// =============================================================================
// FARMACIA TYPES (inventario vacunas)
// =============================================================================
export type {
  VacunaRef,
  CentroRef,
  InventarioVacunaListItem,
  InventarioVacunaDetail,
  CreateInventarioVacunaRequest,
  UpdateInventarioVacunaRequest,
  InventarioVacunaListResponse,
  InventarioVacunaDetailResponse,
  CreateInventarioVacunaResponse,
  UpdateInventarioVacunaResponse,
  DeleteInventarioVacunaResponse,
  InventarioVacunaListParams,
  ApplyDosesRequest,
  ApplyDosesResponse,
} from "@api/types/farmacia/inventario-vacunas.types";

// =============================================================================
// NAVIGATION MENU TYPES (arbol servido por cat_modulos)
// =============================================================================
export type {
  NavigationMenuSource,
  NavigationMenuItemDTO,
  NavigationMenuSectionDTO,
  NavigationMenuResponse,
  ModuleCatalogNodeDTO,
  ModuleCatalogResponse,
  ModuleCatalogListParams,
  ModuleSummaryDTO,
  CreateModuleRequest,
  CreateModuleResponse,
  UpdateModuleRequest,
  UpdateModuleResponse,
  SetModuleVisibilityRequest,
  SetModuleVisibilityResponse,
  ReorderModulesRequest,
  ReorderModulesResultItem,
  ReorderModulesResponse,
} from "@api/types/navigation.types";

// =============================================================================
// CLINICAL FLOW TYPES (visits, vitals, doctor flow)
// =============================================================================
export type {
  ArrivalType,
  VisitService,
  VisitStatus,
  VisitQueueItem,
  VisitsListParams,
  VisitsListResponse,
  CreateVisitRequest,
  CreateVisitResponse,
  PatientMember,
  PatientLookupResponse,
  RecepcionStatusAction,
  UpdateVisitStatusRequest,
  UpdateVisitStatusResponse,
  CaptureVitalsRequest,
  CaptureVitalsResponse,
  EditVitalsRequest,
  EditVitalsResponse,
  VisitVitalsPayload,
  VitalsUserRef,
  ReusedFromPayload,
  LatestPatientVitals,
  LatestVitalsResponse,
  TodayCapturePayload,
  SaveDiagnosisRequest,
  SaveDiagnosisResponse,
  CieSearchParams,
  CieSearchItem,
  CieSearchResponse,
  SavePrescriptionRequest,
  SavePrescriptionResponse,
  StartConsultationResponse,
  VisitConsultationSummary,
  CloseVisitRequest,
  CloseVisitResponse,
  VisitStatusLogItem,
  VisitStatusLogResponse,
} from "@api/types/visits.types";

// =============================================================================
// CITAS
// =============================================================================
export type {
  EstatusCita,
  OrigenCanalCita,
  CitaListItem,
  SlotDisponible,
  CreateCitaRequest,
  UpdateEstatusCitaRequest,
  CitasListParams,
  SlotsParams,
  CitasListResponse,
  SlotsResponse,
  VerificarQRRequest,
  FichaQRResponse,
  ConfirmarQRCheckinResponse,
} from "@api/types/citas.types";
export { ESTATUS_CITA, ORIGEN_CANAL_CITA } from "@api/types/citas.types";

// =============================================================================
// CHECK-IN MANUAL (sin QR) — buscador por nombre o folio
// =============================================================================
export type {
  CheckinCandidato,
  CheckinCandidatosParams,
  CheckinCandidatosResponse,
  ConfirmarCheckinFolioRequest,
} from "@api/types/checkin.types";

export {
  ARRIVAL_TYPE,
  VISIT_SERVICE,
  VISIT_STATUS,
  RECEPCION_STATUS_ACTION,
} from "@api/types/visits.types";

// =============================================================================
// CONTRATOS OXÍGENO TYPES
// =============================================================================
export type {
  ContratoOxigeno,
  ContratoStatus,
  TpDer,
  ContratosListParams,
  ContratosListResponse,
  CreateContratoRequest,
  UpdateContratoRequest,
  ContratosStats,
  NotificarRequest,
  NotificarResponse,
  DerechohabienteResult,
  BuscarDerechohabienteParams,
  BuscarDerechohabienteResponse,
} from "@api/types/contratos.types";
export { CONTRATO_STATUS, TP_DER, TP_DER_LABELS, CONTRATO_STATUS_LABELS } from "@api/types/contratos.types";

// =============================================================================
// ALMACÉN — INVENTARIO DE INSUMOS TYPES
// =============================================================================
export type {
  CatUnidadMedida,
  CatCategoriaInsumo,
  CatProveedor,
  CatInsumo,
  Almacen,
  AlmacenTipo,
  CatalogosBaseListParams,
  InsumosListParams,
  AlmacenesListParams,
  CreateUnidadMedidaRequest,
  CreateCategoriaInsumoRequest,
  CreateProveedorRequest,
  CreateInsumoRequest,
  CreateAlmacenRequest,
  UpdateUnidadMedidaRequest,
  UpdateCategoriaInsumoRequest,
  UpdateProveedorRequest,
  UpdateInsumoRequest,
  UpdateAlmacenRequest,
  UnidadesMedidaListResponse,
  CategoriasInsumoListResponse,
  ProveedoresListResponse,
  InsumosListResponse,
  AlmacenesListResponse,
} from "@api/types/almacen/catalogos.types";
export { ALMACEN_TIPO, ALMACEN_TIPO_LABELS } from "@api/types/almacen/catalogos.types";

// ─── ALMACÉN — KARDEX / EXISTENCIAS / ENTRADAS ────────────────────────────────
export type {
  LoteInsumo,
  EntradaDetalle,
  EntradaInventario,
  KardexMovimiento,
  ExistenciaAlmacen,
  TipoMovimiento,
  LoteDatosInline,
  CreateEntradaDetalleRequest,
  CreateEntradaRequest,
  LotesListParams,
  EntradasListParams,
  KardexListParams,
  ExistenciasListParams,
  LotesListResponse,
  EntradasListResponse,
  KardexListResponse,
  ExistenciasListResponse,
} from "@api/types/almacen/kardex.types";
export { TIPO_MOVIMIENTO, TIPO_MOVIMIENTO_LABELS } from "@api/types/almacen/kardex.types";
export type {
  TipoSalida,
  SalidaDetalle,
  SalidaInventario,
  CreateSalidaDetalleRequest,
  CreateSalidaRequest,
  SalidasListParams,
  SalidasListResponse,
  ConteoFisicoDetalle,
  ConteoFisico,
  CreateConteoRequest,
  CerrarConteoRequest,
  ConteosListParams,
  ConteosListResponse,
  DashboardStats,
  ConsumoConsultaDetalle,
  ConsumoConsulta,
  CreateConsumoDetalleRequest,
  CreateConsumoRequest,
  ConsumosListParams,
  ConsumosListResponse,
} from "@api/types/almacen/kardex.types";
export { TIPO_SALIDA, TIPO_SALIDA_LABELS } from "@api/types/almacen/kardex.types";
