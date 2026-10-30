import { useState } from "react";
import type { Adscripcion, PatientMember } from "@api/types";
import type { ConflictoConsultorioFamiliar } from "@features/recepcion/modules/adscripcion/domain/adscripcionEstado";
import { useAdscripcionPermisos } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionPermisos";
import { ConflictoConsultorioAviso } from "@features/recepcion/modules/adscripcion/components/ConflictoConsultorioAviso";
import { ReasignarAdscripcionDialog } from "@features/recepcion/modules/adscripcion/components/ReasignarAdscripcionDialog";

interface ConflictoCheckinProps {
  conflicto: ConflictoConsultorioFamiliar;
  idPaciente: number | null | undefined;
  nombre: string;
  enviando: boolean;
  /** Reintenta el check-in con el motivo de la excepción. */
  onExcepcion: (motivo: string) => void;
  onReasignado: (adscripcion: Adscripcion) => void;
}

/**
 * P-03 · Check-in de una cita de otro consultorio (por folio o QR): reasignar
 * al paciente o atenderlo hoy con excepción. Lo comparten las dos pantallas.
 */
export const ConflictoCheckin = ({
  conflicto,
  idPaciente,
  nombre,
  enviando,
  onExcepcion,
  onReasignado,
}: ConflictoCheckinProps) => {
  const permisos = useAdscripcionPermisos();
  const [panel, setPanel] = useState(false);

  // El panel solo necesita el registro del paciente (ya existe: tiene cita).
  const member = idPaciente
    ? ({ idPaciente, nombre, noExp: "", pkNum: 0 } as PatientMember)
    : null;

  return (
    <>
      <ConflictoConsultorioAviso
        conflicto={conflicto}
        puedeReasignar={permisos.puedeAsignar && member != null}
        puedeExcepcion={permisos.puedeExcepcion}
        enviando={enviando}
        onReasignar={() => setPanel(true)}
        onExcepcion={onExcepcion}
      />
      <ReasignarAdscripcionDialog
        open={panel}
        onOpenChange={setPanel}
        member={member}
        onAdscrito={onReasignado}
      />
    </>
  );
};
