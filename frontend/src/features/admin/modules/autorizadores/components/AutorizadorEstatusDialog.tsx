import { useState } from "react";
import { toast } from "sonner";
import type { AutorizadorItem, MotivoCatalogo } from "@api/types/autorizaciones/autorizadores.types";
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
import {
  buildCambioEstatusSchema,
  buildRenovacionSchema,
} from "@features/admin/modules/autorizadores/domain/autorizador.estatus";
import {
  useCambiarEstatusAutorizador,
  useRenovarAutorizador,
} from "@features/admin/modules/autorizadores/mutations/useAutorizadorMutations";
import { getAutorizadorErrorMessage } from "@features/admin/modules/autorizadores/utils/autorizador.feedback";
import { formatFecha } from "@features/admin/modules/autorizadores/utils/autorizador.format";

export type AccionAutorizador = "suspender" | "reactivar" | "baja" | "renovar";

interface AutorizadorEstatusDialogProps {
  accion: AccionAutorizador | null;
  autorizador: AutorizadorItem | null;
  motivos: MotivoCatalogo[];
  onClose: () => void;
}

const TEXTOS: Record<AccionAutorizador, { titulo: string; descripcion: string; boton: string; exito: string }> = {
  suspender: {
    titulo: "Suspender autorizador",
    descripcion:
      "Mientras esté suspendido no podrá autorizar ni recibir solicitudes. Se conserva su configuración.",
    boton: "Suspender",
    exito: "Autorizador suspendido",
  },
  reactivar: {
    titulo: "Reactivar autorizador",
    descripcion: "Volverá a poder autorizar dentro de su vigencia, tipos y centros asignados.",
    boton: "Reactivar",
    exito: "Autorizador reactivado",
  },
  baja: {
    titulo: "Dar de baja autorizador",
    descripcion:
      "La baja es definitiva: no podrá volver a autorizar con este registro. El historial se conserva.",
    boton: "Dar de baja",
    exito: "Autorizador dado de baja",
  },
  renovar: {
    titulo: "Renovar vigencia",
    descripcion: "Amplía la fecha de fin de vigencia. El periodo anterior queda en el historial.",
    boton: "Renovar",
    exito: "Vigencia renovada",
  },
};

