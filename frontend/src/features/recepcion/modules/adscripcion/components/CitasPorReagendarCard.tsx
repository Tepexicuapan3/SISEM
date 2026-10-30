import { useState } from "react";
import { toast } from "sonner";
import { CalendarClock } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";
import { Label } from "@shared/ui/label";
import { Textarea } from "@shared/ui/textarea";
import { ApiError } from "@api/utils/errors";
import type { CitaAfectada } from "@api/types";
import { useCitasPorReagendar } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries";
import { useDescartarCitaAfectada } from "@features/recepcion/modules/adscripcion/mutations/useAdscripcionMutations";
import { ReagendarCitaDialog } from "@features/recepcion/modules/adscripcion/components/ReagendarCitaDialog";

const formatoFecha = (iso: string) =>
  new Date(iso).toLocaleString("es-MX", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

interface CitasPorReagendarCardProps {
  /** Permiso de escritura de P-03 (UX; el backend vuelve a validar). */
  puedeEscribir: boolean;
}

/**
 * P-03 · Citas canceladas por un cambio de consultorio familiar, pendientes
 * de reagendar, del centro de quien opera. Sin pendientes no se muestra.
 */
export const CitasPorReagendarCard = ({ puedeEscribir }: CitasPorReagendarCardProps) => {
  const { data } = useCitasPorReagendar();
  const descartar = useDescartarCitaAfectada();
  const [reagendando, setReagendando] = useState<CitaAfectada | null>(null);
  const [descartando, setDescartando] = useState<number | null>(null);
  const [motivo, setMotivo] = useState("");

  const items = data?.items ?? [];
  if (items.length === 0) return null;

  const confirmarDescarte = async (idCitaAfectada: number) => {
    try {
      await descartar.mutateAsync({ idCitaAfectada, motivo: motivo.trim() });
      toast.success("Cita descartada");
      setDescartando(null);
      setMotivo("");
    } catch (error) {
      toast.error("No se pudo descartar", {
        description: error instanceof ApiError ? error.message : "Intente nuevamente.",
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarClock className="size-4" />
          Citas por reagendar ({items.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-line-hairline">
          {items.map((item) => (
            <li key={item.idCitaAfectada} className="space-y-2 py-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0 text-sm">
                  <p className="font-medium text-txt-body">
                    {formatoFecha(item.citaCancelada.fechaHora)} · <span className="font-mono">{item.citaCancelada.folio}</span>
                  </p>
                  <p className="text-xs text-txt-muted">
                    Era en {item.citaCancelada.consultorio ?? "sin consultorio"} → reagendar en {item.consultorioNuevo}
                  </p>
                </div>
                {puedeEscribir ? (
                  <div className="flex gap-2">
                    <Button type="button" size="sm" onClick={() => setReagendando(item)}>
                      Reagendar
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setDescartando(item.idCitaAfectada);
                        setMotivo("");
                      }}
                    >
                      Descartar
                    </Button>
                  </div>
                ) : null}
              </div>
              {descartando === item.idCitaAfectada ? (
                <div className="space-y-1.5">
                  <Label htmlFor={`descarte-${item.idCitaAfectada}`} className="text-xs">
                    Motivo del descarte
                  </Label>
                  <Textarea
                    id={`descarte-${item.idCitaAfectada}`}
                    rows={2}
                    maxLength={255}
                    value={motivo}
                    onChange={(e) => setMotivo(e.target.value)}
                    placeholder="Ej. el paciente ya no la necesita"
                  />
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={descartar.isPending || motivo.trim().length === 0}
                      onClick={() => void confirmarDescarte(item.idCitaAfectada)}
                    >
                      Confirmar descarte
                    </Button>
                    <Button type="button" size="sm" variant="ghost" onClick={() => setDescartando(null)}>
                      Cancelar
                    </Button>
                  </div>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      </CardContent>
      {reagendando ? (
        <ReagendarCitaDialog
          key={reagendando.idCitaAfectada}
          afectada={reagendando}
          onOpenChange={(open) => {
            if (!open) setReagendando(null);
          }}
        />
      ) : null}
    </Card>
  );
};
