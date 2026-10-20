import { useState } from "react";
import { Loader2, Save, ShieldCheck, UserRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { Separator } from "@shared/ui/separator";
import { Badge } from "@shared/ui/badge";
import { useUpdateMedico } from "@features/admin/modules/medicos/hooks/useMedicos";
import type { MedicoDetail, EstatusMedico, TipoMedico } from "@api/types/medicos.types";

interface Props {
  medico: MedicoDetail;
  isEditable: boolean;
}

export function MedicoGeneralTab({ medico, isEditable }: Props) {
  const update = useUpdateMedico(medico.id);

  const [tipoMedico, setTipoMedico]       = useState<TipoMedico>(medico.tipoMedico);
  const [servicio, setServicio]           = useState(medico.servicio ?? "");
  const [observaciones, setObservaciones] = useState(medico.observaciones ?? "");
  const [estatusMedico, setEstatusMedico] = useState<EstatusMedico>(medico.estatusMedico);

  const isDirty =
    tipoMedico !== medico.tipoMedico ||
    servicio   !== (medico.servicio ?? "") ||
    observaciones !== (medico.observaciones ?? "") ||
    estatusMedico !== medico.estatusMedico;

  const handleSave = async () => {
    try {
      await update.mutateAsync({
        tipoMedico, servicio: servicio || null,
        observaciones: observaciones || null, estatusMedico,
      });
      toast.success("Perfil médico actualizado.");
    } catch {
      toast.error("No se pudo actualizar el perfil.");
    }
  };

  const sexoLabel = medico.sexo === "M" ? "Masculino" : medico.sexo === "F" ? "Femenino" : medico.sexo === "O" ? "Otro" : null;

  return (
    <div className="space-y-6">

      {/* ── Datos del usuario (read-only) ────────────────────────────── */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-3.5 text-txt-muted" />
          <p className="text-xs font-semibold tracking-wide text-txt-body uppercase">Datos del usuario</p>
        </div>
        <div className="rounded-2xl border border-line-struct/60 bg-subtle/20 p-4">
          <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            {([
              { label: "Nombre(s)",       val: medico.nombre  || "—", mono: false },
              { label: "Apellido paterno", val: medico.paterno || "—", mono: false },
              { label: "Apellido materno", val: medico.materno || "—", mono: false },
              { label: "Usuario",          val: medico.username, mono: true },
              { label: "Correo",           val: medico.email ?? "—", mono: false },
              { label: "Sexo",             val: sexoLabel ?? "No registrado", mono: false },
            ] as const).map(({ label, val, mono }) => (
              <div key={label} className="space-y-0.5">
                <p className="text-[10px] font-medium uppercase tracking-wider text-txt-muted">{label}</p>
                <p className={`text-sm ${mono ? "font-mono text-txt-muted" : "font-medium text-txt-body"}`}>{val}</p>
              </div>
            ))}
            {medico.telefono ? (
              <div className="space-y-0.5">
                <p className="text-[10px] font-medium uppercase tracking-wider text-txt-muted">Teléfono</p>
                <p className="text-sm font-medium text-txt-body">{medico.telefono}</p>
              </div>
            ) : null}
            {medico.fechaNac ? (
              <div className="space-y-0.5">
                <p className="text-[10px] font-medium uppercase tracking-wider text-txt-muted">Fecha de nac.</p>
                <p className="text-sm font-medium text-txt-body">{medico.fechaNac}</p>
              </div>
            ) : null}
            {medico.direccion ? (
              <div className="space-y-0.5 sm:col-span-2">
                <p className="text-[10px] font-medium uppercase tracking-wider text-txt-muted">Dirección</p>
                <p className="text-sm font-medium text-txt-body">{medico.direccion}</p>
              </div>
            ) : null}
          </div>

          {/* Cédulas */}
          {medico.cedulas.length > 0 ? (
            <div className="mt-4 space-y-1.5 border-t border-line-struct/40 pt-3">
              <p className="text-[10px] font-medium uppercase tracking-wider text-txt-muted">Cédulas profesionales</p>
              <div className="flex flex-wrap gap-1.5">
                {medico.cedulas.map((c) => (
                  <Badge key={c.id} variant="outline" className="gap-1 text-xs">
                    <span className="font-mono">{c.numero}</span>
                    <span className="text-txt-muted">· {c.tipo.toLowerCase()}</span>
                    {c.esPrincipal ? <span className="text-amber-500 ml-0.5">★</span> : null}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}

          {/* Escuela */}
          {medico.escuela ? (
            <div className="mt-4 space-y-1.5 border-t border-line-struct/40 pt-3">
              <p className="text-[10px] font-medium uppercase tracking-wider text-txt-muted">Escuela de egreso</p>
              <p className="text-sm font-medium text-txt-body">
                {medico.escuela.code
                  ? <span className="font-mono text-txt-muted mr-2">{medico.escuela.code}</span>
                  : null}
                {medico.escuela.name}
              </p>
            </div>
          ) : null}
        </div>
      </div>

      <Separator />

      {/* ── Perfil médico (editable) ──────────────────────────────────── */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <UserRound className="size-3.5 text-txt-muted" />
          <p className="text-xs font-semibold tracking-wide text-txt-body uppercase">Perfil médico</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label className="text-xs">Tipo de médico</Label>
            <Select value={tipoMedico} onValueChange={(v) => setTipoMedico(v as TipoMedico)} disabled={!isEditable}>
              <SelectTrigger className="h-11"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="CLINICA">Clínica</SelectItem>
                <SelectItem value="HOSPITAL">Hospital</SelectItem>
                <SelectItem value="AMBOS">Clínica y Hospital</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Estatus médico</Label>
            <Select value={estatusMedico} onValueChange={(v) => setEstatusMedico(v as EstatusMedico)} disabled={!isEditable}>
              <SelectTrigger className="h-11"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="ACTIVO">Activo</SelectItem>
                <SelectItem value="VACACIONES">Vacaciones</SelectItem>
                <SelectItem value="INCAPACIDAD">Incapacidad</SelectItem>
                <SelectItem value="SUSPENDIDO">Suspendido</SelectItem>
                <SelectItem value="BAJA">Baja</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label className="text-xs">Servicio</Label>
            <Input value={servicio} onChange={(e) => setServicio(e.target.value)}
              placeholder="Ej. Medicina general, Cardiología..." disabled={!isEditable} className="h-11" />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label className="text-xs">
              Observaciones <span className="text-txt-muted font-normal">(opcional)</span>
            </Label>
            <textarea
              value={observaciones} onChange={(e) => setObservaciones(e.target.value)}
              placeholder="Notas o indicaciones adicionales..." disabled={!isEditable} rows={3}
              className="w-full rounded-xl border border-input bg-background px-3 py-2 text-sm resize-none disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>

        {/* Botón guardar — visible solo cuando hay cambios */}
        {isEditable && isDirty ? (
          <div className="flex items-center justify-between rounded-xl border border-primary/20 bg-primary/5 px-4 py-3">
            <p className="text-xs text-primary font-medium">Tienes cambios sin guardar</p>
            <Button type="button" size="sm" className="h-8 gap-2" disabled={update.isPending}
              onClick={() => void handleSave()}>
              {update.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
              Guardar
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
