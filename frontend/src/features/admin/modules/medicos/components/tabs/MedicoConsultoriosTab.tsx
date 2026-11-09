import { useState } from "react";
import { ChevronDown, ChevronUp, Clock, Loader2, Pencil, Plus, Save, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { Button }    from "@shared/ui/button";
import { Badge }     from "@shared/ui/badge";
import { Input }     from "@shared/ui/input";
import { Label }     from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { Separator } from "@shared/ui/separator";
import { CatalogCombobox, type CatalogOption }
  from "@/domains/auth-access/components/admin/rbac/users/CatalogCombobox";
import { useConsultoriosList }
  from "@features/admin/modules/catalogos/consultorios/queries/useConsultoriosList";
import {
  useAddConsultorio,
  useUpdateConsultorio,
  useRemoveConsultorio,
  useSaveHorario,
} from "@features/admin/modules/medicos/hooks/useMedicos";
import type { MedicoDetail, MedicoConsultorioItem, DiaSemana, CanalAtencion } from "@api/types/medicos.types";

// ─── Constantes ───────────────────────────────────────────────────────────────

const DIAS: { key: DiaSemana; label: string; grupo: "semana" | "finde" }[] = [
  { key: "LUNES",     label: "Lun", grupo: "semana" },
  { key: "MARTES",    label: "Mar", grupo: "semana" },
  { key: "MIERCOLES", label: "Mié", grupo: "semana" },
  { key: "JUEVES",    label: "Jue", grupo: "semana" },
  { key: "VIERNES",   label: "Vie", grupo: "semana" },
  { key: "SABADO",    label: "Sáb", grupo: "finde" },
  { key: "DOMINGO",   label: "Dom", grupo: "finde" },
];

interface HorarioRow { dia: DiaSemana; horaInicio: string; horaFin: string; intervalo: number; canal: CanalAtencion }

const CANALES: { key: CanalAtencion; label: string }[] = [
  { key: "PRESENCIAL", label: "Presencial" },
  { key: "LINEA",      label: "En línea" },
  { key: "AMBOS",      label: "Ambos" },
];

// ─── Editor de un consultorio (acordeón) ─────────────────────────────────────

interface ConsultorioEditorProps {
  rmc: MedicoConsultorioItem;
  medicoId: number;
  isEditable: boolean;
  onRefresh: () => void;
}

function ConsultorioEditor({ rmc, medicoId, isEditable, onRefresh }: ConsultorioEditorProps) {
  const saveHorario       = useSaveHorario(medicoId, rmc.id);
  const updateConsultorio = useUpdateConsultorio(medicoId);
  const removeConsultorio = useRemoveConsultorio(medicoId);

  const [expanded,  setExpanded]  = useState(false);
  const [editMode,  setEditMode]  = useState(false);

  // Estado horarios
  const [rows, setRows] = useState<HorarioRow[]>(
    rmc.horarios.map((h) => ({
      dia: h.diaSemana as DiaSemana, horaInicio: h.horaInicio,
      horaFin: h.horaFin, intervalo: h.intervaloCitaMin,
      canal: h.canal ?? "PRESENCIAL",
    })),
  );

  // Estado edición asignación
  const [editConsId,  setEditConsId]  = useState<number | null>(null);
  const [editTipo,    setEditTipo]    = useState<"PERMANENTE"|"TEMPORAL">(
    rmc.tipoAsignacion as "PERMANENTE"|"TEMPORAL"
  );

  // Catálogo para cambiar consultorio
  const { data: consData } = useConsultoriosList({ isActive: true, pageSize: 100 });
  const consOptions: CatalogOption[] = (consData?.items ?? []).map((c) => ({
    id: c.id, name: `#${c.numero} — ${c.name}`, isActive: c.isActive,
  }));

  // ── Handlers horarios ─────────────────────────────────────────────────────
  const addRow    = (dia: DiaSemana) =>
    setRows((p) => [...p, { dia, horaInicio: "08:00", horaFin: "14:00", intervalo: 20, canal: "PRESENCIAL" }]);
  const removeRow = (i: number) => setRows((p) => p.filter((_, x) => x !== i));
  const updateRow = (i: number, patch: Partial<HorarioRow>) =>
    setRows((p) => p.map((r, x) => (x === i ? { ...r, ...patch } : r)));

  const handleSaveHorario = async () => {
    try {
      await saveHorario.mutateAsync({
        horarios: rows.map((r) => ({
          diaSemana: r.dia, horaInicio: r.horaInicio, horaFin: r.horaFin,
          intervaloCitaMin: r.intervalo, canal: r.canal,
        })),
      });
      toast.success("Horario guardado.");
      onRefresh();
    } catch { toast.error("No se pudo guardar el horario."); }
  };

  // ── Handlers edición asignación ───────────────────────────────────────────
  const handleSaveAsignacion = async () => {
    const data: { consultorioId?: number; tipoAsignacion?: string } = {};
    if (editConsId && editConsId !== rmc.consultorioId) data.consultorioId = editConsId;
    if (editTipo !== rmc.tipoAsignacion) data.tipoAsignacion = editTipo;
    if (!data.consultorioId && !data.tipoAsignacion) {
      setEditMode(false);
      return;
    }
    try {
      await updateConsultorio.mutateAsync({ rmcId: rmc.id, data });
      toast.success("Consultorio actualizado.");
      setEditMode(false);
      onRefresh();
    } catch { toast.error("No se pudo actualizar el consultorio."); }
  };

  const handleRemove = () =>
    void removeConsultorio.mutateAsync(rmc.id)
      .then(() => { toast.success("Consultorio dado de baja."); onRefresh(); })
      .catch(() => toast.error("No se pudo dar de baja el consultorio."));

  const diasLabel = rows.length > 0
    ? rows.map((r) => DIAS.find((d) => d.key === r.dia)?.label).join(", ")
    : "Sin horario configurado";

  return (
    <div className="overflow-hidden rounded-xl border border-line-struct bg-paper">

      {/* ── Cabecera ──────────────────────────────────────────────────── */}
      <div className="flex items-center gap-0">
        {/* Zona expandible */}
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 text-left hover:bg-subtle/30 transition-colors"
          onClick={() => { setExpanded((v) => !v); if (!expanded) setEditMode(false); }}
        >
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
            <span className="text-xs font-bold text-primary">#{rmc.consultorioNumero}</span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-txt-body">{rmc.consultorioNombre}</p>
            <p className="truncate text-xs text-txt-muted">{diasLabel}</p>
          </div>
          <Badge
            variant={rmc.tipoAsignacion === "PERMANENTE" ? "outline" : "secondary"}
            className="shrink-0 text-xs"
          >
            {rmc.tipoAsignacion === "PERMANENTE" ? "Permanente" : "Temporal"}
          </Badge>
          {expanded
            ? <ChevronUp   className="size-4 shrink-0 text-txt-muted" />
            : <ChevronDown className="size-4 shrink-0 text-txt-muted" />}
        </button>

        {/* Botón editar asignación */}
        {isEditable ? (
          <button
            type="button"
            className={`flex size-12 shrink-0 items-center justify-center border-l border-line-struct/60 transition-colors
              ${editMode ? "bg-primary/10 text-primary" : "text-txt-muted hover:bg-subtle/30"}`}
            title="Editar asignación"
            onClick={() => { setEditMode((v) => !v); setExpanded(true); setEditConsId(null); }}
          >
            <Pencil className="size-3.5" />
          </button>
        ) : null}

        {/* Botón dar de baja */}
        {isEditable ? (
          <button
            type="button"
            className="flex size-12 shrink-0 items-center justify-center border-l border-line-struct/60 text-txt-muted hover:bg-red-50 hover:text-status-critical transition-colors"
            title="Dar de baja consultorio"
            disabled={removeConsultorio.isPending}
            onClick={handleRemove}
          >
            {removeConsultorio.isPending
              ? <Loader2 className="size-3.5 animate-spin" />
              : <Trash2  className="size-3.5" />}
          </button>
        ) : null}
      </div>

      {/* ── Contenido expandido ───────────────────────────────────────── */}
      {expanded ? (
        <div className="space-y-5 border-t border-line-struct/60 bg-subtle/5 p-4">

          {/* ── Edición de la asignación ────────────────────────────── */}
          {editMode ? (
            <div className="space-y-3 rounded-xl border border-primary/30 bg-primary/5 p-3">
              <p className="text-xs font-semibold tracking-wide text-primary uppercase">
                Cambiar consultorio asignado
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5 sm:col-span-2">
                  <Label className="text-xs">Consultorio</Label>
                  <CatalogCombobox
                    value={editConsId ?? rmc.consultorioId}
                    onChange={setEditConsId}
                    options={consOptions}
                    placeholder="Selecciona consultorio"
                    emptyLabel="Sin seleccionar"
                    searchPlaceholder="Buscar por número o nombre..."
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Tipo asignación</Label>
                  <Select value={editTipo} onValueChange={(v) => setEditTipo(v as "PERMANENTE"|"TEMPORAL")}>
                    <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="PERMANENTE">Permanente</SelectItem>
                      <SelectItem value="TEMPORAL">Temporal</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end gap-2">
                  <Button
                    type="button" className="h-10 flex-1 gap-2"
                    disabled={updateConsultorio.isPending}
                    onClick={() => void handleSaveAsignacion()}
                  >
                    {updateConsultorio.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
                    Guardar
                  </Button>
                  <Button type="button" variant="ghost" size="sm" className="h-10"
                    onClick={() => { setEditMode(false); setEditConsId(null); }}>
                    Cancelar
                  </Button>
                </div>
              </div>
            </div>
          ) : null}

          {/* ── Horarios ────────────────────────────────────────────── */}
          <div className="space-y-3">
            <p className="text-xs font-semibold tracking-wide text-txt-muted uppercase">Horario por día</p>

            {rows.length > 0 ? (
              <div className="space-y-2">
                {rows.map((row, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-line-struct/50 bg-paper px-3 py-2">
                    <Badge variant="outline" className="w-10 shrink-0 justify-center text-xs">
                      {DIAS.find((d) => d.key === row.dia)?.label}
                    </Badge>
                    <Clock className="size-3.5 shrink-0 text-txt-muted" />
                    <div className="flex items-center gap-1.5 text-xs">
                      <Input type="time" value={row.horaInicio} disabled={!isEditable}
                        onChange={(e) => updateRow(i, { horaInicio: e.target.value })}
                        className="h-8 w-[136px] text-xs tabular-nums" />
                      <span className="text-txt-muted">→</span>
                      <Input type="time" value={row.horaFin} disabled={!isEditable}
                        onChange={(e) => updateRow(i, { horaFin: e.target.value })}
                        className="h-8 w-[136px] text-xs tabular-nums" />
                    </div>
                    <div className="flex items-center gap-1 text-xs">
                      <span className="text-txt-muted">c/</span>
                      <Input type="number" value={row.intervalo} disabled={!isEditable}
                        min={5} max={120}
                        onChange={(e) => updateRow(i, { intervalo: Number(e.target.value) })}
                        className="h-8 w-14 text-xs" />
                      <span className="text-txt-muted">min</span>
                    </div>
                    <Select
                      value={row.canal}
                      disabled={!isEditable}
                      onValueChange={(v) => updateRow(i, { canal: v as CanalAtencion })}
                    >
                      <SelectTrigger className="h-8 w-[112px] text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {CANALES.map((c) => (
                          <SelectItem key={c.key} value={c.key}>{c.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {isEditable ? (
                      <Button type="button" variant="ghost" size="icon"
                        className="ml-auto size-7 shrink-0 text-txt-muted hover:text-status-critical"
                        onClick={() => removeRow(i)}>
                        <X className="size-3.5" />
                      </Button>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-txt-muted italic">Sin días configurados.</p>
            )}

            {/* Agregar días */}
            {isEditable ? (
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-txt-muted">L–V:</span>
                  {DIAS.filter((d) => d.grupo === "semana").map((d) => (
                    <Button key={d.key} type="button" variant="outline" size="sm"
                      className="h-7 px-2 text-xs" onClick={() => addRow(d.key)}>
                      <Plus className="size-3 mr-0.5" />{d.label}
                    </Button>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-txt-muted">Fin sem:</span>
                  {DIAS.filter((d) => d.grupo === "finde").map((d) => (
                    <Button key={d.key} type="button" variant="outline" size="sm"
                      className="h-7 px-2 text-xs" onClick={() => addRow(d.key)}>
                      <Plus className="size-3 mr-0.5" />{d.label}
                    </Button>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Guardar horario */}
            {isEditable ? (
              <div className="flex justify-end">
                <Button type="button" size="sm" className="h-8 gap-2"
                  disabled={saveHorario.isPending}
                  onClick={() => void handleSaveHorario()}>
                  {saveHorario.isPending
                    ? <Loader2 className="size-3.5 animate-spin" />
                    : <Save    className="size-3.5" />}
                  Guardar horario
                </Button>
              </div>
            ) : null}
          </div>

        </div>
      ) : null}
    </div>
  );
}

// ─── Tab principal ────────────────────────────────────────────────────────────

interface Props {
  medico: MedicoDetail;
  isEditable: boolean;
  onRefresh: () => void;
}

export function MedicoConsultoriosTab({ medico, isEditable, onRefresh }: Props) {
  const [consultorioId, setConsultorioId]   = useState<number | null>(null);
  const [tipoAsignacion, setTipoAsignacion] = useState<"PERMANENTE" | "TEMPORAL">("PERMANENTE");

  const addConsultorio = useAddConsultorio(medico.id);

  const { data: consData } = useConsultoriosList({ isActive: true, pageSize: 100 });
  const consOptions: CatalogOption[] = (consData?.items ?? []).map((c) => ({
    id: c.id, name: `#${c.numero} — ${c.name}`, isActive: c.isActive,
  }));

  const handleAdd = async () => {
    if (!consultorioId) return;
    try {
      await addConsultorio.mutateAsync({
        consultorioId,
        tipoAsignacion,
        fechaInicio: new Date().toISOString().slice(0, 10),
      });
      setConsultorioId(null);
      onRefresh();
      toast.success("Consultorio asignado. Expándelo para configurar el horario.");
    } catch {
      toast.error("No se pudo asignar el consultorio.");
    }
  };

  const consultorios = medico.consultorios ?? [];

  return (
    <div className="space-y-5">

      {/* Contador */}
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold tracking-wide text-txt-muted uppercase">
          Consultorios asignados
        </p>
        <p className="text-xs text-txt-muted">
          {consultorios.length} {consultorios.length === 1 ? "consultorio" : "consultorios"}
        </p>
      </div>

      {/* Lista */}
      {consultorios.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line-struct/60 bg-subtle/10 px-4 py-8 text-center">
          <p className="text-sm text-txt-muted">Sin consultorios asignados.</p>
          <p className="mt-1 text-xs text-txt-muted">
            Asigna un consultorio abajo para configurar su horario.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {consultorios.map((rmc) => (
            <ConsultorioEditor
              key={rmc.id}
              rmc={rmc}
              medicoId={medico.id}
              isEditable={isEditable}
              onRefresh={onRefresh}
            />
          ))}
        </div>
      )}

      {/* Asignar nuevo */}
      {isEditable ? (
        <>
          <Separator />
          <div className="space-y-3">
            <p className="text-xs font-semibold tracking-wide text-txt-muted uppercase">
              Asignar consultorio
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5 sm:col-span-2">
                <Label className="text-xs">Consultorio</Label>
                <CatalogCombobox
                  value={consultorioId}
                  onChange={setConsultorioId}
                  options={consOptions}
                  placeholder="Selecciona consultorio"
                  emptyLabel="Sin seleccionar"
                  searchPlaceholder="Buscar por número o nombre..."
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Tipo de asignación</Label>
                <Select
                  value={tipoAsignacion}
                  onValueChange={(v) => setTipoAsignacion(v as "PERMANENTE" | "TEMPORAL")}
                >
                  <SelectTrigger className="h-11"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="PERMANENTE">Permanente</SelectItem>
                    <SelectItem value="TEMPORAL">Temporal</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end">
                <Button
                  type="button" className="h-11 w-full gap-2"
                  disabled={!consultorioId || addConsultorio.isPending}
                  onClick={() => void handleAdd()}
                >
                  {addConsultorio.isPending
                    ? <Loader2 className="size-4 animate-spin" />
                    : <Plus    className="size-4" />}
                  Asignar consultorio
                </Button>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
