import { writeFile } from "node:fs/promises";
import { test, expect, type Page } from "@playwright/test";

type Doc = { id: string; name: string; status: string; chunks_created: number };
async function mockWorkspace(page: Page, initial: Doc[] = []) {
  const docs = [...initial];
  let uploadFailures = 0;
  let queryFailures = 0;
  let queries = 0;
  let lastQuery: { persona?: { persona_id: string; intensity: number } } | undefined;
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown;
    if (path.endsWith("/auth/me")) body = { id: "user", first_name: "Alex", last_name: "Morgan", email: "alex@example.com", created_at: "2025-01-15T00:00:00Z" };
    else if (path.endsWith("/personas")) body = [
      { persona_id: "concise", name: "Concise", description: "Short, direct answers.", style_config: { system_prompt: "Be concise." }, intensity: 0.6, sample_responses: null, is_active: true, is_system: true },
      { persona_id: "teacher", name: "Teacher", description: "Explains step by step.", style_config: { system_prompt: "Teach carefully." }, intensity: 0.8, sample_responses: null, is_active: true, is_system: true },
    ];
    else if (path.endsWith("/sessions")) body = [{ id: "research", title: "Product research" }, { id: "notes", title: "Meeting notes" }];
    else if (path.endsWith("/history")) body = [];
    else if (path.endsWith("/documents")) body = path.includes("/research/") ? docs : [];
    else if (path.endsWith("/ingest")) {
      if (uploadFailures-- > 0) return route.fulfill({ status: 503, json: { detail: "Upload temporarily unavailable" } });
      const name = route.request().postData()?.match(/filename="([^"]+)"/)?.[1] || "notes.txt";
      const id = `doc-${docs.length}`;
      docs.push({ id, name, status: "queued", chunks_created: 0 });
      return route.fulfill({ status: 202, json: { document_id: id, job_id: `job-${id}`, status: "queued" } });
    } else if (path.includes("/ingest/status/")) body = { status: "queued", error: null, chunks_created: 0 };
    else if (path.includes("/documents/")) body = { status: "failed", error: "No readable text was found in this file.", chunks_created: 0 };
    else if (path.endsWith("/query")) {
      queries++;
      lastQuery = JSON.parse(route.request().postData() || "{}");
      if (queryFailures-- > 0) return route.fulfill({ status: 503, json: { detail: "Please try your question again." } });
      await new Promise(resolve => setTimeout(resolve, 150));
      body = { answer: "## Key findings\n\nResearch suggests **three priorities**:\n\n- Clear navigation\n- Useful feedback\n- Accessible controls", sources: [{ doc_id: "ready", doc_name: "Research notes.pdf", page: 3, excerpt: "Participants preferred clear feedback and simple navigation." }] };
    } else return route.fulfill({ status: 404, json: { detail: "Not found" } });
    await route.fulfill({ json: body });
  });
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "Product research" })).toBeVisible();
  return { docs, failUpload: () => { uploadFailures = 1; }, failQuery: () => { queryFailures = 1; }, queries: () => queries, lastQuery: () => lastQuery };
}
const ready: Doc = { id: "ready", name: "Research notes.pdf", status: "processed", chunks_created: 12 };

