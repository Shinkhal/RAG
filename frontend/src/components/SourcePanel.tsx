import { useEffect, useId, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { CheckCircle2, CircleAlert, Clock3, FileText, LoaderCircle, PanelRightOpen, UploadCloud, X } from "lucide-react";
import { api, errorMessage, type SourceDocument } from "../api";
import { Button } from "./Button";
import { Alert } from "./Alert";

type UploadItem = { id: string; file: File; state: "waiting" | "uploading" | "failed"; error?: string };
const labels: Record<string, string> = { processed: "Ready", failed: "Processing failed", queued: "Queued", processing: "Processing" };

export function SourcePanel({ notebookId, active, collapsed, onExpand, onDocuments }: {
  notebookId: string; active: boolean; collapsed: boolean; onExpand: () => void; onDocuments: (docs: SourceDocument[]) => void;
}) {
  const id = useId();
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [error, setError] = useState("");
  const [rejection, setRejection] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [details, setDetails] = useState<Record<string, { error: string | null; chunks_created: number }>>({});
  const jobIds = useRef(new Map<string, string>());
  const busy = useRef(false);
  const ready = documents.filter(doc => doc.status === "processed").length;
  const pending = documents.filter(doc => ["queued", "processing"].includes(doc.status)).length;

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const list = await api.documents(notebookId, controller.signal);
        if (controller.signal.aborted) return;
        setDocuments(list);
        onDocuments(list);
        setError("");
        setLoading(false);
        // Job metadata provides actual worker errors and completed chunk counts.
        const results = await Promise.allSettled(list.filter(doc => jobIds.current.has(doc.id) || doc.status === "failed").map(async doc => {
          const jobId = jobIds.current.get(doc.id);
          const result = jobId ? await api.ingestStatus(jobId, controller.signal) : await api.document(doc.id, controller.signal);
          return [doc.id, result] as const;
        }));
        if (controller.signal.aborted) return;
        setDetails(previous => ({ ...previous, ...Object.fromEntries(results.flatMap(result => result.status === "fulfilled" ? [result.value] : [])) }));
        if (list.some(doc => ["queued", "processing"].includes(doc.status))) timer = setTimeout(load, 2200);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(errorMessage(err));
          setLoading(false);
          timer = setTimeout(load, 6000);
        }
      }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [active, notebookId, refresh, onDocuments]);

  async function uploadFiles(items: UploadItem[]) {
    if (busy.current) return;
    busy.current = true;
    try {
      for (const item of items) {
        setUploads(list => list.map(row => row.id === item.id ? { ...row, state: "uploading", error: undefined } : row));
        try {
          const result = await api.upload(notebookId, item.file);
          if (result.job_id) jobIds.current.set(result.document_id, result.job_id);
          setUploads(list => list.filter(row => row.id !== item.id));
          setRefresh(value => value + 1);
        } catch (err) {
          setUploads(list => list.map(row => row.id === item.id ? { ...row, state: "failed", error: errorMessage(err) } : row));
        }
      }
    } finally { busy.current = false; }
  }
  const uploading = uploads.some(item => item.state !== "failed");
  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    accept: { "application/pdf": [".pdf"], "text/plain": [".txt"], "text/markdown": [".md"], "text/csv": [".csv"] },
    disabled: uploading,
    multiple: true,
    validator: file => file.size === 0 ? { code: "empty-file", message: "This file is empty." } : null,
    onDrop: (files, rejected) => {
      setRejection(rejected.map(({ file, errors }) => `${file.name}: ${errors.some(e => e.code === "empty-file") ? "This file is empty." : "Choose a PDF, TXT, Markdown, or CSV file."}`).join(" "));
      const items: UploadItem[] = files.map(file => ({ id: crypto.randomUUID(), file, state: "waiting" }));
      setUploads(list => [...list, ...items]);
      void uploadFiles(items);
    },
  });

  return <aside className={`sources-panel ${collapsed ? "is-collapsed" : ""}`} aria-labelledby={`${id}-title`} hidden={!active}>
    {collapsed ? <div className="pane-rail">
      <button type="button" className="icon-button" onClick={onExpand} aria-label="Show sources panel" title="Show sources">
        <PanelRightOpen size={17} aria-hidden="true" />
      </button>
    </div> : <>
    <div className="section-title"><div><span className="kicker">KNOWLEDGE BASE</span><h2 id={`${id}-title`}>Sources <span className="count">{documents.length}</span></h2></div><FileText size={19} aria-hidden="true" /></div>
    <p className="panel-description">Add the documents you want to explore.</p>
    <div {...getRootProps({ className: `dropzone ${isDragActive ? "is-dragging" : ""} ${isDragReject ? "is-rejected" : ""} ${uploading ? "is-disabled" : ""}`, "aria-label": "Upload documents", "aria-describedby": `${id}-formats` })}>
      <input {...getInputProps()} />
      <span className="upload-icon"><UploadCloud size={24} aria-hidden="true" /></span>
      <strong>{uploading ? "Uploading documents…" : isDragActive ? "Drop your files here" : "Drop documents here"}</strong>
      <span>{uploading ? "Your files are being sent securely" : <>or <b>browse files</b></>}</span>
      <small id={`${id}-formats`}>PDF, TXT, Markdown, CSV · Multiple files</small>
    </div>
    {rejection && <Alert>{rejection}</Alert>}
    {error && <Alert>{error} <Button size="sm" variant="secondary" onClick={() => setRefresh(v => v + 1)}>Retry</Button></Alert>}
    <div className="source-summary" role="status">{loading ? "Loading sources…" : `${ready} ready to use${pending ? ` · ${pending} in progress` : ""}`}</div>
    <ul className="documents">
      {uploads.map(item => <li className="document" key={item.id}>
        <FileText className="document-icon" size={19} aria-hidden="true" />
        <div className="document-body"><strong>{item.file.name}</strong><small>{(item.file.size / 1024).toFixed(1)} KB</small>
          <span className={`status-badge status-${item.state}`} role="status">{item.state === "uploading" ? <LoaderCircle size={12} className="spin" /> : item.state === "failed" ? <CircleAlert size={12} /> : <Clock3 size={12} />}{item.state === "uploading" ? "Uploading" : item.state === "failed" ? "Upload failed" : "Waiting to upload"}</span>
          {item.error && <p className="document-error">{item.error}</p>}
          {item.state === "failed" && <div className="document-actions"><Button size="sm" variant="secondary" disabled={uploading} onClick={() => void uploadFiles([item])}>Retry upload</Button><Button size="sm" variant="ghost" aria-label={`Dismiss ${item.file.name}`} onClick={() => setUploads(list => list.filter(row => row.id !== item.id))}><X size={14} /></Button></div>}
        </div>
      </li>)}
      {documents.map(doc => <li className="document" key={doc.id}>
        <FileText className="document-icon" size={19} aria-hidden="true" />
        <div className="document-body"><strong>{doc.name}</strong><span className={`status-badge status-${doc.status}`}>
          {doc.status === "processed" ? <CheckCircle2 size={12} /> : doc.status === "failed" ? <CircleAlert size={12} /> : doc.status === "processing" ? <LoaderCircle size={12} className="spin" /> : <Clock3 size={12} />}{labels[doc.status] || doc.status}
        </span>
          {doc.status === "queued" && <small>Waiting for processing to begin.</small>}
          {doc.status === "processing" && <small>Preparing your document for search…</small>}
          {doc.status === "processed" && <small>{doc.chunks_created ?? details[doc.id]?.chunks_created ?? 0} searchable passages</small>}
          {doc.status === "failed" && <details className="job-error"><summary>View issue</summary><p>{details[doc.id]?.error || "This document could not be processed. Check the file contents and upload it again."}</p></details>}
        </div>
      </li>)}
    </ul>
    {!loading && !error && documents.length === 0 && uploads.length === 0 && <div className="source-empty"><FileText size={26} aria-hidden="true" /><strong>No sources yet</strong><p>Upload your first document to start a conversation grounded in your content.</p></div>}
    <p className="source-footer"><CheckCircle2 size={14} aria-hidden="true" /> Ready sources are available in this notebook.</p>
    </>}
  </aside>;
}
