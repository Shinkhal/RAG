import { test, expect } from "@playwright/test";

test("landing page shows the product illustrations and author credit", async ({ page }) => {
  await page.route("**/api/v1/auth/me", route => route.fulfill({ status: 401, json: { detail: "Sign in to continue" } }));
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /Get instant answers/ })).toBeVisible();
  await expect(page.locator(".preview")).toBeVisible();
  await expect(page.locator(".quote-card")).toBeVisible();
  await expect(page.getByRole("heading", { name: "One workspace for every long document" })).toBeVisible();

  const credit = page.getByRole("link", { name: /Made by Shinkhal Sinha/ });
  await expect(credit).toBeVisible();
  await expect(credit).toHaveAttribute("href", "https://shinkhalsinha.in");
  await expect(credit).toHaveAttribute("target", "_blank");

  await page.screenshot({ path: "/tmp/rag-landing-1440.png", fullPage: true });
  await page.locator(".landing__hero").screenshot({ path: "/tmp/rag-landing-hero.png" });

  await page.setViewportSize({ width: 820, height: 1000 });
  await page.reload();
  await expect(page.getByRole("heading", { name: /Get instant answers/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "/tmp/rag-landing-820.png", fullPage: true });

  await page.setViewportSize({ width: 390, height: 900 });
  await page.reload();
  await expect(page.getByRole("heading", { name: /Get instant answers/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "/tmp/rag-landing-390.png", fullPage: true });
});
