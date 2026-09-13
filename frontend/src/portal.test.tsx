import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider, LoginPage, Protected } from "./auth";
import { Dashboard, Layout, ProjectPage } from "./pages";
import { AdminPage } from "./admin";
import { TimelineTab } from "./project-tabs";
import { api, saveTokens } from "./api";
import type { Role, User } from "./types";
vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  api: vi.fn(),
}));
const mockApi = vi.mocked(api);
const project = {
  id: 1,
  title: "Head of Product",
  client_name: "Halcyon Labs",
  client_org_id: 1,
  description: "A new product leader.",
  ideal_profile: "Collaborative leadership.",
  agreement_terms: "Retained search terms.",
  start_date: "2026-09-01",
  end_date: "2026-11-01",
  created_at: "2026-09-01T12:00:00Z",
  unread_count: 2,
};
let current: User;
let savedMilestone: Record<string, unknown>;
function setup(role: Role = "admin", path = "/") {
  current = {
    id: 1,
    name: "Alex Morgan",
    email: `${role}@example.com`,
    role,
    agency_id: 1,
    client_org_id: role === "client" ? 1 : null,
  };
  saveTokens({ access_token: "test-access", refresh_token: "test-refresh" });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Protected />}>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route
                path="projects/:projectId/:tab?"
                element={<ProjectPage />}
              />
              <Route path="admin" element={<AdminPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  mockApi.mockReset();
  savedMilestone = {
    id: 1,
    title: "Deliver shortlist",
    description: "Three candidates.",
    target_date: "2020-01-01",
    completed: false,
  };
  mockApi.mockImplementation(
    async <T,>(path: string, method = "GET", body?: unknown): Promise<T> => {
      let result: unknown;
      if (path === "/auth/me") result = current;
      else if (path === "/auth/logout") result = undefined;
      else if (path === "/projects") result = [project];
      else if (path === "/projects/1") result = project;
      else if (path === "/projects/1/documents") result = [];
      else if (path === "/projects/1/candidates")
        result = [
          {
            id: 1,
            name: "Olivia Bennett",
            current_role: "Product Manager",
            company: "Arc",
            summary: "A strong profile.",
            cv_url: null,
            stage: "Interviewing",
            client_visible: true,
          },
        ];
      else if (path.endsWith("/feedback") && method === "POST")
        result = { id: 2, body: (body as { body: string }).body };
      else if (path.endsWith("/feedback")) result = [];
      else if (path === "/projects/1/milestones/1" && method === "PUT") {
        savedMilestone = { id: 1, ...(body as object) };
        result = savedMilestone;
      } else if (path === "/projects/1/milestones") result = [savedMilestone];
      else if (path === "/projects/1/messages/read") result = undefined;
      else if (path === "/projects/1/messages")
        result = [
          {
            id: 1,
            author_id: 2,
            author_name: "Jamie",
            body: "Hello!",
            created_at: "2026-09-01T12:00:00Z",
          },
        ];
      else if (path === "/projects/1/updates") result = [];
      else throw new Error(`Unexpected API call: ${method} ${path}`);
      return structuredClone(result) as T;
    },
  );
});

describe("Role-specific portal screens", () => {
  it("shows administrators project creation and access administration", async () => {
    setup();
    expect(
      await screen.findByRole("heading", { name: /Search workspace/ }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "New search" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Administration" })).toBeTruthy();
    expect(
      await screen.findByRole("heading", { name: "Head of Product" }),
    ).toBeTruthy();
  });
  it("lets recruiters manage candidates without exposing administration", async () => {
    setup("recruiter", "/projects/1/candidates");
    expect(
      await screen.findByRole("button", { name: "Add candidate" }),
    ).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Administration" })).toBeNull();
    expect(
      await screen.findByRole("button", { name: "Edit Olivia Bennett" }),
    ).toBeTruthy();
  });
  it("lets clients review shared candidates and send feedback without editing the pipeline", async () => {
    const user = userEvent.setup();
    setup("client", "/projects/1/candidates");
    expect(
      await screen.findByRole("heading", { name: "Olivia Bennett" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Add candidate" })).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Edit Olivia Bennett" }),
    ).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "View & add feedback" }),
    );
    await user.type(
      await screen.findByLabelText("Your feedback"),
      "Strong leadership experience.",
    );
    await user.click(screen.getByRole("button", { name: "Add feedback" }));
    await waitFor(() =>
      expect(mockApi).toHaveBeenCalledWith(
        "/projects/1/candidates/1/feedback",
        "POST",
        { body: "Strong leadership experience." },
      ),
    );
  });
  it("keeps agreement and timeline controls read-only for clients", async () => {
    const user = userEvent.setup();
    setup("client", "/projects/1/overview");
    expect(await screen.findByText("Retained search terms.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Edit details" })).toBeNull();
    await user.click(screen.getByRole("link", { name: "Timeline" }));
    expect(await screen.findByText("Deliver shortlist")).toBeTruthy();
    expect(screen.getByText("Overdue")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Add milestone" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Mark complete" })).toBeNull();
  });
  it("acknowledges only displayed messages and refreshes the conversation", async () => {
    const user = userEvent.setup();
    setup("client", "/projects/1/messages");
    expect(await screen.findByText("Hello!")).toBeTruthy();
    await waitFor(() =>
      expect(mockApi).toHaveBeenCalledWith("/projects/1/messages/read", "PUT", {
        last_message_id: 1,
      }),
    );
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() =>
      expect(
        mockApi.mock.calls.filter((c) => c[0] === "/projects/1/messages")
          .length,
      ).toBe(2),
    );
  });
  it("completes and reopens manual milestones", async () => {
    const user = userEvent.setup();
    render(<TimelineTab base="/projects/1" edit />);
    await user.click(
      await screen.findByRole("button", { name: "Mark complete" }),
    );
    expect(await screen.findByText("Completed")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Reopen milestone" }));
    expect(await screen.findByText("Overdue")).toBeTruthy();
    expect(savedMilestone.completed).toBe(false);
  });
  it("shows API failures rather than an empty success state", async () => {
    mockApi.mockRejectedValue(new Error("Unable to reach the server."));
    render(<TimelineTab base="/projects/1" edit />);
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Unable to reach the server.",
    );
  });
});
