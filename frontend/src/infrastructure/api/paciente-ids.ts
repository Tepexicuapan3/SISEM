/**
 * Plan contraer la llave vieja (docs/plans/contraer-llave-paciente.md): las
 * pantallas buscan por expediente, pero lo que se manda al guardar o leer
 * datos del paciente es su idPaciente (interno, nunca se muestra).
 *
 * Este registro guarda el idPaciente de cada miembro (expediente + pkNum) que
 * devolvió la búsqueda (`/visits/patient-lookup`) o "abrir paciente". Las
 * rutas de datos del paciente se arman SIEMPRE con `rutaPaciente`: con el id
 * conocido van a `/pacientes/<id>/…` y no llevan pkNum. Solo un miembro que
 * nunca se atendió (y por eso no tiene datos) usa todavía la ruta vieja.
 */
import apiClient from "@api/client";

interface MiembroConId {
  noExp: string;
  pkNum: number;
  idPaciente?: number | null;
}

const ids = new Map<string, number>();
const busquedas = new Map<string, Promise<void>>();

/** Mismo criterio que el backend: "040041" y " 40041 " son el mismo expediente. */
const normalizar = (noExp: string) => {
  const texto = String(noExp).trim();
  return /^\d+$/.test(texto) ? String(Number(texto)) : texto;
};

const clave = (noExp: string, pkNum: number) => `${normalizar(noExp)}|${pkNum}`;

export const registrarIdsPaciente = (miembros: Array<MiembroConId | null | undefined>) => {
  for (const miembro of miembros) {
    if (miembro?.idPaciente) ids.set(clave(miembro.noExp, miembro.pkNum), miembro.idPaciente);
  }
};

/** Busca el expediente una vez (las búsquedas simultáneas comparten la misma petición). */
const buscarExpediente = (noExp: string): Promise<void> => {
  const llave = normalizar(noExp);
  let busqueda = busquedas.get(llave);
  if (!busqueda) {
    busqueda = apiClient
      .get<{ titular: MiembroConId | null; dependientes: MiembroConId[] }>("/visits/patient-lookup", {
        params: { noExp, historico: "true" },
      })
      .then(({ data }) => registrarIdsPaciente([data.titular, ...data.dependientes]))
      .catch(() => undefined)
      .finally(() => busquedas.delete(llave));
    busquedas.set(llave, busqueda);
  }
  return busqueda;
};

/**
 * URL y parámetros para un recurso del paciente (`allergies`, `profile`, …).
 * `params` va con `...` dentro de los parámetros propios del recurso.
 */
export const rutaPaciente = async (
  noExp: string,
  pkNum: number,
  recurso: string,
): Promise<{ url: string; params: Record<string, number> }> => {
  let id = ids.get(clave(noExp, pkNum));
  if (id === undefined) {
    await buscarExpediente(noExp);
    id = ids.get(clave(noExp, pkNum));
  }
  return id !== undefined
    ? { url: `/pacientes/${id}/${recurso}`, params: {} }
    : { url: `/patients/${noExp}/${recurso}`, params: { pkNum } };
};

/**
 * Cuerpo para guardar algo del paciente: si se conoce su idPaciente, viaja
 * solo ese id (sin expediente ni pkNum). Si no (nunca se atendió), viaja la
 * llave y el backend lo abre por la puerta central.
 */
export const conIdPaciente = async <T extends { pkNum?: number }>(
  datos: T,
  campoExpediente: "noExp" | "expediente" = "noExp",
): Promise<T> => {
  const noExp = (datos as Record<string, unknown>)[campoExpediente];
  if (typeof noExp !== "string" || !noExp) return datos;
  const pkNum = datos.pkNum ?? 0;
  let id = ids.get(clave(noExp, pkNum));
  if (id === undefined) {
    await buscarExpediente(noExp);
    id = ids.get(clave(noExp, pkNum));
  }
  if (id === undefined) return datos;
  const resto: Record<string, unknown> = { ...datos };
  delete resto[campoExpediente];
  delete resto.pkNum;
  return { ...resto, idPaciente: id } as unknown as T;
};
