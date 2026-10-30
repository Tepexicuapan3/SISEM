/**
 * Tarjeta de selección de paciente para el check-in.
 *
 * Muestra al trabajador titular o a un derechohabiente con su relación
 * y edad. Solo se renderizan miembros ACTIVOS (el backend ya filtra).
 */
import type { ReactNode } from "react";
import { Badge } from "@shared/ui/badge";
import type { PatientMember } from "@api/types";

// ─── Mapa de parentesco → etiqueta legible ────────────────────────────────────

const PARENTESCO_LABEL: Record<string, string> = {
  TRABAJADOR: "Titular",
  ESPOSA:     "Cónyuge",
  ESPOSO:     "Cónyuge",
  CONYUGE:    "Cónyuge",
  HIJO:       "Hijo(a)",
  HIJA:       "Hijo(a)",
  MADRE:      "Madre",
  PADRE:      "Padre",
  CONCUBINO:  "Concubino(a)",
  CONCUBINA:  "Concubino(a)",
};

function resolveParentesco(raw: string | null | undefined): string {
  if (!raw) return "Familiar";
  const upper = raw.toUpperCase();
  return PARENTESCO_LABEL[upper] ?? raw;
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface PatientMemberCardProps {
  member:    PatientMember;
  selected:  boolean;
  onSelect:  () => void;
  /** Contenido extra junto a la etiqueta Titular/Familiar. */
  aside?:    ReactNode;
}

// ─── Componente ───────────────────────────────────────────────────────────────

export function PatientMemberCard({ member, selected, onSelect, aside }: PatientMemberCardProps) {
  const esTitular    = member.pkNum === 0;
  const parentesco   = resolveParentesco(member.parentesco);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        "flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors",
        selected
          ? "border-primary bg-primary/5"
          : "border-line-struct hover:bg-subtle/40",
      ].join(" ")}
    >
      {/* Indicador radio */}
      <div
        className={[
          "flex size-4 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
          selected ? "border-primary bg-primary" : "border-line-struct",
        ].join(" ")}
      >
        {selected ? <span className="size-1.5 rounded-full bg-white" /> : null}
      </div>

      {/* Nombre y parentesco */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-txt-body">
          {member.nombre}
        </p>
        <p className="truncate text-xs text-txt-muted">
          {parentesco}
          {member.edad != null ? ` · ${member.edad} años` : ""}
        </p>
        {member.madre ? (
          <p className="truncate text-xs text-txt-muted">Madre: {member.madre}</p>
        ) : null}
      </div>

      {/* Contenido extra opcional (p. ej. consultorio familiar, P-03) */}
      {aside}

      {/* Badge: Titular o Familiar */}
      <Badge
        variant={esTitular ? "stable" : "outline"}
        className="shrink-0 text-xs"
      >
        {esTitular ? "Titular" : "Familiar"}
      </Badge>
    </button>
  );
}
