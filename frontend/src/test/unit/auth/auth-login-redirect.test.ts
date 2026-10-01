import { describe, expect, it } from "vitest";
import { resolvePostLoginRedirect } from "@/domains/auth-access/adapters/login-redirect";

describe("resolvePostLoginRedirect", () => {
  it("returns the internal route the user was on, with search and hash", () => {
    expect(
      resolvePostLoginRedirect({
        from: { pathname: "/expedientes/12", search: "?tab=notas", hash: "#n3" },
      }),
    ).toBe("/expedientes/12?tab=notas#n3");
  });

  it.each([
    ["no state", null],
    ["no from", {}],
    ["login page", { from: { pathname: "/login" } }],
    ["onboarding", { from: { pathname: "/onboarding" } }],
    ["root", { from: { pathname: "/" } }],
    ["protocol-relative url", { from: { pathname: "//evil.example" } }],
    ["absolute url", { from: { pathname: "https://evil.example" } }],
  ])("ignores %s", (_label, state) => {
    expect(resolvePostLoginRedirect(state)).toBeNull();
  });
});
