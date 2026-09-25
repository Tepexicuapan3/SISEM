import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import RecepcionIncapacidadPage from "@features/recepcion/modules/incapacidad/pages/RecepcionIncapacidadPage";
import { usePatientLookupHistorico } from "@features/recepcion/modules/checkin/queries/usePatientLookup";
import { usePatientMedicalLeaves } from "@features/expedientes/queries/usePatientMedicalLeaves";

vi.mock("@features/recepcion/modules/checkin/queries/usePatientLookup", () => ({
  usePatientLookupHistorico: vi.fn(),
}));

vi.mock("@features/expedientes/queries/usePatientMedicalLeaves", () => ({
  usePatientMedicalLeaves: vi.fn(),
}));

describe("RecepcionIncapacidadPage UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(usePatientLookupHistorico).mockReturnValue({
      data: undefined,
      isFetching: false,
    } as unknown as ReturnType<typeof usePatientLookupHistorico>);

    vi.mocked(usePatientMedicalLeaves).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof usePatientMedicalLeaves>);
  });

  it("muestra estado vacio inicial sin buscar ningun expediente", () => {
    render(<RecepcionIncapacidadPage />);

    expect(
      screen.getByRole("heading", { name: "Historial de incapacidades" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Ingresá un número de expediente para ver su historial de incapacidades.",
      ),
    ).toBeVisible();
    expect(usePatientMedicalLeaves).not.toHaveBeenCalled();
  });

  it("busca por no_exp al confirmar y consulta el historial con pkNum=0 (titular)", async () => {
    const user = userEvent.setup();

    vi.mocked(usePatientLookupHistorico).mockReturnValue({
      data: { titular: { nombre: "Juan Perez" }, dependientes: [] },
      isFetching: false,
    } as unknown as ReturnType<typeof usePatientLookupHistorico>);

    vi.mocked(usePatientMedicalLeaves).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof usePatientMedicalLeaves>);

    render(<RecepcionIncapacidadPage />);

    await user.type(
      screen.getByPlaceholderText("Ej. 12345"),
      "10001{enter}",
    );

    expect(usePatientLookupHistorico).toHaveBeenLastCalledWith("10001");
    expect(usePatientMedicalLeaves).toHaveBeenLastCalledWith("10001", 0);
    expect(screen.getByText(/Juan Perez/)).toBeVisible();
  });
});
