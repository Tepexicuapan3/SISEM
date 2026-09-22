import type { MenuDestination } from "./menu-destinations.generated";

/**
 * Labels humanos por destino de menu — A MANO, NO generado.
 *
 * Razon industria:
 * - El path y el permiso de cada destino se derivan del codigo real
 *   (`menu-destinations.generated.ts`), pero el nombre amigable que ve un
 *   admin no-tecnico ("Vacunas", "Consultas") no es derivable de ahi: no
 *   existe una unica fuente de verdad para "como se llama esto para un
 *   humano".
 * - `grupo` es solo agrupacion visual para el selector de destino
 *   (`MenuDestinationSelect`, Fase 5) — NO es el mismo concepto que
 *   `Modulo.grupo` del backend (ese es "primary"/"secondary" para el
 *   sidebar persistido).
 *
 * Mantenimiento: cuando el generador agrega un path nuevo (`pnpm run
 * gen:menu-destinations`), el test anti-drift
 * (`src/test/unit/navigation/menu-destinations.test.ts`) va a fallar hasta
 * que se agregue su entrada aca. Asi una ruta nueva sin label rompe CI en
 * vez de degradar en silencio (aparecer sin nombre en el selector).
 */

export interface MenuDestinationLabel {
  label: string;
  grupo: string;
}

export const MENU_DESTINATION_LABELS: Record<
  MenuDestination["path"],
  MenuDestinationLabel
