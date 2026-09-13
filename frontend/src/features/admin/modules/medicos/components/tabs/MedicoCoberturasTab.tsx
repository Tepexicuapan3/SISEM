import { useState } from "react";
import { Loader2, Plus, Trash2, UserRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Badge } from "@shared/ui/badge";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { CatalogCombobox, type CatalogOption } from "@/domains/auth-access/components/admin/rbac/users/CatalogCombobox";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { useConsultoriosList } from "@features/admin/modules/catalogos/consultorios/queries/useConsultoriosList";
import {
  useMedicosList,
  useMedicoCoberturas,
  useCreateCobertura,
  useDeleteCobertura,
} from "@features/admin/modules/medicos/hooks/useMedicos";
import type { MedicoDetail, MotivoCobertura } from "@api/types/medicos.types";

const MOTIVO_LABELS: Record<MotivoCobertura, string> = {
  VACACIONES: "Vacaciones",
  INCAPACIDAD: "Incapacidad",
  PERMISO: "Permiso",
  OTRO: "Otro",
};

type Rol = "SUPLENTE" | "TITULAR";

interface Props { medico: MedicoDetail; isEditable: boolean; }

export function MedicoCoberturasTab({ medico, isEditable }: Props) {
  const { data, isLoading } = useMedicoCoberturas(medico.id);
  const { data: medicosData } = useMedicosList({}, { enabled: isEditable });
  const { data: centrosData } = useCentrosAtencionList({ isActive: true });
  const { data: consultoriosData } = useConsultoriosList();
  const createCobertura = useCreateCobertura(medico.id);
  const deleteCobertura = useDeleteCobertura(medico.id);

  const [rol, setRol] = useState<Rol>("SUPLENTE");
  const [otroMedicoId, setOtroMedicoId] = useState<number | null>(null);
  const [centroId, setCentroId] = useState<number | null>(null);
  const [consultorioId, setConsultorioId] = useState<number | null>(null);
  const [fechaInicio, setFechaInicio] = useState("");
  const [fechaFin, setFechaFin] = useState("");
  const [motivo, setMotivo] = useState<MotivoCobertura>("OTRO");

  const medicoOptions: CatalogOption[] = (medicosData?.items ?? [])
    .filter((m) => m.id !== medico.id)
    .map((m) => ({ id: m.id, name: m.nombreCompleto || m.username, isActive: m.isActive }));

  const centroOptions: CatalogOption[] = (centrosData?.items ?? []).map((c) => ({
    id: c.id, name: c.name, isActive: true,
  }));

  const consultorioOptions: CatalogOption[] = (consultoriosData?.items ?? []).map((c) => ({
    id: c.id, name: c.name, isActive: true,
  }));

  const handleAdd = async () => {
    if (!otroMedicoId || !centroId || !consultorioId || !fechaInicio || !fechaFin) return;
    try {
      await createCobertura.mutateAsync({
        medicoSuplenteId: rol === "SUPLENTE" ? medico.id : otroMedicoId,
        medicoTitularId: rol === "TITULAR" ? medico.id : otroMedicoId,
        consultorioId,
        centroId,
        fechaInicio,
        fechaFin,
        motivo,
      });
      setOtroMedicoId(null);
      setCentroId(null);
      setConsultorioId(null);
      setFechaInicio("");
      setFechaFin("");
      setMotivo("OTRO");
      toast.success("Cobertura registrada.");
    } catch {
      toast.error("No se pudo registrar la cobertura.");
    }
  };

  const handleDelete = async (coberturaId: number) => {
    try {
      await deleteCobertura.mutateAsync(coberturaId);
      toast.success("Cobertura cancelada.");
    } catch {
      toast.error("No se pudo cancelar la cobertura.");
    }
  };

  const coberturas = data?.items ?? [];

  return (
    <div className="space-y-4">
      <p className="text-xs font-semibold tracking-wide text-txt-muted uppercase">
        Coberturas entre médicos
      </p>

      {isLoading ? (
        <p className="text-sm text-txt-muted">Cargando...</p>
      ) : coberturas.length === 0 ? (
        <p className="text-sm text-txt-muted italic">Sin coberturas registradas.</p>
      ) : (
        <div className="divide-y divide-line-struct/50 rounded-xl border border-line-struct">
          {coberturas.map((c) => {
            const esSuplente = c.medicoSuplenteId === medico.id;
            const otroNombre = esSuplente ? c.medicoTitularNombre : c.medicoSuplenteNombre;
            return (
              <div key={c.id} className="flex items-center gap-3 px-4 py-3">
                <UserRound className="size-4 shrink-0 text-txt-muted" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-0.5">
                    <p className="truncate text-sm font-medium">
                      {esSuplente ? `Cubre a ${otroNombre}` : `${otroNombre} lo/la cubre`}
                    </p>
                    <Badge variant="outline" className="text-xs shrink-0">
                      {MOTIVO_LABELS[c.motivo]}
                    </Badge>
                  </div>
                  <p className="text-xs text-txt-muted">
                    {c.fechaInicio} → {c.fechaFin ?? "sin fin"}
                    {c.centroNombre ? ` · ${c.centroNombre}` : ""}
                    {c.consultorioNombre ? ` · Consultorio ${c.consultorioNombre}` : ""}
                  </p>
                </div>
                {isEditable ? (
                  <Button
                    type="button" variant="ghost" size="icon" className="size-8 text-status-critical hover:text-status-critical"
                    disabled={deleteCobertura.isPending}
                    onClick={() => void handleDelete(c.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                ) : null}
              </div>
            );
          })}
        </div>
      )}

      {isEditable ? (
        <div className="space-y-3 rounded-xl border border-line-struct/60 bg-subtle/10 p-4">
          <p className="text-xs font-semibold text-txt-muted uppercase">Nueva cobertura</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">Este médico actúa como</Label>
              <Select value={rol} onValueChange={(v) => setRol(v as Rol)}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="SUPLENTE">Suplente (cubre a otro médico)</SelectItem>
                  <SelectItem value="TITULAR">Titular (otro médico lo/la cubre)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">
                {rol === "SUPLENTE" ? "Médico titular a cubrir" : "Médico suplente"}
              </Label>
              <CatalogCombobox
                value={otroMedicoId} onChange={setOtroMedicoId} options={medicoOptions}
                placeholder="Selecciona médico" emptyLabel="Sin seleccionar" searchPlaceholder="Buscar médico..."
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Centro</Label>
              <CatalogCombobox
                value={centroId} onChange={setCentroId} options={centroOptions}
                placeholder="Selecciona centro" emptyLabel="Sin seleccionar" searchPlaceholder="Buscar centro..."
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Consultorio</Label>
              <CatalogCombobox
                value={consultorioId} onChange={setConsultorioId} options={consultorioOptions}
                placeholder="Selecciona consultorio" emptyLabel="Sin seleccionar" searchPlaceholder="Buscar consultorio..."
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Fecha inicio</Label>
              <Input type="date" value={fechaInicio} onChange={(e) => setFechaInicio(e.target.value)} className="h-9" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Fecha fin</Label>
              <Input type="date" value={fechaFin} onChange={(e) => setFechaFin(e.target.value)} className="h-9" />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label className="text-xs">Motivo</Label>
              <Select value={motivo} onValueChange={(v) => setMotivo(v as MotivoCobertura)}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(MOTIVO_LABELS).map(([val, label]) => (
                    <SelectItem key={val} value={val}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <Button
            type="button" size="sm" className="gap-2"
            disabled={!otroMedicoId || !centroId || !consultorioId || !fechaInicio || !fechaFin || createCobertura.isPending}
            onClick={() => void handleAdd()}
          >
            {createCobertura.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
            Registrar cobertura
          </Button>
        </div>
      ) : null}
    </div>
  );
}
