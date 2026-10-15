import { describe, expect, it } from "vitest";
import {
  describeCascade,
  describePreviewRestriction,
  mapNoteCancellationError,
} from "@features/expedientes/domain/note-cancellation";
import type { NoteCancellationPreview } from "@api/types";

const preview = (overrides: Partial<NoteCancellationPreview> = {}): NoteCancellationPreview => ({
  cancelable: true,
  visitStatus: "cerrada",
  alreadyCancelled: false,
  blockers: [],
  cascade: {
    prescriptionItems: 0,
    prescriptionAuthorizations: 0,
    diagnoses: 0,
    referrals: 0,
    referralStudies: 0,
    medicalLeaves: 0,
  },
  puedeAutorizar: true,
  puedeAutorizarMotivo: null,
  autoCancelacion: false,
  fueraAdscripcion: false,
  centroId: 1,
  ...overrides,
});

describe("describeCascade", () => {
  it("omite ceros y pluraliza", () => {
    const lines = describeCascade({
      ...preview().cascade,
      diagnoses: 1,
      prescriptionItems: 2,
    });
    expect(lines).toEqual(["1 diagnostico", "2 medicamentos de receta"]);
  });

  it("sin elementos devuelve lista vacia", () => {
    expect(describeCascade(preview().cascade)).toEqual([]);
  });
});

describe("describePreviewRestriction", () => {
  it("sin restriccion devuelve null", () => {
    expect(describePreviewRestriction(preview())).toBeNull();
  });

  it("nota ya cancelada", () => {
    expect(
      describePreviewRestriction(preview({ alreadyCancelled: true, visitStatus: "cancelada" })),
    ).toContain("ya fue cancelada");
  });

  it("nota no cerrada", () => {
    expect(describePreviewRestriction(preview({ visitStatus: "en_consulta" }))).toContain(
      "cerrada",
    );
  });

  it("autocancelacion", () => {
    expect(describePreviewRestriction(preview({ autoCancelacion: true }))).toContain(
      "medico tratante",
    );
  });

  it("sin designacion", () => {
    expect(
      describePreviewRestriction(
        preview({ puedeAutorizar: false, puedeAutorizarMotivo: "AUTHORIZER_NOT_DESIGNATED" }),
      ),
    ).toContain("designacion vigente");
  });

  it("centro no resuelto", () => {
    expect(
      describePreviewRestriction(
        preview({ puedeAutorizar: false, puedeAutorizarMotivo: "NOTE_CENTER_UNRESOLVED" }),
      ),
    ).toContain("centro de atencion");
  });
});

describe("mapNoteCancellationError", () => {
  it("REAUTH_FAILED limpia la contrasena sin bloquear", () => {
    const info = mapNoteCancellationError({ code: "REAUTH_FAILED", status: 403 });
    expect(info.clearPassword).toBe(true);
    expect(info.lockSubmit).toBe(false);
  });

  it("REAUTH_LOCKED bloquea el envio", () => {
    const info = mapNoteCancellationError({ code: "REAUTH_LOCKED", status: 423 });
    expect(info.lockSubmit).toBe(true);
    expect(info.clearPassword).toBe(true);
  });

  it("bloqueos 409 se toman de details.blockers", () => {
    const info = mapNoteCancellationError({
      code: "PRESCRIPTION_ITEM_DISPENSED",
      details: {
        blockers: [
          { code: "PRESCRIPTION_ITEM_DISPENSED", message: "m", ids: [1] },
          { code: "LEAVE_SENT_TO_RH", message: "m", ids: [2] },
        ],
      },
    });
    expect(info.blockers.map((b) => b.code)).toEqual([
      "PRESCRIPTION_ITEM_DISPENSED",
      "LEAVE_SENT_TO_RH",
    ]);
    expect(info.stale).toBe(true);
  });

  it("bloqueo sin details sintetiza uno desde el codigo", () => {
    const info = mapNoteCancellationError({ code: "STUDY_RESULT_ACTIVE" });
    expect(info.blockers).toHaveLength(1);
    expect(info.blockers[0].code).toBe("STUDY_RESULT_ACTIVE");
  });

  it("estado cambiado marca el preview como viejo", () => {
    expect(mapNoteCancellationError({ code: "NOTE_ALREADY_CANCELLED" }).stale).toBe(true);
    expect(mapNoteCancellationError({ code: "VISIT_STATE_INVALID" }).stale).toBe(true);
  });

  it("codigo desconocido usa el mensaje del error", () => {
    const info = mapNoteCancellationError({ code: "OTHER", message: "algo paso" });
    expect(info.message).toBe("algo paso");
  });

  it("valor no-objeto no revienta", () => {
    expect(mapNoteCancellationError(null).message).toBe("No se pudo cancelar la nota.");
  });
});
