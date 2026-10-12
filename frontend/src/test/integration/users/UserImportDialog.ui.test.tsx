import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { toast } from "sonner";
import { UserImportDialog } from "@/domains/auth-access/components/admin/rbac/users/UserImportDialog";
import { useUserImportPreview } from "@/domains/auth-access/hooks/rbac/users/useUserImportPreview";
import { useUserImportConfirm } from "@/domains/auth-access/hooks/rbac/users/useUserImportConfirm";
import { useUserImportTemplateDownload } from "@/domains/auth-access/hooks/rbac/users/useUserImportTemplateDownload";
import type { UserImportResult } from "@api/types";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock(
  "@/domains/auth-access/hooks/rbac/users/useUserImportPreview",
  () => ({
    useUserImportPreview: vi.fn(),
  }),
);

vi.mock(
  "@/domains/auth-access/hooks/rbac/users/useUserImportConfirm",
  () => ({
    useUserImportConfirm: vi.fn(),
  }),
);

vi.mock(
  "@/domains/auth-access/hooks/rbac/users/useUserImportTemplateDownload",
  () => ({
    useUserImportTemplateDownload: vi.fn(),
  }),
);

const buildResult = (
  overrides: Partial<UserImportResult> = {},
): UserImportResult => ({
  totalRecords: 2,
  totalErrores: 0,
  inserted: 0,
  rows: [
    {
      row: 2,
      data: {
        username: "jperez",
        firstName: "Juan",
        paternalName: "Perez",
        maternalName: "Lopez",
        email: "jperez@metro.cdmx.gob.mx",
        noExp: "123456",
        roleName: "Admin",
        roleId: 1,
        tipoPersonalName: "Médico",
        tipoPersonalId: 1,
        estado: "Activo",
        isActive: true,
      },
      errors: [],
    },
    {
      row: 3,
      data: {
        username: "mlopez",
        firstName: "Maria",
        paternalName: "Lopez",
        maternalName: "",
        email: null,
        noExp: null,
        roleName: "Clinico",
        roleId: 2,
        tipoPersonalName: "Enfermería",
        tipoPersonalId: 2,
        estado: "Activo",
        isActive: true,
      },
      errors: [],
    },
  ],
  ...overrides,
});

const createFile = () =>
  new File(["dummy"], "usuarios.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });

describe("UserImportDialog UI", () => {
  const onOpenChange = vi.fn();
  const previewMutateAsync = vi.fn();
  const confirmMutateAsync = vi.fn();
  const download = vi.fn();

  beforeEach(() => {
    vi.mocked(useUserImportPreview).mockReturnValue({
      mutateAsync: previewMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUserImportPreview>);
    vi.mocked(useUserImportConfirm).mockReturnValue({
      mutateAsync: confirmMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUserImportConfirm>);
    vi.mocked(useUserImportTemplateDownload).mockReturnValue({
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
    render(<UserImportDialog open onOpenChange={onOpenChange} />);

    expect(
      screen.getByRole("button", { name: /validar archivo/i }),
    ).toBeDisabled();
  });

  it("downloads the template when clicked", async () => {
    const user = userEvent.setup();
    render(<UserImportDialog open onOpenChange={onOpenChange} />);

    await user.click(
      screen.getByRole("button", { name: /descargar plantilla/i }),
    );

    expect(download).toHaveBeenCalledTimes(1);
  });

  it("previews a valid file and enables confirm when there are no errors", async () => {
    const user = userEvent.setup();
    previewMutateAsync.mockResolvedValue(buildResult({ totalErrores: 0 }));

    render(<UserImportDialog open onOpenChange={onOpenChange} />);

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
              username: "",
              firstName: "Juan",
              paternalName: "Perez",
              maternalName: "",
              email: null,
              noExp: null,
              roleName: "",
              roleId: null,
              tipoPersonalName: "",
              tipoPersonalId: null,
              estado: "Activo",
              isActive: true,
            },
            errors: ["Usuario es obligatorio."],
          },
        ],
      }),
    );

    render(<UserImportDialog open onOpenChange={onOpenChange} />);

    const fileInput = screen.getByLabelText(/archivo excel/i);
    await user.upload(fileInput, createFile());
    await user.click(screen.getByRole("button", { name: /validar archivo/i }));

    expect(await screen.findByText("Usuario es obligatorio.")).toBeVisible();
    expect(
      screen.getByRole("button", { name: /confirmar e importar/i }),
    ).toBeDisabled();
    expect(
      screen.getByText(/no se puede confirmar parcialmente/i),
    ).toBeVisible();
  });

  it("confirms, closes the dialog and shows a success toast with the inserted count", async () => {
    const user = userEvent.setup();
    previewMutateAsync.mockResolvedValue(buildResult({ totalErrores: 0 }));
    confirmMutateAsync.mockResolvedValue(
      buildResult({ totalErrores: 0, inserted: 2 }),
    );

    render(<UserImportDialog open onOpenChange={onOpenChange} />);

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
      "Usuarios importados",
      expect.objectContaining({
        description: expect.stringContaining("2"),
      }),
    );
  });

  it("shows the background import progress while the confirm is pending", () => {
    vi.mocked(useUserImportConfirm).mockReturnValue({
      mutateAsync: confirmMutateAsync,
      isPending: true,
    } as unknown as ReturnType<typeof useUserImportConfirm>);

    render(<UserImportDialog open onOpenChange={onOpenChange} />);

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.getByText(/en cola, esperando al servidor/i)).toBeVisible();
    expect(
      screen.getByRole("button", { name: /importando/i }),
    ).toBeDisabled();
  });
});
