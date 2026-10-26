import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Baby, CalendarPlus, Link2, X } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Badge } from "@shared/ui/badge";
import { ApiError } from "@api/utils/errors";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { PATIENT_SEX_LABELS } from "@features/expedientes/domain/patient-identity";
import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";
import type {
  CandidatoSermed,
  RecienNacidoProvisional,
  RegistrarRecienNacidoRequest,
} from "@api/types/expedientes.types";
import {
  useDescartarCoincidencia,
  useExtenderVigenciaRecienNacido,
  useRecienNacidos,
  useRegistrarRecienNacido,
  useVincularRecienNacido,
} from "../queries/useRecienNacidos";

// Codigos del backend (consulta_medica.services.newborn_service).
const MENSAJES: Record<string, string> = {
  RN_YA_REGISTRADO: "Ya hay un recién nacido provisional de este titular con esa fecha, sexo y orden.",
  TITULAR_NO_EN_SERMED: "El titular no existe en SERMED.",
  CANDIDATO_NO_VALIDO: "Ese familiar ya no coincide con el recién nacido (o se descartó).",
  RN_YA_VINCULADO: "Este recién nacido ya está vinculado a SERMED.",
  RECIEN_NACIDOS_DESHABILITADO: "El registro de recién nacidos no está habilitado.",
  VIGENCIA_SIN_CAMBIO: "La vigencia ya llega a esa fecha: no hay nada que extender.",
  PERMISSION_DENIED: "No tienes permiso para esta acción.",
};
const mensaje = (error: unknown, fallback: string) => getCatalogErrorMessage(error, fallback, MENSAJES);

const fecha = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

// El boton de extender aparece cuando ya vencio o le quedan pocos dias.
const DIAS_AVISO_VIGENCIA = 15;
const diasParaVencer = (iso: string) => {
  const [anio, mes, dia] = iso.split("-").map(Number);
  const hoy = new Date();
  const vence = Date.UTC(anio, mes - 1, dia);
  return Math.round((vence - Date.UTC(hoy.getFullYear(), hoy.getMonth(), hoy.getDate())) / 86_400_000);
};
const sexo = (valor: RecienNacidoProvisional["sexo"]) => (valor ? PATIENT_SEX_LABELS[valor] : "—");

const FORM_VACIO: RegistrarRecienNacidoRequest = {
  paternalSurname: "",
  maternalSurname: "",
  firstName: "",
  birthDate: "",
  sex: "F",
  motherName: "",
  birthOrder: 1,
  curp: "",
};

