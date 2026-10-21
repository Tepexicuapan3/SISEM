import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { render, screen } from "@/test/utils";
import { UserDetailsGeneralTab } from "@/domains/auth-access/components/admin/rbac/users/UserDetailsGeneralTab";
import { createMockUserDetail } from "@/test/factories/users";
import type { UserDetailsFormValues } from "@/domains/auth-access/types/rbac/users.schemas";
import type { CentroAtencionListItem } from "@api/types";

const createClinicOption = (
  overrides: Partial<CentroAtencionListItem> = {},
): CentroAtencionListItem => ({
  id: 1,
  name: "Centro 1",
  folioCode: "CEN-001",
  isExternal: false,
  isActive: true,
  ...overrides,
});

const renderGeneralTab = () => {
  const userDetail = createMockUserDetail({
    id: 17,
    username: "jperez",
    primaryRole: "Clinico",
    isActive: true,
  });
  const clinicOptions = [createClinicOption({ id: 1, name: "Centro 1" })];

  const Wrapper = () => {
    const form = useForm<UserDetailsFormValues>({
      defaultValues: {
        firstName: userDetail.firstName,
        paternalName: userDetail.paternalName,
        maternalName: userDetail.maternalName,
        email: userDetail.email,
        clinicId: userDetail.clinic?.id ?? null,
      },
    });

    return (
      <UserDetailsGeneralTab
        form={form}
        formId="user-details-form"
        clinicOptions={clinicOptions}
        userDetail={userDetail}
        onSubmit={vi.fn()}
      />
    );
  };

  render(<Wrapper />);
};

describe("UserDetailsGeneralTab", () => {
  it("renders account summary and audit metadata", () => {
    renderGeneralTab();

    expect(screen.getByText("jperez")).toBeVisible();
    expect(screen.getByText("Clinico")).toBeVisible();
    expect(screen.getByLabelText("Nombre")).toBeVisible();
    expect(screen.getByLabelText("Correo")).toBeVisible();
    expect(screen.getByText("Centro de atención")).toBeVisible();
  });

  it("does not offer account status editing", () => {
    renderGeneralTab();

    expect(screen.queryByText("Estado de la cuenta")).toBeNull();
    expect(
      screen.queryByRole("combobox", { name: "Estado de la cuenta" }),
    ).toBeNull();
  });
});
