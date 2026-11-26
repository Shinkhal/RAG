import { Logo } from "../components/Logo";
import { Button } from "../components/Button";
import { FeatureCard } from "../components/FeatureCard";

const features = [
  {
    icon: "📄",
    title: "Upload Documents",
    description:
      "Bring your PDFs, text files, Markdown, and CSVs into one private workspace.",
  },
  {
    icon: "💬",
    title: "Ask Questions",
    description:
      "Query your documents using natural language and get instant, accurate answers.",
  },
  {
    icon: "📑",
    title: "See Your Sources",
    description:
      "Every answer links back to the exact excerpts and pages it was drawn from.",
  },
  {
    icon: "🔒",
    title: "Private & Secure",
    description:
      "Your documents stay private. Only you can access your workspace and data.",
  },
];

const steps = [
  { num: "1", label: "Create an account" },
  { num: "2", label: "Upload your documents" },
  { num: "3", label: "Ask anything" },
];

export function LandingPage() {
  return (
    <div className="landing">
      {/* ───── Navbar ───── */}
      <header className="landing__nav">
        <a href="/" className="landing__brand">
          <Logo size="md" />
        </a>
        <nav className="landing__links">
          <a href="/login">
            <Button variant="ghost" size="sm">Sign in</Button>
          </a>
          <a href="/signup">
            <Button variant="primary" size="sm">Get started</Button>
          </a>
        </nav>
      </header>

      {/* ───── Hero ───── */}
      <section className="landing__hero">
        <span className="landing__kicker">DOCUMENT WORKSPACE</span>
        <h1 className="landing__title">
          Get instant answers
          <br />
          from your documents
        </h1>
        <p className="landing__subtitle">
          Upload your PDFs and notes, ask questions in plain language, and see
          the exact excerpts behind every answer. All in one private workspace.
        </p>
        <div className="landing__cta">
          <a href="/signup">
            <Button size="lg">Create free account</Button>
          </a>
          <a href="/login">
            <Button variant="secondary" size="lg">Sign in</Button>
          </a>
        </div>

        {/* Demo card */}
        <div className="landing__demo">
          <div className="landing__demo-q">
            <span className="landing__demo-label">Your question</span>
            <p>What are the main findings in this report?</p>
          </div>
          <div className="landing__demo-a">
            <span className="landing__demo-label">AI Answer</span>
            <p>
              The report identifies three key findings: increased revenue growth
              of 23% year-over-year, expansion into two new markets, and
              improved customer retention rates…
            </p>
            <div className="landing__demo-source">
              <span>📄 Annual Report 2024 · page 12</span>
            </div>
          </div>
        </div>
      </section>

      {/* ───── Features ───── */}
      <section className="landing__features" id="features">
        <span className="landing__kicker">WHY RAG WORKSPACE</span>
        <h2 className="landing__section-title">
          Everything you need to work with your documents
        </h2>
        <div className="landing__feature-grid">
          {features.map((f) => (
            <FeatureCard key={f.title} {...f} />
          ))}
        </div>
      </section>

      {/* ───── How It Works ───── */}
      <section className="landing__how">
        <span className="landing__kicker">HOW IT WORKS</span>
        <h2 className="landing__section-title">
          Up and running in three simple steps
        </h2>
        <div className="landing__steps">
          {steps.map((s) => (
            <div key={s.num} className="landing__step">
              <span className="landing__step-num">{s.num}</span>
              <span className="landing__step-label">{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ───── CTA Footer ───── */}
      <section className="landing__bottom-cta">
        <h2>Ready to get started?</h2>
        <p>Create your free account and start asking questions in minutes.</p>
        <a href="/signup">
          <Button size="lg">Get started — it's free</Button>
        </a>
      </section>

      {/* ───── Footer ───── */}
      <footer className="landing__footer">
        <Logo size="sm" />
        <small>© {new Date().getFullYear()} RAG Workspace</small>
      </footer>
    </div>
  );
}
