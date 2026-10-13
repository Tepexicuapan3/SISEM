import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  Building2, CalendarX2, ClipboardList,
  Loader2, Plus, Stethoscope, X,
} from "lucide-react";
import { toast } from "sonner";
import { Badge }     from "@shared/ui/badge";
import { Button }    from "@shared/ui/button";
import { Input }     from "@shared/ui/input";
import { Label }     from "@shared/ui/label";
import { Separator } from "@shared/ui/separator";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from "@shared/ui/form";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { ScrollArea } from "@shared/ui/ScrollArea";
import { CatalogCombobox, type CatalogOption }
  from "@/domains/auth-access/components/admin/rbac/users/CatalogCombobox";
import { useCreateMedico } from "@features/admin/modules/medicos/hooks/useMedicos";
import { useEspecialidadesList }
  from "@features/admin/modules/catalogos/especialidades/queries/useEspecialidadesList";
import { useCentrosAtencionList }
  from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { useConsultoriosList }
  from "@features/admin/modules/catalogos/consultorios/queries/useConsultoriosList";
import { medicosAPI } from "@api/resources/medicos.api";
import { MedicoUsuarioPicker } from "@features/admin/modules/medicos/components/MedicoUsuarioPicker";
import type { MedicoListItem, DiaSemana, TipoExcepcion } from "@api/types/medicos.types";

// ─── Schema ──────────────────────────────────────────────────────────────────

const schema = z.object({
  usuarioId:  z.number({ error: "Selecciona un usuario médico" }).int().positive(),
  tipoMedico: z.enum(["CLINICA", "HOSPITAL", "AMBOS"]),
  servicio:   z.string().trim().max(100).optional(),
});
type FormValues = z.infer<typeof schema>;

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

const TIPO_EXC_LABELS: Record<TipoExcepcion, string> = {
  VACACIONES: "Vacaciones", INCAPACIDAD: "Incapacidad", PERMISO: "Permiso",
  HORA_COMIDA: "Hora de comida", CAPACITACION: "Capacitación",
  AUSENCIA: "Ausencia", SUSPENSION: "Suspensión", CAMBIO_HORARIO: "Cambio de horario",
};

// ─── Tipos de pre-selección ───────────────────────────────────────────────────

interface EspItem    { id: number; name: string }
interface CentroItem { id: number; name: string; tipo: "DEFINITIVA" | "TEMPORAL" }
interface HorarioRow { dia: DiaSemana; horaInicio: string; horaFin: string; intervalo: number }

interface PendingConsultorio {
  tempId: string;
  consultorioId: number;
  nombre: string;
  tipoAsignacion: "PERMANENTE" | "TEMPORAL";
  horarios: HorarioRow[];
}

interface PendingExcepcion {
  tempId: string;
  tipo: TipoExcepcion;
  fechaInicio: string;
  fechaFin: string;
  horaInicio: string | null;
  horaFin: string | null;
  motivo: string | null;
}

// ─── Componentes de layout ────────────────────────────────────────────────────

