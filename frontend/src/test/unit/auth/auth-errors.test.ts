import { describe, expect, it } from "vitest";
import {
  ApiError,
  ERROR_CODES,
  ERROR_MESSAGES,
  isExpectedAuthErrorForTelemetry,
} from "@api/utils/errors";

describe("auth telemetry error classification", () => {
  it("classifies expected auth 401 errors", () => {
    const error = new ApiError(
      ERROR_CODES.SESSION_EXPIRED,
      "Sesion expirada",
      401,
    );

    expect(isExpectedAuthErrorForTelemetry(error)).toBe(true);
  });

  it("does not classify non-auth unexpected errors", () => {
    const error = new ApiError(
      ERROR_CODES.INTERNAL_SERVER_ERROR,
      "Error del servidor",
      500,
    );

    expect(isExpectedAuthErrorForTelemetry(error)).toBe(false);
  });
});

describe("session revocation error messages", () => {
  it("has a Spanish message for self force-logout", () => {
    expect(ERROR_MESSAGES[ERROR_CODES.SELF_FORCE_LOGOUT_NOT_ALLOWED]).toBe(
      "No puedes forzar el cierre de tu propia sesión",
    );
    expect(
      ApiError.getMessage(ERROR_CODES.SELF_FORCE_LOGOUT_NOT_ALLOWED),
    ).toBe("No puedes forzar el cierre de tu propia sesión");
  });
});
