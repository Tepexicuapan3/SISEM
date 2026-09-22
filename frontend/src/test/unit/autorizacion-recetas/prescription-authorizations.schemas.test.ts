import { describe, expect, it } from "vitest";
import { rejectPrescriptionSchema } from "@features/autorizacion-recetas/domain/prescription-authorizations.schemas";

describe("rejectPrescriptionSchema", () => {
  it("rejects an empty reason", () => {
    const result = rejectPrescriptionSchema.safeParse({ reason: "" });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((issue) => issue.message)).toContain(
        "Indica el motivo del rechazo",
      );
    }
  });

  it("rejects a reason longer than 500 characters", () => {
    const result = rejectPrescriptionSchema.safeParse({ reason: "a".repeat(501) });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.map((issue) => issue.message)).toContain(
        "Maximo 500 caracteres",
      );
    }
  });

  it("accepts a valid reason", () => {
    const result = rejectPrescriptionSchema.safeParse({ reason: "Dosis incorrecta" });

    expect(result.success).toBe(true);
  });
});
