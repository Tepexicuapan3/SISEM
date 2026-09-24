import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { toast } from "sonner";
import { MedicoImportDialog } from "@features/admin/modules/medicos/components/MedicoImportDialog";
import { useMedicoImportPreview } from "@features/admin/modules/medicos/hooks/useMedicoImportPreview";
import { useMedicoImportConfirm } from "@features/admin/modules/medicos/hooks/useMedicoImportConfirm";
import { useMedicoImportTemplateDownload } from "@features/admin/modules/medicos/hooks/useMedicoImportTemplateDownload";
import type { MedicoImportResult } from "@api/types/medicos.types";

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

const buildResult = (
  overrides: Partial<MedicoImportResult> = {},
): MedicoImportResult => ({
  totalRecords: 2,
  totalErrores: 0,
  inserted: 0,
  rows: [
    {
      row: 2,
      data: {
        legacyCdMedico: "E00000",
        usuario: "jperez",
        usuarioId: 1,
        nombreDisplay: "Dr. Juan Pérez",
        tipoMedico: "CLINICA",
        servicio: "Cardiología",
        estatusMedico: "ACTIVO",
        observaciones: null,
      },
      errors: [],
    },
    {
      row: 3,
      data: {
        legacyCdMedico: null,
        usuario: "mgomez",
        usuarioId: 2,
        nombreDisplay: null,
        tipoMedico: "HOSPITAL",
        servicio: null,
        estatusMedico: "ACTIVO",
        observaciones: null,
      },
      errors: [],
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
            data: {
              legacyCdMedico: null,
              usuario: "",
              usuarioId: null,
              nombreDisplay: null,
              tipoMedico: "CLINICA",
              servicio: null,
              estatusMedico: "ACTIVO",
              observaciones: null,
            },
            errors: ["Usuario (Login del sistema) es obligatorio."],
          },
        ],
      }),
    );

    render(<MedicoImportDialog open onOpenChange={onOpenChange} />);

    const fileInput = screen.getByLabelText(/archivo excel/i);
    await user.upload(fileInput, createFile());
    await user.click(screen.getByRole("button", { name: /validar archivo/i }));

    expect(
      await screen.findByText("Usuario (Login del sistema) es obligatorio."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: /confirmar e importar/i }),
    ).toBeDisabled();
    expect(
      screen.getByText(/no se puede confirmar parcialmente/i),
    ).toBeVisible();
  });

  it("shows an error badge for an invalid Tipo de Médico value and blocks confirm", async () => {
    const user = userEvent.setup();
    previewMutateAsync.mockResolvedValue(
      buildResult({
        totalErrores: 1,
        rows: [
          {
            row: 2,
            data: {
              legacyCdMedico: null,
              usuario: "jperez",
              usuarioId: 1,
              nombreDisplay: null,
              tipoMedico: "CLINICA",
              servicio: null,
              estatusMedico: "ACTIVO",
              observaciones: null,
            },
            errors: [
              "Tipo de Médico 'Clinca' no es válido. Valores permitidos: CLINICA, HOSPITAL, AMBOS.",
            ],
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
        "Tipo de Médico 'Clinca' no es válido. Valores permitidos: CLINICA, HOSPITAL, AMBOS.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: /confirmar e importar/i }),
    ).toBeDisabled();
  });

  it("shows an error badge for an invalid Estatus value and blocks confirm", async () => {
    const user = userEvent.setup();
    previewMutateAsync.mockResolvedValue(
      buildResult({
        totalErrores: 1,
        rows: [
          {
            row: 2,
            data: {
              legacyCdMedico: null,
              usuario: "jperez",
              usuarioId: 1,
              nombreDisplay: null,
              tipoMedico: "CLINICA",
              servicio: null,
              estatusMedico: "ACTIVO",
              observaciones: null,
            },
            errors: [
              "Estatus del Médico 'Jubilado' no es válido. Valores permitidos: ACTIVO, VACACIONES, INCAPACIDAD, SUSPENDIDO, BAJA.",
            ],
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
        "Estatus del Médico 'Jubilado' no es válido. Valores permitidos: ACTIVO, VACACIONES, INCAPACIDAD, SUSPENDIDO, BAJA.",
      ),
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
