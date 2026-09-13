import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  LoaderCircle,
  MessageSquare,
  X,
} from "lucide-react";
import { api } from "./api";
import type { Entry } from "./types";

export function useRemote<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setData(null);
    api<T>(path)
      .then((value) => {
        if (active) setData(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, revision]);
  return { data, error, loading, reload: () => setRevision((n) => n + 1) };
}
export function ErrorBox({ message }: { message: string }) {
  return message ? (
    <div role="alert" className="error">
      <AlertCircle size={18} />
      {message}
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} /> Loading…
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <MessageSquare size={28} />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}
export function External({
  url,
  children,
}: {
  url: string;
  children: ReactNode;
}) {
  return (
    <a
      className="external"
      href={url}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
      <ArrowUpRight size={16} />
    </a>
  );
}
export function dateLabel(date: string | null) {
  return date
    ? new Date(
        date.length === 10 ? `${date}T12:00:00` : date,
      ).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "Not set";
}
export function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export function Initials({ name }: { name: string }) {
  return (
    <span className="avatar" aria-hidden="true">
      {name
        .split(" ")
        .map((x) => x[0])
        .slice(0, 2)
        .join("")}
    </span>
  );
}
export function EntryView({
  entry,
  children,
}: {
  entry: Entry;
  children?: ReactNode;
}) {
  return (
    <article className="entry">
      <Initials name={entry.author_name} />
      <div className="entry-content">
        <div className="entry-heading">
          <strong>{entry.author_name}</strong>
          <time dateTime={entry.created_at}>
            {new Date(entry.created_at).toLocaleString("en-GB", {
              day: "numeric",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </time>
        </div>
        <p className="preserve">{entry.body}</p>
        {children}
      </div>
    </article>
  );
}
export function Field({
  label,
  name,
  value = "",
  type = "text",
  required = false,
  children,
  maxLength,
}: {
  label: string;
  name: string;
  value?: string | number;
  type?: string;
  required?: boolean;
  children?: ReactNode;
  maxLength?: number;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children ? (
        <select name={name} defaultValue={value} required={required}>
          {children}
        </select>
      ) : type === "textarea" ? (
        <textarea
          name={name}
          defaultValue={value}
          required={required}
          rows={4}
          maxLength={maxLength || 10000}
        />
      ) : (
        <input
          name={name}
          type={type}
          defaultValue={value}
          required={required}
          maxLength={maxLength || (type === "url" ? 2048 : 160)}
          minLength={type === "password" ? 10 : undefined}
        />
      )}
    </label>
  );
}
export function Form({
  children,
  onSubmit,
  submit = "Save changes",
  onCancel,
  reset = false,
}: {
  children: ReactNode;
  onSubmit: (data: FormData) => Promise<void>;
  submit?: string;
  onCancel?: () => void;
  reset?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const element = e.currentTarget;
    setBusy(true);
    setError("");
    try {
      await onSubmit(new FormData(element));
      if (reset) element.reset();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save} className="form">
      <fieldset disabled={busy}>{children}</fieldset>
      <ErrorBox message={error} />
      <div className="form-actions">
        {onCancel && (
          <button type="button" className="button secondary" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button className="button" disabled={busy}>
          {busy && <LoaderCircle size={16} className="spin" />}
          {busy ? "Saving…" : submit}
        </button>
      </div>
    </form>
  );
}
export function Editor({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  return (
    <section className="editor">
      <div className="section-heading">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={close}
          aria-label="Close editor"
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </section>
  );
}
export const str = (form: FormData, key: string) =>
  String(form.get(key) || "").trim();
export const optional = (form: FormData, key: string) => str(form, key) || null;
