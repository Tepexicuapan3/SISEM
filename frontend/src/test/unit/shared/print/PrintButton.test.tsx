import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PrintButton } from "@shared/components/print/PrintButton";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { usePrintDocument } from "@shared/hooks/usePrintDocument";

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: vi.fn(),
}));
vi.mock("@shared/hooks/usePrintDocument", () => ({
  usePrintDocument: vi.fn(),
}));

const setCapability = (granted: boolean) =>
  vi.mocked(usePermissionDependencies).mockReturnValue({
    hasCapability: vi.fn(() => granted),
  } as unknown as ReturnType<typeof usePermissionDependencies>);

describe("PrintButton", () => {
  const print = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    setCapability(true);
    vi.mocked(usePrintDocument).mockReturnValue({ print, isPrinting: false });
  });

  it("se oculta si no tiene la capability documentos.<doc>.imprimir", () => {
    setCapability(false);
    render(<PrintButton documento="ficha" resourceId={7} label="Imprimir ficha" />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("consulta la capability correcta del documento", () => {
    const hasCapability = vi.fn(() => true);
    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability,
    } as unknown as ReturnType<typeof usePermissionDependencies>);
    render(<PrintButton documento="nota" resourceId={7} />);
    expect(hasCapability).toHaveBeenCalledWith(
      "documentos.nota.imprimir",
      expect.anything(),
    );
  });

  it("al hacer click llama print con el resourceId", async () => {
    render(<PrintButton documento="ficha" resourceId={7} label="Imprimir ficha" />);
    await userEvent.click(screen.getByRole("button", { name: "Imprimir ficha" }));
    expect(usePrintDocument).toHaveBeenCalledWith("ficha");
    expect(print).toHaveBeenCalledWith(7);
  });

  it("queda deshabilitado y muestra 'Generando PDF...' mientras imprime", () => {
    vi.mocked(usePrintDocument).mockReturnValue({ print, isPrinting: true });
    render(<PrintButton documento="ficha" resourceId={7} label="Imprimir ficha" />);
    const btn = screen.getByRole("button", { name: /Generando PDF/ });
    expect(btn).toBeDisabled();
  });
});