test("multiple dropped files move from queued through processing to ready", async ({ page }) => {
  const state = await mockWorkspace(page);
  await page.locator(".dropzone").evaluate(element => {
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(new File(["First source"], "first.txt", { type: "text/plain" }));
    dataTransfer.items.add(new File(["Second source"], "second.md", { type: "text/markdown" }));
    element.dispatchEvent(new DragEvent("drop", { bubbles: true, dataTransfer }));
  });
  await expect(page.locator(".documents .status-queued")).toHaveCount(2);
  state.docs.forEach(doc => { doc.status = "processing"; });
  await expect(page.locator(".documents .status-processing")).toHaveCount(2);
  state.docs.forEach(doc => { doc.status = "processed"; doc.chunks_created = 8; });
  await expect(page.locator(".documents .status-processed")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Summarize the key takeaways" })).toBeEnabled();
});

test("file rejection and upload retry preserve actionable feedback", async ({ page }) => {
  const state = await mockWorkspace(page);
  await page.locator('input[type="file"]').setInputFiles({ name: "empty.txt", mimeType: "text/plain", buffer: Buffer.from("") });
  await expect(page.getByRole("alert")).toContainText("This file is empty");
  await page.locator('input[type="file"]').setInputFiles({ name: "photo.png", mimeType: "image/png", buffer: Buffer.from("image") });
  await expect(page.getByRole("alert")).toContainText("Choose a PDF");
  state.failUpload();
  await page.locator('input[type="file"]').setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("Document text") });
  await expect(page.getByText("Upload temporarily unavailable")).toBeVisible();
  await page.getByRole("button", { name: "Retry upload" }).click();
  await expect(page.locator(".status-queued")).toHaveCount(1);
  await expect(page.getByText("Upload failed", { exact: true })).toHaveCount(0);
});

test("chat renders Markdown and citations, restores failed questions, and preserves notebook drafts", async ({ page }) => {
  const state = await mockWorkspace(page, [ready]);
  await page.getByRole("button", { name: "Summarize the key takeaways" }).click();
  const input = page.getByRole("textbox", { name: "Ask a question" });
  await input.press("Enter");
  await expect(page.getByRole("heading", { name: "Key findings" })).toBeVisible();
  await expect(page.locator(".answer strong")).toHaveText("three priorities");
  await page.locator(".citations summary").click();
  await expect(page.getByText("Participants preferred clear feedback and simple navigation.")).toBeVisible();
  state.failQuery();
  await input.fill("Explain the feedback");
  await input.press("Enter");
  await expect(page.getByRole("alert")).toContainText("Please try your question again.");
  await expect(input).toHaveValue("Explain the feedback");
  await input.press("Shift+Enter");
  expect(state.queries()).toBe(2);
  await page.getByRole("button", { name: "Meeting notes", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Meeting notes", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Key findings" })).not.toBeVisible();
  await page.getByRole("button", { name: "Product research", exact: true }).click();
  await expect(input).toHaveValue("Explain the feedback\n");
  await page.screenshot({ path: "/tmp/rag-workspace-chat.png", fullPage: true });
});

test("persisted ingestion failures show backend error details", async ({ page }) => {
  await mockWorkspace(page, [{ id: "failed", name: "scan.pdf", status: "failed", chunks_created: 0 }]);
  await page.getByText("View issue").click();
  await expect(page.getByText("No readable text was found in this file.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send question" })).toBeDisabled();
});

test("a persona selected in chat is sent with the question", async ({ page }) => {
  const state = await mockWorkspace(page, [ready]);
  await page.getByRole("button", { name: "Persona" }).click();
  await page.getByRole("button", { name: /^Concise/ }).click();
  const input = page.getByRole("textbox", { name: "Ask a question" });
  await input.fill("What matters most?");
  await input.press("Enter");
  await expect(page.getByRole("heading", { name: "Key findings" })).toBeVisible();
  expect(state.lastQuery()?.persona).toEqual({ persona_id: "concise", intensity: 0.6 });
});

test("topbar theme toggle cycles light, dark, and system", async ({ page }) => {
  await mockWorkspace(page);
  let preferences = {
    theme: "system",
    email_notifications: true,
    default_persona_id: null,
  };
  await page.route("**/auth/profile/preferences", async route => {
    preferences = { ...preferences, ...JSON.parse(route.request().postData() || "{}") };
    return route.fulfill({ json: preferences });
  });

  const toggle = page.getByRole("button", { name: /Switch color mode/ });
  await expect(toggle).toHaveAttribute("aria-label", /currently System/);

  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-label", /currently Light/);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-label", /currently Dark/);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-label", /currently System/);
  await expect(page.locator("html")).toHaveAttribute("data-theme-preference", "system");
});

