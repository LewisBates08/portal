import { beforeEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider, LoginPage, Protected, RegisterPage } from "./auth";
import { Dashboard, Layout } from "./pages";
import { api, tokens } from "./api";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  api: vi.fn(),
}));
const mockApi = vi.mocked(api);
const account = {
  id: 12,
  name: "Taylor Smith",
  email: "taylor@example.com",
  role: "admin",
  agency_id: 8,
  client_org_id: null,
};
beforeEach(() => {
  mockApi.mockReset();
  mockApi.mockImplementation(async <T,>(path: string): Promise<T> => {
    if (path === "/auth/register")
      return {
        access_token: "new-access",
        refresh_token: "new-refresh",
        user: account,
      } as T;
    if (path === "/projects") return [] as T;
    throw new Error(`Unexpected API call: ${path}`);
  });
});
function open(path = "/register") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<Protected />}>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}
async function fill(confirm = "PasswordForSignup!") {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Your name"), "Taylor Smith");
  await user.type(screen.getByLabelText("Agency name"), "Taylor Search");
  await user.type(screen.getByLabelText("Email address"), "taylor@example.com");
  await user.type(
    screen.getByLabelText("Password (at least 10 characters)"),
    "PasswordForSignup!",
  );
  await user.type(screen.getByLabelText("Confirm password"), confirm);
  await user.click(screen.getByRole("button", { name: "Create account" }));
}
it("offers signup from login, creates the account and signs in to an empty workspace", async () => {
  open("/login");
  await userEvent.click(screen.getByRole("link", { name: "Create account" }));
  await fill();
  expect(
    await screen.findByRole("heading", { name: /Search workspace/ }),
  ).toBeTruthy();
  expect(await screen.findByText("Your next search starts here")).toBeTruthy();
  expect(screen.getByRole("button", { name: "New search" })).toBeTruthy();
  expect(mockApi).toHaveBeenCalledWith(
    "/auth/register",
    "POST",
    {
      name: "Taylor Smith",
      agency_name: "Taylor Search",
      email: "taylor@example.com",
      password: "PasswordForSignup!",
    },
    false,
  );
  expect(tokens()?.access_token).toBe("new-access");
});
it("rejects mismatched passwords before submitting", async () => {
  open();
  await fill("DifferentPassword!");
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Passwords do not match.",
  );
  expect(mockApi).not.toHaveBeenCalled();
  expect(tokens()).toBeNull();
});
it("shows duplicate email errors and keeps the form available for correction", async () => {
  mockApi.mockRejectedValue(
    new Error(
      "An account with this email already exists. Please sign in instead.",
    ),
  );
  open();
  await fill();
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "An account with this email already exists. Please sign in instead.",
  );
  expect(screen.getByDisplayValue("Taylor Search")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Sign in" })).toBeTruthy();
  expect(tokens()).toBeNull();
});
it("keeps the existing invitation route visible to invited users", async () => {
  sessionStorage.setItem("searchroom.invite", "pending-invitation");
  open();
  expect(
    await screen.findByRole("link", { name: "Accept your invitation" }),
  ).toHaveProperty(
    "href",
    "http://localhost:5173/invite#token=pending-invitation",
  );
  expect(mockApi).not.toHaveBeenCalled();
});
