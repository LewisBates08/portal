import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, Navigate, Outlet, useNavigate } from "react-router-dom";
import { ArrowRight, Layers3 } from "lucide-react";
import { api, authChanged, ApiError } from "./api";
import { ErrorBox, Field, Form, Loading, str } from "./ui";
import type { Account, User } from "./types";

const AuthContext = createContext<{
  user: User | null;
  loading: boolean;
  setUser: (user: User | null) => void;
  signOut: () => Promise<void>;
}>({ user: null, loading: true, setUser: () => {}, signOut: async () => {} });
export const useAuth = () => useContext(AuthContext);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [account, setAccount] = useState<Account | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let revision = 0;
    let alive = true;
    const sync = () => {
      const current = ++revision;
      setUser(null);
      setAccount(null);
      setLoading(true);
      api<Account>("/auth/me", "GET", undefined, false)
        .then((value) => {
          if (alive && current === revision) {
            setAccount(value);
            if (!value.mfa_required) setUser(value.user);
          }
        })
        .catch((e) => {
          if (
            alive &&
            current === revision &&
            !(e instanceof ApiError && e.status === 401)
          )
            setError(e.message);
        })
        .finally(() => {
          if (alive && current === revision) setLoading(false);
        });
    };
    sync();
    window.addEventListener("auth-change", sync);
    return () => {
      alive = false;
      revision++;
      window.removeEventListener("auth-change", sync);
    };
  }, []);
  async function signOut() {
    await api("/auth/logout", "POST");
    setAccount(null);
    setUser(null);
    authChanged();
  }
  return (
    <AuthContext.Provider value={{ user, loading, setUser, signOut }}>
      {error && <ErrorBox message={error} />}
      {account?.mfa_required ? (
        <MfaPage
          setup={account.mfa_setup}
          done={() => {
            setAccount(null);
            authChanged();
          }}
        />
      ) : (
        <div key={user?.id ?? "anonymous"}>{children}</div>
      )}
    </AuthContext.Provider>
  );
}
export function Protected() {
  const { user, loading } = useAuth();
  return loading ? (
    <Loading />
  ) : user ? (
    <Outlet />
  ) : (
    <Navigate to="/login" replace />
  );
}
export function MfaPage({ setup, done }: { setup: boolean; done: () => void }) {
  const [secret, setSecret] = useState("");
  const [codes, setCodes] = useState<string[]>([]);
  return (
    <AuthLayout
      title={
        setup
          ? "Protect your administrator account"
          : "Verify your authenticator"
      }
    >
      {codes.length ? (
        <>
          <p>Save these recovery codes somewhere private. Each works once.</p>
          <pre>{codes.join("\n")}</pre>
          <button className="button" onClick={done}>
            I have saved my recovery codes
          </button>
        </>
      ) : (
        <>
          {setup && (
            <>
              <p>
                Add a time-based account in your authenticator app using this
                setup key.
              </p>
              <Form
                submit="Generate setup key"
                onSubmit={async () => {
                  const result = await api<{ secret: string }>(
                    "/auth/mfa/setup",
                    "POST",
                  );
                  setSecret(result.secret);
                }}
              >
                {secret && <code>{secret}</code>}
              </Form>
            </>
          )}
          {(!setup || secret) && (
            <Form
              submit="Verify code"
              onSubmit={async (f) => {
                const result = await api<{ recovery_codes: string[] }>(
                  "/auth/mfa/verify",
                  "POST",
                  { code: str(f, "code") },
                );
                if (result.recovery_codes.length)
                  setCodes(result.recovery_codes);
                else done();
              }}
            >
              <Field
                name="code"
                label="Authenticator or recovery code"
                required
              />
            </Form>
          )}
        </>
      )}
    </AuthLayout>
  );
}
export function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark">
        <Layers3 size={23} />
      </span>
      searchroom<span className="brand-dot">.</span>
    </span>
  );
}
function AuthLayout({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="auth-page">
      <aside className="auth-story">
        <Brand />
        <div>
          <span className="eyebrow">A SHARED VIEW OF YOUR SEARCH</span>
          <h1>
            Good searches start with
            <br />
            <em>great conversations.</em>
          </h1>
          <p>
            Your people, progress and next steps.
            <br />
            Together in one workspace.
          </p>
          <div className="auth-line" />
          <span className="small">RECRUITMENT, WITH EVERYONE IN THE LOOP</span>
        </div>
        <p className="auth-footer">Searchroom · Client collaboration</p>
      </aside>
      <main className="auth-main">
        <div className="auth-card">
          <div className="mobile-brand">
            <Brand />
          </div>
          <span className="eyebrow">WELCOME TO SEARCHROOM</span>
          <h1>{title}</h1>
          {children}
        </div>
      </main>
    </div>
  );
}
export function LoginPage() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const invite = sessionStorage.getItem("searchroom.invite");
  if (user)
    return <Navigate to={invite ? `/invite#token=${invite}` : "/"} replace />;
  return (
    <AuthLayout title="Welcome back">
      <p className="muted">Sign in to follow your searches.</p>
      <Form
        submit="Sign in"
        onSubmit={async (f) => {
          const result = await api<Account>(
            "/auth/login",
            "POST",
            { email: str(f, "email"), password: String(f.get("password")) },
            false,
          );
          if (!result.mfa_required) setUser(result.user);
          authChanged();
          navigate(invite ? `/invite#token=${invite}` : "/");
        }}
      >
        <Field label="Email address" name="email" type="email" required />
        <label className="field">
          <span>Password</span>
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            maxLength={128}
          />
        </label>
      </Form>
      <p>
        <Link to="/account/forgot">Forgot password?</Link> ·{" "}
        <Link to="/account/resend">Resend verification</Link>
      </p>
      <p className="auth-help">
        Starting a new agency workspace?{" "}
        <Link to="/register">Create account</Link>.
      </p>
      <p className="small muted">
        Joining an existing agency or search? Use the invitation link from your
        agency administrator.
      </p>
    </AuthLayout>
  );
}
export function RegisterPage() {
  const { user, loading } = useAuth();
  const [sent, setSent] = useState(false);
  const invite = sessionStorage.getItem("searchroom.invite");
  if (sent)
    return (
      <AuthLayout title="Check your email">
        <p>
          Follow the verification link to activate your account. If you already
          have an account, sign in or reset your password.
        </p>
        <Link to="/login">Back to sign in</Link>
      </AuthLayout>
    );
  if (loading) return <Loading />;
  if (user) return <Navigate to="/" replace />;
  return (
    <AuthLayout title="Create your account">
      <p className="muted">
        Set up a new agency workspace. You’ll be its administrator and can
        invite your team and clients.
      </p>
      {invite && (
        <p className="small">
          Already invited to a workspace?{" "}
          <Link to={`/invite#token=${invite}`}>Accept your invitation</Link>{" "}
          instead.
        </p>
      )}
      <Form
        submit="Create account"
        onSubmit={async (f) => {
          const password = String(f.get("password"));
          if (password !== String(f.get("confirm_password"))) {
            throw new Error("Passwords do not match.");
          }
          await api(
            "/auth/register",
            "POST",
            {
              name: str(f, "name"),
              agency_name: str(f, "agency_name"),
              email: str(f, "email"),
              password,
            },
            false,
          );
          setSent(true);
        }}
      >
        <Field label="Your name" name="name" required />
        <Field label="Agency name" name="agency_name" required />
        <Field
          label="Email address"
          name="email"
          type="email"
          maxLength={254}
          required
        />
        <label className="field">
          <span>Password (at least 10 characters)</span>
          <input
            name="password"
            type="password"
            autoComplete="new-password"
            minLength={10}
            maxLength={128}
            required
          />
        </label>
        <label className="field">
          <span>Confirm password</span>
          <input
            name="confirm_password"
            type="password"
            autoComplete="new-password"
            minLength={10}
            maxLength={128}
            required
          />
        </label>
      </Form>
      <p className="auth-help">
        Already have an account? <Link to="/login">Sign in</Link>.
      </p>
      <p className="small muted">
        To join an existing workspace as a recruiter or client, use your
        invitation link.
      </p>
    </AuthLayout>
  );
}

