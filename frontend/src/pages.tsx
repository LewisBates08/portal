import { useState } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  BriefcaseBusiness,
  CalendarDays,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Plus,
  Settings2,
  Users,
} from "lucide-react";
import { api } from "./api";
import { Brand, useAuth } from "./auth";
import {
  CandidatesTab,
  MessagesTab,
  OverviewTab,
  TimelineTab,
  UpdatesTab,
} from "./project-tabs";
import {
  dateLabel,
  Editor,
  Empty,
  ErrorBox,
  Field,
  Form,
  Initials,
  Loading,
  optional,
  str,
  useRemote,
  More,
} from "./ui";
import { stages } from "./types";
import type { Candidate, ClientOrg, Project } from "./types";

export function Layout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand-link">
          <Brand />
        </Link>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          <NavLink to="/" end>
            <LayoutDashboard size={19} />
            Searches
          </NavLink>
          {user?.role === "admin" && (
            <NavLink to="/admin">
              <Settings2 size={19} />
              Administration
            </NavLink>
          )}
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" />A shared view.
          <br />
          <span>Every step of the search.</span>
        </div>
        <div className="sidebar-user">
          <Initials name={user!.name} />
          <div>
            <strong>{user?.name}</strong>
            <small>
              {user?.role === "admin"
                ? "Agency admin"
                : user?.role === "recruiter"
                  ? "Recruiter"
                  : "Client"}
            </small>
          </div>
          <button
            className="icon-button"
            aria-label="Sign out"
            onClick={async () => {
              setError("");
              try {
                await signOut();
                navigate("/login");
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <span>Client collaboration portal</span>
          <span className="topbar-date">
            {dateLabel(new Date().toISOString())}
          </span>
        </header>
        <main className="workspace">
          <ErrorBox message={error} />
          <Outlet />
        </main>
        <footer className="workspace-footer">
          Searchroom<span>Built around your next great hire.</span>
        </footer>
      </div>
    </div>
  );
}
export function ProjectFields({ project }: { project?: Project }) {
  return (
    <>
      <Field label="Role title" name="title" value={project?.title} required />
      <Field
        label="Search description"
        name="description"
        type="textarea"
        value={project?.description}
      />
      <Field
        label="Ideal candidate profile"
        name="ideal_profile"
        type="textarea"
        value={project?.ideal_profile}
      />
      <div className="form-grid">
        <Field
          label="Start date"
          name="start_date"
          type="date"
          value={project?.start_date || ""}
        />
        <Field
          label="Target end date"
          name="end_date"
          type="date"
          value={project?.end_date || ""}
        />
      </div>
      <Field
        label="Agreement terms"
        name="agreement_terms"
        type="textarea"
        value={project?.agreement_terms}
      />
    </>
  );
}
export const projectData = (f: FormData) => ({
  title: str(f, "title"),
  description: str(f, "description"),
  ideal_profile: str(f, "ideal_profile"),
  agreement_terms: str(f, "agreement_terms"),
  start_date: optional(f, "start_date"),
  end_date: optional(f, "end_date"),
});
function NewProject({
  close,
  saved,
}: {
  close: () => void;
  saved: (p: Project) => void;
}) {
  const orgs = useRemote<ClientOrg[]>("/client-organisations");
  return (
    <Editor title="Create a search" close={close}>
      <ErrorBox message={orgs.error} />
      <More remote={orgs} />
      {orgs.loading ? (
        <Loading />
      ) : !orgs.data?.length ? (
        <p>
          Add a client organisation in <Link to="/admin">Administration</Link>{" "}
          first.
        </p>
      ) : (
        <Form
          submit="Create search"
          onCancel={close}
          onSubmit={async (f) =>
            saved(
              await api<Project>("/projects", "POST", {
                ...projectData(f),
                client_org_id: Number(str(f, "client_org_id")),
              }),
            )
          }
        >
          <Field
            label="Client organisation"
            name="client_org_id"
            value=""
            required
          >
            <option value="" disabled>
              Choose a client
            </option>
            {orgs.data.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </Field>
          <ProjectFields />
        </Form>
      )}
    </Editor>
  );
}
export function Dashboard() {
  const { user } = useAuth();
  const projects = useRemote<Project[]>("/projects");
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();
  const list = projects.data || [];
  const summary = useRemote<{ project_count: number; unread_count: number }>(
    "/projects/summary",
  );
  const unread = summary.data?.unread_count ?? 0;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR SEARCHES, CONNECTED</span>
          <h1>
            Search workspace<span className="accent-dot">.</span>
          </h1>
          <p className="muted">
            Welcome back, {user?.name.split(" ")[0]}. Here’s where things stand.
          </p>
        </div>
        {user?.role === "admin" && (
          <button className="button" onClick={() => setCreating(true)}>
            <Plus size={18} />
            New search
          </button>
        )}
      </div>
      {creating && (
        <NewProject
          close={() => setCreating(false)}
          saved={(p) => navigate(`/projects/${p.id}`)}
        />
      )}
      <ErrorBox message={projects.error || summary.error} />
      <More remote={projects} />
      {projects.loading ? (
        <Loading />
      ) : (
        projects.data && (
          <>
            <div className="stats">
              <div className="stat">
                <BriefcaseBusiness size={21} />
                <strong>
                  {(summary.data?.project_count ?? 0)
                    .toString()
                    .padStart(2, "0")}
                </strong>
                <span>Searches in your workspace</span>
              </div>
              <div className="stat">
                <MessageSquare size={21} />
                <strong>{unread.toString().padStart(2, "0")}</strong>
                <span>Unread messages</span>
              </div>
              <div className="stat stat-note">
                <span className="eyebrow">BETTER TOGETHER</span>
                <p>
                  Keep the conversation moving.
                  <br />
                  Keep the search on track.
                </p>
                <ArrowRight size={23} />
              </div>
            </div>
            <div className="section-heading">
              <h2>
                Your projects <span className="count">{list.length}</span>
              </h2>
              <span className="muted small">Latest searches first</span>
            </div>
            {list.length ? (
              <div className="project-grid">
                {list.map((p, i) => (
                  <Link
                    to={`/projects/${p.id}`}
                    key={p.id}
                    className="project-card"
                  >
                    <div className="project-card-top">
                      <span className="company-icon">
                        {p.client_name.slice(0, 2).toUpperCase()}
                      </span>
                      <span className="project-number">
                        SEARCH {String(i + 1).padStart(2, "0")}
                      </span>
                    </div>
                    <span className="client-name">{p.client_name}</span>
                    <h2>{p.title}</h2>
                    <p className="project-excerpt">
                      {p.description || "Search details will appear here."}
                    </p>
                    <div className="project-card-footer">
                      <span>
                        <CalendarDays size={16} />
                        {p.end_date
                          ? dateLabel(p.end_date)
                          : "Target date not set"}
                      </span>
                      {p.unread_count > 0 ? (
                        <span className="unread-badge">
                          {p.unread_count} new
                        </span>
                      ) : (
                        <ArrowRight size={19} />
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <Empty title="Your next search starts here">
                {user?.role === "admin"
                  ? "Create a search to bring your team and client together."
                  : "Projects will appear here when your agency administrator grants you access."}
              </Empty>
            )}
          </>
        )
      )}
    </>
  );
}

interface CandidateExtractionDraft {
  name: string;
  company: string | null;
  job_title: string | null;
  email: string | null;
  phone: string | null;
  skills: string[];
}

export function CandidateUploadPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const project = useRemote<Project>(`/projects/${projectId}`);
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<CandidateExtractionDraft | null>(null);
  const [formRevision, setFormRevision] = useState(0);
  const projectPath = `/projects/${projectId}`;

  async function extractCV() {
    setError("");
    if (Boolean(sourceFile) === Boolean(sourceUrl.trim())) {
      setError("Choose one CV file or enter one CV URL.");
      return;
    }
    const body = new FormData();
    if (sourceFile) body.append("cv_file", sourceFile);
    else body.append("cv_url", sourceUrl.trim());
    setExtracting(true);
    try {
      const result = await api<CandidateExtractionDraft>(
        `${projectPath}/candidates/extract`,
        "POST",
        body,
        true,
        undefined,
        90000,
      );
      setDraft(result);
      setFormRevision((revision) => revision + 1);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setExtracting(false);
    }
  }

  if (project.loading) return <Loading />;
  if (project.error || !project.data)
    return (
      <>
        <Link className="back-link" to="/">
          <ArrowLeft size={16} /> Searches
        </Link>
        <ErrorBox message={project.error || "Search not found."} />
      </>
    );

  const canEdit = user?.role !== "client" && !project.data.archived_at;
  if (!canEdit)
    return (
      <>
        <Link className="back-link" to={`${projectPath}/candidates`}>
          <ArrowLeft size={16} /> Candidates
        </Link>
        <ErrorBox message="Only agency staff can add candidates to an active search." />
      </>
    );

  return (
    <>
      <Link className="back-link" to={`${projectPath}/candidates`}>
        <ArrowLeft size={16} />
        {project.data.title}
        <ChevronRight size={14} />
        Candidates
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{project.data.client_name}</span>
          <h1>Upload a candidate CV</h1>
          <p className="muted">
            Extract candidate details, review the draft, then save it to this
            search.
          </p>
        </div>
      </div>
      <section className="panel stack">
        <div>
          <h2>Choose a CV</h2>
          <p className="muted">
            Upload a PDF, DOCX, or TXT file, or enter a direct HTTPS CV file URL.
            The CV is sent to OpenAI for extraction and is not saved by this
            upload step.
          </p>
        </div>
        <label className="field">
          <span>CV file</span>
          <input
            type="file"
            accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            onChange={(event) => setSourceFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <label className="field">
          <span>Or direct HTTPS CV URL</span>
          <input
            type="url"
            maxLength={2048}
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
          />
        </label>
        <div>
          <button
            type="button"
            className="button"
            onClick={extractCV}
            disabled={extracting}
          >
            {extracting ? "Extracting…" : "Extract details"}
          </button>
        </div>
        <ErrorBox message={error} />
      </section>
      {draft && (
        <section className="panel stack">
          <div>
            <h2>Check the extracted details</h2>
            <p className="muted">
              Review and edit every field before saving. Nothing is added to the
              candidate list until you save this form.
            </p>
          </div>
          <Form
            key={formRevision}
            submit="Save candidate"
            onCancel={() => navigate(`${projectPath}/candidates`)}
            onSubmit={async (form) => {
              await api<Candidate>(`${projectPath}/candidates`, "POST", {
                name: str(form, "name"),
                current_role: str(form, "current_role"),
                company: str(form, "company"),
                email: optional(form, "email"),
                phone: str(form, "phone"),
                skills: str(form, "skills")
                  .split(",")
                  .map((skill) => skill.trim())
                  .filter(Boolean),
                summary: "",
                cv_url: optional(form, "cv_url"),
                stage: str(form, "stage"),
                client_visible: form.get("client_visible") === "on",
              });
              navigate(`${projectPath}/candidates`);
            }}
          >
            <Field label="Candidate name" name="name" value={draft.name} required />
            <div className="form-grid">
              <Field label="Job title" name="current_role" value={draft.job_title ?? ""} />
              <Field label="Company" name="company" value={draft.company ?? ""} />
            </div>
            <div className="form-grid">
              <Field label="Email" name="email" type="email" value={draft.email ?? ""} maxLength={254} />
              <Field label="Phone" name="phone" type="tel" value={draft.phone ?? ""} maxLength={40} />
            </div>
            <Field
              label="Skills (comma-separated)"
              name="skills"
              type="textarea"
              value={draft.skills.join(", ")}
              maxLength={4000}
            />
            <Field
              label="CV URL"
              name="cv_url"
              type="url"
              value={sourceUrl.trim()}
            />
            <Field label="Candidate stage" name="stage" value="Identified">
              {stages.map((stage) => (
                <option key={stage}>{stage}</option>
              ))}
            </Field>
            <label className="checkbox">
              <input name="client_visible" type="checkbox" />
              Share this candidate with the client
            </label>
          </Form>
        </section>
      )}
    </>
  );
}

const tabs = [
  { key: "overview", title: "Overview", icon: BriefcaseBusiness },
  { key: "candidates", title: "Candidates", icon: Users },
  { key: "updates", title: "Updates", icon: LayoutDashboard },
  { key: "messages", title: "Messages", icon: MessageSquare },
  { key: "timeline", title: "Timeline", icon: CalendarDays },
];
export function ProjectPage() {
  const { projectId, tab = "overview" } = useParams();
  const { user } = useAuth();
  const project = useRemote<Project>(`/projects/${projectId}`);
  const [readProject, setReadProject] = useState<number | null>(null);
  if (project.loading) return <Loading />;
  if (project.error)
    return (
      <>
        <Link className="back-link" to="/">
          <ArrowLeft size={16} />
          All searches
        </Link>
        <ErrorBox message={project.error} />
        <More remote={project} />
      </>
    );
  if (!project.data) return null;
  const p = project.data;
  const edit = user?.role !== "client" && !project.data?.archived_at;
  const base = `/projects/${p.id}`;
  return (
    <>
      <Link className="back-link" to="/">
        Searches <ChevronRight size={14} />
        {p.client_name}
      </Link>
      <div className="page-heading project-heading">
        <div>
          <span className="eyebrow">{p.client_name}</span>
          <h1>{p.title}</h1>
          <p className="muted">
            <CalendarDays size={16} />
            {dateLabel(p.start_date)} — {dateLabel(p.end_date)}
          </p>
        </div>
        <span className="shared-badge">
          <span className="status-dot" />
          Shared workspace
        </span>
      </div>
      <nav className="project-tabs" aria-label="Project sections">
        {tabs.map((t) => (
          <Link
            key={t.key}
            to={`${base}/${t.key}`}
            className={tab === t.key ? "active" : ""}
            aria-current={tab === t.key ? "page" : undefined}
          >
            <t.icon size={18} />
            {t.title}
            {t.key === "messages" &&
              readProject !== p.id &&
              p.unread_count > 0 && (
                <span className="count">{p.unread_count}</span>
              )}
          </Link>
        ))}
      </nav>
      <div key={`${p.id}-${tab}`} className="tab-content">
        {tab === "overview" ? (
          <OverviewTab project={p} edit={edit} reload={project.reload} />
        ) : tab === "candidates" ? (
          <CandidatesTab base={base} edit={edit} />
        ) : tab === "updates" ? (
          <UpdatesTab base={base} />
        ) : tab === "messages" ? (
          <MessagesTab base={base} read={() => setReadProject(p.id)} />
        ) : tab === "timeline" ? (
          <TimelineTab base={base} edit={edit} />
        ) : (
          <NotFound />
        )}
      </div>
    </>
  );
}
export function NotFound() {
  return (
    <div className="empty">
      <h1>Page not found</h1>
      <Link to="/">Return to your searches</Link>
    </div>
  );
}
