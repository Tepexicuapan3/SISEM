import { describe, expect, it } from "vitest";
import type { MotivoRechazo } from "@api/types/autorizaciones/solicitudes.types";
import { buildDecisionSchema } from "@features/autorizaciones/domain/decision.schema";
import {
  describirEstatusSolicitud,
  tiempoRestante,
} from "@features/autorizaciones/domain/solicitud.format";

const AHORA = new Date("2026-10-27T10:00:00");

describe("tiempo restante de una solicitud", () => {
  it("vencida si ya paso la fecha limite", () => {
    expect(tiempoRestante("2026-10-27T09:59:00", AHORA)).toEqual({ texto: "Vencida", urgente: true });
  });

  it("en minutos, horas o dias", () => {
    expect(tiempoRestante("2026-10-27T10:45:00", AHORA)).toEqual({ texto: "Vence en 45 min", urgente: true });
    expect(tiempoRestante("2026-10-27T15:00:00", AHORA)).toEqual({ texto: "Vence en 5 h", urgente: false });
    expect(tiempoRestante("2026-10-30T10:00:00", AHORA)).toEqual({ texto: "Vence en 3 d", urgente: false });
  });
});

describe("estatus de la solicitud", () => {
  it("cada estatus tiene etiqueta y color", () => {
    expect(describirEstatusSolicitud("PENDIENTE")).toEqual({ etiqueta: "Pendiente", variante: "alert" });
    expect(describirEstatusSolicitud("AUTORIZADA")).toEqual({ etiqueta: "Autorizada", variante: "stable" });
    expect(describirEstatusSolicitud("RECHAZADA")).toEqual({ etiqueta: "Rechazada", variante: "critical" });
    expect(describirEstatusSolicitud("VENCIDA").etiqueta).toBe("Vencida");
  });
});

describe("validacion de la decision", () => {
  const motivos: MotivoRechazo[] = [
    { id: 1, clave: "NO_JUSTIFICADO", descripcion: "No justificado", requiereDescripcionLibre: false },
    { id: 9, clave: "OTRO", descripcion: "Otro motivo", requiereDescripcionLibre: true },
  ];
  const esquema = buildDecisionSchema(motivos);
  const base = { decision: "APROBAR" as const, motivoId: 0, descripcionMotivo: "", credencial: "Clave_1" };

  it("aprobar solo exige la contraseña", () => {
    expect(esquema.safeParse(base).success).toBe(true);
    expect(esquema.safeParse({ ...base, credencial: "" }).success).toBe(false);
  });

  it("rechazar exige motivo y, si es Otro, descripcion", () => {
    const rechazo = { ...base, decision: "RECHAZAR" as const };
    expect(esquema.safeParse(rechazo).success).toBe(false);
    expect(esquema.safeParse({ ...rechazo, motivoId: 1 }).success).toBe(true);
    expect(esquema.safeParse({ ...rechazo, motivoId: 9 }).success).toBe(false);
    expect(esquema.safeParse({ ...rechazo, motivoId: 9, descripcionMotivo: "Falta estudio previo" }).success).toBe(true);
  });
});