> = {
  "/admin/autorizacion/estudios": {
    label: "Autorización de Estudios",
    grupo: "Administración",
  },
  "/admin/catalogos": { label: "Catálogos", grupo: "Catálogos" },
  "/admin/catalogos/areas": { label: "Áreas", grupo: "Catálogos" },
  "/admin/catalogos/areas-clinicas": {
    label: "Áreas Clínicas",
    grupo: "Catálogos",
  },
  "/admin/catalogos/autorizadores": {
    label: "Autorizadores",
    grupo: "Catálogos",
  },
  "/admin/catalogos/bajas": { label: "Bajas", grupo: "Catálogos" },
  "/admin/catalogos/calidad-laboral": {
    label: "Calidad Laboral",
    grupo: "Catálogos",
  },
  "/admin/catalogos/centro-area-clinica": {
    label: "Centro / Área Clínica",
    grupo: "Catálogos",
  },
  "/admin/catalogos/centros-atencion": {
    label: "Centros de Atención",
    grupo: "Catálogos",
  },
  "/admin/catalogos/cies": {
    label: "CIE-10 (Diagnósticos)",
    grupo: "Catálogos",
  },
  "/admin/catalogos/edo-civil": { label: "Estado Civil", grupo: "Catálogos" },
  "/admin/catalogos/enfermedades": {
    label: "Enfermedades",
    grupo: "Catálogos",
  },
  "/admin/catalogos/escolaridad": {
    label: "Escolaridad",
    grupo: "Catálogos",
  },
  "/admin/catalogos/escuelas": { label: "Escuelas", grupo: "Catálogos" },
  "/admin/catalogos/discapacidades": {
    label: "Discapacidades",
    grupo: "Catálogos",
  },
  "/admin/catalogos/especialidades": {
    label: "Especialidades",
    grupo: "Catálogos",
  },
  "/admin/catalogos/estudios-medicos": {
    label: "Estudios Médicos",
    grupo: "Catálogos",
  },
  "/admin/catalogos/grupos-medicamentos": {
    label: "Grupos de Medicamentos",
    grupo: "Catálogos",
  },
  "/admin/catalogos/licencias": {
    label: "Licencias (Catálogo)",
    grupo: "Catálogos",
  },
  "/admin/catalogos/ocupaciones": {
    label: "Ocupaciones",
    grupo: "Catálogos",
  },
  "/admin/catalogos/origen-consulta": {
    label: "Origen de Consulta",
    grupo: "Catálogos",
  },
  "/admin/catalogos/parentescos": {
    label: "Parentescos",
    grupo: "Catálogos",
  },
  "/admin/catalogos/pases": { label: "Pases", grupo: "Catálogos" },
  "/admin/catalogos/sucursales": { label: "Sucursales", grupo: "Catálogos" },
  "/admin/catalogos/tipo-personal": {
    label: "Tipo de Personal",
    grupo: "Catálogos",
  },
  "/admin/catalogos/tipos-areas": {
    label: "Tipos de Áreas",
    grupo: "Catálogos",
  },
  "/admin/catalogos/tipos-autorizacion": {
    label: "Tipos de Autorización",
    grupo: "Catálogos",
  },
  "/admin/catalogos/tipos-citas": {
    label: "Tipos de Citas",
    grupo: "Catálogos",
  },
  "/admin/catalogos/tipos-consulta": {
    label: "Tipos de Consulta",
    grupo: "Catálogos",
  },
  "/admin/catalogos/tipos-sanguineo": {
    label: "Tipos Sanguíneos",
    grupo: "Catálogos",
  },
  "/admin/catalogos/turnos": { label: "Turnos", grupo: "Catálogos" },
  "/admin/catalogos/vacunas": { label: "Vacunas", grupo: "Catálogos" },
  "/admin/conciliacion": { label: "Conciliación", grupo: "Administración" },
  "/admin/conexiones": {
    label: "Conexiones / Sesiones",
    grupo: "Administración",
  },
  "/admin/estadisticas": { label: "Estadísticas", grupo: "Administración" },
  "/admin/expedientes": {
    label: "Expedientes (Administración)",
    grupo: "Administración",
  },
  "/admin/licencias": {
    label: "Licencias (Control de Accesos)",
    grupo: "Administración",
  },
  "/admin/medicos": { label: "Médicos", grupo: "Administración" },
  "/admin/menus": { label: "Gestión de Menús", grupo: "Administración" },
  "/admin/reportes": {
    label: "Reportes y Analítica Operativa",
    grupo: "Administración",
  },
  "/admin/roles": { label: "Roles", grupo: "Administración" },
  "/admin/usuarios": { label: "Usuarios", grupo: "Administración" },
  "/almacen/almacenes": { label: "Almacenes", grupo: "Almacén" },
  "/almacen/categorias": { label: "Categorías", grupo: "Almacén" },
  "/almacen/consumos": { label: "Consumos", grupo: "Almacén" },
  "/almacen/conteos": { label: "Conteos", grupo: "Almacén" },
  "/almacen/dashboard": { label: "Dashboard de Almacén", grupo: "Almacén" },
  "/almacen/entradas": { label: "Entradas", grupo: "Almacén" },
  "/almacen/existencias": { label: "Existencias", grupo: "Almacén" },
  "/almacen/insumos": { label: "Insumos", grupo: "Almacén" },
  "/almacen/kardex": { label: "Kardex", grupo: "Almacén" },
  "/almacen/proveedores": { label: "Proveedores", grupo: "Almacén" },
  "/almacen/salidas": { label: "Salidas", grupo: "Almacén" },
  "/almacen/unidades-medida": {
    label: "Unidades de Medida",
    grupo: "Almacén",
  },
  "/clinico/ambulancias": { label: "Ambulancias", grupo: "Clínico" },
  "/clinico/autorizacion-recetas": {
    label: "Autorización de Recetas",
    grupo: "Clínico",
  },
  "/clinico/cirugias": { label: "Cirugías", grupo: "Clínico" },
  "/clinico/consultas": { label: "Consultas", grupo: "Clínico" },
  "/clinico/consultas/agenda": {
    label: "Agenda de Consultas",
    grupo: "Clínico",
  },
  "/clinico/consultas/doctor": {
    label: "Consulta Médica (Doctor)",
    grupo: "Clínico",
  },
  "/clinico/consultas/historial": {
    label: "Historial de Consultas",
    grupo: "Clínico",
  },
  "/clinico/consultas/nueva": { label: "Nueva Consulta", grupo: "Clínico" },
  "/clinico/expedientes": { label: "Expedientes Clínicos", grupo: "Clínico" },
  "/clinico/expedientes/nuevo": {
    label: "Nuevo Expediente",
    grupo: "Clínico",
  },
  "/clinico/somatometria": { label: "Somatometría", grupo: "Clínico" },
  "/dashboard": { label: "Panel Principal (Dashboard)", grupo: "Core" },
  "/farmacia/inventario": {
    label: "Inventario de Farmacia",
    grupo: "Farmacia",
  },
  "/farmacia/recetas": { label: "Gestión de Recetas", grupo: "Farmacia" },
  "/farmacia/vacunas": { label: "Inventario de Vacunas", grupo: "Farmacia" },
  "/recepcion/agenda": { label: "Agenda de Recepción", grupo: "Recepción" },
  "/recepcion/agendar-cita": { label: "Agendar Cita", grupo: "Recepción" },
  "/recepcion/checkin": { label: "Check-in", grupo: "Recepción" },
  "/recepcion/checkin/qr": {
    label: "Check-in por QR",
    grupo: "Recepción",
  },
  "/recepcion/fichas": { label: "Fichas de Recepción", grupo: "Recepción" },
  "/recepcion/incapacidad": { label: "Incapacidad", grupo: "Recepción" },
  "/recepcion/turnos": {
    label: "Configuración de Turnos",
    grupo: "Recepción",
  },
  "/servicios/contratos-oxigeno": {
    label: "Contratos de Oxígeno",
    grupo: "Servicios",
  },
  "/urgencias/triage": { label: "Triage", grupo: "Urgencias" },
};
