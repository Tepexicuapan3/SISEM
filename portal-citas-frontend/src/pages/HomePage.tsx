import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { obtenerNucleo, type MiembroNucleo } from "@/api/nucleo.api";
import {
  listarConsultorios,
  listarCentros,
  type Consultorio,
  type Centro,
} from "@/api/consultorios.api";
import type { Slot } from "@/api/slots.api";
import { ApiError } from "@/api/client";
import { clearToken } from "@/api/authStore";
import { setReservaDraft } from "@/api/reservaDraftStore";
import ErrorAlert from "@/components/ErrorAlert";
import SlotsMonthCalendar from "@/components/SlotsMonthCalendar";
import { ParticlesBackground } from "@/components/ParticlesBackground";
import AnunciosBanner from "@/components/AnunciosBanner";

type Step = "miembro" | "horario";

/** Mismo criterio que LoginPage.tsx: ApiError trae el mensaje ya listo para mostrar. */
function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Ocurrió un error inesperado. Intenta de nuevo.";
}

/**
 * Flujo de 3 pasos del portal:
 *   1. Elegir para quién es la cita (núcleo familiar).
 *   2. Elegir consultorio (OBLIGATORIO — a diferencia de la especialidad que
 *      reemplaza, no hay opción "Todas": sin consultorio no hay eje de
 *      búsqueda, ver `sdd/portal-citas-consultorios/spec`) y buscar horario
 *      con el calendario mensual de disponibilidad.
 *   3. Elegir slot -> guarda el draft y navega a /reservar/confirmar
 *      (la reserva real, POST /portal/citas, es Fase F3).
 */
