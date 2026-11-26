import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  BookOpen,
  BriefcaseBusiness,
  Check,
  ExternalLink,
  FileText,
  GraduationCap,
  LockKeyhole,
  MessageSquareText,
  ScanText,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { Logo } from "../components/Logo";
import { Button } from "../components/Button";
import { FeatureCard } from "../components/FeatureCard";

type Feature = {
  icon: LucideIcon;
  title: string;
  description: string;
  tone: "green" | "blue" | "amber" | "rose";
};

const features: Feature[] = [
  {
    icon: UploadCloud,
    title: "Upload Documents",
    description:
      "Bring your PDFs, text files, Markdown, and CSVs into one private workspace.",
    tone: "green",
  },
  {
    icon: MessageSquareText,
    title: "Ask Questions",
    description:
      "Query your documents in natural language and get instant, focused answers.",
    tone: "blue",
  },
  {
    icon: ScanText,
    title: "See Your Sources",
    description:
      "Every answer links back to the exact excerpts and pages it was drawn from.",
    tone: "amber",
  },
  {
    icon: LockKeyhole,
    title: "Private & Secure",
    description:
      "Your documents stay private. Only you can access your workspace and files.",
    tone: "rose",
  },
];

const fileTypes = [
  { label: "PDF documents", icon: FileText },
  { label: "Markdown notes", icon: BookOpen },
  { label: "Text files", icon: FileText },
  { label: "CSV data", icon: ScanText },
];

const useCases: { icon: LucideIcon; tone: string; title: string; description: string; tag: string }[] = [
  {
    icon: GraduationCap,
    tone: "sage",
    title: "For studying",
    description:
      "Turn lecture notes and readings into a study companion that answers in plain language and points you to the right page.",
    tag: "Lecture notes · Readings",
  },
  {
    icon: ScanText,
    tone: "clay",
    title: "For research",
    description:
      "Compare papers, surface key findings, and trace every claim back to the source before you cite it.",
    tag: "Papers · Literature reviews",
  },
  {
    icon: BriefcaseBusiness,
    tone: "sky",
    title: "For work",
    description:
      "Get up to speed on long reports, contracts, and meeting notes without losing the details that matter.",
    tag: "Reports · Contracts",
  },
];

const steps = [
  {
    num: "1",
    title: "Create your workspace",
    description: "Sign up free and open your first notebook in seconds. No setup required.",
  },
  {
    num: "2",
    title: "Add your documents",
    description: "Drop in PDFs, notes, Markdown, or CSVs. We index them for meaning, not just keywords.",
  },
  {
    num: "3",
    title: "Ask anything",
    description: "Get grounded answers with page-level citations, then follow the thread with follow-up questions.",
  },
];

function HeroPreview() {
  return (
    <div className="landing__hero-visual" aria-hidden="true">
      <div className="hero-blob hero-blob--one" />
      <div className="hero-blob hero-blob--two" />
      <div className="preview">
        <div className="preview__chrome">
          <span className="preview__dots"><i /><i /><i /></span>
          <span className="preview__url">rag-workspace.app</span>
          <span className="preview__secure"><LockKeyhole size={11} />Private</span>
        </div>
        <div className="preview__app">
          <aside className="preview__side">
            <span className="preview__side-title">NOTEBOOKS</span>
            <span className="preview__side-item is-active"><BookOpen size={13} />Thesis research</span>
            <span className="preview__side-item"><BookOpen size={13} />Course notes</span>
            <span className="preview__side-item"><BookOpen size={13} />Annual report</span>
            <span className="preview__drop"><UploadCloud size={13} />Drop a PDF</span>
          </aside>
          <div className="preview__chat">
            <div className="preview__chat-head">
              <span className="preview__chat-kicker">YOUR NOTEBOOK</span>
              <strong>Thesis research</strong>
              <span className="preview__ready"><i />4 sources ready</span>
            </div>
            <div className="preview__q">What are the main findings?</div>
            <div className="preview__a">
              <span className="preview__ai"><Sparkles size={12} />Notebook assistant</span>
              <p>The study finds three consistent patterns across the interviews:</p>
              <ul>
                <li>Clear navigation reduces effort</li>
                <li>Feedback builds confidence</li>
                <li>Consistency speeds up learning</li>
              </ul>
              <span className="preview__cite"><FileText size={11} />Interview notes · page 4</span>
              <span className="preview__follow">Follow up · “Compare with the 2023 report”</span>
            </div>
          </div>
        </div>
      </div>
      <div className="preview-float preview-float--source">
        <ScanText size={16} />
        <div><strong>Page-level citations</strong><span>Every answer shows its source</span></div>
      </div>
      <div className="preview-float preview-float--private">
        <ShieldCheck size={16} />
        <div><strong>Private by default</strong><span>Only you can access your files</span></div>
      </div>
    </div>
  );
}