export function InvitePage() {
  const { user, setUser, signOut } = useAuth();
  const navigate = useNavigate();
  const [token] = useState(
    () =>
      new URLSearchParams(window.location.hash.slice(1)).get("token") ||
      sessionStorage.getItem("searchroom.invite") ||
      "",
  );
  const [info, setInfo] = useState<{
    email: string;
    role: string;
    existing_user: boolean;
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!token) {
      setError(
        "This invitation link is incomplete. Ask your administrator for a new link.",
      );
      return;
    }
    sessionStorage.setItem("searchroom.invite", token);
    api<typeof info>("/auth/invitation", "POST", { token }, false)
      .then(setInfo)
      .catch((e) => setError(e.message));
  }, [token]);
  return (
    <AuthLayout title="You’re invited">
      <ErrorBox message={error} />
      {!info && !error && <Loading />}
      {info && (
        <>
          <p className="muted">
            Join as a {info.role} using <strong>{info.email}</strong>.
          </p>
          {info.existing_user && user?.email !== info.email ? (
            <>
              <p>Sign in with the invited account to accept.</p>
              <button
                className="button"
                onClick={async () => {
                  try {
                    if (user) await signOut();
                    navigate("/login");
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Go to sign in <ArrowRight size={16} />
              </button>
            </>
          ) : !info.existing_user && user ? (
            <>
              <p>Sign out to create the invited account.</p>
              <button
                className="button"
                onClick={async () => {
                  try {
                    await signOut();
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Sign out
              </button>
            </>
          ) : (
            <Form
              submit="Accept invitation"
              onSubmit={async (f) => {
                const result = await api<
                  Partial<Account> & { message?: string }
                >(
                  "/auth/accept-invitation",
                  "POST",
                  {
                    token,
                    ...(!info.existing_user
                      ? {
                          name: str(f, "name"),
                          password: String(f.get("password")),
                        }
                      : {}),
                  },
                  info.existing_user,
                );
                if (result.user) {
                  setUser(result.user);
                  sessionStorage.removeItem("searchroom.invite");
                  navigate("/");
                } else
                  setError(
                    "Check your email to verify your address and finish joining.",
                  );
              }}
            >
              {!info.existing_user && (
                <>
                  <Field label="Your name" name="name" required />
                  <Field
                    label="Choose a password (at least 10 characters)"
                    name="password"
                    type="password"
                    required
                  />
                </>
              )}
            </Form>
          )}
        </>
      )}
      <Link
        className="back-link"
        to="/login"
        onClick={() => sessionStorage.removeItem("searchroom.invite")}
      >
        Back to sign in
      </Link>
    </AuthLayout>
  );
}

export function AccountPage() {
  const kind = window.location.pathname.split("/").at(-1);
  const [token] = useState(
    () => new URLSearchParams(window.location.hash.slice(1)).get("token") || "",
  );
  const [done, setDone] = useState(false);
  useEffect(() => {
    window.history.replaceState(null, "", window.location.pathname);
  }, []);
  const title =
    kind === "reset"
      ? "Choose a new password"
      : kind === "verify"
        ? "Verify your email"
        : kind === "resend"
          ? "Resend verification"
          : "Reset your password";
  return (
    <AuthLayout title={title}>
      {done ? (
        <>
          <p>
            {kind === "forgot" || kind === "resend"
              ? "If eligible, an email will arrive shortly."
              : "Your account has been updated. You can now sign in."}
          </p>
          <Link to="/login">Sign in</Link>
        </>
      ) : (
        <Form
          submit="Continue"
          onSubmit={async (f) => {
            const path =
              kind === "reset"
                ? "reset-password"
                : kind === "verify"
                  ? "verify-email"
                  : kind === "resend"
                    ? "resend-verification"
                    : "forgot-password";
            await api(
              `/auth/${path}`,
              "POST",
              kind === "reset"
                ? { token, password: String(f.get("password")) }
                : kind === "verify"
                  ? { token }
                  : { email: str(f, "email") },
              false,
            );
            setDone(true);
          }}
        >
          {kind === "reset" ? (
            <Field
              label="New password (at least 10 characters)"
              name="password"
              type="password"
              required
            />
          ) : kind === "verify" ? (
            <p>Confirm to verify ownership of this email address.</p>
          ) : (
            <Field label="Email address" name="email" type="email" required />
          )}
        </Form>
      )}
    </AuthLayout>
  );
}
