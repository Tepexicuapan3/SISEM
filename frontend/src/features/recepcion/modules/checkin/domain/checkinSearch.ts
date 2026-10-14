import type {
  CheckinCandidato,
  CheckinCandidatosParams,
  ConfirmarQRCheckinResponse,
  FichaQRResponse,
} from "@api/types";

/**
 * Patrón del folio de cita (`CIT-<10 hex uppercase>`, ver
 * `CitaMedica.generar_folio` en `backend/apps/recepcion/models.py`). Se usa
 * de forma permisiva (6+ caracteres tras "CIT-") para poder detectar la
 * intención de búsqueda por folio sin exigirle al usuario que termine de
 * escribirlo completo.
 */
const FOLIO_LIKE_PATTERN = /^CIT-[A-Z0-9]{6,}$/i;

export const looksLikeFolio = (raw: string): boolean =>
  FOLIO_LIKE_PATTERN.test(raw.trim());

/**
 * Resuelve qué parámetro mandarle a `GET /citas/checkin/candidatos` a partir
 * de un único campo de búsqueda de texto libre.
 *
 * Decisión de UX: un solo input con detección automática del formato de
 * folio, en vez de un selector explícito "buscar por nombre" / "buscar por
 * folio". Se eligió así para minimizar clicks y decisiones del personal de
 * recepción bajo presión de tiempo — escriben lo que tengan a mano (el
 * folio impreso en el comprobante o el nombre del paciente que tienen
 * enfrente) y el sistema decide solo. El costo es que un nombre de
 * paciente que por casualidad empezara con "CIT-" se interpretaría como
 * folio, pero es un caso extremadamente improbable en la práctica.
 *
 * Devuelve `null` cuando el texto todavía no alcanza para buscar (evita
 * queries de 1 carácter que traerían casi todas las citas del día).
 */
export const resolveCheckinSearchParams = (
  raw: string,
): CheckinCandidatosParams | null => {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  if (looksLikeFolio(trimmed)) {
    return { folio: trimmed.toUpperCase() };
  }

  if (trimmed.length < 2) return null;

  return { nombre: trimmed };
};

/**
 * Arma la ficha para mostrar tras confirmar un check-in por folio buscado.
 * El response de `POST /citas/checkin/confirmar-folio` no trae la ficha
 * completa (solo `folio`/`paciente`/`verificadoEn`/`visit`, igual que la
 * confirmación por QR) — se completa con los datos que ya teníamos del
 * candidato elegido (médico, consultorio, fecha, origenCanal) y con
 * `servicioTipo`/`motivo` que sí trae el `visit` de la respuesta.
 */
export const buildConfirmedFichaFromCandidato = (
  candidato: CheckinCandidato,
  result: ConfirmarQRCheckinResponse,
): FichaQRResponse => ({
  folio: result.folio,
  paciente: result.paciente || candidato.pacienteNombre,
  vigenciaActiva: candidato.vigenciaActiva,
  medico: candidato.medicoNombre,
  consultorio: candidato.consultorioNombre,
  fechaHora: candidato.fechaHora,
  servicioTipo: result.visit.serviceType,
  motivo: result.visit.notes,
  estatus: candidato.estatus,
  yaVerificada: true,
  origenCanal: candidato.origenCanal,
});