export function LandingPage() {
  return (
    <div className="landing">
      {/* ───── Navbar ───── */}
      <header className="landing__nav">
        <a href="/" className="landing__brand">
          <Logo size="md" />
        </a>
        <nav className="landing__nav-links" aria-label="Landing sections">
          <a href="#features" className="landing__nav-link">Features</a>
          <a href="#how" className="landing__nav-link">How it works</a>
        </nav>
        <div className="landing__links">
          <a href="/login">
            <Button variant="ghost" size="sm">Sign in</Button>
          </a>
          <a href="/signup">
            <Button variant="primary" size="sm">Get started</Button>
          </a>
        </div>
      </header>

      {/* ───── Hero ───── */}
      <section className="landing__hero">
        <div className="landing__hero-glow" aria-hidden="true" />
        <div className="landing__hero-copy">
          <span className="landing__kicker">DOCUMENT INTELLIGENCE, GROUNDED</span>
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
              <Button size="lg">Create free account <ArrowRight size={16} aria-hidden="true" /></Button>
            </a>
            <a href="/login">
              <Button variant="secondary" size="lg">Sign in</Button>
            </a>
          </div>
          <ul className="landing__hero-points">
            <li><Check size={14} aria-hidden="true" />No credit card required</li>
            <li><Check size={14} aria-hidden="true" />Answers with citations</li>
            <li><Check size={14} aria-hidden="true" />Private by default</li>
          </ul>
        </div>
        <HeroPreview />
      </section>

      {/* ───── Supported files ───── */}
      <section className="landing__filetypes" aria-label="Supported file types">
        <span>Works with the documents you already have</span>
        <div className="landing__filetypes-list">
          {fileTypes.map(({ label, icon: Icon }) => (
            <span className="landing__filetype" key={label}><Icon size={14} aria-hidden="true" />{label}</span>
          ))}
        </div>
      </section>

      {/* ───── Features ───── */}
      <section className="landing__features" id="features">
        <span className="landing__kicker">WHY RAG WORKSPACE</span>
        <h2 className="landing__section-title">
          Everything you need to work with your documents
        </h2>
        <div className="landing__feature-grid">
          {features.map(({ icon: Icon, tone, ...feature }) => (
            <FeatureCard key={feature.title} tone={tone} icon={<Icon size={22} />} {...feature} />
          ))}
        </div>
      </section>

      {/* ───── Citations split ───── */}
      <section className="landing__verify">
        <div className="landing__verify-inner">
          <div className="landing__verify-visual" aria-hidden="true">
            <div className="quote-card">
              <span className="quote-card__label">SOURCE EXCERPT</span>
              <p>
                “Participants preferred <mark>clear feedback and simple navigation</mark> over
                additional features.”
              </p>
              <div className="quote-card__meta">
                <FileText size={13} />Research notes.pdf
                <span>Page 3</span>
              </div>
            </div>
            <div className="verify-chip verify-chip--one"><Sparkles size={14} />Grounded answer</div>
            <div className="verify-chip verify-chip--two"><Check size={14} />Citation verified</div>
          </div>
          <div className="landing__verify-copy">
            <span className="landing__kicker">CITATIONS, NOT GUESSWORK</span>
            <h2>See exactly where every answer comes from.</h2>
            <p>
              No black boxes. Each response is grounded in your documents and links
              back to the excerpt and page it was drawn from, so you can check the
              details that matter before you rely on them.
            </p>
            <ul className="landing__checks">
              <li><Check size={16} aria-hidden="true" />Page-level source previews for every answer</li>
              <li><Check size={16} aria-hidden="true" />Responses stay within the documents you added</li>
              <li><Check size={16} aria-hidden="true" />A clear “not found” when your sources don’t support a claim</li>
            </ul>
          </div>
        </div>
      </section>

      {/* ───── Use cases ───── */}
      <section className="landing__use-cases">
        <span className="landing__kicker">MADE FOR DEEP READING</span>
        <h2 className="landing__section-title">One workspace for every long document</h2>
        <div className="landing__use-grid">
          {useCases.map(({ icon: Icon, tone, title, description, tag }) => (
            <article className={`use-card use-card--${tone}`} key={title}>
              <span className="use-card__icon"><Icon size={20} aria-hidden="true" /></span>
              <h3>{title}</h3>
              <p>{description}</p>
              <span className="use-card__tag">{tag}</span>
            </article>
          ))}
        </div>
      </section>

      {/* ───── How It Works ───── */}
      <section className="landing__how" id="how">
        <span className="landing__kicker">HOW IT WORKS</span>
        <h2 className="landing__section-title">Up and running in three simple steps</h2>
        <div className="landing__steps">
          {steps.map((step) => (
            <div key={step.num} className="landing__step">
              <span className="landing__step-num">{step.num}</span>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ───── CTA Footer ───── */}
      <section className="landing__bottom-cta">
        <span className="landing__cta-spark" aria-hidden="true"><Sparkles size={18} /></span>
        <h2>Ready to get started?</h2>
        <p>Create your free account and start asking questions in minutes.</p>
        <a href="/signup">
          <Button size="lg">Get started — it's free <ArrowRight size={16} aria-hidden="true" /></Button>
        </a>
        <small className="landing__cta-note">Free to start · No credit card required</small>
      </section>

      {/* ───── Footer ───── */}
      <footer className="landing__footer">
        <div className="landing__footer-main">
          <a href="/" className="landing__brand"><Logo size="sm" /></a>
          <p>Grounded answers for the documents you already have.</p>
        </div>
        <nav className="landing__footer-links" aria-label="Footer">
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <a href="/login">Sign in</a>
          <a
            href="https://shinkhalsinha.in"
            className="landing__credit"
            target="_blank"
            rel="noreferrer"
          >
            Made by <strong>Shinkhal Sinha</strong><ExternalLink size={13} aria-hidden="true" />
          </a>
        </nav>
        <div className="landing__footer-bottom">
          <small>© {new Date().getFullYear()} RAG Workspace</small>
          <small>Built with care in India · All rights reserved.</small>
        </div>
      </footer>
    </div>
  );
}
