import { useState } from "react";
import { Activity } from "lucide-react";
import { toast } from "sonner";
import type {
  ChronicAdherence,
  ChronicControlParameter,
  ChronicControlProgramPanel,
  ChronicControlStatus,
} from "@api/types/padrones.types";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import {
  useChronicControlPanel,
  useRegisterChronicControl,
} from "@features/padrones/queries/usePadrones";
import { getPadronesErrorMessage } from "@features/padrones/utils/padrones.feedback";
import { formatPadronDate } from "@features/padrones/utils/padrones.format";

const STATUS_LABEL: Record<ChronicControlStatus, string> = {
  sin_datos: "Sin datos",
  descontrolado: "Descontrolado",
  incompleto: "Incompleto",
  controlado: "Controlado",
};

const STATUS_VARIANT: Record<ChronicControlStatus, "critical" | "alert" | "stable" | "outline"> = {
  sin_datos: "outline",
  descontrolado: "critical",
  incompleto: "alert",
  controlado: "stable",
};

const ADHERENCE_OPTIONS: { value: ChronicAdherence; label: string }[] = [
  { value: "buena", label: "Buena" },
  { value: "regular", label: "Regular" },
  { value: "mala", label: "Mala" },
];

const formatGoal = ({ goalMin, goalMax }: ChronicControlParameter) => {
  if (goalMin !== null && goalMax !== null) return `${goalMin}–${goalMax}`;
  if (goalMax !== null) return `≤ ${goalMax}`;
  if (goalMin !== null) return `≥ ${goalMin}`;
  return "—";
};

function GoalLight({ row }: { row: ChronicControlParameter }) {
  const hasGoal = row.goalMin !== null || row.goalMax !== null;
  const [label, dot] = !hasGoal
    ? ["Sin meta", "bg-line-struct"]
    : row.inGoal === null
      ? ["Sin dato", "bg-line-struct"]
      : row.inGoal
        ? ["En meta", "bg-status-stable"]
        : ["Fuera de meta", "bg-status-critical"];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-txt-muted">
      <span aria-hidden="true" className={`size-2 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

interface CardProps {
  visitId: number;
  entry: ChronicControlProgramPanel;
  canRegister: boolean;
}

function ProgramControlCard({ visitId, entry, canRegister }: CardProps) {
  const register = useRegisterChronicControl(visitId);
  const [manualValues, setManualValues] = useState<Record<string, string>>({});
  const [adherence, setAdherence] = useState<ChronicAdherence | "">("");
  const [notes, setNotes] = useState("");

  const { program, registered, last } = entry;
  const editable = canRegister && !registered;
  const rows = registered ? registered.measurements : entry.parameters;
  const status = registered ? registered.status : entry.status;

  const handleRegister = async () => {
    const values = Object.fromEntries(
      Object.entries(manualValues).filter(([, value]) => value.trim() !== ""),
    );
    try {
      const result = await register.mutateAsync({
        programCode: program.code,
        values,
        adherence: adherence || null,
        notes: notes.trim() || null,
      });
      toast.success("Control registrado", {
        description: `Próximo control: ${formatPadronDate(result.nextControlOn)}.`,
      });
    } catch (error) {
      toast.error("No se pudo registrar el control", {
        description: getPadronesErrorMessage(error, "Intenta nuevamente."),
      });
    }
  };

  return (
    <section className="space-y-3 rounded-lg border border-line-hairline bg-paper p-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-txt-body">
          <Activity className="size-4 text-brand" aria-hidden="true" />
          Control de {program.name}
        </p>
        <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABEL[status]}</Badge>
      </header>

      {last ? (
        <p className="flex flex-wrap items-center gap-2 text-xs text-txt-muted">
          Último control: {formatPadronDate(last.controlOn)} · {STATUS_LABEL[last.status]}
          {last.overdue ? <Badge variant="alert">Control vencido</Badge> : null}
        </p>
      ) : null}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-txt-muted">
            <th className="py-1 font-medium">Parámetro</th>
            <th className="py-1 font-medium">Valor</th>
            <th className="py-1 font-medium">Meta</th>
            <th className="py-1 font-medium">Semáforo</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.parameter} className="border-t border-line-hairline">
              <td className="py-1.5 text-txt-body">{row.label}</td>
              <td className="py-1.5">
                {editable && row.source === "manual" ? (
                  <Input
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    aria-label={`${row.label} (${row.unit})`}
                    className="h-8 w-28"
                    value={manualValues[row.parameter] ?? ""}
                    onChange={(event) =>
                      setManualValues((current) => ({ ...current, [row.parameter]: event.target.value }))
                    }
                  />
                ) : row.value !== null ? (
                  <span className="font-mono">{`${row.value} ${row.unit}`}</span>
                ) : (
                  <span className="text-txt-muted">—</span>
                )}
              </td>
              <td className="py-1.5 font-mono text-xs text-txt-muted">{formatGoal(row)}</td>
              <td className="py-1.5">
                <GoalLight row={row} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {registered ? (
        <p className="text-xs text-txt-muted">
          Registrado{registered.registeredBy ? ` por ${registered.registeredBy}` : ""} · próximo control{" "}
          {formatPadronDate(registered.nextControlOn)}
        </p>
      ) : (
        <p className="text-xs text-txt-muted">
          Próximo control sugerido: {formatPadronDate(entry.suggestedNextControlOn)} (cada {entry.everyDays} días)
        </p>
      )}

      {editable ? (
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-txt-muted">
            Adherencia al tratamiento
            <select
              value={adherence}
              onChange={(event) => setAdherence(event.target.value as ChronicAdherence | "")}
              className="h-8 rounded-md border border-line-struct bg-paper px-2 text-sm font-normal text-txt-body"
            >
              <option value="">Sin registrar</option>
              {ADHERENCE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs font-medium text-txt-muted">
            Observaciones del control
            <Input
              className="h-8"
              maxLength={500}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </label>
          <Button type="button" size="sm" onClick={() => void handleRegister()} disabled={register.isPending}>
            Registrar control
          </Button>
        </div>
      ) : null}
    </section>
  );
}

/**
 * Control de cronicos en la consulta: valores de hoy contra la meta de cada
 * programa en que esta inscrito el paciente. El semaforo lo calcula el
 * backend. Ver docs/plans/cronicos-control.md.
 */
export function ChronicControlPanel({ visitId }: { visitId: number }) {
  const panelQuery = useChronicControlPanel(visitId);
  const panel = panelQuery.data;
  if (panelQuery.isError || !panel || panel.programs.length === 0) {
    return null;
  }
  return (
    <div className="space-y-2" data-testid="chronic-control-panel">
      {panel.programs.map((entry) => (
        <ProgramControlCard
          key={entry.program.code}
          visitId={visitId}
          entry={entry}
          canRegister={panel.canRegister}
        />
      ))}
    </div>
  );
}
