import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@/test/utils";
import type { PadronEnrollment } from "@api/types/padrones.types";
import PadronesPage from "@features/padrones/pages/PadronesPage";
import { usePadronList, usePadronPrograms } from "@features/padrones/queries/usePadrones";

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: () => ({ hasCapability: () => true }),
}));

vi.mock("@features/padrones/queries/usePadrones", () => ({
  usePadronList: vi.fn(),
  usePadronPrograms: vi.fn(),
}));

// Los dialogos tienen sus propias pruebas.
vi.mock("@features/padrones/components/EnrollPadronDialog", () => ({ EnrollPadronDialog: () => null }));
vi.mock("@features/padrones/components/DischargePadronDialog", () => ({ DischargePadronDialog: () => null }));
vi.mock("@features/padrones/components/CorrectPadronDialog", () => ({
  CorrectPadronDialog: ({ enrollment }: { enrollment: PadronEnrollment | null }) =>
    enrollment ? <p>Corrigiendo {enrollment.patientName}</p> : null,
}));

const enrollment = (overrides: Partial<PadronEnrollment>): PadronEnrollment => ({
  id: 1,
  registry: "cronicos",
  noExp: "777",
  pkNum: 0,
  patientName: "JUAN PEREZ LOPEZ",
  item: { id: "E11", code: "E11", description: "DIABETES TIPO 2", restricted: false },
  center: { id: 1, name: "Clínica Centro" },
  enrolledOn: "2026-01-10",
  enrolledBy: null,
  notes: null,
  source: "consulta",
  status: "activo",
  program: { code: "DIABETES", name: "Diabetes mellitus" },
  lastControl: { controlOn: "2026-06-01", status: "descontrolado", nextControlOn: "2026-08-30", overdue: true },
  discharge: null,
  ...overrides,
});

const ROWS = [
  enrollment({}),
  enrollment({
    id: 2, noExp: "888", patientName: "MARIA RUIZ", source: "manual", lastControl: null,
    item: { id: "J45", code: "J45", description: "ASMA", restricted: false }, program: null,
  }),
];

const lastParams = () => vi.mocked(usePadronList).mock.calls.at(-1)?.[1];

describe("PadronesPage (crónicos como lista de trabajo)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePadronList).mockReturnValue({
      data: { items: ROWS, total: 2, page: 1, pageSize: 20, totalPages: 1 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof usePadronList>);
    vi.mocked(usePadronPrograms).mockReturnValue({
      data: { items: [{ code: "DIABETES", name: "Diabetes mellitus" }, { code: "ERC", name: "Enfermedad renal crónica" }] },
    } as unknown as ReturnType<typeof usePadronPrograms>);
  });

  it("muestra programa, situación del control y origen", () => {
    render(<PadronesPage />);
    const juan = screen.getByRole("row", { name: /JUAN PEREZ LOPEZ/ });
    expect(within(juan).getByText("Diabetes mellitus")).toBeInTheDocument();
    expect(within(juan).getByText("Vencido")).toBeInTheDocument();
    expect(within(juan).getByText(/30\/08\/2026/)).toBeInTheDocument();
    expect(within(juan).getByText("Consulta")).toBeInTheDocument();

    const maria = screen.getByRole("row", { name: /MARIA RUIZ/ });
    expect(within(maria).getByText("Sin programa")).toBeInTheDocument();
    expect(within(maria).getByText("Manual")).toBeInTheDocument();
  });

  it("sin filtros nuevos pide el listado igual que antes", () => {
    render(<PadronesPage />);
    const params = lastParams();
    expect(params).toMatchObject({ status: "activo", page: 1 });
    expect(params?.program).toBeUndefined();
    expect(params?.control).toBeUndefined();
    expect(params?.search).toBeUndefined();
  });

  it("filtra por programa, por situación del control y por nombre", async () => {
    const user = userEvent.setup();
    render(<PadronesPage />);

    await user.click(screen.getByRole("combobox", { name: "Programa" }));
    await user.click(await screen.findByRole("option", { name: "Diabetes mellitus" }));
    await user.click(screen.getByRole("combobox", { name: "Control" }));
    await user.click(await screen.findByRole("option", { name: "Vencido" }));
    await user.type(screen.getByPlaceholderText("Buscar por nombre"), "perez");

    await waitFor(() => expect(lastParams()).toMatchObject({ program: "DIABETES", control: "vencido", search: "perez" }));
  });

  it("los filtros de programa y control no aparecen en discapacidad", async () => {
    const user = userEvent.setup();
    render(<PadronesPage />);
    await user.click(screen.getByRole("tab", { name: "Discapacidad" }));

    expect(screen.queryByRole("combobox", { name: "Programa" })).not.toBeInTheDocument();
    expect(lastParams()?.program).toBeUndefined();
    expect(screen.queryByRole("combobox", { name: "Orden" })).not.toBeInTheDocument();
    expect(lastParams()?.order).toBeUndefined();
  });

  it("crónicos se ordena por prioridad de control y se puede volver a la inscripción reciente", async () => {
    const user = userEvent.setup();
    render(<PadronesPage />);
    expect(lastParams()?.order).toBe("prioridad");

    await user.click(screen.getByRole("combobox", { name: "Orden" }));
    await user.click(await screen.findByRole("option", { name: "Inscripción reciente" }));
    await waitFor(() => expect(lastParams()?.order).toBeUndefined());
  });

  it("corregir abre el diálogo de la fila; no aparece en bajas ni en diagnósticos restringidos", async () => {
    vi.mocked(usePadronList).mockReturnValue({
      data: {
        items: [
          ...ROWS,
          enrollment({ id: 3, patientName: "BAJA ANTIGUA", status: "baja" }),
          enrollment({
            id: 4, patientName: "OCULTO", program: null,
            item: { id: null, code: null, description: "Diagnóstico restringido", restricted: true },
          }),
        ],
        total: 4, page: 1, pageSize: 20, totalPages: 1,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof usePadronList>);
    const user = userEvent.setup();
    render(<PadronesPage />);

    expect(within(screen.getByRole("row", { name: /BAJA ANTIGUA/ })).queryByRole("button", { name: "Corregir" })).toBeNull();
    expect(within(screen.getByRole("row", { name: /OCULTO/ })).queryByRole("button", { name: "Corregir" })).toBeNull();

    await user.click(within(screen.getByRole("row", { name: /JUAN PEREZ LOPEZ/ })).getByRole("button", { name: "Corregir" }));
    expect(screen.getByText("Corrigiendo JUAN PEREZ LOPEZ")).toBeInTheDocument();
  });
});
