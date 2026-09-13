import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, Navigate, Outlet, useNavigate } from "react-router-dom";
import { ArrowRight, Layers3 } from "lucide-react";
import { api, saveTokens, tokens } from "./api";
import { ErrorBox, Field, Form, Loading, str } from "./ui";
import type { Tokens, User } from "./types";

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
  const [error, setError] = useState("");
  useEffect(() => {
    const sync = () => {
      if (!tokens()) setUser(null);
    };
    window.addEventListener("auth-change", sync);
    window.addEventListener("storage", sync);
    if (tokens())
      api<User>("/auth/me")
        .then(setUser)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    else setLoading(false);
    return () => {
      window.removeEventListener("auth-change", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  async function signOut() {
    const current = tokens();
    if (current)
      await api(
        "/auth/logout",
        "POST",
        { refresh_token: current.refresh_token },
        false,
      );
    saveTokens(null);
    setUser(null);
  }
  return (
    <AuthContext.Provider value={{ user, loading, setUser, signOut }}>
      {error && !user && (
        <div className="connection-error">
          <ErrorBox message={error} />
          <button onClick={() => window.location.reload()}>
            Retry connection
          </button>
          <button
            onClick={() => {
              saveTokens(null);
              setError("");
            }}
          >
            Return to sign in
          </button>
        </div>
      )}
      {children}
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
          const result = await api<Tokens & { user: User }>(
            "/auth/login",
            "POST",
            { email: str(f, "email"), password: String(f.get("password")) },
            false,
          );
          saveTokens(result);
          setUser(result.user);
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
  const { user, loading, setUser } = useAuth();
  const navigate = useNavigate();
  const invite = sessionStorage.getItem("searchroom.invite");
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
          const result = await api<Tokens & { user: User }>(
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
          saveTokens(result);
          setUser(result.user);
          sessionStorage.removeItem("searchroom.invite");
          navigate("/", { replace: true });
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
                const result = await api<Tokens & { user: User }>(
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
                saveTokens(result);
                setUser(result.user);
                sessionStorage.removeItem("searchroom.invite");
                navigate("/");
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
