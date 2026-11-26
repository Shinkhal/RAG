import { useState, type FormEvent } from "react";
import { api, errorMessage } from "./api";

export function AuthPage({ signup }: { signup: boolean }) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const title = signup ? "Create account" : "Sign in";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setSubmitting(true);
    setError("");
    try {
      await api.authenticate(signup ? "signup" : "login", {
        email: String(data.get("email")),
        password: String(data.get("password")),
      });
      location.replace("/workspace");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="intro">
        <p className="kicker">DOCUMENT WORKSPACE</p>
        <h1>Get answers from your documents.</h1>
        <p>Bring your PDFs and notes together, ask questions, and see the excerpts behind each sourced answer.</p>
        <div className="example">
          <span className="kicker">EXAMPLE QUESTION</span>
          <p>What are the main findings in this report?</p>
        </div>
      </section>
      <section className="auth-card" aria-labelledby="auth-heading">
        <h2 id="auth-heading">{title}</h2>
        <form onSubmit={submit}>
          <label htmlFor="auth-email">Email address</label>
          <input id="auth-email" name="email" type="email" autoComplete="email" required maxLength={254} placeholder="you@example.com" />
          <label htmlFor="auth-password">Password</label>
          <input id="auth-password" name="password" type="password" required minLength={signup ? 15 : 1}
            maxLength={128} autoComplete={signup ? "new-password" : "current-password"}
            aria-describedby={signup ? "password-hint" : undefined} />
          {signup && <small id="password-hint">Use at least 15 characters.</small>}
          {error && <p className="error" role="alert">{error}</p>}
          <button disabled={submitting} type="submit">{title}</button>
        </form>
        <p className="auth-switch">
          {signup ? "Already have an account?" : "New to RAG Workspace?"}{" "}
          <a href={signup ? "/login" : "/signup"}>{signup ? "Sign in" : "Create an account"}</a>
        </p>
      </section>
    </main>
  );
}