export default function HomePage() {
  const navigate = useNavigate();

  const [step, setStep] = useState<Step>("miembro");

  // Paso 1: núcleo familiar.
  const [nucleo, setNucleo] = useState<MiembroNucleo[]>([]);
  const [nucleoLoading, setNucleoLoading] = useState(true);
  const [nucleoError, setNucleoError] = useState<string | null>(null);
  const [miembro, setMiembro] = useState<MiembroNucleo | null>(null);

  // Paso 2: clínica (opcional, "Todas las clínicas" por defecto) +
  // consultorio (obligatorio). El calendario mensual de slots vive en
  // `SlotsMonthCalendar`, que se refresca solo cuando cambia
  // `consultorioId` o el mes visible.
  const [centros, setCentros] = useState<Centro[]>([]);
  const [centroId, setCentroId] = useState<number | "">("");
  const [consultorios, setConsultorios] = useState<Consultorio[]>([]);
  const [consultoriosError, setConsultoriosError] = useState<string | null>(null);
  const [consultorioId, setConsultorioId] = useState<number | "">("");

  useEffect(() => {
    let activo = true;
    setNucleoLoading(true);
    obtenerNucleo()
      .then((data) => {
        if (activo) setNucleo(data);
      })
      .catch((err) => {
        if (activo) setNucleoError(messageFor(err));
      })
      .finally(() => {
        if (activo) setNucleoLoading(false);
      });
    return () => {
      activo = false;
    };
  }, []);

  useEffect(() => {
    if (step !== "horario" || !miembro) return;
    let activo = true;
    // Solo las clínicas del paciente elegido (cada familiar puede tener otra).
    setCentroId("");
    listarCentros(miembro.miembroId)
      .then((data) => {
        if (activo) setCentros(data);
      })
      .catch(() => {
        // No bloqueante (`sdd/portal-citas-filtro-clinica/design`): si
        // falla el catálogo de clínicas, el selector se degrada a solo
        // "Todas las clínicas" — el filtro por consultorio sigue andando.
      });
    return () => {
      activo = false;
    };
  }, [step, miembro]);

  // Cascada: cambiar de clínica resetea el consultorio elegido (y con él,
  // el calendario — `SlotsMonthCalendar` se desmonta por el guard
  // `consultorioId !== ""`).
  useEffect(() => {
    if (step !== "horario" || !miembro) return;
    let activo = true;
    setConsultoriosError(null);
    setConsultorioId("");
    listarConsultorios(centroId === "" ? undefined : centroId, miembro.miembroId)
      .then((data) => {
        if (activo) setConsultorios(data);
      })
      .catch((err) => {
        // A diferencia del catálogo de especialidades que reemplaza, el
        // consultorio es OBLIGATORIO (sin "Todas") — sin catálogo no hay
        // eje de búsqueda posible, así que acá SÍ se muestra el error.
        if (activo) setConsultoriosError(messageFor(err));
      });
    return () => {
      activo = false;
    };
  }, [step, centroId, miembro]);

  const handleElegirMiembro = (elegido: MiembroNucleo) => {
    setMiembro(elegido);
    setStep("horario");
  };

  const handleCambiarPaciente = () => {
    setStep("miembro");
  };

  const handleElegirSlot = (slot: Slot) => {
    if (!miembro) return;
    setReservaDraft(miembro, slot);
    navigate("/reservar/confirmar");
  };

  const handleLogout = () => {
    clearToken();
    navigate("/login", { replace: true });
  };

  return (
    <main className="relative min-h-screen w-full overflow-hidden bg-app p-4 sm:p-6">
      <ParticlesBackground quantity={150} staticity={7} ease={50} />
      <div
        className="pointer-events-none absolute inset-0 z-0 bg-radial-[at_center_center] from-transparent via-transparent to-app/90"
        aria-hidden="true"
      />

      <div className="relative z-10 mx-auto flex max-w-4xl flex-col gap-6">
        <header className="flex items-center justify-between rounded-2xl border border-line-struct bg-paper/85 px-4 py-3 shadow-sm backdrop-blur-md sm:px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex items-center gap-1.5">
              <img
                src="/assets/brand/logos/primary/sisem.webp"
                alt="Logo SISEM"
                className="h-9 w-9 object-contain"
              />
              {/* Mismo conector del login (sistemas conectados), pero acá el
                  pulso corre solo unas vueltas al entrar (`animate-network-pulse-once`,
                  3 iteraciones) y se detiene — este header queda montado en
                  toda pantalla mientras el paciente usa el portal, así que
                  el loop infinito del login sería distracción constante. */}
              <div className="relative h-px w-4" aria-hidden="true">
                <span className="absolute inset-0 bg-gradient-to-r from-line-struct via-brand/50 to-line-struct" />
                <span className="animate-network-pulse-once absolute top-1/2 size-1.5 -translate-y-1/2 rounded-full bg-brand shadow-[0_0_6px_var(--action-main)]" />
              </div>
              <img
                src="/assets/brand/logos/secondary/logo_portal_citas.png"
                alt="Logo Citas en Línea"
                className="h-9 w-9 object-contain"
              />
            </div>
            <h1 className="text-xl font-display font-semibold text-txt-body">Citas en Línea</h1>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/mis-citas"
              className="rounded-md border border-line-struct px-3 py-1.5 text-sm font-medium text-txt-body hover:bg-subtle"
            >
              Mis citas
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-md border border-line-struct px-3 py-1.5 text-sm font-medium text-txt-body hover:bg-subtle"
            >
              Cerrar sesión
            </button>
          </div>
        </header>

        <AnunciosBanner />

        {step === "miembro" && (
          <section className="flex flex-col gap-4 rounded-2xl border border-line-struct bg-paper/85 p-4 shadow-sm backdrop-blur-md sm:p-6">
            <h2 className="text-lg font-medium text-txt-body">
              ¿Para quién es la cita?
            </h2>

            {nucleoLoading && (
              <p className="text-sm text-txt-muted">Cargando pacientes…</p>
            )}
            {nucleoError && <ErrorAlert message={nucleoError} />}

            {!nucleoLoading && !nucleoError && nucleo.length === 0 && (
              <p className="text-sm text-txt-muted">
                No encontramos pacientes asociados a tu sesión.
              </p>
            )}

            {!nucleoLoading && !nucleoError && nucleo.length > 0 && (
              <div className="grid gap-3 sm:grid-cols-2">
                {nucleo.map((m) => (
                  <button
                    key={m.miembroId}
                    type="button"
                    onClick={() => handleElegirMiembro(m)}
                    className="flex items-center justify-between gap-3 rounded-lg border border-line-struct bg-paper px-4 py-3 text-left shadow-sm transition-colors hover:border-brand hover:bg-subtle"
                  >
                    <span className="font-medium text-txt-body">
                      {m.nombreVisible}
                    </span>
                    {m.esMenor && (
                      <span className="shrink-0 rounded-full bg-status-alert/15 px-2 py-0.5 text-xs font-semibold text-status-alert">
                        Menor
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </section>
        )}

        {step === "horario" && miembro && (
          <section className="flex flex-col gap-4 rounded-2xl border border-line-struct bg-paper/85 p-4 shadow-sm backdrop-blur-md sm:p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium text-txt-body">
                Buscar horario para {miembro.nombreVisible}
              </h2>
              <button
                type="button"
                onClick={handleCambiarPaciente}
                className="text-sm font-medium text-txt-muted underline hover:text-txt-body"
              >
                Cambiar paciente
              </button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="clinica"
                  className="flex items-center gap-1.5 text-sm font-medium text-txt-body"
                >
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="text-brand"
                    aria-hidden="true"
                  >
                    <path d="M3 21h18" />
                    <path d="M5 21V7l7-4 7 4v14" />
                    <path d="M9 9h1M14 9h1M9 13h1M14 13h1M10 21v-4h4v4" />
                  </svg>
                  Clínica
                </label>
                <div className="relative">
                  <select
                    id="clinica"
                    className="w-full appearance-none rounded-xl border border-line-struct bg-paper px-3.5 py-2.5 text-base text-txt-body shadow-sm transition-colors hover:border-brand/40 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/15"
                    value={centroId}
                    onChange={(e) =>
                      setCentroId(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  >
                    <option value="">Todas las clínicas</option>
                    {centros.map((c) => (
                      <option key={c.centroId} value={c.centroId}>
                        {c.nombre}
                      </option>
                    ))}
                  </select>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-txt-hint"
                    aria-hidden="true"
                  >
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="consultorio"
                  className="flex items-center gap-1.5 text-sm font-medium text-txt-body"
                >
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="text-brand"
                    aria-hidden="true"
                  >
                    <path d="M14 3v18" />
                    <path d="M5 21V5a2 2 0 0 1 2-2h11.5a.5.5 0 0 1 .5.5V21" />
                    <path d="M18 12h.01" />
                  </svg>
                  Consultorio
                </label>
                <div className="relative">
                  <select
                    id="consultorio"
                    className="w-full appearance-none rounded-xl border border-line-struct bg-paper px-3.5 py-2.5 text-base text-txt-body shadow-sm transition-colors hover:border-brand/40 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/15"
                    value={consultorioId}
                    onChange={(e) =>
                      setConsultorioId(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  >
                    <option value="" disabled>
                      Selecciona un consultorio
                    </option>
                    {consultorios.map((c) => (
                      <option key={c.consultorioId} value={c.consultorioId}>
                        {c.nombre}
                        {c.centroNombre ? ` · ${c.centroNombre}` : ""}
                      </option>
                    ))}
                  </select>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-txt-hint"
                    aria-hidden="true"
                  >
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                </div>
              </div>
            </div>

            {consultoriosError && <ErrorAlert message={consultoriosError} />}

            {consultorioId !== "" && (
              <SlotsMonthCalendar consultorioId={consultorioId} onSlotClick={handleElegirSlot} />
            )}
          </section>
        )}
      </div>
    </main>
  );
}
