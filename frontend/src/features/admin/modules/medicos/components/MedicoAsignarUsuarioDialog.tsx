import { useState } from "react";
import { Loader2, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { useAsignarUsuario } from "@features/admin/modules/medicos/hooks/useMedicos";
import { MedicoUsuarioPicker } from "@features/admin/modules/medicos/components/MedicoUsuarioPicker";
import { resolveApiErrorMessage } from "@/domains/auth-access/adapters/rbac/shared/rbac-feedback";
import type { AsignarUsuarioDescartados } from "@api/types/medicos.types";

const ASIGNAR_USUARIO_ERROR_MESSAGES: Record<string, string> = {
  MEDICO_YA_TIENE_USUARIO: "Este médico ya tiene un usuario asignado.",
  MEDICO_EXISTS: "Ese usuario ya tiene un perfil de médico.",
  TIPO_PERSONAL_INVALIDO: "El usuario debe tener tipo de personal Médico.",
  USER_NOT_FOUND: "No se encontró el usuario.",
  MEDICO_NOT_FOUND: "No se encontró el médico.",
  VALIDATION_ERROR: "Selecciona un usuario.",
};

const DESCARTADOS_LABELS: Record<keyof AsignarUsuarioDescartados, string> = {
  nombre: "nombre",
  paterno: "apellido paterno",
  materno: "apellido materno",
  cedulaProfesional: "cédula profesional",
};

interface Props {
  medicoId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MedicoAsignarUsuarioDialog({ medicoId, open, onOpenChange }: Props) {
  const asignar = useAsignarUsuario(medicoId);
  const [usuarioId, setUsuarioId] = useState<number | null>(null);

  const handleOpenChange = (next: boolean) => {
    if (!next) setUsuarioId(null);
    onOpenChange(next);
  };

  const handleSubmit = async () => {
    if (usuarioId === null) return;
    try {
      const result = await asignar.mutateAsync({ usuarioId });
      const descartados = (Object.keys(result.descartados ?? {}) as (keyof AsignarUsuarioDescartados)[])
        .map((k) => DESCARTADOS_LABELS[k]);
      toast.success("Usuario asignado al médico.", {
        description: descartados.length
          ? `El usuario ya tenía: ${descartados.join(", ")}. Se conservó el dato del usuario.`
          : undefined,
      });
      handleOpenChange(false);
    } catch (error) {
      toast.error(
        resolveApiErrorMessage(error, "No se pudo asignar el usuario.", ASIGNAR_USUARIO_ERROR_MESSAGES),
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base font-semibold">
            <UserPlus className="size-4" /> Asignar usuario
          </DialogTitle>
          <DialogDescription className="text-xs text-txt-muted">
            Los nombres y la cédula del médico pasan al usuario solo si este no los tiene;
            nunca se sobrescriben datos del usuario.
          </DialogDescription>
        </DialogHeader>

        <MedicoUsuarioPicker value={usuarioId} onChange={setUsuarioId} enabled={open} />

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            type="button"
            disabled={usuarioId === null || asignar.isPending}
            onClick={() => void handleSubmit()}
          >
            {asignar.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
            Asignar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
