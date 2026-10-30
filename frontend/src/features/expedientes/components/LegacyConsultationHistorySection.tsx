import { useState } from "react";
import { ChevronDown, ChevronUp, History } from "lucide-react";
import { useLegacyConsultationsHistory } from "@features/expedientes/queries/useLegacyConsultationsHistory";
import type { LegacyBase, LegacyConsultationItem } from "@api/types/legacy-consultation.types";

interface Props {
  noExp: string;
  pkNum: number;
}

/** "legado_actual" -> "Base actual"; "legado_2024_a" -> "Base 2024 a". */
const nombreBase = (sourceDb?: string | null) => {
  if (!sourceDb) return null;
  const resto = sourceDb.replace(/^legado_/, "");
  return resto === "actual" ? "Base actual" : `Base ${resto.replace(/_/g, " ")}`;
};

/**
 * "2025-03-10" es una fecha sin hora: `new Date("2025-03-10")` la toma como
 * medianoche UTC y en México se ve el día anterior. Se arma en hora local.
 */
const formatFecha = (fecha: string | null) => {
  if (!fecha) return "";
  const [anio, mes, dia] = fecha.slice(0, 10).split("-").map(Number);
  if (!anio || !mes || !dia) return fecha;
  return new Date(anio, mes - 1, dia).toLocaleDateString("es-MX", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
};

/** "Base 2016 · 2016 · 12 notas"; la actual puede abarcar más de un año. */
const etiquetaBase = (base: LegacyBase) => {
  const desde = base.from?.slice(0, 4);
  const hasta = base.to?.slice(0, 4);
  const rango = desde && hasta && desde !== hasta ? `${desde}–${hasta}` : (hasta ?? desde);
  const notas = `${base.total} ${base.total === 1 ? "nota" : "notas"}`;
  return [nombreBase(base.sourceDb), rango, notas].filter(Boolean).join(" · ");
};

const TITULO_PASE = {
  GABINETE: "Pases de gabinete:",
  LABORATORIO: "Pases de laboratorio:",
  ESPECIALIDAD: "Pases a especialidad:",
  HOSPITAL: "Pases a hospital:",
} as const;

const Campo = ({ titulo, texto }: { titulo: string; texto: string | null | undefined }) =>
  texto ? (
    <p>
      <strong>{titulo}:</strong> {texto}
    </p>
  ) : null;

const NotaLegado = ({ nota }: { nota: LegacyConsultationItem }) => {
  const [detalle, setDetalle] = useState(false);
  const servicio = [nota.serviceName, nota.consultationType, nota.specialtyName].filter(Boolean);
  const medicamentos = nota.medications ?? [];
  const incapacidades = nota.sickLeaves ?? [];
  const conUnidad = (valor: string | null | undefined, unidad: string) =>
    valor ? `${valor} ${unidad}` : "";
  // Mismo acomodo que la pantalla de SISEM: dos columnas de etiqueta y valor.
  const vitales: [string, string][] = [
    ["Estatura", conUnidad(nota.heightLegacy, "m")],
    ["Peso", conUnidad(nota.weightLegacy, "Kg")],
    ["T.A.", conUnidad(nota.bloodPressureLegacy, "mmHg")],
    ["Temperatura", conUnidad(nota.temperatureLegacy, "°C")],
    ["Frecuencia cardiaca", conUnidad(nota.pulseLegacy, "lpm")],
    ["Frecuencia respiratoria", conUnidad(nota.respirationLegacy, "rpm")],
    ["IMC", conUnidad(nota.bmiLegacy, "Kg/m2")],
    ["Glucosa capilar", conUnidad(nota.glucoseLegacy, "mg/dL")],
  ];
  const diagnostico = (
    <>
      {nota.diagnosticImpression && (
        <p className="text-txt-body">
          <strong>Diagnóstico:</strong> {nota.diagnosticImpression}
        </p>
      )}
      {nota.diagnoses && nota.diagnoses.length > 0 && (
        <ul className="text-txt-body list-disc pl-5">
          {nota.diagnoses.map((cie, indice) => (
            <li key={`${nota.id}-cie-${indice}`}>
              {cie.codigo ? <span className="font-mono">{cie.codigo}</span> : null}
              {cie.codigo && cie.descripcion ? " — " : ""}
              {cie.descripcion}
            </li>
          ))}
        </ul>
      )}
    </>
  );

  return (
    <div className="p-3 bg-subtle rounded-md text-sm space-y-1">
      <div className="flex items-center justify-between">
        <p className="font-semibold text-txt-body">
          {formatFecha(nota.date)}
          {nota.time ? ` — ${nota.time}` : ""}
        </p>
        <span className="font-mono text-xs text-txt-muted">
          {nota.legacyFolio}
          {nombreBase(nota.sourceDb) ? ` · ${nombreBase(nota.sourceDb)}` : ""}
        </span>
      </div>
      {(nota.doctorName || nota.clinicName) && (
        <p className="text-txt-muted">
          {[nota.doctorName && `Dr(a). ${nota.doctorName}`, nota.clinicName]
            .filter(Boolean)
            .join(" · ")}
        </p>
      )}
      {servicio.length > 0 && (
        <p className="text-xs font-semibold uppercase tracking-wide text-txt-muted">
          {servicio.join(" · ")}
        </p>
      )}
      {nota.statusLegacy && nota.statusLegacy !== "A" && (
        <p className="text-xs font-semibold text-txt-muted uppercase">Nota cancelada en el legado</p>
      )}
      {!detalle && (
        <>
          {nota.objective && (
            <p className="text-txt-body">
              <strong>Objetivo:</strong> {nota.objective}
            </p>
          )}
          {diagnostico}
        </>
      )}
      {/* Detalle, en el orden que pidió el médico: signos vitales, SOAP,
          diagnóstico, próxima cita y complemento; los medicamentos con sus
          indicaciones; al final incapacidad y pases. */}
      {detalle && (
        <div className="space-y-1 border-t border-line-struct pt-2 text-txt-body">
          {/* Siempre, aunque vengan vacios: asi se ve que no se tomaron. */}
          <dl className="grid grid-cols-1 gap-x-6 gap-y-0.5 border-b border-line-struct pb-2 sm:grid-cols-2">
            {vitales.map(([etiqueta, valor]) => (
              <div key={etiqueta} className="flex justify-between gap-3">
                <dt className="font-semibold">{etiqueta}:</dt>
                <dd className="tabular-nums">{valor}</dd>
              </div>
            ))}
          </dl>
          <Campo titulo="Subjetivo" texto={nota.subjective} />
          <Campo titulo="Objetivo" texto={nota.objective} />
          <Campo titulo="Análisis" texto={nota.assessment} />
          <Campo titulo="Plan" texto={nota.plan} />
          {diagnostico}
          {nota.nextAppointment && (
            <Campo titulo="Próxima cita" texto={formatFecha(nota.nextAppointment)} />
          )}
          <Campo titulo="Complemento" texto={nota.addendumLegacy} />
        </div>
      )}
      {medicamentos.length > 0 && (
        <div className="text-txt-body">
          <strong>Medicamentos:</strong>
          <ul className="list-disc pl-5">
            {medicamentos.map((medicamento, indice) => (
              <li
                key={`${nota.id}-med-${indice}`}
                className={medicamento.cancelled ? "text-txt-muted line-through" : undefined}
              >
                {/* Sin principio activo en el catálogo, el nombre del medicamento. */}
                {medicamento.activeIngredient ?? medicamento.name}
                {medicamento.cancelled ? " — cancelado" : ""}
                {detalle && medicamento.instructions && (
                  <span className="block text-txt-muted">
                    Indicaciones: {medicamento.instructions}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {detalle && incapacidades.length > 0 && (
        <p className="text-txt-body">
          <strong>Días de incapacidad:</strong>{" "}
          {incapacidades.map((incapacidad, indice) => (
            <span
              key={`${nota.id}-inc-${indice}`}
              className={incapacidad.cancelled ? "text-txt-muted line-through" : undefined}
            >
              {indice > 0 ? " · " : ""}
              {incapacidad.days ?? "sin dato"}
              {incapacidad.cancelled ? " (cancelada)" : ""}
            </span>
          ))}
        </p>
      )}
      {detalle &&
        (["GABINETE", "LABORATORIO", "ESPECIALIDAD", "HOSPITAL"] as const).map((tipo) => {
          const estudios = (nota.referralStudies ?? []).filter((estudio) => estudio.type === tipo);
          return estudios.length > 0 ? (
            <div key={`${nota.id}-pase-${tipo}`} className="text-txt-body">
              <strong>{TITULO_PASE[tipo]}</strong>
              <ul className="list-disc pl-5">
                {estudios.map((estudio, indice) => (
                  <li
                    key={`${nota.id}-${tipo}-${indice}`}
                    className={estudio.cancelled ? "text-txt-muted line-through" : undefined}
                  >
                    {estudio.name}
                    {estudio.note ? ` — ${estudio.note}` : ""}
                    {estudio.cancelled ? " — cancelado" : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null;
        })}
      <button
        type="button"
        onClick={() => setDetalle((v) => !v)}
        className="text-xs font-semibold text-txt-muted hover:text-txt-body underline"
      >
        {detalle ? "Ocultar detalle" : "Ver detalle"}
      </button>
    </div>
  );
};

/**
 * Notas del legado (previas a SIRES) -- archivo de solo lectura,
 * separado de las consultas reales de SIRES (ConsultationRepository /
 * usePatientConsultationsHistory). No tiene acciones (editar/cancelar/
 * aclarar) porque es un volcado histórico inmutable, no un registro
 * operativo. El legado tiene una base por año: se abre en la más reciente
 * y el selector consulta las demás solo cuando se eligen.
 */
export const LegacyConsultationHistorySection = ({ noExp, pkNum }: Props) => {
  const [abierto, setAbierto] = useState(false);
  const [baseElegida, setBaseElegida] = useState<string | null>(null);

  const inicial = useLegacyConsultationsHistory(noExp, pkNum, abierto);
  const baseInicial = inicial.data?.base ?? null;
  const otraBase = baseElegida && baseElegida !== baseInicial ? baseElegida : undefined;
  const elegida = useLegacyConsultationsHistory(noExp, pkNum, abierto && Boolean(otraBase), otraBase);

  const data = otraBase ? elegida.data : inicial.data;
  const isLoading = inicial.isLoading || (otraBase ? elegida.isLoading : false);
  const bases = inicial.data?.bases ?? [];
  const baseActual = otraBase ?? baseInicial ?? "";

  return (
    <div className="mt-6 rounded-lg border border-line-struct">
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-subtle/40 transition-colors"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-txt-body">
          <History className="size-4 text-txt-muted" />
          Historial previo a SIRES (legado)
        </span>
        {abierto ? (
          <ChevronUp className="size-4 text-txt-muted" />
        ) : (
          <ChevronDown className="size-4 text-txt-muted" />
        )}
      </button>

      {abierto && (
        <div className="border-t border-line-struct p-4 space-y-3">
          {bases.length > 0 && (
            <label className="flex flex-col gap-1 text-xs font-semibold text-txt-muted sm:flex-row sm:items-center sm:gap-2">
              Año
              <select
                aria-label="Año del legado"
                value={baseActual}
                onChange={(e) => setBaseElegida(e.target.value)}
                className="h-9 w-full rounded-md border border-line-struct bg-paper px-3 text-sm font-normal text-txt-body sm:w-auto"
              >
                {bases.map((base) => (
                  <option key={base.sourceDb} value={base.sourceDb}>
                    {etiquetaBase(base)}
                  </option>
                ))}
              </select>
            </label>
          )}

          {isLoading && (
            <p className="text-txt-muted text-sm text-center py-6">
              Cargando historial del legado...
            </p>
          )}

          {data?.disponible === false && (
            <p className="text-txt-muted text-sm text-center py-6">{data.mensaje}</p>
          )}

          {data && data.disponible !== false && data.items.length === 0 && (
            <p className="text-txt-muted text-sm text-center py-6">
              No hay notas del legado para este paciente.
            </p>
          )}

          {data && data.items.length > 0 && (
            <>
              {data.totalCount > data.items.length && (
                <p className="text-xs text-txt-muted italic">
                  Mostrando las {data.items.length} más recientes de {data.totalCount} en esta base.
                </p>
              )}
              {data.items.map((nota) => (
                <NotaLegado key={nota.id} nota={nota} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
};
