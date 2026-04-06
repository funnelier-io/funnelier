/**
 * E2E Tests: Language Switching
 *
 * Tests Persian/English locale switching via sidebar toggle.
 */

import { test, expect, login } from "./helpers";

test.describe("i18n & Locale Switching", () => {
  test("can switch from Persian to English", async ({ page }) => {
    await login(page);
    await page.waitForLoadState("networkidle");


    // Find the language switcher button (has "EN" text)
    const langButton = page.locator("button", { hasText: "EN" }).first();
    await expect(langButton).toBeVisible();
    await langButton.click();

    // Wait for navigation to /en
    await page.waitForURL((url) => url.pathname.includes("/en"), { timeout: 5000 });
    expect(page.url()).toContain("/en");
  });

  test("English locale renders English text", async ({ page }) => {
    await page.goto("/en/login");
    await page.waitForLoadState("networkidle");

    // Should have English text on the login page
    const body = await page.locator("body").textContent();
    expect(body).toContain("Login");
  });

  test("Persian locale renders RTL direction", async ({ page }) => {
    await page.goto("/fa/login");
    await page.waitForLoadState("networkidle");

    // Should have dir=rtl on html
    const dir = await page.locator("html").getAttribute("dir");
    expect(dir).toBe("rtl");
  });
});

