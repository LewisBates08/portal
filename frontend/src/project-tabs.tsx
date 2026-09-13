import { useEffect, useState } from "react";
import {
  Check,
  Circle,
  FileText,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { api } from "./api";
import { useAuth } from "./auth";
import { ProjectFields, projectData } from "./pages";
import {
  dateLabel,
  Editor,
  Empty,
  EntryView,
  ErrorBox,
  External,
  Field,
  Form,
  Loading,
  optional,
  str,
  today,
  useRemote,
} from "./ui";
import { stages } from "./types";
import type {
  Candidate,
  DocumentLink,
  Entry,
  Milestone,
  Post,
  Project,
} from "./types";

export function OverviewTab({
  project,
  edit,
  reload,
}: {
  project: Project;
  edit: boolean;
  reload: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const docs = useRemote<DocumentLink[]>(`/projects/${project.id}/documents`);
  return (
    <>
      {editing && (
        <Editor title="Edit search details" close={() => setEditing(false)}>
          <Form
            onCancel={() => setEditing(false)}
            onSubmit={async (f) => {
              await api(`/projects/${project.id}`, "PUT", projectData(f));
              setEditing(false);
              reload();
            }}
          >
            <ProjectFields project={project} />
          </Form>
        </Editor>
      )}
      <div className="overview-grid">
        <div className="stack">
          <section className="panel">
            <div className="section-heading">
              <h2>The search brief</h2>
              {edit && (
                <button
                  className="button secondary compact"
                  onClick={() => setEditing(true)}
                >
                  <Pencil size={15} />
                  Edit details
                </button>
              )}
            </div>
            <p className="preserve">
              {project.description ||
                "The search brief has not been added yet."}
            </p>
            <hr />
            <h3>Ideal candidate profile</h3>
            <p className="preserve muted">
              {project.ideal_profile ||
                "The candidate profile has not been added yet."}
            </p>
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>Agreement terms</h2>
              <FileText size={20} className="muted" />
            </div>
            <p className="preserve">
              {project.agreement_terms ||
                "Agreement terms have not been added yet."}
            </p>
          </section>
        </div>
        <div className="stack">
          <section className="panel search-at-glance">
            <span className="eyebrow">SEARCH AT A GLANCE</span>
            <dl>
              <dt>Client organisation</dt>
              <dd>{project.client_name}</dd>
              <dt>Start date</dt>
              <dd>{dateLabel(project.start_date)}</dd>
              <dt>Target completion</dt>
              <dd>{dateLabel(project.end_date)}</dd>
            </dl>
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>Shared documents</h2>
              {edit && (
                <button
                  className="icon-button"
                  aria-label="Add document link"
                  onClick={() => setAdding(!adding)}
                >
                  <Plus size={20} />
                </button>
              )}
            </div>
            <ErrorBox message={error || docs.error} />
            {docs.loading ? (
              <Loading />
            ) : docs.data?.length ? (
              <div className="document-list">
                {docs.data.map((d) => (
                  <div key={d.id}>
                    <FileText size={19} />
                    <External url={d.url}>{d.title}</External>
                    {edit && (
                      <button
                        className="icon-button danger"
                        aria-label={`Remove ${d.title}`}
                        onClick={async () => {
                          if (!window.confirm(`Remove the link to ${d.title}?`))
                            return;
                          try {
                            await api(
                              `/projects/${project.id}/documents/${d.id}`,
                              "DELETE",
                            );
                            docs.reload();
                          } catch (e) {
                            setError((e as Error).message);
                          }
                        }}
                      >
                        <Trash2 size={15} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">No document links shared yet.</p>
            )}
            {adding && (
              <Form
                submit="Add link"
                onSubmit={async (f) => {
                  await api(`/projects/${project.id}/documents`, "POST", {
                    title: str(f, "title"),
                    url: str(f, "url"),
                  });
                  setAdding(false);
                  docs.reload();
                }}
              >
                <Field label="Document title" name="title" required />
                <Field label="Document URL" name="url" type="url" required />
              </Form>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
function CandidateForm({
  candidate,
  save,
  close,
}: {
  candidate?: Candidate;
  save: (data: unknown) => Promise<void>;
  close: () => void;
}) {
  return (
    <Editor
      title={candidate ? "Edit candidate" : "Add a candidate"}
      close={close}
    >
      <Form
        onCancel={close}
        onSubmit={async (f) =>
          save({
            name: str(f, "name"),
            current_role: str(f, "current_role"),
            company: str(f, "company"),
            summary: str(f, "summary"),
            cv_url: optional(f, "cv_url"),
            stage: str(f, "stage"),
            client_visible: f.get("client_visible") === "on",
          })
        }
      >
        <Field
          label="Candidate name"
          name="name"
          value={candidate?.name}
          required
        />
        <div className="form-grid">
          <Field
            label="Current role"
            name="current_role"
            value={candidate?.current_role}
          />
          <Field label="Company" name="company" value={candidate?.company} />
        </div>
        <Field
          label="Profile summary"
          name="summary"
          type="textarea"
          value={candidate?.summary}
        />
        <Field
          label="CV URL"
          name="cv_url"
          type="url"
          value={candidate?.cv_url || ""}
        />
        <Field
          label="Candidate stage"
          name="stage"
          value={candidate?.stage || "Identified"}
        >
          {stages.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </Field>
        <label className="checkbox">
          <input
            name="client_visible"
            type="checkbox"
            defaultChecked={candidate?.client_visible}
          />
          Share this candidate with the client
        </label>
      </Form>
    </Editor>
  );
}
function FeedbackPanel({
  base,
  candidate,
}: {
  base: string;
  candidate: Candidate;
}) {
  const path = `${base}/candidates/${candidate.id}/feedback`;
  const entries = useRemote<Entry[]>(path);
  return (
    <div className="feedback-panel">
      <h3>Candidate feedback</h3>
      <ErrorBox message={entries.error} />
      {entries.loading ? (
        <Loading />
      ) : entries.data?.length ? (
        entries.data.map((e) => <EntryView key={e.id} entry={e} />)
      ) : (
        <p className="muted">
          Start the conversation about {candidate.name.split(" ")[0]}.
        </p>
      )}
      <Form
        reset
        submit="Add feedback"
        onSubmit={async (f) => {
          await api(path, "POST", { body: str(f, "body") });
          entries.reload();
        }}
      >
        <Field label="Your feedback" name="body" type="textarea" required />
      </Form>
    </div>
  );
}
export function CandidatesTab({ base, edit }: { base: string; edit: boolean }) {
  const candidates = useRemote<Candidate[]>(`${base}/candidates`);
  const [editing, setEditing] = useState<Candidate | "new" | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>Candidates</h2>
          <p className="muted">
            {edit
              ? "Manage the pipeline and choose what to share."
              : "Meet the candidates shared with you."}
          </p>
        </div>
        {edit && (
          <button className="button" onClick={() => setEditing("new")}>
            <Plus size={18} />
            Add candidate
          </button>
        )}
      </div>
      {editing && (
        <CandidateForm
          candidate={editing === "new" ? undefined : editing}
          close={() => setEditing(null)}
          save={async (data) => {
            await api(
              `${base}/candidates${editing === "new" ? "" : `/${editing.id}`}`,
              editing === "new" ? "POST" : "PUT",
              data,
            );
            setEditing(null);
            candidates.reload();
          }}
        />
      )}
      <ErrorBox message={candidates.error} />
      {candidates.loading ? (
        <Loading />
      ) : !candidates.data?.length ? (
        <Empty title="No candidates yet">
          {edit
            ? "Add a candidate to begin building your pipeline."
            : "Your recruitment team will share candidates here when they are ready."}
        </Empty>
      ) : (
        stages.map((stage) => {
          const group = candidates.data!.filter((c) => c.stage === stage);
          return (
            group.length > 0 && (
              <section key={stage} className="candidate-group">
                <h3>
                  <span className={`stage-dot ${stage.toLowerCase()}`} />
                  {stage}
                  <span className="count">{group.length}</span>
                </h3>
                {group.map((c) => (
                  <article key={c.id} className="candidate-card">
                    <div className="candidate-summary">
                      <span className="candidate-avatar">
                        {c.name
                          .split(" ")
                          .map((s) => s[0])
                          .slice(0, 2)
                          .join("")}
                      </span>
                      <div className="candidate-title">
                        <h3>{c.name}</h3>
                        <p className="muted">
                          {[c.current_role, c.company]
                            .filter(Boolean)
                            .join(" · ") || "Role details not added"}
                        </p>
                      </div>
                      {edit && (
                        <span
                          className={`badge ${c.client_visible ? "green" : ""}`}
                        >
                          {c.client_visible
                            ? "Shared with client"
                            : "Agency only"}
                        </span>
                      )}
                      {edit && (
                        <button
                          className="icon-button"
                          aria-label={`Edit ${c.name}`}
                          onClick={() => setEditing(c)}
                        >
                          <Pencil size={17} />
                        </button>
                      )}
                    </div>
                    <p className="preserve">
                      {c.summary || "No profile summary yet."}
                    </p>
                    <div className="candidate-actions">
                      {c.cv_url && <External url={c.cv_url}>View CV</External>}
                      <button
                        className="text-button"
                        onClick={() =>
                          setExpanded(expanded === c.id ? null : c.id)
                        }
                        aria-expanded={expanded === c.id}
                      >
                        {expanded === c.id
                          ? "Hide feedback"
                          : "View & add feedback"}
                      </button>
                    </div>
                    {expanded === c.id && (
                      <FeedbackPanel base={base} candidate={c} />
                    )}
                  </article>
                ))}
              </section>
            )
          );
        })
      )}
    </>
  );
}
function CommentForm({ path, done }: { path: string; done: () => void }) {
  return (
    <Form
      reset
      submit="Add comment"
      onSubmit={async (f) => {
        await api(path, "POST", { body: str(f, "body") });
        done();
      }}
    >
      <Field label="Add a comment" name="body" type="textarea" required />
    </Form>
  );
}
export function UpdatesTab({ base }: { base: string }) {
  const posts = useRemote<Post[]>(`${base}/updates`);
  return (
    <div className="feed-layout">
      <div>
        <div className="section-heading">
          <div>
            <h2>Search updates</h2>
            <p className="muted">
              Ideas, decisions and notes that keep everyone aligned.
            </p>
          </div>
        </div>
        <ErrorBox message={posts.error} />
        {posts.loading ? (
          <Loading />
        ) : posts.data?.length ? (
          posts.data.map((post) => (
            <section className="panel post" key={post.id}>
              <EntryView entry={post}>
                {post.attachment_url && (
                  <External url={post.attachment_url}>Attachment link</External>
                )}
              </EntryView>
              <div className="comments">
                {post.comments.map((c) => (
                  <EntryView key={c.id} entry={c} />
                ))}
                <CommentForm
                  path={`${base}/updates/${post.id}/comments`}
                  done={posts.reload}
                />
              </div>
            </section>
          ))
        ) : (
          <Empty title="A fresh page for this search">
            Share the first update, idea or decision.
          </Empty>
        )}
      </div>
      <aside className="panel composer">
        <h2>Share an update</h2>
        <Form
          reset
          submit="Post update"
          onSubmit={async (f) => {
            await api(`${base}/updates`, "POST", {
              body: str(f, "body"),
              attachment_url: optional(f, "attachment_url"),
            });
            posts.reload();
          }}
        >
          <Field
            label="What should everyone know?"
            name="body"
            type="textarea"
            required
          />
          <Field
            label="Attachment link (optional)"
            name="attachment_url"
            type="url"
          />
        </Form>
        <p className="small muted">
          Visible to everyone with access to this search.
        </p>
      </aside>
    </div>
  );
}
export function MessagesTab({
  base,
  read,
}: {
  base: string;
  read: () => void;
}) {
  const messages = useRemote<Entry[]>(`${base}/messages`);
  const { user } = useAuth();
  const [error, setError] = useState("");
  useEffect(() => {
    if (messages.data) {
      api(`${base}/messages/read`, "PUT", {
        last_message_id: messages.data.at(-1)?.id || 0,
      })
        .then(read)
        .catch((e) => setError(e.message));
    }
  }, [messages.data, base]);
  return (
    <section className="panel messages-panel">
      <div className="section-heading">
        <div>
          <h2>The conversation</h2>
          <p className="muted">
            A direct line between your team and your client.
          </p>
        </div>
        <button
          className="button secondary compact"
          onClick={messages.reload}
          disabled={messages.loading}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>
      <ErrorBox message={messages.error || error} />
      <div className="message-list">
        {messages.loading ? (
          <Loading />
        ) : messages.data?.length ? (
          messages.data.map((m) => (
            <div
              key={m.id}
              className={m.author_id === user?.id ? "message own" : "message"}
            >
              <EntryView entry={m} />
            </div>
          ))
        ) : (
          <Empty title="Start the conversation">
            Messages stay here so everyone can catch up.
          </Empty>
        )}
      </div>
      <Form
        reset
        submit="Send message"
        onSubmit={async (f) => {
          await api(`${base}/messages`, "POST", { body: str(f, "body") });
          messages.reload();
        }}
      >
        <Field label="Your message" name="body" type="textarea" required />
      </Form>
    </section>
  );
}
function milestoneData(m: Milestone) {
  return {
    title: m.title,
    description: m.description,
    target_date: m.target_date,
    completed: m.completed,
  };
}
export function TimelineTab({ base, edit }: { base: string; edit: boolean }) {
  const milestones = useRemote<Milestone[]>(`${base}/milestones`);
  const [editing, setEditing] = useState<Milestone | "new" | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const current = editing && editing !== "new" ? editing : undefined;
  const completed = milestones.data?.filter((m) => m.completed).length || 0;
  async function change(m: Milestone, remove = false) {
    if (remove && !window.confirm(`Delete milestone “${m.title}”?`)) return;
    setBusy(true);
    setError("");
    try {
      await api(
        `${base}/milestones/${m.id}`,
        remove ? "DELETE" : "PUT",
        remove ? undefined : { ...milestoneData(m), completed: !m.completed },
      );
      milestones.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>The road ahead</h2>
          <p className="muted">Key dates and commitments for this search.</p>
        </div>
        {edit && (
          <button className="button" onClick={() => setEditing("new")}>
            <Plus size={18} />
            Add milestone
          </button>
        )}
      </div>
      {editing && (
        <Editor
          title={current ? "Edit milestone" : "Add a milestone"}
          close={() => setEditing(null)}
        >
          <Form
            onCancel={() => setEditing(null)}
            onSubmit={async (f) => {
              await api(
                `${base}/milestones${current ? `/${current.id}` : ""}`,
                current ? "PUT" : "POST",
                {
                  title: str(f, "title"),
                  description: str(f, "description"),
                  target_date: str(f, "target_date"),
                  completed: f.get("completed") === "on",
                },
              );
              setEditing(null);
              milestones.reload();
            }}
          >
            <Field
              label="Milestone title"
              name="title"
              value={current?.title}
              required
            />
            <Field
              label="Description"
              name="description"
              type="textarea"
              value={current?.description}
            />
            <Field
              label="Target date"
              name="target_date"
              type="date"
              value={current?.target_date}
              required
            />
            <label className="checkbox">
              <input
                name="completed"
                type="checkbox"
                defaultChecked={current?.completed}
              />
              Completed
            </label>
          </Form>
        </Editor>
      )}
      <ErrorBox message={milestones.error || error} />
      {milestones.loading ? (
        <Loading />
      ) : milestones.data?.length ? (
        <section className="panel">
          <div className="timeline-progress">
            <div>
              <strong>
                {completed} of {milestones.data.length}
              </strong>
              <span className="muted"> milestones complete</span>
            </div>
            <progress
              value={completed}
              max={milestones.data.length}
              aria-label="Milestones completed"
            />
          </div>
          <ol className="timeline">
            {milestones.data.map((m) => {
              const overdue = !m.completed && m.target_date < today();
              return (
                <li
                  key={m.id}
                  className={
                    m.completed ? "complete" : overdue ? "overdue" : ""
                  }
                >
                  <div className="timeline-node">
                    {m.completed ? <Check size={17} /> : <Circle size={14} />}
                  </div>
                  <div className="timeline-body">
                    <div className="timeline-date">
                      {dateLabel(m.target_date)}
                      <span
                        className={`badge ${m.completed ? "green" : overdue ? "red" : ""}`}
                      >
                        {m.completed
                          ? "Completed"
                          : overdue
                            ? "Overdue"
                            : "Upcoming"}
                      </span>
                    </div>
                    <h3>{m.title}</h3>
                    {m.description && (
                      <p className="preserve muted">{m.description}</p>
                    )}
                    {edit && (
                      <div className="milestone-actions">
                        <button
                          className="text-button"
                          disabled={busy}
                          onClick={() => change(m)}
                        >
                          {m.completed ? "Reopen milestone" : "Mark complete"}
                        </button>
                        <button
                          className="icon-button"
                          aria-label={`Edit ${m.title}`}
                          onClick={() => setEditing(m)}
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          className="icon-button danger"
                          disabled={busy}
                          aria-label={`Delete ${m.title}`}
                          onClick={() => change(m, true)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ) : (
        <Empty title="Map out the next steps">
          {edit
            ? "Add your first milestone and give the search a clear timeline."
            : "Your recruitment team will add dates and milestones here."}
        </Empty>
      )}
    </>
  );
}