export function RecienNacidosPanel({ noExp }: { noExp: string }) {
  const { hasCapability } = usePermissionDependencies();
  const puedeRegistrar = hasCapability("admin.expedientes.recienNacidos", {
    allOf: ["admin:gestion:expedientes:recien_nacidos"],
  });
  const puedeVincular = hasCapability("admin.expedientes.vincular", {
    allOf: ["admin:gestion:expedientes:vincular"],
  });

  const { data } = useRecienNacidos(noExp);
  const registrar = useRegistrarRecienNacido(noExp);
  const vincular = useVincularRecienNacido(noExp);
  const descartar = useDescartarCoincidencia(noExp);
  const extender = useExtenderVigenciaRecienNacido(noExp);

  const [abierto, setAbierto] = useState(false);
  const [form, setForm] = useState<RegistrarRecienNacidoRequest>(FORM_VACIO);
  // SERMED ya tiene un hijo con esa fecha y sexo: hay que confirmar que es otro bebe.
  const [enSermed, setEnSermed] = useState<CandidatoSermed[] | null>(null);

  if (!data?.habilitado) return null;

  const campo = (nombre: keyof RegistrarRecienNacidoRequest) => ({
    value: String(form[nombre] ?? ""),
    onChange: (e: { target: { value: string } }) => setForm({ ...form, [nombre]: e.target.value }),
  });

  const enviar = (confirmarAunqueExista: boolean) => {
    registrar.mutate(
      { ...form, birthOrder: Number(form.birthOrder) || 1, confirmarAunqueExista },
      {
        onSuccess: () => {
          toast.success("Recién nacido registrado como provisional.");
          setForm(FORM_VACIO);
          setEnSermed(null);
          setAbierto(false);
        },
        onError: (error) => {
          if (error instanceof ApiError && error.code === "RN_YA_EN_SERMED") {
            const candidatos = (error.details as { candidatos?: CandidatoSermed[] } | undefined)?.candidatos;
            setEnSermed(candidatos ?? []);
            return;
          }
          toast.error("No se pudo registrar al recién nacido", { description: mensaje(error, "Intenta nuevamente.") });
        },
      },
    );
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    enviar(false);
  };

  const onVincular = (rn: RecienNacidoProvisional, c: CandidatoSermed) => {
    const ok = window.confirm(
      `¿Confirmás que ${rn.nombre} (provisional) y ${c.nombre} (SERMED, pk ${c.pkNum}) son el MISMO bebé?\n\n` +
        "Sus historias se van a ver juntas. Queda registrado con tu usuario.",
    );
    if (!ok) return;
    vincular.mutate(
      { idPaciente: rn.idPaciente, pkNum: c.pkNum },
      {
        onSuccess: () => toast.success("Recién nacido vinculado con SERMED."),
        onError: (error) => toast.error("No se pudo vincular", { description: mensaje(error, "Intenta nuevamente.") }),
      },
    );
  };

  const onDescartar = (rn: RecienNacidoProvisional, c: CandidatoSermed) => {
    const motivo = window.prompt(`¿Por qué ${c.nombre} NO es el mismo bebé? (opcional)`);
    if (motivo === null) return;
    descartar.mutate(
      { idPaciente: rn.idPaciente, pkNum: c.pkNum, motivo: motivo || undefined },
      {
        onSuccess: () => toast.success("Coincidencia descartada: no se volverá a proponer."),
        onError: (error) => toast.error("No se pudo descartar", { description: mensaje(error, "Intenta nuevamente.") }),
      },
    );
  };

  const onExtender = (rn: RecienNacidoProvisional) => {
    const motivo = window.prompt(
      `Extender la vigencia de ${rn.nombre} otros 60 días a partir de hoy.\n\n` +
        "Hacelo solo si cuentas con un documento que lo respalde. " +
        "Motivo (opcional, queda en la bitácora con tu usuario):",
    );
    if (motivo === null) return;
    extender.mutate(
      { idPaciente: rn.idPaciente, motivo: motivo || undefined },
      {
        onSuccess: (r) => toast.success(`Vigencia extendida hasta el ${fecha(r.vigencia)}.`),
        onError: (error) =>
          toast.error("No se pudo extender la vigencia", { description: mensaje(error, "Intenta nuevamente.") }),
      },
    );
  };

  const provisionales = data.provisionales;

  return (
    <section className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold">
          <Baby className="h-4 w-4" />
          Recién nacidos provisionales
        </h2>
        {puedeRegistrar && !abierto && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setForm({ ...FORM_VACIO, motherName: data.madreSugerida ?? "" });
              setAbierto(true);
            }}
          >
            Registrar recién nacido
          </Button>
        )}
      </div>

      {abierto && (
        <form onSubmit={onSubmit} className="grid gap-3 rounded-md bg-muted/40 p-3 sm:grid-cols-2">
          <p className="text-xs text-txt-muted sm:col-span-2">
            Solo hijos del titular que todavía no están en SERMED. Clínica: la de adscripción del titular.
            Vigencia: provisional hasta que Capital Humano lo registre.
          </p>
          <Input placeholder="Apellido paterno" {...campo("paternalSurname")} />
          <Input placeholder="Apellido materno" {...campo("maternalSurname")} />
          <Input placeholder="Nombre(s) (opcional)" title="Si aún no tiene nombre, déjalo vacío" {...campo("firstName")} />
          <Input type="date" aria-label="Fecha de nacimiento" {...campo("birthDate")} required />
          <select
            aria-label="Sexo"
            className="h-9 rounded-md border bg-background px-3 text-sm"
            value={form.sex}
            onChange={(e) => setForm({ ...form, sex: e.target.value as RegistrarRecienNacidoRequest["sex"] })}
          >
            <option value="F">{PATIENT_SEX_LABELS.F}</option>
            <option value="M">{PATIENT_SEX_LABELS.M}</option>
            <option value="X">{PATIENT_SEX_LABELS.X}</option>
          </select>
          <Input type="number" min={1} aria-label="Orden de nacimiento" title="1, 2... en partos múltiples" {...campo("birthOrder")} />
          <div className="space-y-1">
            <Input placeholder="Nombre de la madre (opcional)" {...campo("motherName")} />
            {data.madreSugerida && form.motherName === data.madreSugerida && (
              <p className="text-xs text-txt-muted">
                Propuesta desde SERMED (titular o esposa/concubina). Corrígela si no es la madre.
              </p>
            )}
          </div>
          <Input placeholder="CURP (opcional)" {...campo("curp")} />

          {enSermed && (
            <div role="alert" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 sm:col-span-2">
              <p className="font-medium">SERMED ya tiene un hijo de este titular con esa fecha de nacimiento y sexo:</p>
              <ul className="ml-4 list-disc">
                {enSermed.map((c) => (
                  <li key={c.pkNum}>
                    {c.nombre} — {fecha(c.fechaNacimiento)} (pk {c.pkNum})
                  </li>
                ))}
              </ul>
              <p className="mt-1">Atendelo desde SERMED. Registrá igual solo si es OTRO bebé (por ejemplo, gemelos).</p>
              <Button type="button" size="sm" variant="outline" className="mt-2" onClick={() => enviar(true)}>
                Es otro bebé: registrar igual
              </Button>
            </div>
          )}

          <div className="flex gap-2 sm:col-span-2">
            <Button type="submit" disabled={registrar.isPending}>
              Registrar
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setAbierto(false);
                setEnSermed(null);
                setForm(FORM_VACIO);
              }}
            >
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {provisionales.length === 0 && !abierto && (
        <p className="text-sm text-txt-muted">Este titular no tiene recién nacidos provisionales.</p>
      )}

      {provisionales.map((rn) => (
        <div key={rn.idPaciente} className="space-y-2 rounded-md border p-3 text-sm">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="font-medium">{rn.nombre}</span>
            <span>Hijo(a) del titular</span>
            <span>Orden {rn.orden}</span>
            <span>{fecha(rn.fechaNacimiento)}</span>
            <span>{sexo(rn.sexo)}</span>
            {!data.titularEsMujer && rn.madre && <span>Madre: {rn.madre}</span>}
            <span className="text-txt-muted">cd_familiar {rn.cdFamiliar}</span>
            {rn.estatus === "B" ? (
              <Badge variant="stable">Vinculado a SERMED (pk {rn.pkNumSermed})</Badge>
            ) : rn.vigente ? (
              <Badge variant="stable">Provisional · vigente hasta {fecha(rn.vigencia)}</Badge>
            ) : (
              <Badge variant="critical">Provisional · vencido {fecha(rn.vigencia)}</Badge>
            )}
            {rn.estatus === "A" && puedeRegistrar && diasParaVencer(rn.vigencia) <= DIAS_AVISO_VIGENCIA && (
              <Button size="sm" variant="outline" onClick={() => onExtender(rn)} disabled={extender.isPending}>
                <CalendarPlus className="mr-1 h-4 w-4" /> Extender vigencia
              </Button>
            )}
          </div>

          {rn.estatus === "A" && rn.candidatos.length > 0 && (
            <div className="rounded-md border border-sky-300 bg-sky-50 p-2">
              <p className="mb-1 font-medium text-sky-900">Posible coincidencia en SERMED:</p>
              {rn.candidatos.map((c) => (
                <div key={c.pkNum} className="flex flex-wrap items-center gap-2 py-1">
                  <span>
                    {c.nombre} — {fecha(c.fechaNacimiento)} · {sexo(c.sexo)} (pk {c.pkNum})
                  </span>
                  {puedeVincular && (
                    <>
                      <Button size="sm" onClick={() => onVincular(rn, c)} disabled={vincular.isPending}>
                        <Link2 className="mr-1 h-4 w-4" /> Es el mismo
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => onDescartar(rn, c)} disabled={descartar.isPending}>
                        <X className="mr-1 h-4 w-4" /> No es
                      </Button>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </section>
  );
}
