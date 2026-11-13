import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { ApiError } from "@api/utils/errors";
import { PhysicalExamButton } from "@features/consulta-medica/modules/atencion/components/PhysicalExamButton";
import { SecondaryDiagnosesButton } from "@features/consulta-medica/modules/atencion/components/SecondaryDiagnosesButton";
import { usePhysicalExam, useBodyRegions } from "@features/consulta-medica/modules/atencion/queries/usePhysicalExam";
import { useSecondaryDiagnoses } from "@features/consulta-medica/modules/atencion/queries/useSecondaryDiagnoses";

vi.mock("@features/consulta-medica/modules/atencion/queries/usePhysicalExam", () => ({
  usePhysicalExam: vi.fn(),
  useBodyRegions: vi.fn(),
}));
vi.mock("@features/consulta-medica/modules/atencion/mutations/useSavePhysicalExam", () => ({
  useSavePhysicalExam: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock("@features/consulta-medica/modules/atencion/queries/useSecondaryDiagnoses", () => ({
  useSecondaryDiagnoses: vi.fn(),
}));
vi.mock("@features/consulta-medica/modules/atencion/queries/useCieSearch", () => ({
  useCieSearch: () => ({ data: undefined }),
}));
vi.mock("@features/consulta-medica/modules/atencion/mutations/useAddSecondaryDiagnosis", () => ({
  useAddSecondaryDiagnosis: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock("@features/consulta-medica/modules/atencion/mutations/useCancelSecondaryDiagnosis", () => ({
  useCancelSecondaryDiagnosis: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

/** Iniciar la consulta no crea la nota: se crea al guardar el diagnostico. */
const noteMissing = new ApiError("CONSULTATION_NOT_FOUND", "La visita no tiene consulta iniciada.", 404);

describe("Sin diagnostico guardado, los dialogos lo dicen claramente", () => {
  beforeEach(() => {
    vi.mocked(useBodyRegions).mockReturnValue({
      data: [], isLoading: false,
    } as unknown as ReturnType<typeof useBodyRegions>);
  });

  it("Exploracion fisica pide guardar el diagnostico (no 'iniciar la consulta')", async () => {
    vi.mocked(usePhysicalExam).mockReturnValue({
      data: undefined, isLoading: false, isError: true, error: noteMissing,
    } as unknown as ReturnType<typeof usePhysicalExam>);
    const user = userEvent.setup();
    render(<PhysicalExamButton visitId={7} />);

    await user.click(screen.getByRole("button", { name: /Exploración física/ }));

    expect(await screen.findByText(/Guarda el diagnóstico primero/)).toBeInTheDocument();
    expect(screen.queryByText("Primero inicia la consulta.")).toBeNull();
  });

  it("Dx secundarios avisa en vez de mostrar la lista vacia", async () => {
    vi.mocked(useSecondaryDiagnoses).mockReturnValue({
      data: undefined, isLoading: false, isError: true, error: noteMissing,
    } as unknown as ReturnType<typeof useSecondaryDiagnoses>);
    const user = userEvent.setup();
    render(<SecondaryDiagnosesButton visitId={7} />);

    await user.click(screen.getByRole("button", { name: /secundarios/i }));

    expect(await screen.findByText(/Guarda el diagnóstico primero/)).toBeInTheDocument();
    expect(screen.queryByText(/No hay diagnósticos secundarios/)).toBeNull();
  });
});
