import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@/test/utils";
import { ConsultorioFamiliarConfigPage } from "@features/admin/modules/catalogos/consultorio-familiar/pages/ConsultorioFamiliarConfigPage";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { consultoriosAPI } from "@api/resources/catalogos/consultorios.api";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type {
  CentrosAtencionListResponse,
  ConsultorioFamiliar,
  ConsultoriosListResponse,
  EquivalenciaClinica,
} from "@api/types";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: vi.fn(),
}));

// El factory de catálogos guarda la referencia a getAll al cargar: se mockea el hook.
vi.mock("@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList", () => ({
  useCentrosAtencionList: vi.fn(),
}));

const permisos = (allows: (code: string) => boolean) =>
  ({
    hasCapability: allows,
    hasEffectivePermission: allows,
    hasEffectiveRequirement: () => true,
  }) as unknown as ReturnType<typeof usePermissionDependencies>;

const centros: CentrosAtencionListResponse = {
  items: [
    { id: 5, name: "Clínica Norte", code: "N", centerType: "CLINICA", legacyFolio: null, isExternal: false, isActive: true },
    { id: 7, name: "Clínica Sur", code: "S", centerType: "CLINICA", legacyFolio: null, isExternal: false, isActive: true },
  ],
  page: 1,
  pageSize: 500,
  total: 2,
  totalPages: 1,
};

const equivalencias: EquivalenciaClinica[] = [
  { idClinicaCentro: 1, claveClinicaSermed: "5", idCentroAtencion: 5, centro: "Clínica Norte", estaActivo: true },
];

const familiares: ConsultorioFamiliar[] = [
  {
    idAdscripcionConsultorio: 11,
    consultorioId: 41,
    consultorio: "Consultorio 4",
    numero: 4,
    idCentroAtencion: 5,
    turno: "Matutino",
    capacidadMaxima: 200,
    estaActivo: true,
    carga: 37,
  },
];

const consultoriosCentro: ConsultoriosListResponse = {
  items: [
    { id: 41, name: "Consultorio 4", numero: 4, isActive: true, centerId: 5, centerName: "Clínica Norte", turnName: "Matutino" },
    { id: 42, name: "Consultorio 5", numero: 5, isActive: true, centerId: 5, centerName: "Clínica Norte", turnName: "Vespertino" },
  ],
  page: 1,
  pageSize: 500,
  total: 2,
  totalPages: 1,
};

// Los <select> de centro se pintan antes de que lleguen los centros.
const esperarCentros = () =>
  waitFor(() => expect(screen.getAllByRole("option", { name: "Clínica Sur" }).length).toBeGreaterThan(0));

