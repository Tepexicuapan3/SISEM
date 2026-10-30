import { Stethoscope } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import type { AdscripcionResumen } from "@api/types";
import { presentarEstadoAdscripcion } from "@features/recepcion/modules/adscripcion/domain/adscripcionEstado";

const TONO_AVISO = {
  stable: "border-status-info/40 bg-status-info/10 text-status-info",
  info: "border-status-info/40 bg-status-info/10 text-status-info",
  alert: "border-status-alert/40 bg-status-alert/10 text-status-alert",
  critical: "border-status-critical/40 bg-status-critical/10 text-status-critical",
} as const;

/** P-03 · Etiqueta del consultorio familiar en la lista de la familia. */
export const AdscripcionBadge = ({ resumen }: { resumen: AdscripcionResumen | null | undefined }) => {
  const presentacion = presentarEstadoAdscripcion(resumen);
  if (!presentacion) return null;
  return (
    <Badge variant={presentacion.variante} className="gap-1 text-xs">
      <Stethoscope className="size-3" />
      {presentacion.etiqueta}
    </Badge>
  );
};

interface AdscripcionAvisoProps {
  resumen: AdscripcionResumen | null | undefined;
  /** Permiso para adscribir/reasignar (UX; el backend vuelve a validar). */
  puedeAsignar: boolean;
  onAccion: () => void;
}

/** P-03 · Aviso al elegir a la persona, con la acción que corresponde. */
export const AdscripcionAviso = ({ resumen, puedeAsignar, onAccion }: AdscripcionAvisoProps) => {
  const presentacion = presentarEstadoAdscripcion(resumen);
  if (!presentacion?.aviso) return null;
  return (
    <div
      role="alert"
      className={["space-y-2 rounded-xl border px-3 py-2.5 text-sm", TONO_AVISO[presentacion.variante]].join(" ")}
    >
      <p>{presentacion.aviso}</p>
      {presentacion.accion && puedeAsignar ? (
        <Button type="button" size="sm" onClick={onAccion}>
          {presentacion.accion === "asignar" ? "Asignar consultorio" : "Revisar y reasignar"}
        </Button>
      ) : null}
    </div>
  );
};
