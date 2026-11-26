import { writeFile } from "node:fs/promises";
import { test, expect, type Page } from "@playwright/test";

type Doc = { id: string; name: string; status: string; chunks_created: number };
async function mockWorkspace(page: Page, initial: Doc[] = []) {
  const docs = [...initial];
  let uploadFailures = 0;
  let queryFailures = 0;
  let queries = 0;
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown;
    if (path.endsWith("/auth/me")) body = { id: "user", first_name: "Alex", last_name: "Morgan", email: "alex@example.com" };
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
      if (queryFailures-- > 0) return route.fulfill({ status: 503, json: { detail: "Please try your question again." } });
      await new Promise(resolve => setTimeout(resolve, 150));
      body = { answer: "## Key findings\n\nResearch suggests **three priorities**:\n\n- Clear navigation\n- Useful feedback\n- Accessible controls", sources: [{ doc_id: "ready", doc_name: "Research notes.pdf", page: 3, excerpt: "Participants preferred clear feedback and simple navigation." }] };
    } else return route.fulfill({ status: 404, json: { detail: "Not found" } });
    await route.fulfill({ json: body });
  });
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "Product research" })).toBeVisible();
  return { docs, failUpload: () => { uploadFailures = 1; }, failQuery: () => { queryFailures = 1; }, queries: () => queries };
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
