import { useEffect, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { CheckCircle2, Clock, Stethoscope } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Badge }  from "@shared/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import { Input }    from "@shared/ui/input";
import { Label }    from "@shared/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { Textarea } from "@shared/ui/textarea";
import { Separator } from "@shared/ui/separator";
import { ARRIVAL_TYPE } from "@api/types";
import type { PatientMember, VisitQueueItem } from "@api/types";
import type { MedicoDisponible } from "@api/types/medicos.types";
import { isOpenVisitStatus } from "@features/recepcion/shared/utils/recepcion-format";
import { ApiError }        from "@api/utils/errors";
import { PatientMemberCard } from "@features/recepcion/shared/components/PatientMemberCard";
import { useCreateVisit }   from "@features/recepcion/modules/checkin/mutations/useCreateVisit";
import { useTiposCitasList } from "@features/admin/modules/catalogos/tipos-citas/queries/useTiposCitasList";
import { usePatientLookup } from "@features/recepcion/modules/checkin/queries/usePatientLookup";
import { mapCheckinFormToCreateVisitRequest } from "@features/recepcion/modules/checkin/domain/checkin.mappers";
import {
  createCheckinFormSchema,
  DEFAULT_CHECKIN_FORM_VALUES,
  type CheckinFormInput,
  type CheckinFormValues,
} from "@features/recepcion/modules/checkin/domain/checkin.schemas";
import {
  RECEPCION_SERVICE_LIST,
  RECEPCION_SERVICE_PROFILES,
  isServiceForcedToWalkIn,
} from "@features/recepcion/shared/domain/recepcion.services";
import { useMedicosDisponibles } from "@features/admin/modules/medicos/hooks/useMedicos";
import { useAgendaSemanal }       from "@features/recepcion/modules/citas/queries/useAgendaSemanal";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { useDebounce } from "@shared/hooks/useDebounce";

// ─── Constantes ───────────────────────────────────────────────────────────────

const DOMAIN_ERROR_MESSAGE: Record<string, string> = {
  VISIT_DUPLICATE_SUBMIT: "Ya existe una visita abierta para este paciente.",
  VISIT_SLOT_CONFLICT:    "El médico ya tiene una ficha generada para ese horario.",
  PATIENT_NOT_FOUND:      "Expediente no encontrado en el sistema.",
  PATIENT_NO_SERVICE:     "El trabajador está de baja y no hay derechohabientes con vigencia activa.",
  ROLE_NOT_ALLOWED:       "No tienes permiso para registrar llegadas en recepción.",
  VALIDATION_ERROR:       "Revisa los datos de llegada antes de continuar.",
  PERMISSION_DENIED:      "No tienes permiso para ejecutar esta acción.",
};

const FALLBACK_ERROR = "No se pudo generar la ficha. Intenta nuevamente.";

const resolveDomainError = (error: unknown): string => {
  if (!(error instanceof ApiError)) return FALLBACK_ERROR;
  return DOMAIN_ERROR_MESSAGE[error.code] ?? error.message ?? FALLBACK_ERROR;
};

// ─── Sub-componente: tarjeta de disponibilidad de médico ─────────────────────

