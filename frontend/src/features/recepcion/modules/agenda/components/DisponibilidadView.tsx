import { CalendarDays, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { SlotCalendar } from "@features/recepcion/modules/citas/components/SlotCalendar";
import { addDays } from "@features/recepcion/modules/citas/utils/dates";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { ARRIVAL_TYPE } from "@api/types";
import type { MedicoListItem } from "@api/types/medicos.types";
import type { CheckinFormInput } from "@features/recepcion/modules/checkin/domain/checkin.schemas";
import { DisponibilidadMedicoCard } from "./DisponibilidadMedicoCard";
import { formatWeekRange, getMonday, SIN_USUARIO_HINT } from "../pages/RecepcionAgendaPage.helpers";

interface Props {
  centroOptions:          { id: number; nombre: string }[];
  calCentroId:            number | null;
  setCalCentroId:         (id: number | null) => void;
  calMedicoId:            number | null;
  setCalMedicoId:         (id: number | null) => void;
  calWeekStart:           string;
  setCalWeekStart:        (updater: (current: string) => string) => void;
  medicoSearch:           string;
  setMedicoSearch:        (value: string) => void;
  disponibilidadMedicos:  MedicoListItem[];
  allMedicos:             MedicoListItem[];
  onOpenQuickCheckin:     (defaults?: Partial<CheckinFormInput>) => void;
}

export function DisponibilidadView({
  centroOptions,
  calCentroId,
  setCalCentroId,
  calMedicoId,
  setCalMedicoId,
  calWeekStart,
  setCalWeekStart,
  medicoSearch,
  setMedicoSearch,
  disponibilidadMedicos,
  allMedicos,
  onOpenQuickCheckin,
}: Props) {
  const calMedico = allMedicos.find((m) => m.id === calMedicoId);
  const calMedicoUsuarioId = calMedico?.usuarioId ?? null;

  return (
    <div className="space-y-4 rounded-xl border border-line-struct/60 bg-subtle/10 p-4">

      {/* Controles: centro + navegación semana */}
      <div className="flex flex-wrap items-end gap-3">

        {/* Filtro centro */}
        {centroOptions.length > 1 ? (
          <div className="space-y-1 w-52">
            <p className="text-xs font-medium text-txt-muted">Centro de atención</p>
            <Select
              value={calCentroId !== null ? String(calCentroId) : "all"}
              onValueChange={(v) => {
                setCalCentroId(v === "all" ? null : Number(v));
                setCalMedicoId(null);
              }}
            >
              <SelectTrigger className="h-9 w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los centros</SelectItem>
                {centroOptions.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.nombre}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}

        {/* Navegación de semana */}
        <div className="ml-auto flex items-center gap-1">
          <Button variant="ghost" size="icon" className="size-8" aria-label="Semana anterior"
            disabled={calWeekStart <= getMonday(new Date())}
            onClick={() => setCalWeekStart((s) => addDays(s, -7))}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <span className="px-2 text-sm text-txt-muted whitespace-nowrap">
            {formatWeekRange(calWeekStart)}
          </span>
          <Button variant="ghost" size="icon" className="size-8" aria-label="Semana siguiente"
            onClick={() => setCalWeekStart((s) => addDays(s, 7))}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      {/* Maestro-detalle: listado de médicos + grilla de slots */}
      <div className="grid gap-4 lg:grid-cols-[300px_1fr]">

        {/* Lista de médicos */}
        <div className="space-y-3 rounded-xl border border-line-struct bg-paper p-3 lg:max-h-[640px] lg:overflow-y-auto">
          <div className="space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-txt-muted">
              Médicos {disponibilidadMedicos.length > 0 ? `(${disponibilidadMedicos.length})` : ""}
            </p>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-txt-muted pointer-events-none" />
              <Input
                placeholder="Buscar médico..."
                value={medicoSearch}
                onChange={(e) => setMedicoSearch(e.target.value)}
                className="h-8 pl-8 text-xs"
              />
            </div>
          </div>

          {disponibilidadMedicos.length === 0 ? (
            <p className="py-6 text-center text-xs text-txt-muted">
              Sin médicos para los filtros aplicados.
            </p>
          ) : (
            <div className="space-y-1.5">
              {disponibilidadMedicos.map((m) => (
                <DisponibilidadMedicoCard
                  key={m.id}
                  medico={m}
                  centroFiltroId={calCentroId}
                  selected={calMedicoId === m.id}
                  onSelect={() => setCalMedicoId(m.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Grilla de slots */}
        <div>
          {calMedicoId ? (
            <>
            {calMedicoUsuarioId == null ? (
              <p className="mb-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-700" role="status">
                {SIN_USUARIO_HINT}. Puedes ver su agenda, pero no generar fichas.
              </p>
            ) : null}
            <SlotCalendar
              medicoId={calMedicoId}
              medicoNombre={calMedico?.nombreCompleto}
              weekStart={calWeekStart}
              onSlotClick={(fecha, slot) => {
                // Visit.doctorId vive en el espacio USUARIO; medicoId (No. Médico) solo para la agenda.
                if (calMedicoUsuarioId == null) return;
                onOpenQuickCheckin({
                  doctorId:      calMedicoUsuarioId,
                  consultorioId: slot.consultorioId ?? undefined,
                  horaConsulta:  slot.hora,
                  fechaConsulta: fecha,
                  arrivalType:   ARRIVAL_TYPE.WALK_IN,
                });
              }}
            />
            </>
          ) : (
            <div className="flex flex-col items-center gap-3 py-14 text-center">
              <CalendarDays className="size-12 text-txt-muted/30" />
              <p className="text-sm text-txt-muted">
                Selecciona un médico de la lista para ver su disponibilidad semanal.
              </p>
              <p className="text-xs text-txt-muted/70">
                Los slots en verde están disponibles — hacé clic para generar una ficha.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