export function AutorizadorEstatusDialog({ accion, autorizador, motivos, onClose }: AutorizadorEstatusDialogProps) {
  const cambiarEstatus = useCambiarEstatusAutorizador();
  const renovar = useRenovarAutorizador();

  const [motivoId, setMotivoId] = useState(0);
  const [descripcion, setDescripcion] = useState("");
  const [fechaFinSuspension, setFechaFinSuspension] = useState("");
  const [nuevaFin, setNuevaFin] = useState("");
  const [errores, setErrores] = useState<Record<string, string>>({});

  // El estado se reinicia remontando el dialogo: la pagina le da una `key` por accion.
  if (!accion || !autorizador) return null;

  const textos = TEXTOS[accion];
  const ambito = accion === "baja" ? "BAJA" : "SUSPENSION";
  const motivosAplicables = motivos.filter((motivo) => motivo.ambito === ambito);
  const pideMotivo = accion === "suspender" || accion === "baja";
  const motivoElegido = motivosAplicables.find((motivo) => motivo.id === motivoId);
  const enviando = cambiarEstatus.isPending || renovar.isPending;

  const validar = (): boolean => {
    const resultado = pideMotivo
      ? buildCambioEstatusSchema(motivosAplicables).safeParse({
          motivoId,
          descripcionMotivo: descripcion,
          fechaFinSuspension,
        })
      : accion === "renovar"
        ? buildRenovacionSchema(autorizador.fechaFinVigencia).safeParse({ fechaFinVigencia: nuevaFin })
        : { success: true as const };
    if (resultado.success) {
      setErrores({});
      return true;
    }
    setErrores(
      Object.fromEntries(resultado.error.issues.map((issue) => [String(issue.path[0]), issue.message])),
    );
    return false;
  };

  const confirmar = async () => {
    if (!validar()) return;
    try {
      if (accion === "renovar") {
        await renovar.mutateAsync({
          id: autorizador.id,
          data: { fechaFinVigencia: nuevaFin, version: autorizador.version },
        });
      } else {
        await cambiarEstatus.mutateAsync({
          id: autorizador.id,
          accion,
          data: pideMotivo
            ? {
                motivoId,
                descripcionMotivo: descripcion.trim() || null,
                fechaFinSuspension: accion === "suspender" ? fechaFinSuspension || null : null,
                version: autorizador.version,
              }
            : { version: autorizador.version },
        });
      }
      toast.success(textos.exito, { description: autorizador.usuario.nombreCompleto });
      onClose();
    } catch (error) {
      toast.error(`No se pudo ${textos.boton.toLowerCase()}`, {
        description: getAutorizadorErrorMessage(error, "Intenta nuevamente."),
      });
    }
  };

  return (
    <Dialog open onOpenChange={(abierto) => !abierto && onClose()}>
      <DialogContent className="max-w-lg rounded-3xl bg-paper">
        <DialogHeader>
          <DialogTitle>{textos.titulo}</DialogTitle>
          <DialogDescription>
            <strong>{autorizador.usuario.nombreCompleto}</strong>. {textos.descripcion}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {pideMotivo ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="aut-motivo">Motivo</Label>
                <Select
                  value={motivoId ? String(motivoId) : ""}
                  onValueChange={(valor) => setMotivoId(Number(valor))}
                >
                  <SelectTrigger id="aut-motivo" aria-invalid={Boolean(errores.motivoId)}>
                    <SelectValue placeholder="Selecciona un motivo" />
                  </SelectTrigger>
                  <SelectContent>
                    {motivosAplicables.map((motivo) => (
                      <SelectItem key={motivo.id} value={String(motivo.id)}>
                        {motivo.descripcion}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errores.motivoId ? <p className="text-xs text-status-critical">{errores.motivoId}</p> : null}
              </div>

              <div className="space-y-2">
                <Label htmlFor="aut-descripcion">
                  Descripción{motivoElegido?.requiereDescripcionLibre ? "" : " (opcional)"}
                </Label>
                <Textarea
                  id="aut-descripcion"
                  value={descripcion}
                  maxLength={255}
                  onChange={(event) => setDescripcion(event.target.value)}
                />
                {errores.descripcionMotivo ? (
                  <p className="text-xs text-status-critical">{errores.descripcionMotivo}</p>
                ) : null}
              </div>

              {accion === "suspender" ? (
                <div className="space-y-2">
                  <Label htmlFor="aut-fin-suspension">Fin de la suspensión (opcional)</Label>
                  <Input
                    id="aut-fin-suspension"
                    type="date"
                    value={fechaFinSuspension}
                    onChange={(event) => setFechaFinSuspension(event.target.value)}
                  />
                  <p className="text-xs text-txt-muted">
                    Es informativa: la reactivación siempre se hace manualmente.
                  </p>
                </div>
              ) : null}
            </>
          ) : null}

          {accion === "renovar" ? (
            <div className="space-y-2">
              <p className="text-sm text-txt-muted">
                Vigencia actual: {formatFecha(autorizador.fechaInicioVigencia)} –{" "}
                {formatFecha(autorizador.fechaFinVigencia)}
              </p>
              <Label htmlFor="aut-nueva-fin">Nueva fecha de fin</Label>
              <Input
                id="aut-nueva-fin"
                type="date"
                min={autorizador.fechaFinVigencia}
                value={nuevaFin}
                onChange={(event) => setNuevaFin(event.target.value)}
              />
              {errores.fechaFinVigencia ? (
                <p className="text-xs text-status-critical">{errores.fechaFinVigencia}</p>
              ) : null}
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            type="button"
            variant={accion === "baja" || accion === "suspender" ? "destructive" : "default"}
            disabled={enviando}
            onClick={() => void confirmar()}
          >
            {textos.boton}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
