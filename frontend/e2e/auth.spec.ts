/**
 * E2E Tests: Authentication Flow
 */

import { test, expect, login, ADMIN_USER } from "./helpers";

test.describe("Authentication", () => {
  test("login page renders correctly", async ({ page }) => {
    await page.goto("/fa/login");
    await page.waitForLoadState("domcontentloaded");

    await expect(page.locator('input[type="text"]').first()).toBeVisible();
    await expect(page.locator('input[type="password"]').first()).toBeVisible();
    await expect(page.locator('button[type="submit"]').first()).toBeVisible();
  });

  test("login with valid credentials sets token and redirects", async ({ page }) => {
    await login(page);

    // After login, should have a token in localStorage
    const hasToken = await page.evaluate(() => !!localStorage.getItem("token"));
    expect(hasToken).toBe(true);

    // Should not be on login page anymore
    expect(page.url()).not.toContain("/login");
  });

  test("login with invalid credentials shows error", async ({ page }) => {
    await page.goto("/fa/login");
    await page.waitForLoadState("domcontentloaded");

    await page.locator('input[type="text"]').first().fill("wronguser");
    await page.locator('input[type="password"]').first().fill("wrongpassword");
    await page.locator('button[type="submit"]').first().click();

    // Should stay on login page
    await page.waitForTimeout(3000);
    expect(page.url()).toContain("/login");

    // Should show error text
    const errorEl = page.locator(".text-red-500, .bg-red-50");
    await expect(errorEl.first()).toBeVisible({ timeout: 5000 });
  });
});
