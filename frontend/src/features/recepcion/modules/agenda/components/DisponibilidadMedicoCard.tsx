import { Building2, DoorOpen } from "lucide-react";
import { cn } from "@shared/utils/styling/cn";

interface DisponibilidadMedicoCardMedico {
  id: number;
  nombreCompleto: string;
  servicio: string | null;
  especialidades: { name: string }[];
  centros: { centroId: number; centroNombre: string }[];
  consultoriosActivos: { centroId: number; centroNombre: string; consultorioNumero: number; consultorioNombre: string }[];
}

// Iniciales para el avatar: primera letra de las dos primeras palabras del nombre.
function iniciales(nombre: string): string {
  return nombre
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p.charAt(0).toUpperCase())
    .join("");
}

export function DisponibilidadMedicoCard({
  medico,
  centroFiltroId,
  selected,
  onSelect,
}: {
  medico:         DisponibilidadMedicoCardMedico;
  centroFiltroId: number | null;
  selected:       boolean;
  onSelect:       () => void;
}) {
  const especialidad = medico.especialidades[0]?.name ?? medico.servicio;

  // Si hay centro filtrado, mostrar solo lo relativo a ese centro; si no, todos.
  const centros = centroFiltroId
    ? medico.centros.filter((c) => c.centroId === centroFiltroId)
    : medico.centros;
  const consultorios = centroFiltroId
    ? medico.consultoriosActivos.filter((c) => c.centroId === centroFiltroId)
    : medico.consultoriosActivos;

  const centroLabel = centros.map((c) => c.centroNombre).join(", ");

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "w-full rounded-xl border p-3 text-left transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40",
        selected
          ? "border-brand bg-brand/5 shadow-md shadow-brand/15 ring-1 ring-brand/30"
          : "border-line-struct bg-paper hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-sm",
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-bold",
            selected
              ? "bg-gradient-to-br from-brand to-brand-hover text-txt-inverse shadow-sm"
              : "bg-brand/10 text-brand",
          )}
        >
          {iniciales(medico.nombreCompleto)}
        </div>
        <div className="min-w-0 flex-1">
          <p className={cn(
            "truncate text-[15px] font-bold leading-tight",
            selected ? "text-brand" : "text-txt-body",
          )}>
            {medico.nombreCompleto}
          </p>
          {especialidad ? (
            <p className="mt-0.5 truncate text-xs font-medium text-txt-muted">{especialidad}</p>
          ) : null}
          {centroLabel ? (
            <p className="mt-0.5 flex items-center gap-1 truncate text-[11px] text-txt-hint">
              <Building2 className="size-3 shrink-0" />
              <span className="truncate">{centroLabel}</span>
            </p>
          ) : null}
        </div>
      </div>

      {consultorios.length > 0 ? (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {consultorios.map((c) => (
            <span
              key={`${c.centroId}-${c.consultorioNumero}`}
              title={`${c.consultorioNombre} · ${c.centroNombre}`}
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-bold",
                selected
                  ? "border-brand/40 bg-paper text-brand"
                  : "border-line-struct bg-subtle/40 text-txt-body",
              )}
            >
              <DoorOpen className="size-3.5" />
              C{c.consultorioNumero}
            </span>
          ))}
        </div>
      ) : null}
    </button>
  );
}