function SectionHeader({ icon: Icon, children, optional }: {
  icon?: React.ElementType; children: React.ReactNode; optional?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      {Icon ? (
        <div className="flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/10">
          <Icon className="size-3.5 text-primary" />
        </div>
      ) : null}
      <p className="text-xs font-semibold tracking-wide text-txt-body uppercase">{children}</p>
      {optional ? <span className="ml-1 text-xs font-normal normal-case text-txt-muted">(opcional)</span> : null}
    </div>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (m: MedicoListItem) => void;
}

// ─── Componente ──────────────────────────────────────────────────────────────

export function MedicoCreateDialog({ open, onOpenChange, onCreated }: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ── Especialidades (pre-selección) ────────────────────────────────────────
  const [espItems, setEspItems]             = useState<EspItem[]>([]);
  const [selectedEspId, setSelectedEspId]   = useState<number | null>(null);

  // ── Centros (pre-selección) ───────────────────────────────────────────────
  const [centroItems, setCentroItems]             = useState<CentroItem[]>([]);
  const [selectedCentroId, setSelectedCentroId]   = useState<number | null>(null);
  const [tipoCentro, setTipoCentro]               = useState<"DEFINITIVA" | "TEMPORAL">("DEFINITIVA");

  // ── Consultorios (pre-selección con horarios) ─────────────────────────────
  const [pendingConsultorios, setPendingConsultorios] = useState<PendingConsultorio[]>([]);
  // Estado del constructor activo (antes de agregar a la lista)
  const [activeConsId, setActiveConsId]   = useState<number | null>(null);
  const [activeConsTipo, setActiveConsTipo] = useState<"PERMANENTE" | "TEMPORAL">("PERMANENTE");
  const [activeConsHorarios, setActiveConsHorarios] = useState<HorarioRow[]>([]);

  // ── Excepciones (pre-selección) ───────────────────────────────────────────
  const [pendingExcepciones, setPendingExcepciones] = useState<PendingExcepcion[]>([]);
  const [excTipo, setExcTipo]     = useState<TipoExcepcion>("VACACIONES");
  const [excFechaI, setExcFechaI] = useState("");
  const [excFechaF, setExcFechaF] = useState("");
  const [excHoraI, setExcHoraI]   = useState("");
  const [excHoraF, setExcHoraF]   = useState("");
  const [excMotivo, setExcMotivo] = useState("");

  const createMedico = useCreateMedico();

  // ── Catálogos ─────────────────────────────────────────────────────────────

  const { data: espData }    = useEspecialidadesList({ pageSize: 100, isActive: true });
  const espOptions: CatalogOption[] = (espData?.items ?? []).map((e) => ({ id: e.id, name: e.name, isActive: e.isActive }));

  const { data: centrosData } = useCentrosAtencionList({ isActive: true });
  const centroOptions: CatalogOption[] = (centrosData?.items ?? []).map((c) => ({ id: c.id, name: c.name, isActive: c.isActive }));

  const { data: consData } = useConsultoriosList({ isActive: true, pageSize: 100 });
  const consOptions: CatalogOption[] = (consData?.items ?? []).map((c) => ({
    id: c.id, name: `#${c.numero} — ${c.name}`, isActive: c.isActive,
  }));

  // ── Form ──────────────────────────────────────────────────────────────────

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { tipoMedico: "CLINICA", servicio: "" },
  });

  const tipoMedico = form.watch("tipoMedico");
  const esClinica  = tipoMedico === "CLINICA" || tipoMedico === "AMBOS";

  // ── Reset ─────────────────────────────────────────────────────────────────

  const handleClose = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset();
      setEspItems([]); setSelectedEspId(null);
      setCentroItems([]); setSelectedCentroId(null); setTipoCentro("DEFINITIVA");
      setPendingConsultorios([]);
      setActiveConsId(null); setActiveConsTipo("PERMANENTE"); setActiveConsHorarios([]);
      setPendingExcepciones([]);
      setExcTipo("VACACIONES"); setExcFechaI(""); setExcFechaF("");
      setExcHoraI(""); setExcHoraF(""); setExcMotivo("");
    }
    onOpenChange(nextOpen);
  };

  // ── Handlers especialidades ───────────────────────────────────────────────

  const addEspItem = () => {
    if (!selectedEspId) return;
    const opt = espOptions.find((e) => e.id === selectedEspId);
    if (!opt || espItems.some((e) => e.id === selectedEspId)) return;
    setEspItems((p) => [...p, { id: opt.id, name: opt.name }]);
    setSelectedEspId(null);
  };

  // ── Handlers centros ──────────────────────────────────────────────────────

  const addCentroItem = () => {
    if (!selectedCentroId) return;
    const opt = centroOptions.find((c) => c.id === selectedCentroId);
    if (!opt || centroItems.some((c) => c.id === selectedCentroId)) return;
    setCentroItems((p) => [...p, { id: opt.id, name: opt.name, tipo: tipoCentro }]);
    setSelectedCentroId(null);
  };

  // ── Handlers horarios del consultorio activo ──────────────────────────────

  const addHorario = (dia: DiaSemana) =>
    setActiveConsHorarios((p) => [...p, { dia, horaInicio: "08:00", horaFin: "14:00", intervalo: 20 }]);

  const removeHorario = (i: number) =>
    setActiveConsHorarios((p) => p.filter((_, idx) => idx !== i));

  const updateHorario = (i: number, patch: Partial<HorarioRow>) =>
    setActiveConsHorarios((p) => p.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  const addConsultorioToList = () => {
    if (!activeConsId) return;
    const opt = consOptions.find((c) => c.id === activeConsId);
    if (!opt) return;
    setPendingConsultorios((p) => [
      ...p,
      {
        tempId: `${activeConsId}-${Date.now()}`,
        consultorioId:  activeConsId,
        nombre:         opt.name,
        tipoAsignacion: activeConsTipo,
        horarios:       activeConsHorarios,
      },
    ]);
    setActiveConsId(null);
    setActiveConsTipo("PERMANENTE");
    setActiveConsHorarios([]);
  };

  // ── Handlers excepciones ──────────────────────────────────────────────────

  const addExcepcionToList = () => {
    if (!excFechaI || !excFechaF) return;
    setPendingExcepciones((p) => [
      ...p,
      {
        tempId:      `exc-${Date.now()}`,
        tipo:        excTipo,
        fechaInicio: excFechaI,
        fechaFin:    excFechaF,
        horaInicio:  excHoraI || null,
        horaFin:     excHoraF || null,
        motivo:      excMotivo || null,
      },
    ]);
    setExcFechaI(""); setExcFechaF(""); setExcHoraI(""); setExcHoraF(""); setExcMotivo("");
  };

  // ── Submit: crea todo de una sola vez ─────────────────────────────────────

  const onSubmit = async (values: FormValues) => {
    setIsSubmitting(true);
    try {
      // 1. Crear médico
      const result   = await createMedico.mutateAsync({
        usuarioId:  values.usuarioId,
        tipoMedico: values.tipoMedico,
        servicio:   values.servicio || null,
      });
      const medicoId = result.id;
      const today    = new Date().toISOString().slice(0, 10);

      // 2. Especialidades
      for (let i = 0; i < espItems.length; i++) {
        await medicosAPI.addEspecialidad(medicoId, { especialidadId: espItems[i].id, esPrincipal: i === 0 });
      }

      // 3. Centros
      for (const c of centroItems) {
        await medicosAPI.addCentro(medicoId, { centroId: c.id, tipoAdscripcion: c.tipo, fechaInicio: today });
      }

      // 4. Consultorios con sus horarios
      for (const cons of pendingConsultorios) {
        await medicosAPI.addConsultorio(medicoId, {
          consultorioId:  cons.consultorioId,
          tipoAsignacion: cons.tipoAsignacion,
          fechaInicio:    today,
          horarios: cons.horarios.map((h) => ({
            diaSemana:        h.dia,
            horaInicio:       h.horaInicio,
            horaFin:          h.horaFin,
            intervaloCitaMin: h.intervalo,
          })),
        });
      }

      // 5. Excepciones
      for (const exc of pendingExcepciones) {
        await medicosAPI.createExcepcion(medicoId, {
          tipo:        exc.tipo,
          fechaInicio: exc.fechaInicio,
          fechaFin:    exc.fechaFin,
          horaInicio:  exc.horaInicio,
          horaFin:     exc.horaFin,
          motivo:      exc.motivo,
        });
      }

      toast.success("Médico registrado correctamente.");
      onCreated?.(result as MedicoListItem);
      handleClose(false);
    } catch {
      toast.error("No se pudo registrar el médico.", {
        description: "Verifica que el usuario tenga tipo_personal = MEDICO y no tenga ya un perfil.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        showCloseButton
        className="w-[96vw] max-w-none overflow-hidden rounded-3xl bg-paper p-0 sm:max-w-[600px]"
      >
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-line-struct">
          <div className="flex items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10">
              <Stethoscope className="size-5 text-primary" />
            </div>
            <div>
              <DialogTitle className="text-base font-semibold">Registrar nuevo médico</DialogTitle>
              <DialogDescription className="text-xs text-txt-muted">
                Completa los datos. Los consultorios, horarios y excepciones son opcionales.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <ScrollArea className="max-h-[76vh] px-6 pb-2">
          <Form {...form}>
            <form id="medico-create-form" onSubmit={form.handleSubmit(onSubmit)} className="space-y-5 py-4">

              {/* ── 1. Usuario médico ──────────────────────────────────── */}
              <div className="space-y-2">
                <SectionHeader>Buscar usuario médico</SectionHeader>
                <MedicoUsuarioPicker
                  value={form.watch("usuarioId")}
                  onChange={(id) => form.setValue("usuarioId", id, { shouldValidate: true })}
                  enabled={open}
                />
                <FormField control={form.control} name="usuarioId" render={() => <FormMessage />} />
              </div>

              {/* ── 2. Tipo + Servicio ─────────────────────────────────── */}
              <div className="grid gap-3 sm:grid-cols-2">
                <FormField control={form.control} name="tipoMedico" render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs">Tipo de médico</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="h-11"><SelectValue placeholder="Selecciona tipo" /></SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="CLINICA">Clínica</SelectItem>
                        <SelectItem value="HOSPITAL">Hospital</SelectItem>
                        <SelectItem value="AMBOS">Clínica y Hospital</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="servicio" render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-xs">
                      Servicio <span className="font-normal text-txt-muted">(opcional)</span>
                    </FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="Ej. Medicina General..." className="h-11" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>

              <Separator />

              {/* ── 3. Especialidades ─────────────────────────────────── */}
              <div className="space-y-3">
                <SectionHeader icon={Stethoscope} optional>Especialidades</SectionHeader>
                {espItems.length > 0 ? (
                  <div className="divide-y divide-line-struct/50 rounded-xl border border-line-struct">
                    {espItems.map((e, i) => (
                      <div key={e.id} className="flex items-center gap-2 px-3 py-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm">{e.name}</p>
                        </div>
                        {i === 0 ? (
                          <Badge variant="outline" className="shrink-0 gap-1 text-xs">
                            <span className="text-amber-500">★</span> Principal
                          </Badge>
                        ) : null}
                        <button type="button"
                          className="shrink-0 text-txt-muted hover:text-status-critical"
                          onClick={() => setEspItems((p) => p.filter((x) => x.id !== e.id))}>
                          <X className="size-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-txt-muted italic">Sin especialidades. La primera agregada será la principal.</p>
                )}
                <div className="flex gap-2">
                  <div className="flex-1">
                    <CatalogCombobox value={selectedEspId} onChange={setSelectedEspId} options={espOptions}
                      placeholder="Agregar especialidad" emptyLabel="Sin seleccionar" searchPlaceholder="Buscar..." />
                  </div>
                  <Button type="button" size="sm" className="h-10 shrink-0 gap-1.5"
                    disabled={!selectedEspId} onClick={addEspItem}>
                    <Plus className="size-3.5" /> Agregar
                  </Button>
                </div>
              </div>

              <Separator />

              {/* ── 4. Centros de atención ────────────────────────────── */}
              <div className="space-y-3">
                <SectionHeader icon={Building2} optional>Centros de atención</SectionHeader>
                {centroItems.length > 0 ? (
                  <div className="divide-y divide-line-struct/50 rounded-xl border border-line-struct">
                    {centroItems.map((c) => (
                      <div key={c.id} className="flex items-center gap-2 px-3 py-2.5">
                        <p className="flex-1 truncate text-sm">{c.name}</p>
                        <Badge variant="outline" className="shrink-0 text-xs">
                          {c.tipo === "DEFINITIVA" ? "Definitiva" : "Temporal"}
                        </Badge>
                        <button type="button"
                          className="shrink-0 text-txt-muted hover:text-status-critical"
                          onClick={() => setCentroItems((p) => p.filter((x) => x.id !== c.id))}>
                          <X className="size-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-txt-muted italic">Sin centros asignados.</p>
                )}
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <CatalogCombobox value={selectedCentroId} onChange={setSelectedCentroId} options={centroOptions}
                      placeholder="Selecciona centro" emptyLabel="Sin seleccionar" searchPlaceholder="Buscar centro..." />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Tipo adscripción</Label>
                    <Select value={tipoCentro} onValueChange={(v) => setTipoCentro(v as "DEFINITIVA" | "TEMPORAL")}>
                      <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="DEFINITIVA">Definitiva</SelectItem>
                        <SelectItem value="TEMPORAL">Temporal</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-end">
                    <Button type="button" className="h-10 w-full gap-1.5"
                      disabled={!selectedCentroId} onClick={addCentroItem}>
                      <Plus className="size-3.5" /> Agregar centro
                    </Button>
                  </div>
                </div>
              </div>

              {/* ── 5. Consultorios y horarios (CLINICA / AMBOS) ─────── */}
              {esClinica ? (
                <>
                  <Separator />
                  <div className="space-y-3">
                    <SectionHeader icon={ClipboardList} optional>Consultorios y horarios</SectionHeader>

                    {/* Lista de consultorios ya agregados */}
                    {pendingConsultorios.length > 0 ? (
                      <div className="divide-y divide-line-struct/50 rounded-xl border border-line-struct">
                        {pendingConsultorios.map((c) => (
                          <div key={c.tempId} className="flex items-center gap-2 px-3 py-2.5">
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm font-medium">{c.nombre}</p>
                              <p className="text-xs text-txt-muted">
                                {c.horarios.length > 0
                                  ? c.horarios.map((h) => DIAS.find((d) => d.key === h.dia)?.label).join(", ")
                                  : "Sin horario configurado"}
                              </p>
                            </div>
                            <Badge variant="outline" className="shrink-0 text-xs">
                              {c.tipoAsignacion === "PERMANENTE" ? "Permanente" : "Temporal"}
                            </Badge>
                            <button type="button"
                              className="shrink-0 text-txt-muted hover:text-status-critical"
                              onClick={() => setPendingConsultorios((p) => p.filter((x) => x.tempId !== c.tempId))}>
                              <X className="size-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : null}

                    {/* Constructor de consultorio */}
                    <div className="space-y-3 rounded-xl border border-line-struct/60 bg-subtle/10 p-3">
                      <div className="grid gap-2 sm:grid-cols-2">
                        <div className="space-y-1 sm:col-span-2">
                          <Label className="text-xs">Consultorio</Label>
                          <CatalogCombobox value={activeConsId} onChange={setActiveConsId} options={consOptions}
                            placeholder="Selecciona consultorio" emptyLabel="Sin seleccionar"
                            searchPlaceholder="Buscar por número o nombre..." />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Tipo asignación</Label>
                          <Select value={activeConsTipo} onValueChange={(v) => setActiveConsTipo(v as "PERMANENTE" | "TEMPORAL")}>
                            <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="PERMANENTE">Permanente</SelectItem>
                              <SelectItem value="TEMPORAL">Temporal</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      {/* Horarios del consultorio activo */}
                      {activeConsId ? (
                        <div className="space-y-2">
                          <Label className="text-xs">Horario por día</Label>

                          {activeConsHorarios.length > 0 ? (
                            <div className="space-y-1.5">
                              {activeConsHorarios.map((row, i) => (
                                <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-line-struct/50 bg-paper px-3 py-2">
                                  <Badge variant="outline" className="w-10 justify-center shrink-0 text-xs">
                                    {DIAS.find((d) => d.key === row.dia)?.label}
                                  </Badge>
                                  <div className="flex items-center gap-1 text-xs">
                                    <Input type="time" value={row.horaInicio}
                                      onChange={(e) => updateHorario(i, { horaInicio: e.target.value })}
                                      className="h-8 w-[88px] text-xs" />
                                    <span className="text-txt-muted">→</span>
                                    <Input type="time" value={row.horaFin}
                                      onChange={(e) => updateHorario(i, { horaFin: e.target.value })}
                                      className="h-8 w-[88px] text-xs" />
                                  </div>
                                  <div className="flex items-center gap-1 text-xs">
                                    <span className="text-txt-muted">c/</span>
                                    <Input type="number" value={row.intervalo} min={5} max={120}
                                      onChange={(e) => updateHorario(i, { intervalo: Number(e.target.value) })}
                                      className="h-8 w-14 text-xs" />
                                    <span className="text-txt-muted">min</span>
                                  </div>
                                  <Button type="button" variant="ghost" size="icon"
                                    className="ml-auto size-7 shrink-0"
                                    onClick={() => removeHorario(i)}>
                                    <X className="size-3.5" />
                                  </Button>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-txt-muted italic">Sin días configurados.</p>
                          )}

                          {/* Botones para agregar días */}
                          <div className="space-y-1.5">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="text-xs text-txt-muted">L–V:</span>
                              {DIAS.filter((d) => d.grupo === "semana").map((d) => (
                                <Button key={d.key} type="button" variant="outline" size="sm"
                                  className="h-7 px-2 text-xs" onClick={() => addHorario(d.key)}>
                                  <Plus className="size-3 mr-0.5" />{d.label}
                                </Button>
                              ))}
                            </div>
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="text-xs text-txt-muted">Fin semana:</span>
                              {DIAS.filter((d) => d.grupo === "finde").map((d) => (
                                <Button key={d.key} type="button" variant="outline" size="sm"
                                  className="h-7 px-2 text-xs" onClick={() => addHorario(d.key)}>
                                  <Plus className="size-3 mr-0.5" />{d.label}
                                </Button>
                              ))}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <p className="text-xs text-txt-muted">Selecciona un consultorio para configurar su horario.</p>
                      )}

                      <Button type="button" className="w-full gap-2" size="sm"
                        disabled={!activeConsId}
                        onClick={addConsultorioToList}>
                        <Plus className="size-3.5" /> Agregar consultorio a la lista
                      </Button>
                    </div>
                  </div>
                </>
              ) : null}

              <Separator />

              {/* ── 6. Excepciones y ausencias ───────────────────────── */}
              <div className="space-y-3">
                <SectionHeader icon={CalendarX2} optional>Excepciones y ausencias</SectionHeader>

                {/* Lista de excepciones ya agregadas */}
                {pendingExcepciones.length > 0 ? (
                  <div className="divide-y divide-line-struct/50 rounded-xl border border-line-struct">
                    {pendingExcepciones.map((e) => (
                      <div key={e.tempId} className="flex items-center gap-2 px-3 py-2.5">
                        <Badge variant="outline" className="shrink-0 text-xs">{TIPO_EXC_LABELS[e.tipo]}</Badge>
                        <p className="flex-1 text-xs text-txt-muted">
                          {e.fechaInicio} → {e.fechaFin}
                          {e.horaInicio ? ` · ${e.horaInicio}–${e.horaFin}` : ""}
                        </p>
                        <button type="button"
                          className="shrink-0 text-txt-muted hover:text-status-critical"
                          onClick={() => setPendingExcepciones((p) => p.filter((x) => x.tempId !== e.tempId))}>
                          <X className="size-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : null}

                {/* Constructor de excepción */}
                <div className="space-y-3 rounded-xl border border-line-struct/60 bg-subtle/10 p-3">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div className="space-y-1 sm:col-span-2">
                      <Label className="text-xs">Tipo</Label>
                      <Select value={excTipo} onValueChange={(v) => setExcTipo(v as TipoExcepcion)}>
                        <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {Object.entries(TIPO_EXC_LABELS).map(([val, lbl]) => (
                            <SelectItem key={val} value={val}>{lbl}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Fecha inicio</Label>
                      <Input type="date" value={excFechaI}
                        onChange={(e) => setExcFechaI(e.target.value)} className="h-9" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Fecha fin</Label>
                      <Input type="date" value={excFechaF}
                        onChange={(e) => setExcFechaF(e.target.value)} className="h-9" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Hora inicio <span className="text-txt-muted">(opcional)</span></Label>
                      <Input type="time" value={excHoraI}
                        onChange={(e) => setExcHoraI(e.target.value)} className="h-9" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Hora fin <span className="text-txt-muted">(opcional)</span></Label>
                      <Input type="time" value={excHoraF}
                        onChange={(e) => setExcHoraF(e.target.value)} className="h-9" />
                    </div>
                    <div className="space-y-1 sm:col-span-2">
                      <Label className="text-xs">Motivo <span className="text-txt-muted">(opcional)</span></Label>
                      <Input value={excMotivo} onChange={(e) => setExcMotivo(e.target.value)}
                        placeholder="Describe el motivo..." className="h-9" />
                    </div>
                  </div>
                  <Button type="button" size="sm" className="w-full gap-2"
                    disabled={!excFechaI || !excFechaF}
                    onClick={addExcepcionToList}>
                    <Plus className="size-3.5" /> Agregar excepción a la lista
                  </Button>
                </div>
              </div>

            </form>
          </Form>
        </ScrollArea>

        <DialogFooter className="flex gap-2 border-t border-line-struct px-6 py-4">
          <Button type="button" variant="outline"
            onClick={() => handleClose(false)} disabled={isSubmitting}>
            Cancelar
          </Button>
          <Button type="submit" form="medico-create-form"
            disabled={isSubmitting} className="gap-2">
            {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
            Registrar médico
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
