import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { render, screen } from "@/test/utils";
import type { ChronicVisitNotice } from "@api/types/padrones.types";
import { ChronicConditionsNotice } from "@features/padrones/components/ChronicConditionsNotice";
import {
  useChronicVisitNotice,
  useEnrollChronicFromVisit,
} from "@features/padrones/queries/usePadrones";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@features/padrones/queries/usePadrones", () => ({
  useChronicVisitNotice: vi.fn(),
  useEnrollChronicFromVisit: vi.fn(),
}));

const DIABETES = { code: "DIABETES", name: "Diabetes mellitus" };

const buildNotice = (overrides: Partial<ChronicVisitNotice> = {}): ChronicVisitNotice => ({
  enrollments: [],
  suggestion: null,
  canEnroll: false,
  ...overrides,
});

const mutateAsync = vi.fn();

function mockHooks(data: ChronicVisitNotice | undefined, extra: Record<string, unknown> = {}) {
  vi.mocked(useChronicVisitNotice).mockReturnValue({
    data,
    isError: false,
    ...extra,
  } as unknown as ReturnType<typeof useChronicVisitNotice>);
  vi.mocked(useEnrollChronicFromVisit).mockReturnValue({
    mutateAsync,
    isPending: false,
  } as unknown as ReturnType<typeof useEnrollChronicFromVisit>);
}

describe("ChronicConditionsNotice", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("no muestra nada si el paciente no esta en el padron ni hay sugerencia", () => {
    mockHooks(buildNotice());
    const { container } = render(<ChronicConditionsNotice visitId={7} cieCode="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("no muestra nada si el aviso no se pudo cargar", () => {
    mockHooks(undefined, { isError: true });
    const { container } = render(<ChronicConditionsNotice visitId={7} cieCode="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("avisa los padecimientos activos con su programa y fecha de inscripcion", () => {
    mockHooks(buildNotice({
      enrollments: [{
        id: 1,
        item: { id: "E11", code: "E11", description: "DIABETES TIPO 2", restricted: false },
        program: DIABETES,
        enrolledOn: "2021-03-04",
      }],
    }));
    render(<ChronicConditionsNotice visitId={7} cieCode="" />);

    expect(screen.getByText("Paciente en el padrón de crónicos")).toBeInTheDocument();
    expect(screen.getByText(/Diabetes mellitus/)).toBeInTheDocument();
    expect(screen.getByText(/E11 · DIABETES TIPO 2/)).toBeInTheDocument();
    expect(screen.getByText(/desde 04\/03\/2021/)).toBeInTheDocument();
    expect(vi.mocked(useChronicVisitNotice)).toHaveBeenCalledWith(7, "");
  });

  it("un diagnostico restringido se muestra sin codigo ni programa", () => {
    mockHooks(buildNotice({
      enrollments: [{
        id: 2,
        item: { id: null, code: null, description: "Diagnóstico restringido", restricted: true },
        program: null,
        enrolledOn: "2022-01-10",
      }],
    }));
    render(<ChronicConditionsNotice visitId={7} cieCode="" />);
    expect(screen.getByText(/Diagnóstico restringido/)).toBeInTheDocument();
    expect(screen.queryByText(/Diabetes/)).not.toBeInTheDocument();
  });

  it("sugiere inscribir y lo inscribe con un clic cuando tiene permiso", async () => {
    mutateAsync.mockResolvedValue({});
    mockHooks(buildNotice({
      suggestion: { cie: { code: "E119", description: "DIABETES TIPO 2 SIN COMPLICACIONES" }, program: DIABETES },
      canEnroll: true,
    }));
    render(<ChronicConditionsNotice visitId={7} cieCode="E119" />);

    expect(screen.getByText(/pertenece al programa Diabetes mellitus/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Inscribir en el padrón" }));

    expect(mutateAsync).toHaveBeenCalledWith({ itemId: "E119" });
    expect(toast.success).toHaveBeenCalledWith("Paciente inscrito en el padrón de crónicos");
  });

  it("sin permiso de padron muestra la sugerencia sin boton", () => {
    mockHooks(buildNotice({
      suggestion: { cie: { code: "I10", description: "HIPERTENSION ESENCIAL" }, program: { code: "HIPERTENSION", name: "Hipertensión arterial" } },
      canEnroll: false,
    }));
    render(<ChronicConditionsNotice visitId={7} cieCode="I10" />);
    expect(screen.getByText(/pertenece al programa Hipertensión arterial/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Inscribir en el padrón" })).not.toBeInTheDocument();
  });

  it("si la inscripcion falla avisa el motivo", async () => {
    mutateAsync.mockRejectedValue(new Error("boom"));
    mockHooks(buildNotice({
      suggestion: { cie: { code: "E119", description: "DIABETES" }, program: DIABETES },
      canEnroll: true,
    }));
    render(<ChronicConditionsNotice visitId={7} cieCode="E119" />);
    await userEvent.click(screen.getByRole("button", { name: "Inscribir en el padrón" }));
    expect(toast.error).toHaveBeenCalled();
  });
});
