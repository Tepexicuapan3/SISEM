import { useState } from "react";
import { toast } from "sonner";
import type { AmbitoMotivo, MotivoConfiguracion } from "@api/types/autorizaciones/configuracion.types";
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
import { Switch } from "@shared/ui/switch";
import { ETIQUETA_AMBITO } from "@features/admin/modules/autorizaciones-config/domain/configuracion.format";
import {
  AMBITOS,
  erroresPorCampo,
  motivoSchema,
  type MotivoFormValues,
} from "@features/admin/modules/autorizaciones-config/domain/configuracion.schemas";
import {
  useCreateMotivo,
  useUpdateMotivo,
} from "@features/admin/modules/autorizaciones-config/mutations/useConfiguracionMutations";
import { getConfiguracionErrorMessage } from "@features/admin/modules/autorizaciones-config/utils/configuracion.feedback";

interface MotivoDialogProps {
  /** null = alta. */
  motivo: MotivoConfiguracion | null;
  ambitoInicial: AmbitoMotivo;
  onClose: () => void;
}

/** El estado se reinicia remontando el dialogo: la pestaña le da una `key` por motivo. */
export function MotivoDialog({ motivo, ambitoInicial, onClose }: MotivoDialogProps) {
  const crear = useCreateMotivo();
  const actualizar = useUpdateMotivo();
  const [valores, setValores] = useState<MotivoFormValues>({
    ambito: motivo?.ambito ?? ambitoInicial,
    clave: motivo?.clave ?? "",
    descripcion: motivo?.descripcion ?? "",
    requiereDescripcionLibre: motivo?.requiereDescripcionLibre ?? false,
  });
  const [errores, setErrores] = useState<Record<string, string>>({});
  const enviando = crear.isPending || actualizar.isPending;

  const guardar = async () => {
    const resultado = motivoSchema.safeParse(valores);
    if (!resultado.success) {
      setErrores(erroresPorCampo(resultado.error.issues));
      return;
    }
    setErrores({});
    try {
      if (motivo) {
        await actualizar.mutateAsync({
          id: motivo.id,
          data: {
            version: motivo.version,
            descripcion: resultado.data.descripcion,
            requiereDescripcionLibre: resultado.data.requiereDescripcionLibre,
          },
        });
      } else {
        await crear.mutateAsync(resultado.data);
      }
      toast.success(motivo ? "Motivo actualizado" : "Motivo creado", { description: resultado.data.descripcion });
      onClose();
    } catch (error) {
      toast.error("No se pudo guardar el motivo", {
        description: getConfiguracionErrorMessage(error, "Intenta nuevamente."),
      });
    }
  };

  return (
    <Dialog open onOpenChange={(abierto) => !abierto && onClose()}>
      <DialogContent className="max-w-lg rounded-3xl bg-paper">
        <DialogHeader>
          <DialogTitle>{motivo ? "Editar motivo" : "Nuevo motivo"}</DialogTitle>
          <DialogDescription>
            {motivo
              ? "La clave no cambia: las decisiones y movimientos ya registrados la usan."
              : "Aparecerá como opción al rechazar, suspender, dar de baja o cancelar, según su ámbito."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="motivo-ambito">Ámbito</Label>
            <Select
              value={valores.ambito}
              onValueChange={(valor) => setValores((actual) => ({ ...actual, ambito: valor as AmbitoMotivo }))}
              disabled={Boolean(motivo)}
            >
              <SelectTrigger id="motivo-ambito">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AMBITOS.map((ambito) => (
                  <SelectItem key={ambito} value={ambito}>
                    {ETIQUETA_AMBITO[ambito]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="motivo-clave">Clave</Label>
            <Input
              id="motivo-clave"
              value={valores.clave}
              disabled={Boolean(motivo)}
              placeholder="DOSIS_EXCESIVA"
              aria-invalid={Boolean(errores.clave)}
              onChange={(event) => setValores((actual) => ({ ...actual, clave: event.target.value }))}
            />
            {errores.clave ? <p className="text-xs text-status-critical">{errores.clave}</p> : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="motivo-descripcion">Descripción</Label>
            <Input
              id="motivo-descripcion"
              value={valores.descripcion}
              maxLength={150}
              aria-invalid={Boolean(errores.descripcion)}
              onChange={(event) => setValores((actual) => ({ ...actual, descripcion: event.target.value }))}
            />
            {errores.descripcion ? <p className="text-xs text-status-critical">{errores.descripcion}</p> : null}
          </div>

          <div className="flex items-start justify-between gap-4 rounded-xl border border-line-struct px-3 py-2">
            <div>
              <Label htmlFor="motivo-libre">Pide explicación en texto</Label>
              <p className="text-xs text-txt-muted">Para motivos como «Otro»: obliga a escribir el detalle.</p>
            </div>
            <Switch
              id="motivo-libre"
              checked={valores.requiereDescripcionLibre}
              onCheckedChange={(valor) => setValores((actual) => ({ ...actual, requiereDescripcionLibre: valor }))}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={enviando}>
            Cancelar
          </Button>
          <Button onClick={() => void guardar()} disabled={enviando}>
            {enviando ? "Guardando…" : "Guardar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