describe("ConsultorioFamiliarConfigPage (P-03)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(usePermissionDependencies).mockReturnValue(permisos(() => true));
    vi.mocked(useCentrosAtencionList).mockReturnValue({ data: centros } as ReturnType<typeof useCentrosAtencionList>);
    vi.spyOn(consultoriosAPI, "getAll").mockResolvedValue(consultoriosCentro);
    vi.spyOn(adscripcionAPI, "getEquivalencias").mockResolvedValue({ items: equivalencias });
    vi.spyOn(adscripcionAPI, "getConsultoriosFamiliares").mockResolvedValue({ items: familiares });
  });

  it("sin permiso de configuración avisa y no consulta nada", () => {
    vi.mocked(usePermissionDependencies).mockReturnValue(permisos(() => false));
    render(<ConsultorioFamiliarConfigPage />);

    expect(screen.getByText(/no tienes acceso/i)).toBeInTheDocument();
    expect(adscripcionAPI.getEquivalencias).not.toHaveBeenCalled();
  });

  it("lista las equivalencias y da de alta una nueva", async () => {
    const crear = vi.spyOn(adscripcionAPI, "crearEquivalencia").mockResolvedValue({
      idClinicaCentro: 2, claveClinicaSermed: "9", idCentroAtencion: 7, centro: "Clínica Sur", estaActivo: true,
    });
    const user = userEvent.setup();
    render(<ConsultorioFamiliarConfigPage />);

    const tabla = await screen.findByRole("table", { name: /equivalencias/i });
    expect(within(tabla).getByText("Clínica Norte")).toBeInTheDocument();

    await user.type(screen.getByLabelText(/clave de clínica sermed/i), " 9 ");
    await esperarCentros();
    await user.selectOptions(screen.getByLabelText(/centro de la clave/i), "7");
    await user.click(screen.getByRole("button", { name: /agregar equivalencia/i }));

    await waitFor(() => expect(crear).toHaveBeenCalledWith({ claveClinicaSermed: "9", idCentroAtencion: 7 }));
  });

  it("desactiva una equivalencia", async () => {
    const actualizar = vi.spyOn(adscripcionAPI, "actualizarEquivalencia").mockResolvedValue({ ...equivalencias[0], estaActivo: false });
    const user = userEvent.setup();
    render(<ConsultorioFamiliarConfigPage />);

    await user.click(await screen.findByRole("button", { name: /desactivar clave 5/i }));

    await waitFor(() => expect(actualizar).toHaveBeenCalledWith(1, { estaActivo: false }));
  });

  it("muestra los consultorios familiares del centro con su carga y da de alta uno que falta", async () => {
    const crear = vi.spyOn(adscripcionAPI, "crearConsultorioFamiliar").mockResolvedValue({
      ...familiares[0], idAdscripcionConsultorio: 12, consultorioId: 42, consultorio: "Consultorio 5", capacidadMaxima: 150, carga: 0,
    });
    const user = userEvent.setup();
    render(<ConsultorioFamiliarConfigPage />);

    await esperarCentros();
    await user.selectOptions(screen.getByLabelText(/^centro de los consultorios/i), "5");

    const tabla = await screen.findByRole("table", { name: /consultorios familiares/i });
    expect(within(tabla).getByText("37 / 200")).toBeInTheDocument();
    expect(adscripcionAPI.getConsultoriosFamiliares).toHaveBeenCalledWith(5);

    // Solo se ofrecen los consultorios del centro que todavía no son familiares.
    const selector = await screen.findByLabelText(/consultorio por agregar/i);
    await waitFor(() => expect(within(selector).getByRole("option", { name: /consultorio 5/i })).toBeInTheDocument());
    expect(within(selector).queryByRole("option", { name: /consultorio 4/i })).not.toBeInTheDocument();

    await user.selectOptions(selector, "42");
    await user.type(screen.getByLabelText(/capacidad del consultorio nuevo/i), "150");
    await user.click(screen.getByRole("button", { name: /agregar consultorio/i }));

    await waitFor(() => expect(crear).toHaveBeenCalledWith({ consultorioId: 42, capacidadMaxima: 150 }));
  });

  it("cambia la capacidad (vacía = sin tope) y desactiva un consultorio familiar", async () => {
    const actualizar = vi.spyOn(adscripcionAPI, "actualizarConsultorioFamiliar").mockResolvedValue(familiares[0]);
    const user = userEvent.setup();
    render(<ConsultorioFamiliarConfigPage />);

    await esperarCentros();
    await user.selectOptions(screen.getByLabelText(/^centro de los consultorios/i), "5");
    const capacidad = await screen.findByLabelText(/^capacidad de consultorio 4/i);
    await user.clear(capacidad);
    await user.click(screen.getByRole("button", { name: /guardar capacidad de consultorio 4/i }));
    await waitFor(() => expect(actualizar).toHaveBeenCalledWith(11, { capacidadMaxima: null }));

    await user.click(screen.getByRole("button", { name: /desactivar consultorio 4/i }));
    await waitFor(() => expect(actualizar).toHaveBeenCalledWith(11, { estaActivo: false }));
  });
});
