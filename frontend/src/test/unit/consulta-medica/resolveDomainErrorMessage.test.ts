import { describe, expect, it } from "vitest";
import { ApiError } from "@api/utils/errors";
import { resolveDomainErrorMessage } from "@features/consulta-medica/modules/atencion/pages/DoctorConsultationPage.helpers";

const MESSAGES = { VALIDATION_ERROR: "Revisa los campos." };

describe("resolveDomainErrorMessage", () => {
  it("con detalle del backend muestra el motivo exacto", () => {
    const error = new ApiError("VALIDATION_ERROR", "Hay errores en el formulario", 422, {
      followUpDate: ["La fecha de seguimiento tiene que ser posterior a la consulta."],
    });
    expect(resolveDomainErrorMessage(error, MESSAGES, "Falló")).toBe(
      "La fecha de seguimiento tiene que ser posterior a la consulta.",
    );
  });

  it("varios detalles se unen", () => {
    const error = new ApiError("VALIDATION_ERROR", "x", 422, {
      morbidity: ["Indica si es primera vez."],
      cieCode: "La clave CIE no existe.",
    });
    expect(resolveDomainErrorMessage(error, MESSAGES, "Falló")).toBe(
      "Indica si es primera vez. La clave CIE no existe.",
    );
  });

  it("sin detalle usa el mensaje del código", () => {
    const error = new ApiError("VALIDATION_ERROR", "x", 422);
    expect(resolveDomainErrorMessage(error, MESSAGES, "Falló")).toBe("Revisa los campos.");
  });
});
