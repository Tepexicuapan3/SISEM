import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { render, screen, within } from "@/test/utils";
import type {
  ChronicControlPanel as PanelData,
  ChronicControlParameter,
  ChronicControlProgramPanel,
} from "@api/types/padrones.types";
import { ChronicControlPanel } from "@features/padrones/components/ChronicControlPanel";
import {
  useChronicControlPanel,
  useRegisterChronicControl,
} from "@features/padrones/queries/usePadrones";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@features/padrones/queries/usePadrones", () => ({
  useChronicControlPanel: vi.fn(),
  useRegisterChronicControl: vi.fn(),
}));

const param = (overrides: Partial<ChronicControlParameter>): ChronicControlParameter => ({
  parameter: "ta_sistolica",
  label: "Presión sistólica",
  unit: "mmHg",
  source: "somatometria",
  value: null,
  goalMin: null,
  goalMax: null,
  inGoal: null,
  ...overrides,
});

const diabetes = (overrides: Partial<ChronicControlProgramPanel> = {}): ChronicControlProgramPanel => ({
  program: { code: "DIABETES", name: "Diabetes mellitus" },
  everyDays: 90,
  parameters: [
    param({ value: 135, goalMax: 130, inGoal: false }),
    param({ parameter: "glucosa_capilar", label: "Glucosa capilar", unit: "mg/dL", value: 110, goalMin: 70, goalMax: 130, inGoal: true }),
    param({ parameter: "hba1c", label: "Hemoglobina glucosilada (HbA1c)", unit: "%", source: "manual", goalMax: 7 }),
    param({ parameter: "cintura", label: "Cintura", unit: "cm", value: 98 }),
  ],
  status: "descontrolado",
  suggestedNextControlOn: "2027-02-09",
  registered: null,
  last: null,
  ...overrides,
});

const mutateAsync = vi.fn();

function mockHooks(data: PanelData | undefined, extra: Record<string, unknown> = {}) {
  vi.mocked(useChronicControlPanel).mockReturnValue({
    data,
    isError: false,
    ...extra,
  } as unknown as ReturnType<typeof useChronicControlPanel>);
  vi.mocked(useRegisterChronicControl).mockReturnValue({
    mutateAsync,
    isPending: false,
  } as unknown as ReturnType<typeof useRegisterChronicControl>);
}

describe("ChronicControlPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("no muestra nada sin programas o si falla la carga", () => {
    mockHooks({ programs: [], vitalsCapturedAt: null, canRegister: true });
    const { container, rerender } = render(<ChronicControlPanel visitId={3} />);
    expect(container).toBeEmptyDOMElement();
    mockHooks(undefined, { isError: true });
    rerender(<ChronicControlPanel visitId={3} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("muestra los valores de hoy contra la meta con semaforo y el estado", () => {
    mockHooks({ programs: [diabetes()], vitalsCapturedAt: "2026-11-11T10:00:00", canRegister: true });
    render(<ChronicControlPanel visitId={3} />);

    expect(screen.getByText("Control de Diabetes mellitus")).toBeInTheDocument();
    expect(screen.getByText("Descontrolado")).toBeInTheDocument();
    const sistolica = screen.getByRole("row", { name: /Presión sistólica/ });
    expect(within(sistolica).getByText("135 mmHg")).toBeInTheDocument();
    expect(within(sistolica).getByText("≤ 130")).toBeInTheDocument();
    expect(within(sistolica).getByText("Fuera de meta")).toBeInTheDocument();
    const glucosa = screen.getByRole("row", { name: /Glucosa capilar/ });
    expect(within(glucosa).getByText("70–130")).toBeInTheDocument();
    expect(within(glucosa).getByText("En meta")).toBeInTheDocument();
    const cintura = screen.getByRole("row", { name: /Cintura/ });
    expect(within(cintura).getByText("Sin meta")).toBeInTheDocument();
    expect(screen.getByText(/Próximo control sugerido: 09\/02\/2027/)).toBeInTheDocument();
  });

  it("avisa el ultimo control y si esta vencido", () => {
    mockHooks({
      programs: [diabetes({ last: { controlOn: "2026-06-01", status: "controlado", nextControlOn: "2026-08-30", overdue: true } })],
      vitalsCapturedAt: null,
      canRegister: false,
    });
    render(<ChronicControlPanel visitId={3} />);
    expect(screen.getByText(/Último control: 01\/06\/2026 · Controlado/)).toBeInTheDocument();
    expect(screen.getByText("Control vencido")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Registrar control" })).not.toBeInTheDocument();
  });

  it("registra el control con la HbA1c capturada y la adherencia", async () => {
    mutateAsync.mockResolvedValue({ nextControlOn: "2027-02-09" });
    mockHooks({ programs: [diabetes()], vitalsCapturedAt: null, canRegister: true });
    render(<ChronicControlPanel visitId={3} />);

    await userEvent.type(screen.getByLabelText("Hemoglobina glucosilada (HbA1c) (%)"), "7.8");
    await userEvent.selectOptions(screen.getByLabelText("Adherencia al tratamiento"), "regular");
    await userEvent.click(screen.getByRole("button", { name: "Registrar control" }));

    expect(mutateAsync).toHaveBeenCalledWith({
      programCode: "DIABETES",
      values: { hba1c: "7.8" },
      adherence: "regular",
      notes: null,
    });
    expect(toast.success).toHaveBeenCalledWith("Control registrado", {
      description: "Próximo control: 09/02/2027.",
    });
  });

  it("un control ya registrado se muestra de solo lectura", () => {
    mockHooks({
      programs: [diabetes({
        registered: {
          id: 9,
          program: { code: "DIABETES", name: "Diabetes mellitus" },
          controlOn: "2026-11-11",
          status: "controlado",
          nextControlOn: "2027-02-09",
          adherence: "buena",
          notes: null,
          registeredBy: "Dra. Ruiz",
          measurements: [param({ parameter: "hba1c", label: "Hemoglobina glucosilada (HbA1c)", unit: "%", source: "manual", value: 6.5, goalMax: 7, inGoal: true })],
        },
      })],
      vitalsCapturedAt: null,
      canRegister: true,
    });
    render(<ChronicControlPanel visitId={3} />);
    expect(screen.getByText(/Registrado por Dra. Ruiz · próximo control 09\/02\/2027/)).toBeInTheDocument();
    expect(screen.getByText("Controlado")).toBeInTheDocument();
    expect(screen.getByText("6.5 %")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Registrar control" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Hemoglobina glucosilada (HbA1c) (%)")).not.toBeInTheDocument();
  });

  it("si el registro falla avisa el motivo", async () => {
    mutateAsync.mockRejectedValue(new Error("boom"));
    mockHooks({ programs: [diabetes()], vitalsCapturedAt: null, canRegister: true });
    render(<ChronicControlPanel visitId={3} />);
    await userEvent.click(screen.getByRole("button", { name: "Registrar control" }));
    expect(toast.error).toHaveBeenCalled();
  });
});
