import { useState } from "react";
import { Navigate } from "react-router-dom";
import { Copy, Link2, ShieldCheck, Trash2, Users } from "lucide-react";
import { useAuth } from "./auth";
import { api } from "./api";
import {
  dateLabel,
  Empty,
  ErrorBox,
  Field,
  Form,
  Initials,
  Loading,
  str,
  useRemote,
} from "./ui";
import type { ClientOrg, Invitation, Project, User } from "./types";

function AccessPanel({ project, users }: { project: Project; users: User[] }) {
  const members = useRemote<User[]>(`/projects/${project.id}/members`);
  const [error, setError] = useState("");
  const available = users.filter(
    (u) =>
      u.role !== "admin" &&
      (u.role !== "client" || u.client_org_id === project.client_org_id) &&
      !members.data?.some((m) => m.id === u.id),
  );
  return (
    <div>
      <ErrorBox message={members.error || error} />
      {members.loading ? (
        <Loading />
      ) : (
        <>
          {members.data?.length ? (
            <div className="people-list">
              {members.data.map((m) => (
                <div key={m.id}>
                  <Initials name={m.name} />
                  <div>
                    <strong>{m.name}</strong>
                    <span className="muted small">
                      {m.email} · {m.role}
                    </span>
                  </div>
                  <button
                    className="icon-button danger"
                    aria-label={`Remove access for ${m.name}`}
                    onClick={async () => {
                      if (
                        !window.confirm(
                          `Remove ${m.name} from ${project.title}?`,
                        )
                      )
                        return;
                      try {
                        await api(
                          `/projects/${project.id}/members/${m.id}`,
                          "DELETE",
                        );
                        members.reload();
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    <Trash2 size={17} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">
              No recruiters or clients assigned yet. Agency admins can always
              access this search.
            </p>
          )}
          {available.length > 0 && (
            <Form
              submit="Grant project access"
              onSubmit={async (f) => {
                await api(
                  `/projects/${project.id}/members/${str(f, "user_id")}`,
                  "PUT",
                );
                members.reload();
              }}
            >
              <Field
                label="Add an existing user"
                name="user_id"
                value=""
                required
              >
                <option value="" disabled>
                  Choose a user
                </option>
                {available.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.role})
                  </option>
                ))}
              </Field>
            </Form>
          )}
        </>
      )}
    </div>
  );
}
export function AdminPage() {
  const { user } = useAuth();
  if (user?.role !== "admin") return <Navigate to="/" replace />;
  return <Administration />;
}
function Administration() {
  const users = useRemote<User[]>("/users");
  const orgs = useRemote<ClientOrg[]>("/client-organisations");
  const projects = useRemote<Project[]>("/projects");
  const invites = useRemote<Invitation[]>("/invitations");
  const [selected, setSelected] = useState("");
  const [link, setLink] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [role, setRole] = useState("client");
  const project = projects.data?.find((p) => p.id === Number(selected));
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">AGENCY ADMINISTRATION</span>
          <h1>
            People & access<span className="accent-dot">.</span>
          </h1>
          <p className="muted">Bring the right people into each search.</p>
        </div>
        <ShieldCheck size={34} className="muted" />
      </div>
      <ErrorBox
        message={
          users.error || orgs.error || projects.error || invites.error || error
        }
      />
      <div className="admin-grid">
        <section className="panel">
          <h2>
            <Link2 size={20} />
            Invite someone
          </h2>
          <Form
            submit="Create invitation link"
            onSubmit={async (f) => {
              const result = await api<{ url: string }>(
                "/invitations",
                "POST",
                {
                  email: str(f, "email"),
                  role,
                  project_id: str(f, "project_id")
                    ? Number(str(f, "project_id"))
                    : null,
                },
              );
              setLink(result.url);
              setCopied(false);
              invites.reload();
            }}
          >
            <Field label="Email address" name="email" type="email" required />
            <label className="field">
              <span>Role</span>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="client">Client</option>
                <option value="recruiter">Recruiter</option>
              </select>
            </label>
            <Field
              label={role === "client" ? "Project" : "Project (optional)"}
              name="project_id"
              required={role === "client"}
              value=""
            >
              <option value="">
                {role === "client" ? "Choose a project" : "Agency access only"}
              </option>
              {projects.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} · {p.client_name}
                </option>
              ))}
            </Field>
          </Form>
          {link && (
            <div className="invite-result" role="status">
              <strong>Invitation ready</strong>
              <p className="small">
                Share this link manually. It expires in seven days and can be
                used once.
              </p>
              <label className="field">
                <span>Invitation link</span>
                <input
                  readOnly
                  value={link}
                  onFocus={(e) => e.target.select()}
                />
              </label>
              <button
                className="button secondary"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(link);
                    setCopied(true);
                  } catch {
                    setError("Copy the link from the field above.");
                  }
                }}
              >
                <Copy size={16} />
                {copied ? "Copied" : "Copy link"}
              </button>
            </div>
          )}
        </section>
        <section className="panel">
          <h2>
            <Users size={20} />
            Client organisations
          </h2>
          {orgs.loading ? (
            <Loading />
          ) : (
            <ul className="org-list">
              {orgs.data?.map((o) => (
                <li key={o.id}>
                  <span className="company-icon small-icon">
                    {o.name.slice(0, 2).toUpperCase()}
                  </span>
                  {o.name}
                </li>
              ))}
            </ul>
          )}
          <Form
            reset
            submit="Add organisation"
            onSubmit={async (f) => {
              await api("/client-organisations", "POST", {
                name: str(f, "name"),
              });
              orgs.reload();
            }}
          >
            <Field label="Client organisation name" name="name" required />
          </Form>
        </section>
      </div>
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Project access</h2>
            <p className="muted">
              Assignment gives recruiters editing access and clients
              collaboration access.
            </p>
          </div>
        </div>
        <label className="field">
          <span>Choose a search</span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            <option value="">Select a project</option>
            {projects.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title} · {p.client_name}
              </option>
            ))}
          </select>
        </label>
        {project && users.data && (
          <AccessPanel key={project.id} project={project} users={users.data} />
        )}
      </section>
      <section className="panel">
        <h2>Agency directory</h2>
        {users.loading ? (
          <Loading />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                {users.data?.map((u) => (
                  <tr key={u.id}>
                    <td>{u.name}</td>
                    <td>{u.email}</td>
                    <td>
                      <span className="badge">
                        {u.role === "admin" ? "Agency admin" : u.role}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section className="panel">
        <h2>Invitations</h2>
        {invites.loading ? (
          <Loading />
        ) : invites.data?.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Expires</th>
                  <th>Status</th>
                  <th>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {invites.data.map((i) => {
                  const status = i.used_at
                    ? "Accepted"
                    : i.revoked
                      ? "Revoked"
                      : new Date(i.expires_at) < new Date()
                        ? "Expired"
                        : "Pending";
                  return (
                    <tr key={i.id}>
                      <td>{i.email}</td>
                      <td>{i.role}</td>
                      <td>{dateLabel(i.expires_at)}</td>
                      <td>
                        <span
                          className={`badge ${status === "Accepted" ? "green" : ""}`}
                        >
                          {status}
                        </span>
                      </td>
                      <td>
                        {status === "Pending" && (
                          <button
                            className="text-button danger"
                            onClick={async () => {
                              if (
                                !window.confirm(
                                  `Revoke the invitation for ${i.email}?`,
                                )
                              )
                                return;
                              try {
                                await api(`/invitations/${i.id}`, "DELETE");
                                invites.reload();
                              } catch (e) {
                                setError((e as Error).message);
                              }
                            }}
                          >
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="No invitations yet">
            Create a link to invite a recruiter or client.
          </Empty>
        )}
      </section>
    </>
  );
}
