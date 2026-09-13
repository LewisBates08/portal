import { useState } from "react";
import { api } from "./api";
import { ErrorBox, Field, Form, More, useRemote } from "./ui";
import type { Project, User } from "./types";
export function AccountAdministration() {
  const policy = useRemote<{ retention_days: number | null }>("/agency/policy");
  const people = useRemote<User[]>("/users");
  const searches = useRemote<Project[]>("/projects");
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<{
    id: number;
    title: string;
    version: number;
    review_due: boolean;
    counts: Record<string, number>;
  } | null>(null);
  return (
    <section className="panel stack">
      <h2>Account security & data retention</h2>
      <ErrorBox
        message={error || policy.error || people.error || searches.error}
      />
      <Form
        submit="Save retention policy"
        onSubmit={async (f) => {
          await api("/agency/policy", "PUT", {
            retention_days: Number(f.get("retention_days")),
          });
          policy.reload();
        }}
      >
        <Field
          label="Review archived search data after this many days"
          name="retention_days"
          type="number"
          value={String(policy.data?.retention_days ?? "")}
          required
        />
        <p className="small muted">
          Choose a period appropriate to your agency's retention policy.
          Deletion requires an administrator's review and confirmation. CV and
          document access must also be revoked at the document provider.
        </p>
      </Form>
      <h3>Account access</h3>
      {people.data?.map((person) => (
        <div key={person.id} className="section-heading">
          <span>
            {person.name} · {person.role} ·{" "}
            {person.active ? "Active" : "Suspended"}
          </span>
          <button
            className="button secondary compact"
            onClick={async () => {
              try {
                await api(`/users/${person.id}/status`, "PUT", {
                  active: !person.active,
                });
                people.reload();
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            {person.active ? "Suspend" : "Reactivate"}
          </button>
          {person.role === "recruiter" && person.active && (
            <button
              className="button secondary compact"
              onClick={async () => {
                if (
                  !window.confirm(
                    `Give ${person.name} administrator access to every agency search?`,
                  )
                )
                  return;
                try {
                  await api(`/users/${person.id}/promote-admin`, "POST");
                  people.reload();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Make administrator
            </button>
          )}
        </div>
      ))}
      <More remote={people} />
      <h3>Search data</h3>
      {searches.data?.map((project) => (
        <div key={project.id} className="section-heading">
          <span>
            {project.title}
            {project.archived_at ? " · Archived" : ""}
          </span>
          <div className="actions">
            <a
              className="button secondary compact"
              href={`/api/v1/projects/${project.id}/export`}
              download
            >
              Export
            </a>
            <button
              className="button secondary compact"
              onClick={async () => {
                try {
                  if (!project.archived_at) {
                    await api(`/projects/${project.id}/archive`, "POST");
                    searches.reload();
                  } else {
                    const result = await api<
                      Omit<NonNullable<typeof preview>, "id">
                    >(`/projects/${project.id}/deletion-preview`);
                    setPreview({ ...result, id: project.id });
                  }
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              {project.archived_at ? "Review deletion" : "Archive"}
            </button>
          </div>
        </div>
      ))}
      <More remote={searches} />
      {preview && (
        <div className="panel">
          <h3>Delete {preview.title}</h3>
          <p>
            {preview.review_due
              ? "This search is due for a retention review."
              : "Review your retention policy before deleting."}{" "}
            This permanently removes the search and its collaboration data.
            Backup copies expire separately.
          </p>
          <pre>{JSON.stringify(preview.counts, null, 2)}</pre>
          <Form
            submit="Permanently delete search"
            onCancel={() => setPreview(null)}
            onSubmit={async (f) => {
              await api(`/projects/${preview.id}`, "DELETE", {
                confirmation: String(f.get("confirmation")),
                version: preview.version,
              });
              setPreview(null);
              searches.reload();
            }}
          >
            <Field
              label="Type the exact search title to confirm"
              name="confirmation"
              required
            />
          </Form>
        </div>
      )}
    </section>
  );
}
