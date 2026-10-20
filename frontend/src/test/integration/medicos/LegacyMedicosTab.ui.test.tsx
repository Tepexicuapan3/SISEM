import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { LegacyMedicosTab } from "@features/admin/modules/medicos/components/legado/LegacyMedicosTab";
import type {
  LegacyMedicoItem,
  LegacyMedicosListResponse,
} from "@api/types/medicos.types";

const { getLegacy } = vi.hoisted(() => ({ getLegacy: vi.fn() }));

vi.mock("@api/resources/medicos.api", () => ({
  medicosAPI: { getLegacy },
}));

const item = (over: Partial<LegacyMedicoItem> = {}): LegacyMedicoItem => ({
  noMedico: 7,
  claveRh: "0512",
  nombreCompleto: "JUAN PEREZ LOPEZ",
  paterno: "PEREZ",
  materno: "LOPEZ",
  nombre: "JUAN",
  cedula: "998877",
  sexo: "M",
  clinica: { clave: 3, descripcion: "CLINICA NORTE" },
  especialidad: { clave: 9, descripcion: "CARDIOLOGIA" },
  estatus: "A",
  usuarioLegado: "jperez",
  medicoActual: null,
  ...over,
});

const response = (items: LegacyMedicoItem[], total = items.length): LegacyMedicosListResponse => ({
  items,
  total,
  page: 1,
  pageSize: 20,
  totalPages: 1,
});

describe("LegacyMedicosTab", () => {
  beforeEach(() => {
    getLegacy.mockReset();
  });

  it("renderiza filas del archivo legado, estatus y médico actual", async () => {
    getLegacy.mockResolvedValue(
      response([
        item(),
        item({
          noMedico: 8,
          nombreCompleto: "ANA RUIZ",
          estatus: "X",
          medicoActual: { id: 4, nombreCompleto: "Ana Ruiz Torres" },
        }),
      ]),
    );

    render(<LegacyMedicosTab canRead />);

    expect(await screen.findByText("JUAN PEREZ LOPEZ")).toBeInTheDocument();
    expect(screen.getByText("A · Activo")).toBeInTheDocument();
    expect(screen.getByText("X")).toBeInTheDocument();
    expect(screen.getByText("Ana Ruiz Torres")).toBeInTheDocument();
    expect(screen.getAllByText("998877")).toHaveLength(2);
  });

  it("buscar dispara una petición con `search`", async () => {
    getLegacy.mockResolvedValue(response([item()]));
    const user = userEvent.setup();

    render(<LegacyMedicosTab canRead />);
    await screen.findByText("JUAN PEREZ LOPEZ");

    await user.type(screen.getByRole("searchbox"), "perez");

    await waitFor(() =>
      expect(getLegacy).toHaveBeenCalledWith(expect.objectContaining({ search: "perez" })),
    );
  });

  it("muestra el estado vacío cuando no hay padrón cargado", async () => {
    getLegacy.mockResolvedValue(response([], 0));

    render(<LegacyMedicosTab canRead />);

    expect(await screen.findByText("Aún no se ha cargado el padrón del legado")).toBeInTheDocument();
  });
});