test("sidebars collapse, expand, and remember their state", async ({ page }) => {
  await mockWorkspace(page, [ready]);

  await page.getByRole("button", { name: "Hide notebooks sidebar" }).click();
  await expect(page.locator(".workspace")).toHaveClass(/is-left-collapsed/);
  await expect(page.getByRole("navigation", { name: "Your notebooks" })).toHaveCount(0);
  await page.getByRole("button", { name: "Show notebooks sidebar" }).first().click();
  await expect(page.locator(".workspace")).not.toHaveClass(/is-left-collapsed/);

  await page.getByRole("button", { name: "Hide sources sidebar" }).click();
  await expect(page.locator(".workspace")).toHaveClass(/is-right-collapsed/);
  await page.screenshot({ path: "/tmp/rag-workspace-collapsed.png", fullPage: true });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Product research" })).toBeVisible();
  await expect(page.locator(".workspace")).toHaveClass(/is-right-collapsed/);
  await page.getByRole("button", { name: "Show sources sidebar" }).first().click();
  await expect(page.locator(".workspace")).not.toHaveClass(/is-right-collapsed/);
  await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible();
});

test("profile page updates the account name", async ({ page }) => {
  let account = { id: "user", first_name: "Alex", last_name: "Morgan", email: "alex@example.com", created_at: "2025-01-15T00:00:00Z" };
  const profile = () => ({
    ...account,
    full_name: `${account.first_name} ${account.last_name}`.trim(),
    is_active: true,
    updated_at: "2025-01-15T00:00:00Z",
    last_login_at: null,
    preferences: { theme: "system", email_notifications: true, default_persona_id: null },
    stats: { total_documents: 0, total_sessions: 0, total_chunks: 0, total_queries: 0, storage_bytes: 0, documents_by_status: {} },
    documents: [],
  });
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return route.fulfill({ json: account });
    if (path.endsWith("/auth/profile/preferences")) {
      return route.fulfill({ json: JSON.parse(route.request().postData() || "{}") });
    }
    if (path.endsWith("/auth/profile")) {
      if (route.request().method() === "PATCH") {
        account = { ...account, ...JSON.parse(route.request().postData() || "{}") };
        return route.fulfill({ json: account });
      }
      return route.fulfill({ json: profile() });
    }
    if (path.endsWith("/personas")) return route.fulfill({ json: [] });
    return route.fulfill({ status: 404, json: { detail: "Not found" } });
  });

  await page.goto("/profile");
  await expect(page.getByRole("heading", { name: "Your profile" })).toBeVisible();
  await expect(page.getByText("Joined Jan 15, 2025")).toBeVisible();

  await page.getByLabel("First name").fill("Alexa");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Profile updated.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Alexa Morgan" })).toBeVisible();

  // Password management is no longer part of the profile page.
  await expect(page.getByRole("heading", { name: "Password" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Update password" })).toHaveCount(0);
  await page.screenshot({ path: "/tmp/rag-profile.png", fullPage: true });
});

for (const width of [1440, 820, 390]) {
  test(`workspace is usable without horizontal overflow at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await mockWorkspace(page, [ready]);
    await expect(page.locator(".status-processed")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole("textbox", { name: "Ask a question" }).fill("What matters most?");
    await expect(page.getByRole("button", { name: "Send question" })).toBeEnabled();
    await page.screenshot({ path: `/tmp/rag-workspace-${width}.png`, fullPage: true });
    if (width === 1440) {
      const html = await page.evaluate(() => {
        const snapshot = document.documentElement.cloneNode(true) as HTMLElement;
        snapshot.querySelectorAll("script").forEach(node => node.remove());
        return "<!DOCTYPE html>" + snapshot.outerHTML;
      });
      await writeFile("/tmp/rag-workspace-preview.html", html);
    }
  });
}
