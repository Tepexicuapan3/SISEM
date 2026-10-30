import { useState } from "react";
import { Button } from "@shared/ui/button";
import { Label } from "@shared/ui/label";
import { Textarea } from "@shared/ui/textarea";
import type { ConflictoConsultorioFamiliar } from "@features/recepcion/modules/adscripcion/domain/adscripcionEstado";

interface ConflictoConsultorioAvisoProps {
  conflicto: ConflictoConsultorioFamiliar;
  puedeReasignar: boolean;
  puedeExcepcion: boolean;
  enviando: boolean;
  onReasignar: () => void;
  onExcepcion: (motivo: string) => void;
}

/**
 * P-03 · Respuesta al 409 CONSULTORIO_FAMILIAR_DIFERENTE: recepción elige
 * reasignar al paciente o atenderlo hoy con excepción (permiso + motivo).
 */
export const ConflictoConsultorioAviso = ({
  conflicto,
  puedeReasignar,
  puedeExcepcion,
  enviando,
  onReasignar,
  onExcepcion,
}: ConflictoConsultorioAvisoProps) => {
  const [motivo, setMotivo] = useState("");
  const motivoLimpio = motivo.trim();

  return (
    <div
      role="alert"
      className="space-y-2 rounded-xl border border-status-alert/40 bg-status-alert/10 px-3 py-2.5 text-sm text-status-alert"
    >
      <p className="font-semibold">{conflicto.mensaje}</p>
      {puedeReasignar ? (
        <Button type="button" size="sm" onClick={onReasignar} disabled={enviando}>
          Revisar y reasignar
        </Button>
      ) : null}
      {puedeExcepcion ? (
        <div className="space-y-1.5 text-txt-body">
          <Label htmlFor="excepcion-consultorio" className="text-xs">
            Motivo de la excepción
          </Label>
          <Textarea
            id="excepcion-consultorio"
            rows={2}
            value={motivo}
            maxLength={255}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Ej. su médico no vino hoy"
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={enviando || motivoLimpio.length === 0}
            onClick={() => onExcepcion(motivoLimpio)}
          >
            Atender con excepción
          </Button>
        </div>
      ) : null}
    </div>
  );
};
