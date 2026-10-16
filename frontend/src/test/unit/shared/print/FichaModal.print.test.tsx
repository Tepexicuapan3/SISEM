import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FichaModal } from "@features/recepcion/shared/components/FichaModal";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { usePrintDocument } from "@shared/hooks/usePrintDocument";
import type { VisitQueueItem } from "@api/types";

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: vi.fn(),
}));
vi.mock("@shared/hooks/usePrintDocument", () => ({
  usePrintDocument: vi.fn(),
}));
vi.mock(
  "@features/recepcion/modules/checkin/queries/usePatientLookup",
  () => ({ usePatientLookupHistorico: () => ({ data: undefined, isFetching: false }) }),
);
vi.mock(
  "@features/recepcion/modules/checkin/queries/useVisitStatusLog",
  () => ({ useVisitStatusLog: () => ({ data: [], isFetching: false }) }),
);

const visit = {
  id: 42,
  folio: "VST-042",
  noExp: "123",
  pkNum: 0,
  status: "en_espera",
  serviceType: "medicina_general",
  nombrePaciente: "Paciente Prueba",
} as unknown as VisitQueueItem;

describe("FichaModal - impresion", () => {
  const print = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability: () => true,
    } as unknown as ReturnType<typeof usePermissionDependencies>);
    vi.mocked(usePrintDocument).mockReturnValue({ print, isPrinting: false });
  });

  it("'Imprimir ficha' dispara la impresion documento=ficha con el id de la visita", async () => {
    render(<FichaModal open onOpenChange={() => {}} visit={visit} />);
    await userEvent.click(screen.getByRole("button", { name: "Imprimir ficha" }));
    expect(usePrintDocument).toHaveBeenCalledWith("ficha");
    expect(print).toHaveBeenCalledWith(42);
  });

  it("oculta 'Imprimir ficha' sin la capability", () => {
    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability: () => false,
    } as unknown as ReturnType<typeof usePermissionDependencies>);
    render(<FichaModal open onOpenChange={() => {}} visit={visit} />);
    expect(screen.queryByRole("button", { name: "Imprimir ficha" })).toBeNull();
    expect(screen.getByRole("button", { name: "Cerrar" })).toBeInTheDocument();
  });
});
