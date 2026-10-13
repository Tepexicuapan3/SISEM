import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@/test/utils";
import { toast } from "sonner";
import { MedicoImportDialog } from "@features/admin/modules/medicos/components/MedicoImportDialog";
import { useMedicoImportPreview } from "@features/admin/modules/medicos/hooks/useMedicoImportPreview";
import { useMedicoImportConfirm } from "@features/admin/modules/medicos/hooks/useMedicoImportConfirm";
import { useMedicoImportTemplateDownload } from "@features/admin/modules/medicos/hooks/useMedicoImportTemplateDownload";
import type {
  MedicoImportResult,
  MedicoImportRowData,
} from "@api/types/medicos.types";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock(
  "@features/admin/modules/medicos/hooks/useMedicoImportPreview",
  () => ({
    useMedicoImportPreview: vi.fn(),
  }),
);

vi.mock(
  "@features/admin/modules/medicos/hooks/useMedicoImportConfirm",
  () => ({
    useMedicoImportConfirm: vi.fn(),
  }),
);

vi.mock(
  "@features/admin/modules/medicos/hooks/useMedicoImportTemplateDownload",
  () => ({
    useMedicoImportTemplateDownload: vi.fn(),
  }),
);

const buildData = (
  overrides: Partial<MedicoImportRowData> = {},
): MedicoImportRowData => ({
  noMedico: null,
  usuario: "",
  usuarioId: null,
  paterno: null,
  materno: null,
  nombre: null,
  cedulaProfesional: null,
  escuela: null,
  escuelaId: null,
  sexo: null,
  fechaNac: null,
  especialidad: null,
  especialidadId: null,
  tipoMedico: "CLINICA",
  servicio: null,
  estatusMedico: "ACTIVO",
  observaciones: null,
  ...overrides,
});

const buildResult = (
  overrides: Partial<MedicoImportResult> = {},
): MedicoImportResult => ({
  totalRecords: 2,
  totalErrores: 0,
  totalWarnings: 0,
  warningSummary: [],
  inserted: 0,
  rows: [
    {
      row: 2,
      data: buildData({
        noMedico: 2726,
        usuario: "jperez",
        usuarioId: 1,
        servicio: "Cardiología",
      }),
      errors: [],
      warnings: [],
    },
    {
      row: 3,
      data: buildData({
        usuario: "mgomez",
        usuarioId: 2,
        tipoMedico: "HOSPITAL",
      }),
      errors: [],
      warnings: [],
    },
  ],
  ...overrides,
});

