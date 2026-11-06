import type {
  AdscripcionResumen,
  AsignacionFamilia,
  CitaAdscripcion,
  FamiliaAdscripcionResponse,
  MotivoSinOpciones,
  RazonNoElegible,
} from "@api/types";

/**
 * P-03 · Asignación por familia: qué se manda según lo que eligió recepción.
 * Solo arma el envío; las reglas (elegibilidad, capacidad, citas) las decide
 * el backend y vienen en la respuesta de GET /adscripcion/familia.
 */

/** consultorioId null = el consultorio elegido para toda la familia. */
export interface EleccionMiembro {
  marcado: boolean;
  consultorioId: number | null;
}

export type EleccionFamilia = Record<number, EleccionMiembro>;

export const eleccionInicial = (familia: FamiliaAdscripcionResponse): EleccionFamilia =>
  Object.fromEntries(
    familia.miembros.map((m) => [m.pkNum, { marcado: m.elegible && m.preseleccionado, consultorioId: null }]),
  );

export const consultorioSugerido = (familia: FamiliaAdscripcionResponse): number | null =>
  (familia.opciones.find((o) => o.sugerida) ?? familia.opciones[0])?.consultorioId ?? null;

const consultorioDe = (eleccion: EleccionMiembro | undefined, consultorioFamilia: number) =>
  eleccion?.consultorioId ?? consultorioFamilia;

const marcados = (familia: FamiliaAdscripcionResponse, eleccion: EleccionFamilia) =>
  familia.miembros.filter((m) => m.elegible && eleccion[m.pkNum]?.marcado);

export function armarAsignaciones(
  familia: FamiliaAdscripcionResponse,
  eleccion: EleccionFamilia,
  consultorioFamilia: number,
): AsignacionFamilia[] {
  const sugerido = consultorioSugerido(familia);
  return marcados(familia, eleccion).map((m) => {
    const consultorioId = consultorioDe(eleccion[m.pkNum], consultorioFamilia);
    return {
      pkNum: m.pkNum,
      consultorioId,
      idAdscripcionEsperada: m.idAdscripcionActual,
      citasACancelar: (m.citasACancelarPorConsultorio[String(consultorioId)] ?? []).map((c) => c.idCita),
      fueSugerida: consultorioId === sugerido,
    };
  });
}

export function citasDelPlan(
  familia: FamiliaAdscripcionResponse,
  eleccion: EleccionFamilia,
  consultorioFamilia: number,
): { nombre: string; cita: CitaAdscripcion }[] {
  return marcados(familia, eleccion).flatMap((m) =>
    (m.citasACancelarPorConsultorio[String(consultorioDe(eleccion[m.pkNum], consultorioFamilia))] ?? []).map(
      (cita) => ({ nombre: m.nombre, cita }),
    ),
  );
}

const RAZONES: Record<RazonNoElegible, string> = {
  NO_VIGENTE: "No vigente en SERMED",
  SIN_DATO_EXPEDIENTE: "SERMED no trae su clínica",
  CLINICA_SIN_CENTRO: "Su clínica de SERMED no está registrada en SIRES",
  P03_INACTIVO: "Su centro no tiene consultorios familiares",
  OTRA_CLINICA: "Pertenece a otra clínica: se asigna aparte",
};

export const textoRazon = (razon: RazonNoElegible) => RAZONES[razon];

const SIN_OPCIONES: Record<MotivoSinOpciones, string> = {
  SIN_CONSULTORIOS: "El centro no tiene consultorios familiares configurados.",
  SIN_MEDICO: "Los consultorios familiares del centro no tienen médico activo.",
  TODOS_LLENOS: "Todos los consultorios familiares del centro están llenos.",
};

export const textoSinOpciones = (motivo: MotivoSinOpciones) => SIN_OPCIONES[motivo];

/**
 * Centro de la clínica de SERMED del paciente: el que resolvió la equivalencia
 * de P-03 (adscripcion.idCentroSermed); sin equivalencia, la clave contra el
 * id del centro, como el backend.
 */
export function centroDeLaClinica<T extends { id: number }>(
  paciente: { cdClinica: string | null; adscripcion?: Pick<AdscripcionResumen, "idCentroSermed"> | null },
  centros: T[],
): T | undefined {
  const equivalente = paciente.adscripcion?.idCentroSermed;
  if (equivalente != null) return centros.find((c) => c.id === equivalente);
  if (!paciente.cdClinica) return undefined;
  return centros.find((c) => String(c.id) === String(paciente.cdClinica).trim());
}
