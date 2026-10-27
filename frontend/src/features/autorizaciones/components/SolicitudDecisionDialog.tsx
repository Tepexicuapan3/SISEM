import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import type { DecisionSolicitud, SolicitudDetalle } from "@api/types/autorizaciones/solicitudes.types";
import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { Textarea } from "@shared/ui/textarea";
import { buildDecisionSchema } from "@features/autorizaciones/domain/decision.schema";
import { useDecidirSolicitud } from "@features/autorizaciones/mutations/useSolicitudMutations";
import { useMotivosRechazo } from "@features/autorizaciones/queries/useSolicitudes";
import {
  esErrorDeConcurrencia,
  getSolicitudErrorMessage,
} from "@features/autorizaciones/utils/solicitud.feedback";

interface SolicitudDecisionDialogProps {
  decision: DecisionSolicitud;
  solicitud: SolicitudDetalle;
  onClose: () => void;
}

/**
 * Confirmacion explicita de la decision. Nada se autoriza por abrir un enlace:
 * hace falta este dialogo, la contraseña propia (firma) y que el servidor
 * vuelva a validar estatus, vigencia, tipo, centro y version.
 * La pagina lo monta con una `key` por decision: el estado se reinicia al remontar.
 */
export function SolicitudDecisionDialog({ decision, solicitud, onClose }: SolicitudDecisionDialogProps) {
  const decidir = useDecidirSolicitud();
  const esRechazo = decision === "RECHAZAR";
  const { data: motivosData } = useMotivosRechazo(esRechazo);
  const motivos = motivosData?.items ?? [];

  const [motivoId, setMotivoId] = useState(0);
  const [descripcion, setDescripcion] = useState("");
  const [credencial, setCredencial] = useState("");
  const [errores, setErrores] = useState<Record<string, string>>({});

  const motivoElegido = motivos.find((motivo) => motivo.id === motivoId);
  const accion = esRechazo ? "Rechazar" : "Autorizar";

  const confirmar = async () => {
    const resultado = buildDecisionSchema(motivos).safeParse({
      decision,
      motivoId,
      descripcionMotivo: descripcion,
      credencial,
    });
    if (!resultado.success) {
      setErrores(Object.fromEntries(resultado.error.issues.map((issue) => [String(issue.path[0]), issue.message])));
      return;
    }
    setErrores({});
    try {
      await decidir.mutateAsync({
        uuid: solicitud.uuid,
        data: {
          decision,
          motivoId: esRechazo ? motivoId : null,
          descripcionMotivo: esRechazo ? descripcion.trim() || null : null,
          version: solicitud.version,
          credencial,
        },
      });
      toast.success(esRechazo ? "Solicitud rechazada" : "Decisión registrada", {
        description: `${solicitud.folio} · ${solicitud.tipo.nombre}`,
      });
      onClose();
    } catch (error) {
      setCredencial("");
      toast.error(`No se pudo ${accion.toLowerCase()}`, {
        description: getSolicitudErrorMessage(error, "Intenta nuevamente."),
      });
      if (esErrorDeConcurrencia(error)) onClose();
    }
  };

  return (
    <Dialog open onOpenChange={(abierto) => !abierto && onClose()}>
      <DialogContent className="w-[95vw] max-w-lg rounded-3xl bg-paper">
        <DialogHeader>
          <DialogTitle>{esRechazo ? "Rechazar solicitud" : "Autorizar solicitud"}</DialogTitle>
          <DialogDescription>
            <strong>{solicitud.folio}</strong> · {solicitud.tipo.nombre} · {solicitud.centro.nombre} (
            {solicitud.centro.clues})
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void confirmar();
          }}
        >
          {esRechazo ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="decision-motivo">Motivo del rechazo</Label>
                <Select value={motivoId ? String(motivoId) : ""} onValueChange={(valor) => setMotivoId(Number(valor))}>
                  <SelectTrigger id="decision-motivo" aria-invalid={Boolean(errores.motivoId)}>
                    <SelectValue placeholder="Selecciona un motivo" />
                  </SelectTrigger>
                  <SelectContent>
                    {motivos.map((motivo) => (
                      <SelectItem key={motivo.id} value={String(motivo.id)}>
                        {motivo.descripcion}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errores.motivoId ? <p className="text-xs text-status-critical">{errores.motivoId}</p> : null}
              </div>
              <div className="space-y-2">
                <Label htmlFor="decision-descripcion">
                  Descripción{motivoElegido?.requiereDescripcionLibre ? "" : " (opcional)"}
                </Label>
                <Textarea
                  id="decision-descripcion"
                  value={descripcion}
                  maxLength={500}
                  onChange={(event) => setDescripcion(event.target.value)}
                />
                {errores.descripcionMotivo ? (
                  <p className="text-xs text-status-critical">{errores.descripcionMotivo}</p>
                ) : null}
              </div>
            </>
          ) : (
            <p className="text-sm text-txt-body">
              Vas a autorizar esta solicitud. La decisión queda firmada con tu usuario y cédula, y se
              registra en la bitácora.
            </p>
          )}

          <div className="space-y-2">
            <Label htmlFor="decision-credencial" className="inline-flex items-center gap-2">
              <ShieldCheck className="size-4" />
              Contraseña (firma de la decisión)
            </Label>
            <Input
              id="decision-credencial"
              type="password"
              autoComplete="current-password"
              value={credencial}
              onChange={(event) => setCredencial(event.target.value)}
            />
            {errores.credencial ? <p className="text-xs text-status-critical">{errores.credencial}</p> : null}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" variant={esRechazo ? "destructive" : "default"} disabled={decidir.isPending}>
              {accion}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
