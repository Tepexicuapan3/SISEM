import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { CancelarNotaDialog } from "@features/expedientes/components/CancelarNotaDialog";
import { noteCancellationAPI } from "@api/resources/note-cancellation.api";
import { ApiError } from "@api/utils/errors";
import type {
  CancelConsultationNoteResponse,
  NoteCancellationPreview,
} from "@api/types";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

// Radix Select no es operable en happy-dom: se reemplaza por un <select> nativo.
vi.mock("@shared/ui/select", () => ({
  Select: ({
    value,
    onValueChange,
    children,
  }: {
    value: string;
    onValueChange: (value: string) => void;
    children: React.ReactNode;
  }) => (
    <select
      aria-label="Motivo"
      value={value}
      onChange={(event) => onValueChange(event.target.value)}
    >
      <option value="">Selecciona</option>
      {children}
    </select>
  ),
  SelectTrigger: () => null,
  SelectValue: () => null,
  SelectContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectItem: ({ value, children }: { value: string; children: React.ReactNode }) => (
    <option value={value}>{children}</option>
  ),
}));

vi.mock(
  "@features/admin/modules/catalogos/motivos-cancelacion-nota/queries/useMotivoCancelacionNotaList",
  () => ({
    useMotivoCancelacionNotaList: () => ({
      data: {
        items: [
          { id: 1, name: "Paciente equivocado", isActive: true },
          { id: 2, name: "Error de captura", isActive: true },
        ],
      },
    }),
  }),
);

const buildPreview = (
  overrides: Partial<NoteCancellationPreview> = {},
): NoteCancellationPreview => ({
  cancelable: true,
  visitStatus: "cerrada",
  alreadyCancelled: false,
  blockers: [],
  cascade: {
    prescriptionItems: 3,
    prescriptionAuthorizations: 0,
    diagnoses: 1,
    referrals: 1,
    referralStudies: 2,
    medicalLeaves: 0,
  },
  puedeAutorizar: true,
  puedeAutorizarMotivo: null,
  autoCancelacion: false,
  fueraAdscripcion: false,
  centroId: 5,
  ...overrides,
});

const successResponse: CancelConsultationNoteResponse = {
  cancellationId: 9,
  visit: { id: 77, status: "cancelada" },
  hashContenido: "a".repeat(64),
  metodoFirma: "SIMPLE",
  fueraAdscripcion: false,
  cascade: buildPreview().cascade,
};

const renderDialog = (onOpenChange = vi.fn()) => {
  render(<CancelarNotaDialog visitId={77} open onOpenChange={onOpenChange} />);
  return onOpenChange;
};

const fillAndSubmit = async (password = "secreto") => {
  const user = userEvent.setup();
  await screen.findByLabelText("Motivo");
  await user.selectOptions(screen.getByLabelText("Motivo"), "1");
  await user.type(screen.getByLabelText("Tu contrasena"), password);
  await user.click(screen.getByRole("button", { name: "Cancelar nota" }));
  return user;
};

