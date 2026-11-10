import { useState } from "react";
import { CalendarClock, Loader2, RefreshCcw, Stethoscope } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Label } from "@shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import type { ProximaCitaItem } from "@api/types";
import type { MedicoListItem } from "@api/types/medicos.types";
import { useProximasCitas } from "@features/recepcion/modules/citas/queries/useProximasCitas";
import {
  PROXIMAS_RANGOS,
  groupCitasByDay,
  rangoProximas,
  type ProximasRango,
} from "@features/recepcion/modules/agenda/domain/proximas-citas";
import { ESTATUS_LABEL, ESTATUS_VARIANT } from "../pages/RecepcionAgendaPage.helpers";

const TODOS = "todos";
const PAGE_SIZE = 25;

const formatHora = (iso: string): string =>
  new Date(iso).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", hour12: false });

interface Props {
  allMedicos: MedicoListItem[];
  enabled: boolean;
}

/**
 * Próximas citas: quién viene en los próximos días, incluidas las citas de
 * seguimiento que deja el médico al cerrar la consulta. El día de la cita
 * la ficha aparece sola en la bandeja; solo las del portal hacen check-in.
 */
export function ProximasCitasView({ allMedicos, enabled }: Props) {
  const [rango, setRango] = useState<ProximasRango>("7dias");
  const [medicoId, setMedicoId] = useState<string>(TODOS);
  const [soloSeguimiento, setSoloSeguimiento] = useState(false);
  const [page, setPage] = useState(1);

  const { data, isLoading, isFetching, isError, refetch } = useProximasCitas(
    {
      ...rangoProximas(rango),
      medicoId: medicoId === TODOS ? undefined : Number(medicoId),
      soloSeguimiento,
      page,
      pageSize: PAGE_SIZE,
    },
    { enabled },
  );
  const items = data?.items ?? [];
  const groups = groupCitasByDay(items);
  const totalPages = data?.totalPages ?? 0;

  return (
    <section className="space-y-4 rounded-xl border border-line-struct bg-paper p-4">
      <header className="space-y-1">
        <h2 className="flex items-center gap-2 text-base font-semibold text-txt-body">
          <CalendarClock className="size-4" aria-hidden="true" /> Próximas citas
        </h2>
        <p className="text-xs text-txt-muted">
          Citas agendadas y confirmadas. Las marcadas como <strong>Seguimiento</strong> las
          dejó el médico al cerrar la consulta. El día de la cita la ficha aparece sola en la
          bandeja; solo las citas del portal hacen check-in.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex items-center gap-1 rounded-lg border border-line-struct bg-subtle/20 p-1">
          {PROXIMAS_RANGOS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              aria-pressed={rango === value}
              onClick={() => {
                setRango(value);
                setPage(1);
              }}
              className={[
                "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                rango === value ? "bg-paper text-txt-body shadow-sm" : "text-txt-muted hover:text-txt-body",
              ].join(" ")}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="space-y-1">
          <Label htmlFor="proximas-medico" className="text-xs">Médico</Label>
          <Select
            value={medicoId}
            onValueChange={(value) => {
              setMedicoId(value);
              setPage(1);
            }}
          >
            <SelectTrigger id="proximas-medico" className="h-8 w-56 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TODOS}>Todos los médicos</SelectItem>
              {allMedicos.map((medico) => (
                <SelectItem key={medico.id} value={String(medico.id)}>
                  {medico.nombreCompleto}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <label className="flex h-8 items-center gap-2 text-xs font-medium text-txt-body">
          <input
            type="checkbox"
            checked={soloSeguimiento}
            onChange={(event) => {
              setSoloSeguimiento(event.target.checked);
              setPage(1);
            }}
          />
          Solo seguimientos
        </label>

        <div className="ml-auto flex items-center gap-2 text-xs text-txt-muted">
          {data ? <span>{data.total} {data.total === 1 ? "cita" : "citas"}</span> : null}
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            aria-label="Actualizar"
            disabled={isFetching}
            onClick={() => void refetch()}
          >
            <RefreshCcw className={isFetching ? "size-4 animate-spin" : "size-4"} />
          </Button>
        </div>
      </div>

      {isLoading ? (
        <p className="flex items-center gap-2 text-sm text-txt-muted">
          <Loader2 className="size-4 animate-spin" /> Cargando citas...
        </p>
      ) : isError ? (
        <div className="flex items-center gap-3 text-sm text-status-critical">
          <span>No se pudieron cargar las próximas citas.</span>
          <Button type="button" size="sm" variant="outline" onClick={() => void refetch()}>
            Reintentar
          </Button>
        </div>
      ) : groups.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line-struct p-6 text-center text-sm text-txt-muted">
          No hay citas agendadas en este rango.
        </p>
      ) : (
        <div className="space-y-4">
          {groups.map((group) => (
            <section key={group.fecha} aria-label={group.label} className="space-y-1.5">
              <h3 className="flex items-center justify-between border-b border-line-hairline pb-1 text-xs font-semibold uppercase tracking-wide text-txt-muted">
                <span className="first-letter:uppercase">{group.label}</span>
                <span className="font-normal normal-case">{group.items.length}</span>
              </h3>
              <ul className="divide-y divide-line-hairline">
                {group.items.map((cita) => (
                  <ProximaCitaRow key={cita.id} cita={cita} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      {totalPages > 1 ? (
        <div className="flex items-center justify-end gap-2 text-xs text-txt-muted">
          <Button type="button" size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Anterior
          </Button>
          <span>
            Página {page} de {totalPages}
          </span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Siguiente
          </Button>
        </div>
      ) : null}
    </section>
  );
}

function ProximaCitaRow({ cita }: { cita: ProximaCitaItem }) {
  return (
    <li className="grid grid-cols-[3.5rem_1fr] gap-x-3 gap-y-1 py-2 sm:grid-cols-[3.5rem_minmax(0,1.4fr)_minmax(0,1fr)_auto] sm:items-center">
      <span className="text-sm font-semibold tabular-nums text-txt-body">{formatHora(cita.fechaHora)}</span>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-txt-body">{cita.pacienteNombre || `Exp. ${cita.noExp}`}</p>
        <p className="text-xs text-txt-muted">
          Exp. {cita.noExp}
          {cita.pkNum ? ` · Fam. ${cita.pkNum}` : ""} · {cita.folio}
        </p>
      </div>
      <div className="col-start-2 min-w-0 text-xs text-txt-muted sm:col-start-auto">
        <p className="truncate text-txt-body">{cita.medicoNombre}</p>
        {cita.consultorioNombre ? <p className="truncate">{cita.consultorioNombre}</p> : null}
      </div>
      <div className="col-start-2 flex flex-wrap items-center gap-1.5 sm:col-start-auto sm:justify-end">
        {cita.esSeguimiento ? (
          <Badge variant="info" className="gap-1">
            <Stethoscope className="size-3" aria-hidden="true" />
            Seguimiento
          </Badge>
        ) : null}
        <Badge variant={ESTATUS_VARIANT[cita.estatus]}>{ESTATUS_LABEL[cita.estatus]}</Badge>
        {cita.esSeguimiento && cita.notas ? (
          <span className="w-full text-[11px] text-txt-muted sm:text-right">
            Desde la consulta {cita.notas.replace(/^Consulta\s+/, "")}
          </span>
        ) : null}
      </div>
    </li>
  );
}
