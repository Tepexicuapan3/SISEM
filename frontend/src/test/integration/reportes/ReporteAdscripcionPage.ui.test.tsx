import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@/test/utils";
import { ReporteAdscripcionPage } from "@features/admin/modules/reportes/pages/ReporteAdscripcionPage";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { AdscritosResponse, ResumenAdscripcionResponse } from "@api/types";

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: vi.fn(),
}));

const permisos = (allows: (code: string) => boolean) =>
  ({
    hasCapability: allows,
    hasEffectivePermission: allows,
    hasEffectiveRequirement: () => true,
  }) as unknown as ReturnType<typeof usePermissionDependencies>;

const resumen: ResumenAdscripcionResponse = {
  centros: [
    {
      idCentroAtencion: 5,
      centro: "Clínica Norte",
      titulares: 30,
      familiares: 70,
      total: 100,
      consultorios: [
        {
          consultorioId: 41, consultorio: "Medicina general", numero: 4, turnoId: 1, turno: "Matutino",
          titulares: 20, familiares: 40, total: 60, capacidadMaxima: 200, estaActivo: true, medicos: ["Ana López"],
        },
        {
          consultorioId: 42, consultorio: "Medicina general", numero: 5, turnoId: 2, turno: "Vespertino",
          titulares: 10, familiares: 30, total: 40, capacidadMaxima: null, estaActivo: true, medicos: [],
        },
      ],
    },
    {
      idCentroAtencion: 7,
      centro: "Clínica Sur",
      titulares: 1,
      familiares: 0,
      total: 1,
      consultorios: [
        {
          consultorioId: 71, consultorio: "Medicina general", numero: 1, turnoId: 1, turno: "Matutino",
          titulares: 1, familiares: 0, total: 1, capacidadMaxima: 50, estaActivo: true, medicos: ["Luis Ruiz"],
        },
      ],
    },
  ],
  totales: { titulares: 31, familiares: 70, total: 101 },
};

const adscritos: AdscritosResponse = {
  items: [
    {
      idAdscripcion: 1, idPaciente: 10, noExp: "12345", nombre: "Pérez Gómez Ana", tipo: "TITULAR",
      idCentroAtencion: 5, centro: "Clínica Norte", consultorioId: 41, consultorio: "Medicina general",
      numeroConsultorio: 4, turnoId: 1, turno: "Matutino", origen: "CHECKIN", fechaInicio: "2026-11-01T10:00:00",
    },
    {
      idAdscripcion: 2, idPaciente: 11, noExp: "12345", nombre: "Pérez Gómez Luis", tipo: "FAMILIAR",
      idCentroAtencion: 5, centro: "Clínica Norte", consultorioId: 41, consultorio: "Medicina general",
      numeroConsultorio: 4, turnoId: 1, turno: "Matutino", origen: "CITA", fechaInicio: "2026-11-02T10:00:00",
    },
  ],
  page: 1,
  pageSize: 20,
  total: 2,
  totalPages: 1,
};