export function MedicoDisponibleCard({
  medico,
  selected,
  onSelect,
}: {
  medico:   MedicoDisponible;
  selected: boolean;
  onSelect: () => void;
}) {
  const tieneHorario = medico.horaInicio && medico.horaFin;
  const bloqueado  = !medico.disponible;

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={bloqueado}
      className={[
        "flex w-full items-start gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors",
        selected
          ? "border-primary bg-primary/5"
          : "border-line-struct hover:bg-subtle/40",
        bloqueado ? "cursor-not-allowed opacity-50" : "",
      ].join(" ")}
    >
      {/* Radio indicator */}
      <div
        className={[
          "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
          selected ? "border-primary bg-primary" : "border-line-struct",
        ].join(" ")}
      >
        {selected ? <span className="size-1.5 rounded-full bg-white" /> : null}
      </div>

      {/* Info del médico */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-txt-body">
          {medico.nombreCompleto}
        </p>
        {medico.servicio ? (
          <p className="truncate text-xs text-txt-muted">{medico.servicio}</p>
        ) : null}

        {/* Horario y consultorio */}
        {tieneHorario ? (
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1 text-xs text-primary">
              <Clock className="size-3" />
              {medico.horaInicio?.slice(0, 5)} – {medico.horaFin?.slice(0, 5)}
            </span>
            {medico.consultorioNumero != null ? (
              <span className="text-xs text-txt-muted">
                Consultorio #{medico.consultorioNumero}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* Badge disponibilidad */}
      <Badge
        variant={medico.disponible ? "stable" : "secondary"}
        className="shrink-0 text-xs"
      >
        {medico.disponible ? "Disponible" : "No disponible"}
      </Badge>
    </button>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface RecepcionQuickCheckinDialogProps {
  open:          boolean;
  onOpenChange:  (open: boolean) => void;
  canWrite:      boolean;
  initialValues?: Partial<CheckinFormInput>;
  activeVisits?: VisitQueueItem[];
}

// ─── Dialog ───────────────────────────────────────────────────────────────────

export const RecepcionQuickCheckinDialog = ({
  open,
  onOpenChange,
  canWrite,
  initialValues,
  activeVisits = [],
}: RecepcionQuickCheckinDialogProps) => {
  const createVisit = useCreateVisit();

  // Cuando viene de un slot ya está todo pre-llenado — se oculta la sección de médico
  const fromSlot = !!initialValues?.horaConsulta;

  // ── Estado local (no va al form) ─────────────────────────────────────────
  const [noExpSearch,  setNoExpSearch]  = useState("");
  const todayISO = new Date().toISOString().slice(0, 10);
  const [fechaSlot,    setFechaSlot]    = useState(todayISO);
  const [centroId,          setCentroId]          = useState<number | null>(null);
  const [consultorioFiltro, setConsultorioFiltro] = useState<number | null>(null);
  const [selectedMedico,    setSelectedMedico]    = useState<MedicoDisponible | null>(null);

  const debouncedNoExp = useDebounce(noExpSearch, 400);

  // ── Form ──────────────────────────────────────────────────────────────────
  const form = useForm<CheckinFormInput, unknown, CheckinFormValues>({
    resolver: zodResolver(createCheckinFormSchema),
    defaultValues: { ...DEFAULT_CHECKIN_FORM_VALUES, fechaConsulta: todayISO },
  });

  const [pkNumWatch, horaConsultaWatch] = useWatch({
    control: form.control,
    name:    ["pkNum", "horaConsulta"],
  });

  const serviceTypeField    = form.register("serviceType");
  const { data: tiposCitasData } = useTiposCitasList({
    pageSize: 100,
    isActive: true,
  });
  const tiposCitas = tiposCitasData?.items ?? [];

  // ── Búsqueda de paciente ──────────────────────────────────────────────────
  const { data: patientData, isFetching: isSearching, isError: lookupFailed } =
    usePatientLookup(debouncedNoExp);

  const allMembers: PatientMember[] = patientData
    ? [
        ...(patientData.titular ? [patientData.titular] : []),
        ...patientData.dependientes,
      ]
    : [];

  const selectedMember = allMembers.find((m) => m.pkNum === pkNumWatch);

  // ── Centros disponibles ───────────────────────────────────────────────────
  const { data: centrosData } = useCentrosAtencionList({ isActive: true });
  const centros = centrosData?.items ?? [];

  // Auto-seleccionar centro según cd_clinica del paciente seleccionado
  useEffect(() => {
    if (!selectedMember) {
      // Sin paciente: auto-seleccionar si solo hay un centro
      if (centros.length === 1 && !centroId) {
        setCentroId(centros[0].id);
      }
      return;
    }
    const cdClinica = selectedMember.cdClinica;
    if (!cdClinica) return;
    const centroMatch = centros.find((c) => String(c.id) === String(cdClinica));
    if (centroMatch) {
      setCentroId(centroMatch.id);
      setSelectedMedico(null);
      setConsultorioFiltro(null);
    }
  }, [selectedMember, centros]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Médicos disponibles ───────────────────────────────────────────────────
  const { data: disponibilidadData, isFetching: cargandoMedicos } =
    useMedicosDisponibles(centroId ?? undefined, fechaSlot, open && !!centroId);

  const medicosDisponibles = disponibilidadData?.medicos ?? [];

  // ── Slots del médico seleccionado (generados desde su horario, sin llamada API) ──
  const slots: string[] = (() => {
    if (!selectedMedico?.horaInicio || !selectedMedico?.horaFin) return [];
    const intervalo = selectedMedico.intervaloCitaMin ?? 20;
    const result: string[] = [];
    const [hI, mI] = selectedMedico.horaInicio.split(":").map(Number);
    const [hF, mF] = selectedMedico.horaFin.split(":").map(Number);
    let total = hI * 60 + mI;
    const fin  = hF * 60 + mF;
    while (total < fin) {
      const h = String(Math.floor(total / 60)).padStart(2, "0");
      const m = String(total % 60).padStart(2, "0");
      result.push(`${h}:${m}`);
      total += intervalo;
    }
    return result;
  })();

  // ── Horarios ocupados — dos fuentes para máxima precisión ───────────────
  // La agenda semanal es del espacio MÉDICO (CatMedico.id): aquí sí va medicoId.
  const { data: agendaData } = useAgendaSemanal(
    selectedMedico?.medicoId ?? null,
    fechaSlot,
    fechaSlot,
    { refetchInterval: open ? 30_000 : undefined },
  );

  // Fuente 1: slots marcados en HorarioDisponible (citas + visits nuevas)
  const agendaHorasOcupadas = new Set(
    (agendaData?.agenda[fechaSlot] ?? [])
      .filter((s) => !s.disponible)
      .map((s) => s.hora),
  );

  // Fuente 2: visits activas ya existentes en la cola del día
  // slice(0, 5) normaliza "08:00:00" → "08:00" para que coincida con los slot buttons
  const visitHorasOcupadas = new Set(
    activeVisits
      .filter(
        (v) =>
          selectedMedico &&
          v.doctorId === selectedMedico.usuarioId &&
          v.horaConsulta !== null &&
          isOpenVisitStatus(v.status),
      )
      .map((v) => (v.horaConsulta as string).slice(0, 5)),
  );

  const horasOcupadas = new Set([...agendaHorasOcupadas, ...visitHorasOcupadas]);

  // Hora efectiva: si la seleccionada está ocupada (o no hay selección),
  // usa el primer slot libre. Se recalcula en cada render → siempre fresco.
  // Consultorios únicos derivados de la disponibilidad
  const consultoriosDisponibles = Array.from(
    new Map(
      medicosDisponibles
        .filter((m) => m.consultorioId != null)
        .map((m) => [m.consultorioId, { id: m.consultorioId!, numero: m.consultorioNumero, nombre: m.consultorioNombre }])
    ).values()
  ).sort((a, b) => (a.numero ?? 0) - (b.numero ?? 0));

  const medicosFiltrados = consultorioFiltro
    ? medicosDisponibles.filter((m) => m.consultorioId === consultorioFiltro)
    : medicosDisponibles;

  // ── Reset al abrir/cerrar ─────────────────────────────────────────────────
  useEffect(() => {
    if (!open) return;
    form.reset({ ...DEFAULT_CHECKIN_FORM_VALUES, ...initialValues });
    setNoExpSearch("");
    setSelectedMedico(null);
    setConsultorioFiltro(null);
  }, [form, initialValues, open]);

  // Limpiar selección de miembro cuando cambia el expediente
  useEffect(() => { form.setValue("pkNum", 0); }, [debouncedNoExp, form]);

  // Sincronizar médico con el form y pre-llenar hora con el PRIMER slot libre
  useEffect(() => {
    if (selectedMedico) {
      // Visit.doctorId = espacio USUARIO (no el No. Médico).
      form.setValue("doctorId",      selectedMedico.usuarioId, { shouldValidate: true });
      form.setValue("consultorioId", selectedMedico.consultorioId ?? undefined, { shouldValidate: true });
      const primerLibre = slots.find((h) => !horasOcupadas.has(h));
      // Fallback chain: primer slot libre → hora inicio del médico → hora actual
      const defaultHora =
        primerLibre ??
        selectedMedico.horaInicio?.slice(0, 5) ??
        new Date().toTimeString().slice(0, 5);
      form.setValue("horaConsulta", defaultHora, { shouldValidate: true });
    } else if (!fromSlot) {
      // No limpiar si viene de slot — horaConsulta ya está pre-llenada
      form.setValue("horaConsulta", "");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMedico, form]);

  // Verificar que el paciente pertenece a un centro registrado
  const cdClinicaPaciente = selectedMember?.cdClinica ?? null;
  const centroDelPaciente = cdClinicaPaciente
    ? centros.find((c) => String(c.id) === String(cdClinicaPaciente))
    : null;
  const pacienteSinCentro = !!selectedMember && !!cdClinicaPaciente && !centroDelPaciente;

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (values: CheckinFormValues) => {
    if (!canWrite) return;
    if (pacienteSinCentro) {
      toast.error("No se puede generar la ficha", {
        description: `El paciente pertenece a la clínica ${cdClinicaPaciente} que no está registrada en el sistema.`,
      });
      return;
    }
    try {
      await createVisit.mutateAsync(
        mapCheckinFormToCreateVisitRequest(values, selectedMember?.nombre),
      );
      toast.success("Ficha de consulta generada.");
      form.reset(DEFAULT_CHECKIN_FORM_VALUES);
      setNoExpSearch("");
      setSelectedMedico(null);
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo generar la ficha", {
        description: resolveDomainError(error),
      });
    }
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Generar ficha de consulta</DialogTitle>
          <DialogDescription>
            Busca al paciente, elige médico y genera la ficha de llegada.
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          noValidate
          onSubmit={form.handleSubmit(handleSubmit)}
        >

          {/* ── 1. Paciente ─────────────────────────────────────────── */}
          <div className="space-y-2">
            <Label htmlFor="quick-noExp">Número de expediente</Label>
            <Input
              id="quick-noExp"
              placeholder="Ej. 12345"
              value={noExpSearch}
              onChange={(e) => {
                setNoExpSearch(e.target.value);
                form.setValue("noExp", e.target.value, { shouldValidate: false });
              }}
              disabled={!canWrite || createVisit.isPending}
            />
          </div>

          {debouncedNoExp.trim().length > 0 ? (
            <div className="space-y-1.5">
              <Label>Paciente</Label>
              {isSearching ? (
                <p className="text-sm text-txt-muted">Buscando expediente...</p>
              ) : lookupFailed || allMembers.length === 0 ? (
                <p className="text-sm text-status-critical">
                  {lookupFailed
                    ? "Sin derecho al servicio o expediente no encontrado."
                    : "Sin miembros activos."}
                </p>
              ) : (
                <>
                  {allMembers.map((member) => (
                    <PatientMemberCard
                      key={`${member.noExp}-${member.pkNum}`}
                      member={member}
                      selected={pkNumWatch === member.pkNum}
                      onSelect={() =>
                        form.setValue("pkNum", member.pkNum, { shouldValidate: true })
                      }
                    />
                  ))}

                  {selectedMember ? (
                    <div className="flex items-center gap-2.5 rounded-xl border border-primary/30 bg-primary/5 px-3 py-2.5">
                      <CheckCircle2 className="size-4 shrink-0 text-primary" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-primary">
                          {selectedMember.nombre}
                        </p>
                        <p className="truncate text-xs text-txt-muted">
                          {selectedMember.pkNum === 0 ? "Titular" : selectedMember.parentesco ?? "Familiar"}
                          {" · Exp. "}{selectedMember.noExp}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-txt-muted italic">
                      ↑ Selecciona a quien se le generará la ficha.
                    </p>
                  )}
                </>
              )}
            </div>
          ) : null}

          <Separator />

          {/* ── 2. Servicio y tipo de llegada ────────────────────────── */}
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="quick-serviceType">Servicio</Label>
              <select
                id="quick-serviceType"
                className="h-10 w-full rounded-md border border-line-struct bg-paper px-3 text-sm"
                disabled={!canWrite || createVisit.isPending}
                {...serviceTypeField}
                onChange={(e) => {
                  serviceTypeField.onChange(e);
                  const next = e.target.value as CheckinFormValues["serviceType"];
                  if (isServiceForcedToWalkIn(next)) {
                    form.setValue("arrivalType",   ARRIVAL_TYPE.WALK_IN, { shouldValidate: true });
                    form.setValue("appointmentId", "",                   { shouldValidate: true });
                  }
                }}
              >
                {RECEPCION_SERVICE_LIST.map((s) => (
                  <option key={s} value={s}>{RECEPCION_SERVICE_PROFILES[s].label}</option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="quick-tipoCita">Tipo de cita</Label>
              <Controller
                control={form.control}
                name="tipoCitaId"
                render={({ field }) => (
                  <Select
                    value={field.value ? String(field.value) : ""}
                    onValueChange={field.onChange}
                    disabled={!canWrite || createVisit.isPending}
                  >
                    <SelectTrigger id="quick-tipoCita" className="w-full">
                      <SelectValue placeholder="Selecciona un tipo de cita" />
                    </SelectTrigger>
                    <SelectContent>
                      {tiposCitas.map((tipoCita) => (
                        <SelectItem key={tipoCita.id} value={String(tipoCita.id)}>
                          {tipoCita.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>


          <Separator />

          {/* ── 3a. Resumen de slot (cuando viene del calendario) ────── */}
          {fromSlot ? (
            <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 space-y-1">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
                <p className="text-sm font-semibold text-emerald-700">Horario del slot</p>
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-0.5 pl-6 text-xs text-emerald-700">
                {initialValues?.fechaConsulta ? (
                  <span>
                    {new Date(initialValues.fechaConsulta + "T00:00:00").toLocaleDateString(
                      "es-MX", { weekday: "long", day: "2-digit", month: "long", year: "numeric" }
                    )}
                  </span>
                ) : null}
                <span className="flex items-center gap-1 font-mono font-semibold">
                  <Clock className="size-3" />
                  {initialValues?.horaConsulta}
                </span>
              </div>
            </div>
          ) : null}

          {/* ── 3b. Selector médico (cuando NO viene del calendario) ─── */}
          <div className={fromSlot ? "hidden" : "space-y-3"}>
            <div className="flex items-center gap-2">
              <Stethoscope className="size-3.5 text-txt-muted" />
              <p className="text-xs font-semibold tracking-wide text-txt-body uppercase">
                Médico y consultorio
              </p>
            </div>

            {/* Fecha y centro */}
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="space-y-1">
                <Label className="text-xs">Fecha de consulta</Label>
                <Input
                  type="date"
                  value={fechaSlot}
                  onChange={(e) => {
                    setFechaSlot(e.target.value);
                    setSelectedMedico(null);
                    form.setValue("fechaConsulta", e.target.value, { shouldValidate: false });
                  }}
                  className="h-9"
                />
              </div>

              {centros.length > 1 ? (
                <div className="space-y-1">
                  <Label className="text-xs flex items-center gap-1.5">
                    Centro de atención
                    {centroDelPaciente ? (
                      <span className="text-[10px] font-normal text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                        Adscrito
                      </span>
                    ) : null}
                  </Label>
                  <select
                    className={[
                      "h-9 w-full rounded-md border px-3 text-sm",
                      centroDelPaciente
                        ? "border-primary/40 bg-primary/5 text-txt-body cursor-not-allowed"
                        : "border-line-struct bg-paper",
                    ].join(" ")}
                    value={centroId ?? ""}
                    disabled={!!centroDelPaciente}
                    onChange={(e) => {
                      setCentroId(e.target.value ? Number(e.target.value) : null);
                      setSelectedMedico(null);
                      setConsultorioFiltro(null);
                    }}
                  >
                    <option value="">Selecciona centro</option>
                    {centros.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              ) : null}
            </div>

            {/* Filtro de consultorio */}
            {!cargandoMedicos && consultoriosDisponibles.length > 1 ? (
              <div className="space-y-1">
                <Label className="text-xs">Consultorio</Label>
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => { setConsultorioFiltro(null); setSelectedMedico(null); }}
                    className={[
                      "rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                      consultorioFiltro === null
                        ? "border-primary bg-primary text-white"
                        : "border-line-struct hover:border-primary/60 hover:bg-primary/5",
                    ].join(" ")}
                  >
                    Todos
                  </button>
                  {consultoriosDisponibles.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => { setConsultorioFiltro(c.id); setSelectedMedico(null); }}
                      className={[
                        "rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                        consultorioFiltro === c.id
                          ? "border-primary bg-primary text-white"
                          : "border-line-struct hover:border-primary/60 hover:bg-primary/5",
                      ].join(" ")}
                    >
                      {`Consultorio #${c.numero ?? c.id}`}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Lista de médicos disponibles */}
            {!centroId ? (
              <p className="text-xs text-txt-muted italic">
                Selecciona un centro para ver médicos disponibles.
              </p>
            ) : cargandoMedicos ? (
              <p className="text-sm text-txt-muted">Cargando disponibilidad...</p>
            ) : medicosFiltrados.length === 0 ? (
              <p className="text-sm text-txt-muted italic">
                {consultorioFiltro
                  ? "Sin médicos disponibles para ese consultorio."
                  : "Sin médicos configurados para esa fecha en este centro."}
              </p>
            ) : (
              <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
                {medicosFiltrados.map((med) => (
                  <MedicoDisponibleCard
                    key={med.medicoId}
                    medico={med}
                    selected={selectedMedico?.medicoId === med.medicoId}
                    onSelect={() => setSelectedMedico(med)}
                  />
                ))}
              </div>
            )}

            {/* Confirmación del médico seleccionado */}
            {selectedMedico ? (
              <div className="rounded-xl border border-primary/30 bg-primary/5 px-3 py-2.5">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="size-4 shrink-0 text-primary mt-0.5" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-primary">
                      {selectedMedico.nombreCompleto}
                    </p>
                    {selectedMedico.servicio ? (
                      <p className="text-xs text-txt-muted">{selectedMedico.servicio}</p>
                    ) : null}
                    <div className="mt-1 flex flex-wrap gap-3 text-xs text-txt-muted">
                      {selectedMedico.horaInicio && selectedMedico.horaFin ? (
                        <span className="flex items-center gap-1">
                          <Clock className="size-3" />
                          {selectedMedico.horaInicio.slice(0, 5)} – {selectedMedico.horaFin.slice(0, 5)}
                        </span>
                      ) : null}
                      {selectedMedico.consultorioNumero != null ? (
                        <span>Consultorio #{selectedMedico.consultorioNumero}</span>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-txt-muted italic">
                ↑ Selecciona el médico que atenderá al paciente.
              </p>
            )}

            {/* ── Selector/escritura de horario ────────────────────── */}
            {selectedMedico ? (
              <div className="space-y-2">
                <Label className="text-xs">
                  Horario de consulta
                  <span className="ml-1 text-status-critical">*</span>
                </Label>

                {/* Input manual — siempre visible */}
                <Input
                  type="time"
                  className="h-9 w-36"
                  disabled={!canWrite || createVisit.isPending}
                  {...form.register("horaConsulta")}
                />

                {!horaConsultaWatch ? (
                  <p className="text-xs text-amber-600">
                    Selecciona o escribe la hora de consulta del paciente.
                  </p>
                ) : null}

                {/* Chips rápidos si el médico tiene horario configurado */}
                {slots.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {slots.map((hora) => {
                      const ocupado = horasOcupadas.has(hora);
                      return (
                        <button
                          key={hora}
                          type="button"
                          disabled={ocupado}
                          onClick={() => !ocupado && form.setValue("horaConsulta", hora, { shouldValidate: true })}
                          className={[
                            "flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors",
                            ocupado
                              ? "cursor-not-allowed border-red-200 bg-red-50 text-red-400 line-through"
                              : horaConsultaWatch === hora
                                ? "border-primary bg-primary text-white"
                                : "border-line-struct hover:border-primary/60 hover:bg-primary/5",
                          ].join(" ")}
                        >
                          <Clock className="size-3" />
                          {hora}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>

          {/* ── 4. Notas ─────────────────────────────────────────────── */}
          <div className="space-y-2">
            <Label htmlFor="quick-notes">Motivo de consulta</Label>
            <Textarea
              id="quick-notes"
              rows={2}
              disabled={!canWrite || createVisit.isPending}
              {...form.register("notes")}
            />
          </div>

          {pacienteSinCentro ? (
            <p className="text-sm text-status-critical" role="alert">
              El paciente pertenece a la clínica <strong>{cdClinicaPaciente}</strong> que no está
              registrada en el sistema. No se puede generar la ficha.
            </p>
          ) : null}

          {!canWrite ? (
            <p className="text-sm text-txt-muted" role="status">
              No tienes permisos completos para registrar llegadas desde agenda.
            </p>
          ) : null}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cerrar
            </Button>
            <Button
              type="submit"
              disabled={!canWrite || createVisit.isPending || !selectedMember || pacienteSinCentro}
            >
              Generar ficha de consulta
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
