import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, History } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { useHistoricalNotes } from "@features/expedientes/queries/useUnifiedHistory";
import type { HistoricalNote, LegacyVitalSigns } from "@api/types";

const MISSING = "—";

const formatValue = (value: string | number | null, unit?: string) =>
  value === null ? MISSING : [value, unit].filter(Boolean).join(" ");

const formatBloodPressure = (vitals: LegacyVitalSigns) =>
  vitals.bloodPressureSystolic === null || vitals.bloodPressureDiastolic === null
    ? MISSING
    : `${vitals.bloodPressureSystolic}/${vitals.bloodPressureDiastolic} mmHg`;

function LegacyVitalsCard({ vitals }: { vitals: LegacyVitalSigns }) {
  const metrics: [string, string][] = [
    ["Peso", formatValue(vitals.weightKg, "kg")],
    ["Talla", formatValue(vitals.heightCm, "cm")],
    ["IMC", formatValue(vitals.bmi)],
    ["TA", formatBloodPressure(vitals)],
    ["Pulso", formatValue(vitals.heartRateBpm, "lpm")],
    ["Temperatura", formatValue(vitals.temperatureC, "°C")],
    ["Respiración", formatValue(vitals.respiratoryRateBpm, "rpm")],
  ];
  return (
    <li className="rounded-lg border border-line-struct p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-txt-muted">
        <span>{vitals.measuredOn ?? "Fecha desconocida"}</span>
        <Badge variant="outline">Sin consulta</Badge>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
        {metrics.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-txt-muted">{label}</dt>
            <dd className="text-txt-body">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-txt-muted">Texto original: {vitals.rawText}</p>
    </li>
  );
}

interface Props {
  noExp: string;
  pkNum: number;
  specialty?: "general" | "stomatology";
}

/**
 * Notas historicas de SOLO LECTURA: el texto del modelo anterior (partido
 * por anotacion con su fecha y autor) y las versiones previas de la
 * historia. Colapsado por defecto -- es consulta, no captura.
 */
export function HistoricalNotesSection({ noExp, pkNum, specialty }: Props) {
  const [open, setOpen] = useState(false);
  const { data, isLoading, isError } = useHistoricalNotes(noExp, pkNum, specialty);

  const groups = useMemo(() => {
    const bySection = new Map<string, HistoricalNote[]>();
    for (const note of data?.items ?? []) {
      const list = bySection.get(note.sectionLabel) ?? [];
      list.push(note);
      bySection.set(note.sectionLabel, list);
    }
    return [...bySection.entries()];
  }, [data]);

  const legacyVitals = data?.legacyVitals ?? [];
  const total = (data?.items.length ?? 0) + legacyVitals.length;

  return (
    <section className="space-y-3">
      <Button
        type="button" variant="ghost" className="px-0 text-sm font-semibold text-txt-body"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? <ChevronDown className="mr-1 size-4" /> : <ChevronRight className="mr-1 size-4" />}
        <History className="mr-2 size-4" />
        Notas históricas ({isLoading ? "…" : total})
      </Button>

      {open ? (
        <div className="space-y-4">
          <p className="text-xs text-txt-muted">
            Texto del sistema anterior y versiones previas de la historia. Solo lectura.
          </p>
          {isError ? <p className="text-sm text-status-critical">No se pudieron cargar las notas.</p> : null}
          {!isLoading && total === 0 ? <p className="text-sm text-txt-muted">Sin notas históricas.</p> : null}
          {legacyVitals.length > 0 ? (
            <div className="space-y-2">
              <h5 className="text-xs font-semibold uppercase text-txt-muted">
                Signos vitales (última medición del sistema anterior)
              </h5>
              <ul className="space-y-2">
                {legacyVitals.map((vitals) => <LegacyVitalsCard key={vitals.id} vitals={vitals} />)}
              </ul>
            </div>
          ) : null}
          {groups.map(([label, notes]) => (
            <div key={label} className="space-y-2">
              <h5 className="text-xs font-semibold uppercase text-txt-muted">{label}</h5>
              <ul className="space-y-2">
                {notes.map((note) => (
                  <li key={note.id} className="rounded-lg border border-line-struct p-3">
                    <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-txt-muted">
                      <span>{note.notedOn ?? "Sin fecha"}</span>
                      {note.author ? <span>· {note.author}</span> : null}
                      {note.origin === "V" ? <Badge variant="outline">Versión anterior</Badge> : null}
                    </div>
                    <p className="whitespace-pre-wrap text-sm text-txt-body">{note.content}</p>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