describe("CancelarNotaDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("muestra los conteos de la cascada del preview", async () => {
    vi.spyOn(noteCancellationAPI, "getPreview").mockResolvedValue(buildPreview());
    renderDialog();

    const cascade = await screen.findByTestId("cancel-note-cascade");
    expect(cascade).toHaveTextContent("1 diagnostico");
    expect(cascade).toHaveTextContent("3 medicamentos de receta");
    expect(cascade).toHaveTextContent("2 estudios de pase");
    expect(cascade).not.toHaveTextContent("incapacidad");
  });

  it("avisa cuando la nota esta fuera de la adscripcion del autorizador", async () => {
    vi.spyOn(noteCancellationAPI, "getPreview").mockResolvedValue(
      buildPreview({ fueraAdscripcion: true }),
    );
    renderDialog();

    expect(await screen.findByTestId("cancel-note-outside-assignment")).toBeInTheDocument();
  });

  it("muestra los bloqueos con mensaje legible y no ofrece el formulario", async () => {
    vi.spyOn(noteCancellationAPI, "getPreview").mockResolvedValue(
      buildPreview({
        cancelable: false,
        blockers: [
          { code: "PRESCRIPTION_ITEM_DISPENSED", message: "x", ids: [4] },
          { code: "LEAVE_SENT_TO_RH", message: "y", ids: [2] },
        ],
      }),
    );
    renderDialog();

    const blockers = await screen.findByTestId("cancel-note-blockers");
    expect(blockers).toHaveTextContent("ya fueron surtidos");
    expect(blockers).toHaveTextContent("enviada o verificada por RH");
    expect(screen.queryByLabelText("Tu contrasena")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar nota" })).toBeDisabled();
  });

  it("explica cuando el usuario no tiene designacion vigente (puedeAutorizar false)", async () => {
    vi.spyOn(noteCancellationAPI, "getPreview").mockResolvedValue(
      buildPreview({
        cancelable: false,
        puedeAutorizar: false,
        puedeAutorizarMotivo: "AUTHORIZER_NOT_DESIGNATED",
      }),
    );
    renderDialog();

    expect(await screen.findByTestId("cancel-note-restriction")).toHaveTextContent(
      "designacion vigente",
    );
    expect(screen.queryByLabelText("Tu contrasena")).not.toBeInTheDocument();
  });

  it("envia motivo, detalle y contrasena; al exito cierra el modal", async () => {
    vi.spyOn(noteCancellationAPI, "getPreview").mockResolvedValue(buildPreview());
    const cancelSpy = vi
      .spyOn(noteCancellationAPI, "cancel")
      .mockResolvedValue(successResponse);
    const onOpenChange = renderDialog();

    const user = userEvent.setup();
    await screen.findByLabelText("Motivo");
    await user.selectOptions(screen.getByLabelText("Motivo"), "2");
    await user.type(screen.getByLabelText("Detalle (opcional)"), "  captura doble  ");
    await user.type(screen.getByLabelText("Tu contrasena"), "secreto");
    await user.click(screen.getByRole("button", { name: "Cancelar nota" }));

    await waitFor(() => expect(cancelSpy).toHaveBeenCalledTimes(1));
    expect(cancelSpy).toHaveBeenCalledWith(77, {
      motivoId: 2,
      motivoDetalle: "captura doble",
      password: "secreto",
    });
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("no habilita el envio sin motivo o sin contrasena", async () => {
    vi.spyOn(noteCancellationAPI, "getPreview").mockResolvedValue(buildPreview());
    renderDialog();

    const user = userEvent.setup();
    await screen.findByLabelText("Motivo");
    const submit = screen.getByRole("button", { name: "Cancelar nota" });
    expect(submit).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("Motivo"), "1");
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText("Tu contrasena"), "x");
    expect(submit).toBeEnabled();
  });

  it("403 REAUTH_FAILED: mantiene el modal, limpia la contrasena y deja reintentar", async () => {
    vi.spyOn(noteCancellationAPI, "getPreview").mockResolvedValue(buildPreview());
    vi.spyOn(noteCancellationAPI, "cancel").mockRejectedValue(
      new ApiError("REAUTH_FAILED", "Contrasena incorrecta", 403),
    );
    const onOpenChange = renderDialog();

    await fillAndSubmit();

    expect(await screen.findByTestId("cancel-note-error")).toHaveTextContent(
      "La contrasena es incorrecta.",
    );
    expect(screen.getByLabelText("Tu contrasena")).toHaveValue("");
    expect(screen.getByLabelText("Tu contrasena")).toBeEnabled();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("423 REAUTH_LOCKED: deshabilita contrasena y envio", async () => {
    vi.spyOn(noteCancellationAPI, "getPreview").mockResolvedValue(buildPreview());
    vi.spyOn(noteCancellationAPI, "cancel").mockRejectedValue(
      new ApiError("REAUTH_LOCKED", "Bloqueado", 423),
    );
    renderDialog();

    const user = await fillAndSubmit();

    expect(await screen.findByTestId("cancel-note-error")).toHaveTextContent("bloqueada");
    expect(screen.getByLabelText("Tu contrasena")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancelar nota" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Cancelar nota" }));
    expect(noteCancellationAPI.cancel).toHaveBeenCalledTimes(1);
  });

  it("409 con bloqueos: lista cada bloqueo y no cierra el modal", async () => {
    vi.spyOn(noteCancellationAPI, "getPreview").mockResolvedValue(buildPreview());
    vi.spyOn(noteCancellationAPI, "cancel").mockRejectedValue(
      new ApiError("STUDY_RESULT_ACTIVE", "x", 409, {
        blockers: [
          { code: "STUDY_RESULT_ACTIVE", message: "x", ids: [1] },
        ] as unknown as string[],
      }),
    );
    const onOpenChange = renderDialog();

    await fillAndSubmit();

    const error = await screen.findByTestId("cancel-note-error");
    expect(error).toHaveTextContent("resultados de estudio activos");
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("403 SELF_AUTHORIZATION_NOT_ALLOWED muestra su mensaje", async () => {
    vi.spyOn(noteCancellationAPI, "getPreview").mockResolvedValue(buildPreview());
    vi.spyOn(noteCancellationAPI, "cancel").mockRejectedValue(
      new ApiError("SELF_AUTHORIZATION_NOT_ALLOWED", "x", 403),
    );
    renderDialog();

    await fillAndSubmit();

    expect(await screen.findByTestId("cancel-note-error")).toHaveTextContent(
      "medico tratante",
    );
  });
});
