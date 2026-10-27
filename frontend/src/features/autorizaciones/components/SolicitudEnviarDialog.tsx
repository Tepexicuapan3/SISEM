import { useState } from "react";
import { toast } from "sonner";
import type { SolicitudDetalle } from "@api/types/autorizaciones/solicitudes.types";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Checkbox } from "@shared/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import { Label } from "@shared/ui/label";
import { Skeleton } from "@shared/ui/skeleton";
import { useNotificarSolicitud } from "@features/autorizaciones/mutations/useSolicitudMutations";
import { useElegibles } from "@features/autorizaciones/queries/useSolicitudes";
import { getSolicitudErrorMessage } from "@features/autorizaciones/utils/solicitud.feedback";

const ALCANCE: Record<string, string> = {
  CENTRO: "Asignado al centro",
  TIPO_CENTRO: "Por tipo de centro",
  GLOBAL: "Todos los centros",
};

interface SolicitudEnviarDialogProps {
  solicitud: SolicitudDetalle;
  onClose: () => void;
}

/** Envio manual: solo aparecen quienes HOY pueden autorizar este tipo en este centro. */
export function SolicitudEnviarDialog({ solicitud, onClose }: SolicitudEnviarDialogProps) {
  const { data, isLoading } = useElegibles(solicitud.uuid, true);
  const notificar = useNotificarSolicitud();
  const [elegidos, setElegidos] = useState<number[]>([]);
  const elegibles = data?.items ?? [];

  const enviar = async (todos: boolean) => {
    try {
      const respuesta = await notificar.mutateAsync({
        uuid: solicitud.uuid,
        data: todos ? { todosElegibles: true } : { autorizadorIds: elegidos },
      });
      toast.success("Solicitud enviada", {
        description: `Se notificó a ${respuesta.notificados} autorizador(es).`,
      });
      onClose();
    } catch (error) {
      toast.error("No se pudo enviar", { description: getSolicitudErrorMessage(error, "Intenta nuevamente.") });
    }
  };

  return (
    <Dialog open onOpenChange={(abierto) => !abierto && onClose()}>
      <DialogContent className="w-[95vw] max-w-lg rounded-3xl bg-paper">
        <DialogHeader>
          <DialogTitle>Enviar a autorizadores</DialogTitle>
          <DialogDescription>
            {solicitud.folio} · {solicitud.tipo.nombre} · {solicitud.centro.nombre}
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-80 space-y-2 overflow-y-auto">
          {isLoading ? (
            Array.from({ length: 3 }).map((_, indice) => <Skeleton key={`eleg-${indice}`} className="h-12" />)
          ) : elegibles.length === 0 ? (
            <p className="py-6 text-center text-sm text-txt-muted">
              No hay autorizadores vigentes para este tipo y centro.
            </p>
          ) : (
            elegibles.map((elegible) => {
              const id = `enviar-${elegible.idAutorizador}`;
              return (
                <div key={elegible.idAutorizador} className="flex items-center gap-3 rounded-xl border border-line-struct px-3 py-2">
                  <Checkbox
                    id={id}
                    checked={elegidos.includes(elegible.idAutorizador)}
                    onCheckedChange={(checked) =>
                      setElegidos((actual) =>
                        checked === true
                          ? [...actual, elegible.idAutorizador]
                          : actual.filter((valor) => valor !== elegible.idAutorizador),
                      )
                    }
                  />
                  <Label htmlFor={id} className="flex min-w-0 flex-1 flex-col font-normal">
                    <span className="font-medium">{elegible.nombre}</span>
                    <span className="text-xs text-txt-muted">{ALCANCE[elegible.alcanceAplicado] ?? elegible.alcanceAplicado}</span>
                  </Label>
                  {elegible.yaNotificado ? <Badge variant="outline">Ya notificado</Badge> : null}
                </div>
              );
            })
          )}
        </div>

        <DialogFooter className="flex flex-col gap-2 sm:flex-row sm:justify-between">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              type="button"
              variant="outline"
              disabled={notificar.isPending || elegibles.length === 0}
              onClick={() => void enviar(true)}
            >
              Enviar a todos
            </Button>
            <Button
              type="button"
              disabled={notificar.isPending || elegidos.length === 0}
              onClick={() => void enviar(false)}
            >
              Enviar a seleccionados ({elegidos.length})
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
