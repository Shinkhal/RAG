import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { ArrowUp, BookOpen, Check, Copy, MessageSquare, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Sparkles } from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, errorMessage, type Answer, type Notebook, type Persona, type PersonaSelection, type SourceDocument, type Turn } from "../api";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { Alert } from "../components/Alert";
import { SourcePanel } from "../components/SourcePanel";
import { PersonaSelector } from "../components/PersonaSelector";

const nameOf = (notebook: Notebook) => notebook.title || "Untitled notebook";
const suggestions = ["Summarize the key takeaways", "What are the main themes?", "Which details should I pay attention to?"];
const LEFT_PANE_KEY = "rag.workspace.leftCollapsed";
const RIGHT_PANE_KEY = "rag.workspace.rightCollapsed";

function readFlag(key: string) {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeFlag(key: string, value: boolean) {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    // Storage can be unavailable in private or embedded contexts.
  }
}

function PaneControls({ leftCollapsed, rightCollapsed, onToggleLeft, onToggleRight }: {
  leftCollapsed: boolean; rightCollapsed: boolean; onToggleLeft: () => void; onToggleRight: () => void;
}) {
  return <div className="pane-controls">
    <button type="button" className="icon-button" onClick={onToggleLeft} aria-label={leftCollapsed ? "Show notebooks sidebar" : "Hide notebooks sidebar"} title={leftCollapsed ? "Show notebooks" : "Hide notebooks"}>
      {leftCollapsed ? <PanelLeftOpen size={17} aria-hidden="true" /> : <PanelLeftClose size={17} aria-hidden="true" />}
    </button>
    <button type="button" className="icon-button" onClick={onToggleRight} aria-label={rightCollapsed ? "Show sources sidebar" : "Hide sources sidebar"} title={rightCollapsed ? "Show sources" : "Hide sources"}>
      {rightCollapsed ? <PanelRightOpen size={17} aria-hidden="true" /> : <PanelRightClose size={17} aria-hidden="true" />}
    </button>
  </div>;
}

function ConversationTurn({ question, response }: { question: string; response?: Answer }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);
  return <article className="turn">
    <div className="question"><span className="message-label">You</span><p>{question}</p></div>
    <div className="answer-card">
      <div className="answer-heading"><span className="assistant-mark"><Sparkles size={15} aria-hidden="true" /></span><strong>Notebook assistant</strong></div>
      {response ? <>
        <div className="answer markdown"><Markdown remarkPlugins={[remarkGfm]}>{response.answer}</Markdown></div>
        {response.sources.length > 0 ? <div className="citations"><span className="message-label">Sources · {response.sources.length}</span>{response.sources.map((source, index) => <details key={index}>
          <summary><span className="citation-number">{index + 1}</span>{source.doc_name || "Document"}{source.page != null && <span className="citation-page">Page {source.page}</span>}</summary>
          <p>{source.excerpt || "No excerpt available for this source."}</p>
        </details>)}</div> : <small>No document excerpts were cited for this answer.</small>}
        <div className="answer-actions"><button type="button" className="copy-button" onClick={async () => { try { await navigator.clipboard.writeText(response.answer); setCopied(true); setCopyError(""); } catch { setCopyError("Could not copy. Select the answer text to copy it."); } }}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? "Copied" : "Copy answer"}</button><span role="status">{copyError}</span></div>
      </> : <div className="thinking" role="status"><span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span>Looking through your sources…</div>}
    </div>
  </article>;
}

