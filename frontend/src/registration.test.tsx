import { beforeEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider, RegisterPage, MfaPage } from "./auth";
import { api, ApiError } from "./api";
vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  api: vi.fn(),
}));
const mocked = vi.mocked(api);
beforeEach(() => {
  mocked.mockReset();
  mocked.mockImplementation(async (path) => {
    if (path === "/auth/me") throw new ApiError("Sign in", 401);
    return {} as never;
  });
});
it("requires email verification instead of storing login credentials after signup", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>
    </MemoryRouter>,
  );
  await user.type(await screen.findByLabelText("Your name"), "Test Person");
  await user.type(screen.getByLabelText("Agency name"), "Test Agency");
  await user.type(screen.getByLabelText("Email address"), "test@example.com");
  await user.type(
    screen.getByLabelText("Password (at least 10 characters)"),
    "PasswordForTests!",
  );
  await user.type(
    screen.getByLabelText("Confirm password"),
    "PasswordForTests!",
  );
  await user.click(screen.getByRole("button", { name: "Create account" }));
  expect(
    await screen.findByRole("heading", { name: "Check your email" }),
  ).toBeTruthy();
  expect(localStorage.getItem("searchroom.tokens")).toBeNull();
});
it("preserves signup fields when passwords do not match", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>
    </MemoryRouter>,
  );
  await user.type(await screen.findByLabelText("Your name"), "Test");
  await user.type(screen.getByLabelText("Agency name"), "Agency");
  await user.type(screen.getByLabelText("Email address"), "test@example.com");
  await user.type(
    screen.getByLabelText("Password (at least 10 characters)"),
    "PasswordForTests!",
  );
  await user.type(
    screen.getByLabelText("Confirm password"),
    "AnotherPassword!",
  );
  await user.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Passwords do not match.",
  );
});
it("requires saving recovery codes before leaving authenticator setup", async () => {
  mocked.mockImplementation(
    async (path) =>
      (path.endsWith("/setup")
        ? { secret: "EXAMPLEKEY" }
        : { recovery_codes: ["recovery-code"] }) as never,
  );
  const user = userEvent.setup();
  const done = vi.fn();
  render(
    <MemoryRouter>
      <MfaPage setup done={done} />
    </MemoryRouter>,
  );
  await user.click(screen.getByRole("button", { name: "Generate setup key" }));
  await user.type(
    await screen.findByLabelText("Authenticator or recovery code"),
    "123456",
  );
  await user.click(screen.getByRole("button", { name: "Verify code" }));
  expect(await screen.findByText("recovery-code")).toBeTruthy();
  expect(done).not.toHaveBeenCalled();
});
