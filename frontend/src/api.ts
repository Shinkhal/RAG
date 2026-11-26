export interface Account {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  created_at?: string;
}

export interface Notebook {
  id: string;
  title: string | null;
}

export interface SourceDocument {
  id: string;
  name: string;
  status: string;
  chunks_created?: number;
}

export interface Answer {
  answer: string;
  sources: {
    doc_id: string;
    doc_name: string | null;
    page: number | null;
    excerpt: string | null;
  }[];
}

export interface Turn {
  question: string;
  response: Answer;
}

export interface Persona {
  persona_id: string;
  name: string;
  description: string | null;
  style_config: Record<string, unknown>;
  intensity: number;
  sample_responses: Record<string, unknown>[] | null;
  is_active: boolean;
  is_system: boolean;
}

export interface PersonaSelection {
  persona_id: string;
  intensity: number;
}

const auth = "/api/v1/auth";
const rag = "/api/v1/rag";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

interface Options {
  method?: "GET" | "POST" | "PATCH";
  data?: object;
  body?: FormData;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: Options = {}): Promise<T> {
  const { data, method = "GET", signal } = options;
  const headers = new Headers({ "X-RAG-Request": "1" });
  if (data) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      signal,
      body: data ? JSON.stringify(data) : options.body,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
  }
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path.startsWith(rag)) location.replace("/login");
    const fallback = response.status === 422
      ? "Check the fields and try again."
      : response.status >= 500
      ? "The backend is unavailable. Check that the API server is running and try again."
      : "The service could not complete the request. Try again.";
    throw new ApiError(response.status, typeof payload?.detail === "string" ? payload.detail : fallback);
  }
  if (payload === null || !response.headers.get("content-type")?.includes("application/json")) {
    throw new ApiError(502, "The API returned an unexpected response. Check the frontend API proxy configuration.");
  }
  return payload as T;
}

const sessionPath = (id: string) => `${rag}/sessions/${encodeURIComponent(id)}`;

export const api = {
  account: (signal: AbortSignal) => request<Account>(`${auth}/me`, { signal }),
  authenticate: (
    mode: "login" | "signup",
    data: { email: string; password: string; first_name?: string; last_name?: string }
  ) => request<Account>(`${auth}/${mode}`, { method: "POST", data }),
  forgotPassword: (email: string) =>
    request<{ message: string }>(`${auth}/forgot-password`, { method: "POST", data: { email } }),
  resetPassword: (token: string, password: string) =>
    request<{ message: string }>(`${auth}/reset-password`, {
      method: "POST",
      data: { token, password },
    }),
  logout: () => request<void>(`${auth}/logout`, { method: "POST" }),
  updateProfile: (data: { first_name: string; last_name: string }) =>
    request<Account>(`${auth}/profile`, { method: "PATCH", data }),
  changePassword: (data: { current_password: string; new_password: string }) =>
    request<Account>(`${auth}/change-password`, { method: "POST", data }),
  personas: (signal: AbortSignal) => request<Persona[]>(`${rag}/personas`, { signal }),
  notebooks: (signal: AbortSignal) => request<Notebook[]>(`${rag}/sessions`, { signal }),
  createNotebook: (title: string) =>
    request<Notebook>(`${rag}/sessions`, { method: "POST", data: { title } }),
  history: (id: string, signal: AbortSignal) => request<Turn[]>(`${sessionPath(id)}/history`, { signal }),
  documents: (id: string, signal: AbortSignal) =>
    request<SourceDocument[]>(`${sessionPath(id)}/documents`, { signal }),
  ingestStatus: (jobId: string, signal: AbortSignal) =>
    request<{ status: string; error: string | null; chunks_created: number }>(`${rag}/ingest/status/${encodeURIComponent(jobId)}`, { signal }),
  document: (documentId: string, signal: AbortSignal) =>
    request<{ status: string; error: string | null; chunks_created: number }>(`${rag}/documents/${encodeURIComponent(documentId)}`, { signal }),
  upload: (sessionId: string, file: File) => {
    const body = new FormData();
    body.set("session_id", sessionId);
    body.set("file", file);
    return request<{ document_id: string; job_id: string | null; status: string }>(`${rag}/ingest`, { method: "POST", body });
  },
  ask: (sessionId: string, question: string, persona?: PersonaSelection | null) =>
    request<Answer>(`${rag}/query`, {
      method: "POST",
      data: { session_id: sessionId, query: question, ...(persona ? { persona } : {}) },
    }),
};

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Try again.";
}