function NotebookPanel({ notebook, active, personas, leftCollapsed, rightCollapsed, onToggleLeft, onToggleRight }: {
  notebook: Notebook;
  active: boolean;
  personas: Persona[];
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
}) {
  const id = useId();
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [turns, setTurns] = useState<Turn[]>();
  const [question, setQuestion] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [actionError, setActionError] = useState("");
  const [persona, setPersona] = useState<PersonaSelection | null>(null);
  const messages = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const submitting = useRef(false);
  const nearBottom = useRef(true);
  const readyCount = documents.filter(doc => doc.status === "processed").length;
  const ready = readyCount > 0;

  useEffect(() => {
    const controller = new AbortController();
    setHistoryError("");
    api.history(notebook.id, controller.signal).then(setTurns).catch(err => {
      if (!controller.signal.aborted) setHistoryError(errorMessage(err));
    });
    return () => controller.abort();
  }, [notebook.id, historyRefresh]);

  useEffect(() => {
    if (active && nearBottom.current && messages.current) messages.current.scrollTop = messages.current.scrollHeight;
  }, [turns, pendingQuestion, active]);

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (!text || !ready || submitting.current || !turns) return;
    submitting.current = true;
    nearBottom.current = true;
    setPendingQuestion(text);
    setQuestion("");
    setActionError("");
    try {
      const response = await api.ask(notebook.id, text, persona);
      setTurns(prev => [...(prev ?? []), { question: text, response }]);
    } catch (err) {
      setQuestion(draft => draft || text);
      setActionError(errorMessage(err));
    } finally { setPendingQuestion(""); submitting.current = false; textarea.current?.focus(); }
  }

  return <div className="notebook-panel" hidden={!active}>
    <section className="conversation" aria-labelledby={`${id}-title`}>
      <header className="conversation-head">
        <div className="conversation-head__main">
          <span className="kicker">YOUR NOTEBOOK</span>
          <h1 id={`${id}-title`}>{nameOf(notebook)}</h1>
          <p className="conversation-head__subtitle">{ready ? "Grounded answers with citations from your sources." : "Add a source to unlock grounded answers."}</p>
        </div>
        <div className="conversation-head__actions">
          <span className={`chat-availability ${ready ? "is-ready" : ""}`}><span />{ready ? `${readyCount} source${readyCount === 1 ? "" : "s"} ready` : "Waiting for sources"}</span>
          <PersonaSelector personas={personas} value={persona} onChange={setPersona} />
          <PaneControls leftCollapsed={leftCollapsed} rightCollapsed={rightCollapsed} onToggleLeft={onToggleLeft} onToggleRight={onToggleRight} />
        </div>
      </header>
      {actionError && <Alert className="banner">{actionError}</Alert>}
      <div className="messages" ref={messages} role="log" aria-label="Conversation" aria-live="polite" aria-busy={!!pendingQuestion} onScroll={() => { const el = messages.current; if (el) nearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100; }}>
        {historyError && <Alert>{historyError} <Button size="sm" variant="secondary" onClick={() => setHistoryRefresh(v => v + 1)}>Retry history</Button></Alert>}
        {!turns && !historyError && <EmptyState title="Loading conversation…" />}
        {turns?.length === 0 && !pendingQuestion && <div className="chat-welcome"><div className="welcome-icon"><BookOpen size={30} strokeWidth={1.5} aria-hidden="true" /></div><span className="kicker">FROM INFORMATION TO INSIGHT</span><h2>Your documents. A new perspective.</h2><p>{ready ? "Ask a question, connect ideas, or get a clear summary. Every conversation starts with your sources." : "Add your sources, then ask questions and explore the ideas inside. Your answers and citations will appear here."}</p><div className="suggestions">{suggestions.map(prompt => <button type="button" key={prompt} disabled={!ready} onClick={() => { setQuestion(prompt); textarea.current?.focus(); }}><MessageSquare size={16} aria-hidden="true" /><span>{prompt}</span><span aria-hidden="true">↗</span></button>)}</div></div>}
        {turns?.map((turn, index) => <ConversationTurn key={index} {...turn} />)}
        {pendingQuestion && <ConversationTurn question={pendingQuestion} />}
      </div>
      <form className="composer" onSubmit={ask}>
        <label className="visually-hidden" htmlFor={`${id}-question`}>Ask a question</label>
        <div className="question-row">
          <textarea ref={textarea} id={`${id}-question`} rows={2} maxLength={8000} required value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder={ready ? "Ask anything about your sources…" : "Add a source to start asking questions…"} aria-describedby={`${id}-hint`} />
          <Button className="send-button" type="submit" aria-label={pendingQuestion ? "Waiting for answer" : "Send question"} disabled={!turns || !ready || !!pendingQuestion || !question.trim()}><ArrowUp size={20} aria-hidden="true" /></Button>
        </div>
        <div className="composer-meta"><small id={`${id}-hint`}>{ready ? "Check citations to verify important details." : "Sources become available when processing finishes."}</small><small className="keyboard-hint">Enter to send · Shift + Enter for a new line</small></div>
      </form>
    </section>
    <SourcePanel notebookId={notebook.id} active={active} collapsed={rightCollapsed} onExpand={onToggleRight} onDocuments={setDocuments} />
  </div>;
}

/* ——— Create Notebook Dialog ——— */