const createFile = () =>
  new File(["dummy"], "medicos.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });

describe("MedicoImportDialog UI", () => {
  const onOpenChange = vi.fn();
  const previewMutateAsync = vi.fn();
  const confirmMutateAsync = vi.fn();
  const download = vi.fn();

  beforeEach(() => {
    vi.mocked(useMedicoImportPreview).mockReturnValue({
      mutateAsync: previewMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useMedicoImportPreview>);
    vi.mocked(useMedicoImportConfirm).mockReturnValue({
      mutateAsync: confirmMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useMedicoImportConfirm>);
    vi.mocked(useMedicoImportTemplateDownload).mockReturnValue({
      download,
      isDownloading: false,
    });

    onOpenChange.mockReset();
    previewMutateAsync.mockReset();
    confirmMutateAsync.mockReset();
    download.mockReset();
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
  });

  it("disables validation until a file is selected", () => {
    render(<MedicoImportDialog open onOpenChange={onOpenChange} />);

    expect(
      screen.getByRole("button", { name: /validar archivo/i }),
    ).toBeDisabled();
  });

  it("downloads the template when clicked", async () => {
    const user = userEvent.setup();
    render(<MedicoImportDialog open onOpenChange={onOpenChange} />);

    await user.click(
      screen.getByRole("button", { name: /descargar plantilla/i }),
    );

    expect(download).toHaveBeenCalledTimes(1);
  });

  it("previews a valid file and enables confirm when there are no errors", async () => {
    const user = userEvent.setup();
    previewMutateAsync.mockResolvedValue(buildResult({ totalErrores: 0 }));

    render(<MedicoImportDialog open onOpenChange={onOpenChange} />);

    const fileInput = screen.getByLabelText(/archivo excel/i);
    await user.upload(fileInput, createFile());

    await user.click(screen.getByRole("button", { name: /validar archivo/i }));

    await waitFor(() => {
      expect(previewMutateAsync).toHaveBeenCalledWith({
        file: expect.any(File),
      });
    });

    expect(await screen.findByText("jperez")).toBeVisible();
    expect(
      screen.getByRole("button", { name: /confirmar e importar/i }),
    ).toBeEnabled();
  });

  it("disables confirm and shows guidance when the preview has errors", async () => {
    const user = userEvent.setup();
    previewMutateAsync.mockResolvedValue(
      buildResult({
        totalErrores: 1,
        rows: [
          {
            row: 2,
            data: buildData({}),
            errors: ["Nombre(s) es obligatorio cuando no se captura Usuario."],
            warnings: [],
          },
        ],
      }),
    );

    render(<MedicoImportDialog open onOpenChange={onOpenChange} />);

    const fileInput = screen.getByLabelText(/archivo excel/i);
    await user.upload(fileInput, createFile());
    await user.click(screen.getByRole("button", { name: /validar archivo/i }));

    expect(
      await screen.findByText("Nombre(s) es obligatorio cuando no se captura Usuario."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: /confirmar e importar/i }),
    ).toBeDisabled();
    expect(
      screen.getByText(/no se puede confirmar parcialmente/i),
    ).toBeVisible();
  });

  it("shows an error badge for an invalid Estatus value and blocks confirm", async () => {
    const user = userEvent.setup();
    previewMutateAsync.mockResolvedValue(
      buildResult({
        totalErrores: 1,
        rows: [
          {
            row: 2,
            data: buildData({
              usuario: "jperez",
              usuarioId: 1,
            }),
            errors: [
              "Estatus del Médico 'Jubilado' no es válido. Valores permitidos: ACTIVO, VACACIONES, INCAPACIDAD, SUSPENDIDO, BAJA (o A / B).",
            ],
            warnings: [],
          },
        ],
      }),
    );

    render(<MedicoImportDialog open onOpenChange={onOpenChange} />);

    const fileInput = screen.getByLabelText(/archivo excel/i);
    await user.upload(fileInput, createFile());
    await user.click(screen.getByRole("button", { name: /validar archivo/i }));

    expect(
      await screen.findByText(
        "Estatus del Médico 'Jubilado' no es válido. Valores permitidos: ACTIVO, VACACIONES, INCAPACIDAD, SUSPENDIDO, BAJA (o A / B).",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: /confirmar e importar/i }),
    ).toBeDisabled();
  });

  it("shows a warning summary grouped by type instead of per-row warnings", async () => {
    const user = userEvent.setup();
    const sinCedula = "Sin Usuario y sin Cédula Profesional: el médico queda sin cédula.";
    previewMutateAsync.mockResolvedValue(
      buildResult({
        totalErrores: 0,
        totalWarnings: 3,
        warningSummary: [
          {
            code: "SIN_CEDULA",
            description: "Médicos sin usuario y sin Cédula Profesional: se crean sin cédula.",
            count: 2,
            rows: [2, 3],
          },
          {
            code: "NOMBRE_IGNORADO",
            description: "Médicos con usuario que traen nombre o apellidos en el Excel: se ignoran (se toman del usuario).",
            count: 1,
            rows: [4],
          },
        ],
        rows: [
          {
            row: 2,
            data: buildData({ noMedico: 35, paterno: "López", materno: "Ramírez", nombre: "Juan" }),
            errors: [],
            warnings: [sinCedula],
          },
        ],
      }),
    );

    render(<MedicoImportDialog open onOpenChange={onOpenChange} />);

    await user.upload(screen.getByLabelText(/archivo excel/i), createFile());
    await user.click(screen.getByRole("button", { name: /validar archivo/i }));

    const summary = await screen.findByRole("list", { name: /resumen de advertencias/i });
    expect(within(summary).getAllByRole("listitem")).toHaveLength(2);
    expect(within(summary).getByText(/se crean sin cédula/i)).toBeVisible();
    expect(within(summary).getByText("Filas: 2, 3")).toBeVisible();
    expect(within(summary).getByText("Fila: 4")).toBeVisible();
    expect(screen.getByText(/3 filas con advertencia/i)).toBeVisible();
    // El detalle por fila ya no se muestra en la tabla.
    expect(screen.queryByText(sinCedula)).not.toBeInTheDocument();
    expect(screen.getByText("Juan López Ramírez")).toBeVisible();
    expect(
      screen.getByRole("button", { name: /confirmar e importar/i }),
    ).toBeEnabled();
  });

  it("summarizes long row lists with 'y N más'", async () => {
    const user = userEvent.setup();
    const rows = Array.from({ length: 30 }, (_, i) => i + 2);
    previewMutateAsync.mockResolvedValue(
      buildResult({
        totalWarnings: 30,
        warningSummary: [
          { code: "SIN_CEDULA", description: "Sin cédula.", count: 30, rows },
        ],
      }),
    );

    render(<MedicoImportDialog open onOpenChange={onOpenChange} />);

    await user.upload(screen.getByLabelText(/archivo excel/i), createFile());
    await user.click(screen.getByRole("button", { name: /validar archivo/i }));

    expect(await screen.findByText(/y 5 más$/)).toBeVisible();
  });

  it("blocks confirm when there are errors even if there are also warnings", async () => {
    const user = userEvent.setup();
    previewMutateAsync.mockResolvedValue(
      buildResult({
        totalErrores: 1,
        totalWarnings: 1,
        rows: [
          {
            row: 2,
            data: buildData({ noMedico: 10 }),
            errors: ["Ya existe un médico con el No. Médico 10."],
            warnings: ["Sin Usuario y sin Cédula Profesional: el médico queda sin cédula."],
          },
        ],
      }),
    );

    render(<MedicoImportDialog open onOpenChange={onOpenChange} />);

    await user.upload(screen.getByLabelText(/archivo excel/i), createFile());
    await user.click(screen.getByRole("button", { name: /validar archivo/i }));

    expect(
      await screen.findByText("Ya existe un médico con el No. Médico 10."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: /confirmar e importar/i }),
    ).toBeDisabled();
  });

  it("confirms, closes the dialog and shows a success toast with the inserted count", async () => {
    const user = userEvent.setup();
    previewMutateAsync.mockResolvedValue(buildResult({ totalErrores: 0 }));
    confirmMutateAsync.mockResolvedValue(
      buildResult({ totalErrores: 0, inserted: 2 }),
    );

    render(<MedicoImportDialog open onOpenChange={onOpenChange} />);

    const fileInput = screen.getByLabelText(/archivo excel/i);
    await user.upload(fileInput, createFile());
    await user.click(screen.getByRole("button", { name: /validar archivo/i }));
    await screen.findByRole("button", { name: /confirmar e importar/i });

    await user.click(
      screen.getByRole("button", { name: /confirmar e importar/i }),
    );

    await waitFor(() => {
      expect(confirmMutateAsync).toHaveBeenCalledWith({
        file: expect.any(File),
        onProgress: expect.any(Function),
      });
    });

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
    expect(toast.success).toHaveBeenCalledWith(
      "Médicos importados",
      expect.objectContaining({
        description: expect.stringContaining("2"),
      }),
    );
  });
});
