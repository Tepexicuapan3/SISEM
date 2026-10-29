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

const NotaLegado = ({ nota }: { nota: LegacyConsultationItem }) => {
  const [detalle, setDetalle] = useState(false);
  const servicio = [nota.serviceName, nota.consultationType, nota.specialtyName].filter(Boolean);
  const medicamentos = nota.medications ?? [];
  const vitales = [
    nota.weightLegacy && `Peso ${nota.weightLegacy} kg`,
    nota.heightLegacy && `Talla ${nota.heightLegacy}`,
    nota.bmiLegacy && `IMC ${nota.bmiLegacy}`,
    nota.bloodPressureLegacy && `TA ${nota.bloodPressureLegacy}`,
    nota.pulseLegacy && `Pulso ${nota.pulseLegacy}`,
    nota.respirationLegacy && `Resp. ${nota.respirationLegacy}`,
    nota.temperatureLegacy && `Temp. ${nota.temperatureLegacy} °C`,
    nota.glucoseLegacy && `Glucosa ${nota.glucoseLegacy}`,
  ].filter(Boolean) as string[];

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
      {nota.objective && (
        <p className="text-txt-body">
          <strong>Objetivo:</strong> {nota.objective}
        </p>
      )}
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
      {nota.assessment && (
        <p className="text-txt-muted">
          <strong>Análisis:</strong> {nota.assessment}
        </p>
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
                {medicamento.name}
                {medicamento.quantity ? ` (${medicamento.quantity})` : ""}
                {medicamento.cancelled ? " — cancelado" : ""}
                {detalle && (
                  <span className="block text-txt-muted">
                    {[
                      medicamento.activeIngredient && `Principio activo: ${medicamento.activeIngredient}`,
                      medicamento.instructions && `Indicaciones: ${medicamento.instructions}`,
                      medicamento.dispensedOn
                        ? `Surtido el ${formatFecha(medicamento.dispensedOn)}`
                        : "Sin surtir",
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {nota.addendumLegacy && (
        <p className="text-txt-muted italic">
          <strong>Adenda del legado:</strong> {nota.addendumLegacy}
        </p>
      )}
      {detalle && (nota.subjective || nota.plan || vitales.length > 0) && (
        <div className="space-y-1 border-t border-line-struct pt-2 text-txt-body">
          {nota.subjective && (
            <p>
              <strong>Subjetivo:</strong> {nota.subjective}
            </p>
          )}
          {nota.plan && (
            <p>
              <strong>Plan:</strong> {nota.plan}
            </p>
          )}
          {vitales.length > 0 && (
            <p>
              <strong>Signos vitales:</strong> {vitales.join(" · ")}
            </p>
          )}
        </div>
      )}
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
