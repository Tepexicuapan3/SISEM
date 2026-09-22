import { describe, expect, it } from "vitest";
import { ApiError } from "@api/utils/errors";
import { getPrescriptionAuthErrorMessage } from "@features/autorizacion-recetas/utils/prescription-authorizations.feedback";

describe("getPrescriptionAuthErrorMessage", () => {
  it("maps AUTHORIZATION_NOT_FOUND (404)", () => {
    const error = new ApiError("AUTHORIZATION_NOT_FOUND", "Not found", 404);

    expect(getPrescriptionAuthErrorMessage(error, "fallback")).toBe(
      "La autorizacion ya no existe.",
    );
  });

  it("maps AUTHORIZATION_ALREADY_RESOLVED (409)", () => {
    const error = new ApiError("AUTHORIZATION_ALREADY_RESOLVED", "Conflict", 409);

    expect(getPrescriptionAuthErrorMessage(error, "fallback")).toBe(
      "Otro autorizador ya resolvio esta receta.",
    );
  });

  it("maps SELF_AUTHORIZATION_NOT_ALLOWED (403)", () => {
    const error = new ApiError("SELF_AUTHORIZATION_NOT_ALLOWED", "Forbidden", 403);

    expect(getPrescriptionAuthErrorMessage(error, "fallback")).toBe(
      "No puedes autorizar tu propia receta.",
    );
  });

  it("maps ROLE_NOT_ALLOWED (403)", () => {
    const error = new ApiError("ROLE_NOT_ALLOWED", "Forbidden", 403);

    expect(getPrescriptionAuthErrorMessage(error, "fallback")).toBe(
      "No tienes permiso para autorizar recetas.",
    );
  });

  it("maps VALIDATION_ERROR (422)", () => {
    const error = new ApiError("VALIDATION_ERROR", "Unprocessable", 422);

    expect(getPrescriptionAuthErrorMessage(error, "fallback")).toBe(
      "Revisa los datos capturados.",
    );
  });

  it("falls back for unmapped errors", () => {
    expect(getPrescriptionAuthErrorMessage(new Error("boom"), "fallback")).toBe("fallback");
  });
});