describe("ReporteAdscripcionPage (P-03)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(usePermissionDependencies).mockReturnValue(permisos(() => true));
    vi.spyOn(adscripcionAPI, "getReporteResumen").mockResolvedValue(resumen);
    vi.spyOn(adscripcionAPI, "getReporteAdscritos").mockResolvedValue(adscritos);
  });

  it("sin permiso avisa y no consulta nada", () => {
    vi.mocked(usePermissionDependencies).mockReturnValue(permisos(() => false));
    render(<ReporteAdscripcionPage />);

    expect(screen.getByText(/no tienes permiso/i)).toBeInTheDocument();
    expect(adscripcionAPI.getReporteResumen).not.toHaveBeenCalled();
    expect(adscripcionAPI.getReporteAdscritos).not.toHaveBeenCalled();
  });

  it("muestra los totales y el resumen por consultorio y turno", async () => {
    render(<ReporteAdscripcionPage />);

    const totales = await screen.findByRole("region", { name: /totales/i });
    expect(within(totales).getByText("101")).toBeInTheDocument();
    expect(within(totales).getByText("31")).toBeInTheDocument();
    expect(within(totales).getByText("70")).toBeInTheDocument();

    const tabla = screen.getByRole("table", { name: /resumen por consultorio/i });
    const fila = within(tabla).getByRole("row", { name: /consultorio 4/i });
    expect(within(fila).getByText("Matutino")).toBeInTheDocument();
    expect(within(fila).getByText("60 / 200")).toBeInTheDocument();
    expect(within(fila).getByText("Ana López")).toBeInTheDocument();
    expect(within(tabla).getByText("Clínica Sur")).toBeInTheDocument();
  });

  it("lista los adscritos con su tipo, consultorio y turno", async () => {
    render(<ReporteAdscripcionPage />);

    const tabla = await screen.findByRole("table", { name: /adscritos/i });
    const ana = await within(tabla).findByRole("row", { name: /pérez gómez ana/i });
    expect(within(ana).getByText("Titular")).toBeInTheDocument();
    expect(within(ana).getByText(/consultorio 4/i)).toBeInTheDocument();
    expect(within(tabla).getByRole("row", { name: /pérez gómez luis/i })).toHaveTextContent("Familiar");
  });

  it("filtra por centro, turno y tipo", async () => {
    const user = userEvent.setup();
    render(<ReporteAdscripcionPage />);
    // Las opciones de centro salen del resumen: se pintan cuando llega.
    await screen.findByRole("option", { name: "Clínica Sur" });

    await user.selectOptions(screen.getByLabelText(/^centro$/i), "7");
    await waitFor(() =>
      expect(adscripcionAPI.getReporteAdscritos).toHaveBeenLastCalledWith(expect.objectContaining({ centroId: 7 })),
    );
    // El resumen se pide una vez con todo el alcance; el centro se filtra en pantalla.
    expect(adscripcionAPI.getReporteResumen).toHaveBeenCalledTimes(1);
    const tabla = screen.getByRole("table", { name: /resumen por consultorio/i });
    expect(within(tabla).queryByText("Clínica Norte")).not.toBeInTheDocument();
    // Totales del centro elegido (total 1, titulares 1, familiares 0), no los globales.
    const totales = screen.getByRole("region", { name: /totales/i });
    expect(within(totales).queryByText("101")).not.toBeInTheDocument();
    expect(within(totales).getAllByText("1")).toHaveLength(2);
    expect(within(totales).getByText("0")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/^turno$/i), "1");
    await user.selectOptions(screen.getByLabelText(/^tipo$/i), "FAMILIAR");
    await waitFor(() =>
      expect(adscripcionAPI.getReporteAdscritos).toHaveBeenLastCalledWith(
        expect.objectContaining({ centroId: 7, turnoId: 1, tipo: "FAMILIAR", page: 1 }),
      ),
    );
  });

  it("ver los adscritos de un consultorio lo elige en el filtro", async () => {
    const user = userEvent.setup();
    render(<ReporteAdscripcionPage />);

    await user.click(await screen.findByRole("button", { name: /ver adscritos de consultorio 5/i }));

    await waitFor(() =>
      expect(adscripcionAPI.getReporteAdscritos).toHaveBeenLastCalledWith(
        expect.objectContaining({ consultorioId: 42 }),
      ),
    );
    expect(screen.getByLabelText(/^consultorio$/i)).toHaveValue("42");
  });

  it("el filtro de consultorio ofrece solo los del centro elegido", async () => {
    const user = userEvent.setup();
    render(<ReporteAdscripcionPage />);
    await screen.findByRole("option", { name: "Clínica Sur" });

    await user.selectOptions(screen.getByLabelText(/^centro$/i), "7");
    const select = screen.getByLabelText(/^consultorio$/i);
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Todos",
      "Consultorio 1 · Matutino",
    ]);

    await user.selectOptions(select, "71");
    await waitFor(() =>
      expect(adscripcionAPI.getReporteAdscritos).toHaveBeenLastCalledWith(
        expect.objectContaining({ centroId: 7, consultorioId: 71 }),
      ),
    );

    // Cambiar de centro limpia el consultorio, que ya no pertenece.
    await user.selectOptions(screen.getByLabelText(/^centro$/i), "5");
    expect(screen.getByLabelText(/^consultorio$/i)).toHaveValue("");
  });

  it("agrupa el resumen por centro y cada grupo se puede contraer", async () => {
    const user = userEvent.setup();
    render(<ReporteAdscripcionPage />);
    const tabla = await screen.findByRole("table", { name: /resumen por consultorio/i });
    await within(tabla).findByRole("row", { name: /consultorio 4/i });

    const norte = within(tabla).getByRole("button", { name: /clínica norte/i });
    expect(norte).toHaveAttribute("aria-expanded", "true");
    expect(norte).toHaveTextContent("100 adscritos");

    await user.click(norte);
    expect(norte).toHaveAttribute("aria-expanded", "false");
    expect(within(tabla).queryByRole("row", { name: /consultorio 4/i })).not.toBeInTheDocument();
    expect(within(tabla).getByRole("row", { name: /consultorio 1/i })).toBeInTheDocument();
  });

  it("muestra la ocupación contra el tope", async () => {
    render(<ReporteAdscripcionPage />);
    const tabla = await screen.findByRole("table", { name: /resumen por consultorio/i });

    const fila4 = await within(tabla).findByRole("row", { name: /consultorio 4/i });
    expect(within(fila4).getByRole("progressbar", { name: /ocupación/i })).toHaveAttribute("aria-valuenow", "30");

    const fila5 = within(tabla).getByRole("row", { name: /consultorio 5/i });
    expect(within(fila5).queryByRole("progressbar")).not.toBeInTheDocument();
    expect(within(fila5).getByText("40 / sin tope")).toBeInTheDocument();
  });

  it("exporta a Excel con los filtros aplicados", async () => {
    const exportar = vi.spyOn(adscripcionAPI, "exportReporteAdscritos").mockResolvedValue(new Blob(["x"]));
    Object.assign(URL, { createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
    const user = userEvent.setup();
    render(<ReporteAdscripcionPage />);
    await screen.findByRole("option", { name: "Clínica Sur" });

    await user.selectOptions(screen.getByLabelText(/^tipo$/i), "TITULAR");
    await user.click(screen.getByRole("button", { name: /exportar excel/i }));

    await waitFor(() => expect(exportar).toHaveBeenCalledWith(expect.objectContaining({ tipo: "TITULAR" })));
    expect(exportar.mock.calls[0][0]).not.toHaveProperty("page");
  });
});
