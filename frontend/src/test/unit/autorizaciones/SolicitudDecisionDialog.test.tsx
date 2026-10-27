import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import type { SolicitudDetalle } from "@api/types/autorizaciones/solicitudes.types";
import { SolicitudDecisionDialog } from "@features/autorizaciones/components/SolicitudDecisionDialog";

const decidir = vi.fn();

vi.mock("@features/autorizaciones/mutations/useSolicitudMutations", () => ({
  useDecidirSolicitud: () => ({ mutateAsync: decidir, isPending: false }),
}));

vi.mock("@features/autorizaciones/queries/useSolicitudes", () => ({
  useMotivosRechazo: () => ({
    data: {
      items: [
        { id: 1, clave: "NO_JUSTIFICADO", descripcion: "No justificado clínicamente", requiereDescripcionLibre: false },
      ],
    },
  }),
}));

const solicitud = {
  uuid: "6f1c0000-0000-4000-8000-000000000001",
  folio: "AUT-2026-000123",
  tipo: { clave: "REC", nombre: "Recetas" },
  centro: { id: 3, nombre: "Clínica Norte", clues: "DFSSA000123" },
  version: 4,
} as unknown as SolicitudDetalle;

describe("SolicitudDecisionDialog", () => {
  beforeEach(() => {
    decidir.mockReset();
    decidir.mockResolvedValue({});
  });

  it("muestra que se autoriza y no envia sin contraseña", async () => {
    const user = userEvent.setup();
    render(<SolicitudDecisionDialog decision="APROBAR" solicitud={solicitud} onClose={vi.fn()} />);

    expect(screen.getByText(/AUT-2026-000123/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Autorizar" }));

    expect(await screen.findByText(/Escribe tu contraseña/i)).toBeVisible();
    expect(decidir).not.toHaveBeenCalled();
  });

  it("autoriza con la contraseña y la version que se esta viendo", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<SolicitudDecisionDialog decision="APROBAR" solicitud={solicitud} onClose={onClose} />);

    await user.type(screen.getByLabelText(/Contraseña/i), "Clave_12345");
    await user.click(screen.getByRole("button", { name: "Autorizar" }));

    await waitFor(() =>
      expect(decidir).toHaveBeenCalledWith({
        uuid: solicitud.uuid,
        data: { decision: "APROBAR", motivoId: null, descripcionMotivo: null, version: 4, credencial: "Clave_12345" },
      }),
    );
    expect(onClose).toHaveBeenCalled();
  });

  it("rechazar exige elegir un motivo", async () => {
    const user = userEvent.setup();
    render(<SolicitudDecisionDialog decision="RECHAZAR" solicitud={solicitud} onClose={vi.fn()} />);

    await user.type(screen.getByLabelText(/Contraseña/i), "Clave_12345");
    await user.click(screen.getByRole("button", { name: "Rechazar" }));

    expect(await screen.findByText(/Selecciona el motivo/i)).toBeVisible();
    expect(decidir).not.toHaveBeenCalled();
  });
});
