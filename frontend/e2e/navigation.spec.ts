/**
 * E2E Tests: Navigation & Page Access
 *
 * Tests that all major pages are accessible after login,
 * sidebar navigation works, and key UI elements are present.
 */

import { test, expect, login } from "./helpers";

test.describe("Dashboard & Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("dashboard loads with KPI cards", async ({ page }) => {
    // Should be on dashboard
    await page.waitForLoadState("networkidle");

    // Dashboard should have stat cards
    const statCards = page.locator(".stat-card");
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test("sidebar navigation is visible on desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.waitForLoadState("networkidle");

    // Sidebar should contain nav links
    const sidebar = page.locator("aside").first();
    await expect(sidebar).toBeVisible();
  });

  test("can navigate to leads page", async ({ page }) => {
    await page.click('a[href*="/leads"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/leads");
  });

  test("can navigate to funnel page", async ({ page }) => {
    await page.click('a[href*="/funnel"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/funnel");
  });

  test("can navigate to communications page", async ({ page }) => {
    await page.click('a[href*="/communications"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/communications");
  });

  test("can navigate to sales page", async ({ page }) => {
    await page.click('a[href*="/sales"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/sales");
  });

  test("can navigate to segments page", async ({ page }) => {
    await page.click('a[href*="/segments"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/segments");
  });

  test("can navigate to campaigns page", async ({ page }) => {
    await page.click('a[href*="/campaigns"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/campaigns");
  });

  test("can navigate to imports page", async ({ page }) => {
    await page.click('a[href*="/imports"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/imports");
  });

  test("can navigate to reports page", async ({ page }) => {
    await page.click('a[href*="/reports"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/reports");
  });

  test("can navigate to team page", async ({ page }) => {
    await page.click('a[href*="/team"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/team");
  });

  test("can navigate to users page", async ({ page }) => {
    await page.click('a[href*="/users"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/users");
  });

  test("can navigate to activity log page", async ({ page }) => {
    await page.click('a[href*="/activity"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/activity");
  });

  test("can navigate to settings page", async ({ page }) => {
    await page.click('a[href*="/settings"]');
    await page.waitForLoadState("networkidle");

    expect(page.url()).toContain("/settings");
  });
});

