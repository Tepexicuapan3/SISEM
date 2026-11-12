import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { SolicitudAccionOrigen } from "@features/autorizaciones/components/SolicitudAccionOrigen";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { usePrintDocument } from "@shared/hooks/usePrintDocument";

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: vi.fn(),
}));
vi.mock("@shared/hooks/usePrintDocument", () => ({ usePrintDocument: vi.fn() }));

describe("SolicitudAccionOrigen (detalle de la solicitud)", () => {
  const print = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePrintDocument).mockReturnValue({ print, isPrinting: false });
    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability: () => true,
    } as unknown as ReturnType<typeof usePermissionDependencies>);
  });

  it("con la receta autorizada ofrece imprimirla", async () => {
    const user = userEvent.setup();
    render(<SolicitudAccionOrigen accion={{ tipo: "IMPRIMIR_RECETA", visitId: 15 }} />);

    await user.click(screen.getByRole("button", { name: /Imprimir receta/ }));

    expect(usePrintDocument).toHaveBeenCalledWith("receta");
    expect(print).toHaveBeenCalledWith(15);
  });

  it("sin accion no muestra nada", () => {
    const { container } = render(<SolicitudAccionOrigen accion={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("sin permiso de imprimir no muestra el boton", () => {
    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability: () => false,
    } as unknown as ReturnType<typeof usePermissionDependencies>);
    render(<SolicitudAccionOrigen accion={{ tipo: "IMPRIMIR_RECETA", visitId: 15 }} />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
