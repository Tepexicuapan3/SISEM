import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@/test/utils";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { ApiError } from "@api/utils/errors";
import { AuthorizePrescriptionDialog } from "@features/autorizacion-recetas/components/AuthorizePrescriptionDialog";
import { RejectPrescriptionDialog } from "@features/autorizacion-recetas/components/RejectPrescriptionDialog";
import { rutaSolicitudEnBandeja } from "@features/autorizacion-recetas/utils/solicitud-en-bandeja";
import { getPrescriptionAuthErrorMessage } from "@features/autorizacion-recetas/utils/prescription-authorizations.feedback";
import type { PrescriptionAuthorizationItem } from "@api/types";

// Con AUTORIZACIONES_RECETAS_V2, una receta que espera en el motor responde 409
// AUTHORIZATION_MANAGED_BY_INBOX con el uuid de su solicitud: la pantalla avisa
// y ofrece ir a la solicitud en vez de mostrar un error generico.

const UUID = "272a4d41-c8df-44c7-b5e6-cef57818f57b";
const gestionadaEnBandeja = () =>
  new ApiError("AUTHORIZATION_MANAGED_BY_INBOX", "Se autoriza desde Solicitudes", 409, { solicitudUuid: UUID });

const authorize = vi.fn();
const reject = vi.fn();
vi.mock("@features/autorizacion-recetas/mutations/useAuthorizePrescription", () => ({
  useAuthorizePrescription: () => ({ mutateAsync: authorize, isPending: false }),
}));
vi.mock("@features/autorizacion-recetas/mutations/useRejectPrescription", () => ({
  useRejectPrescription: () => ({ mutateAsync: reject, isPending: false }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), info: vi.fn(), warning: vi.fn(), error: vi.fn() },
}));

const AUTORIZACION = {
  id: 7,
  noExp: "1234",
  medicationsCount: 1,
  specializedCount: 1,
  controlledCount: 0,
} as unknown as PrescriptionAuthorizationItem;

describe("receta gestionada en la bandeja", () => {
  beforeEach(() => vi.clearAllMocks());

  it("arma la ruta de la solicitud con el uuid del error", () => {
    expect(rutaSolicitudEnBandeja(gestionadaEnBandeja())).toBe(`/clinico/autorizaciones/${UUID}`);
  });

  it("sin uuid lleva a la bandeja; con otro error no aplica", () => {
    expect(rutaSolicitudEnBandeja(new ApiError("AUTHORIZATION_MANAGED_BY_INBOX", "x", 409))).toBe(
      "/clinico/autorizaciones",
    );
    expect(rutaSolicitudEnBandeja(new ApiError("ROLE_NOT_ALLOWED", "x", 403))).toBeNull();
  });

  it("tiene mensaje propio", () => {
    expect(getPrescriptionAuthErrorMessage(gestionadaEnBandeja(), "fallback")).toMatch(
      /Solicitudes de autorización/,
    );
  });

  it("al autorizar avisa, ofrece ir a la solicitud y cierra el dialogo", async () => {
    authorize.mockRejectedValueOnce(gestionadaEnBandeja());
    const onOpenChange = vi.fn();
    render(<AuthorizePrescriptionDialog open onOpenChange={onOpenChange} authorization={AUTORIZACION} />);

    await userEvent.click(screen.getByRole("button", { name: "Autorizar" }));

    expect(toast.info).toHaveBeenCalledWith(
      expect.stringMatching(/Solicitudes de autorización/),
      expect.objectContaining({ action: expect.objectContaining({ label: "Ver solicitud" }) }),
    );
    expect(toast.error).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("al rechazar hace lo mismo", async () => {
    reject.mockRejectedValueOnce(gestionadaEnBandeja());
    const onOpenChange = vi.fn();
    render(<RejectPrescriptionDialog open onOpenChange={onOpenChange} authorization={AUTORIZACION} />);

    await userEvent.type(screen.getByRole("textbox"), "Dosis fuera de rango para el paciente");
    await userEvent.click(screen.getByRole("button", { name: /Rechazar/i }));

    expect(toast.info).toHaveBeenCalledWith(
      expect.stringMatching(/Solicitudes de autorización/),
      expect.objectContaining({ action: expect.objectContaining({ label: "Ver solicitud" }) }),
    );
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