function CreateNotebookDialog({
  onCreate,
}: {
  onCreate: (notebook: Notebook) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const form = useRef<HTMLFormElement>(null);
  const id = useId();
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = String(
      new FormData(event.currentTarget).get("title")
    ).trim();
    if (!title) {
      setError("Enter a notebook name.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      onCreate(await api.createNotebook(title));
      dialog.current?.close();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        aria-label="New notebook"
        onClick={() => {
          setError("");
          form.current?.reset();
          dialog.current?.showModal();
        }}
      >
        + New
      </Button>
      <dialog
        ref={dialog}
        aria-labelledby={`${id}-title`}
        onCancel={(e) => {
          if (saving) e.preventDefault();
        }}
      >
        <form ref={form} onSubmit={submit}>
          <h2 id={`${id}-title`}>New notebook</h2>
          <label htmlFor={`${id}-name`}>Notebook name</label>
          <input
            id={`${id}-name`}
            name="title"
            required
            maxLength={120}
            placeholder="e.g. Research notes"
          />
          {error && <Alert>{error}</Alert>}
          <div className="dialog-actions">
            <Button
              variant="secondary"
              disabled={saving}
              type="button"
              onClick={() => dialog.current?.close()}
            >
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              Create notebook
            </Button>
          </div>
        </form>
      </dialog>
    </>
  );
}

/* ——— Main Workspace ——— */

export function WorkspacePage() {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selected, setSelected] = useState<string>();
  const [opened, setOpened] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [leftCollapsed, setLeftCollapsed] = useState(() => readFlag(LEFT_PANE_KEY));
  const [rightCollapsed, setRightCollapsed] = useState(() => readFlag(RIGHT_PANE_KEY));

  function select(id: string) {
    setOpened((ids) => (ids.includes(id) ? ids : [...ids, id]));
    setSelected(id);
  }

  useEffect(() => writeFlag(LEFT_PANE_KEY, leftCollapsed), [leftCollapsed]);
  useEffect(() => writeFlag(RIGHT_PANE_KEY, rightCollapsed), [rightCollapsed]);

  useEffect(() => {
    const controller = new AbortController();
    api
      .personas(controller.signal)
      .then((list) => {
        if (!controller.signal.aborted) setPersonas(list.filter((persona) => persona.is_active));
      })
      .catch(() => {
        // Personas are optional; the workspace still works without them.
        if (!controller.signal.aborted) setPersonas([]);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    api
      .notebooks(controller.signal)
      .then((list) => {
        setNotebooks(list);
        if (list[0]) select(list[0].id);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(errorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const toggleLeft = () => setLeftCollapsed((value) => !value);
  const toggleRight = () => setRightCollapsed((value) => !value);

  return (
    <main className={`workspace ${leftCollapsed ? "is-left-collapsed" : ""} ${rightCollapsed ? "is-right-collapsed" : ""}`}>
      <aside className={`sidebar ${leftCollapsed ? "is-collapsed" : ""}`} aria-label="Notebooks">
        {leftCollapsed ? (
          <div className="pane-rail">
            <button type="button" className="icon-button" onClick={toggleLeft} aria-label="Show notebooks sidebar" title="Show notebooks">
              <PanelLeftOpen size={17} aria-hidden="true" />
            </button>
          </div>
        ) : (
          <>
            <div className="section-title">
              <h2>Notebooks <span className="count">{notebooks.length}</span></h2>
              {!loading && (
                <CreateNotebookDialog
                  onCreate={(notebook) => {
                    setNotebooks((list) => [notebook, ...list]);
                    select(notebook.id);
                  }}
                />
              )}
            </div>
            <nav id="notebooks" aria-label="Your notebooks">
              {notebooks.map((notebook) => (
                <button
                  className="notebook"
                  key={notebook.id}
                  aria-current={
                    notebook.id === selected ? true : undefined
                  }
                  onClick={() => select(notebook.id)}
                >
                  <BookOpen size={17} aria-hidden="true" /><span>{nameOf(notebook)}</span>
                </button>
              ))}
            </nav>
          </>
        )}
      </aside>
      {notebooks
        .filter(({ id }) => opened.includes(id))
        .map((notebook) => (
          <NotebookPanel
            key={notebook.id}
            notebook={notebook}
            active={selected === notebook.id}
            personas={personas}
            leftCollapsed={leftCollapsed}
            rightCollapsed={rightCollapsed}
            onToggleLeft={toggleLeft}
            onToggleRight={toggleRight}
          />
        ))}
      {!selected && (
        <section className="conversation">
          <header className="conversation-head">
            <div className="conversation-head__main">
              <span className="kicker">WORKSPACE</span>
              <h1>Your workspace</h1>
              <p className="conversation-head__subtitle">Notebooks keep your sources and questions together.</p>
            </div>
            <div className="conversation-head__actions">
              <PaneControls leftCollapsed={leftCollapsed} rightCollapsed={rightCollapsed} onToggleLeft={toggleLeft} onToggleRight={toggleRight} />
            </div>
          </header>
          {error && <Alert className="banner">{error}</Alert>}
          {loading && <EmptyState title="Loading notebooks…" />}
          {!loading && !error && (
            <EmptyState
              title="Create your first notebook"
              description="Use + New to make a place for your documents and questions."
            />
          )}
        </section>
      )}
    </main>
  );
}
