import { expect, test, type Page } from "@playwright/test";
import { writeFile } from "node:fs/promises";
import { deflateSync } from "node:zlib";

const PASSWORD = "Password1";

test.describe("Khetibadi dashboard end-to-end", () => {
  test("covers auth, farms, advisory, disease scan, market, AI, settings, and mobile nav", async ({ page }, testInfo) => {
    const consoleIssues: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error" || message.type() === "warning") {
        consoleIssues.push(`${message.type()}: ${message.text()}`);
      }
    });
    page.on("pageerror", (error) => {
      consoleIssues.push(`pageerror: ${error.message}`);
    });
    page.on("requestfailed", (request) => {
      consoleIssues.push(`requestfailed: ${request.method()} ${request.url()} ${request.failure()?.errorText ?? "unknown"}`);
    });
    page.on("response", (response) => {
      if (response.status() >= 500) {
        consoleIssues.push(`response: ${response.status()} ${response.url()}`);
      }
    });

    const runID = Date.now().toString().slice(-8).padStart(8, "0");
    const email = `frontend-e2e-${runID}@khetibadi.local`;
    const registrationPhone = `+9198${runID}`;
    const updatedPhone = `+9197${runID}`;
    await register(page, email, registrationPhone);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(
      page.getByRole("heading", { name: "E2E Farmer", exact: true }),
    ).toBeVisible();

    await page.getByRole("button", { name: /logout/i }).click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByPlaceholder("you@example.com")).toHaveValue("");

    await login(page, email);
    await page.goto("/dashboard");
    await expect(page.getByText(/Khetibadi overview/i)).toBeVisible();

    await page.getByRole("link", { name: /farms/i }).click();
    await page.getByPlaceholder("North field").fill("E2E North Field");
    await page.getByRole("button", { name: /create farm/i }).click();
    await expect(page.getByText(/E2E North Field/i)).toBeVisible();
    await expectActiveNav(page, "Farms");

    await page.getByRole("link", { name: /crop advisor/i }).click();
    await page.getByRole("button", { name: /run advisory/i }).click();
    await expect(page.getByText(/Crop recommendation/i)).toBeVisible();
    await expect(page.getByText(/Yield forecast/i)).toBeVisible();
    await expect(page.getByText(/Nitrogen/i)).toBeVisible();
    await expect(page.getByText(/Phosphorus/i)).toBeVisible();
    await expect(page.getByText(/Potassium/i)).toBeVisible();

    await page.getByRole("link", { name: /disease scan/i }).click();
    const leafPath = testInfo.outputPath("leaf.png");
    await writeFile(leafPath, createPng(128, 128, [54, 120, 58]));
    await page.locator('input[type="file"]').setInputFiles(leafPath);
    await expect(page.getByText(/Selected leaf\.png/i)).toBeVisible();
    await page.getByRole("button", { name: /scan plant/i }).click();
    await expect(page.getByText(/confidence/i)).toBeVisible({ timeout: 90_000 });

    await page.getByRole("link", { name: /^market$/i }).click();
    await expect(page.getByText(/Market prices/i)).toBeVisible();
    await page.getByRole("button", { name: /save alert/i }).click();
    await expect(page.getByText(/above ₹/i)).toBeVisible();
    await expectActiveNav(page, "Market");

    await page.getByRole("link", { name: /assistant/i }).click();
    await page.getByRole("button", { name: /new chat/i }).click();
    await page.getByRole("textbox", { name: /ask about irrigation/i }).fill("Use my farm and market data. Should I irrigate today? Direct answer.");
    await page.getByRole("button", { name: /send message/i }).click();
    await expect(page.getByText(/assistant:/i)).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText(/event: token|data: \{/i)).toHaveCount(0);

    await page.getByRole("link", { name: /settings/i }).click();
    const settingsPhone = page.getByLabel(/whatsapp phone number/i);
    await expect(settingsPhone).toHaveValue(registrationPhone);
    await settingsPhone.fill(updatedPhone);
    await page.getByRole("button", { name: /save whatsapp number/i }).click();
    await expect(page.getByText(/WhatsApp phone updated/i)).toBeVisible();
    await expect(settingsPhone).toHaveValue(updatedPhone);
    await expect(page.getByText(/Public API origin/i)).toBeVisible();

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/dashboard/ai-assistant");
    await expect(page.getByRole("main")).toBeVisible();
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    expect(bodyWidth).toBeLessThanOrEqual(410);
    await expectActiveNav(page, "Assistant");

    expect(consoleIssues).toEqual([]);
  });
});

async function register(page: Page, email: string, phone: string): Promise<void> {
  await page.goto("/register");
  await page.getByRole("textbox", { name: /name/i }).fill("E2E Farmer");
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByPlaceholder("+91 98765 43210").fill(phone);
  await page.getByPlaceholder(/at least 8 chars/i).fill(PASSWORD);
  await page.getByRole("button", { name: /create account/i }).click();
}

async function login(page: Page, email: string): Promise<void> {
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByPlaceholder("Enter your password").fill(PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

async function expectActiveNav(page: Page, label: string): Promise<void> {
  const link = page.getByRole("link", { name: new RegExp(label, "i") }).first();
  await expect(link).toBeVisible();
  await expect(link).toHaveClass(/bg-\[#f7eddc\]|bg-\[#fffaf0\]/);
}

function createPng(width: number, height: number, rgb: [number, number, number]): Uint8Array {
  const stride = width * 3 + 1;
  const raw = Buffer.alloc(stride * height);
  for (let y = 0; y < height; y += 1) {
    raw[y * stride] = 0;
    for (let x = 0; x < width; x += 1) {
      const offset = y * stride + 1 + x * 3;
      raw[offset] = rgb[0];
      raw[offset + 1] = rgb[1];
      raw[offset + 2] = rgb[2];
    }
  }
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    pngChunk("IHDR", Buffer.concat([uint32(width), uint32(height), Buffer.from([8, 2, 0, 0, 0])])),
    pngChunk("IDAT", deflateSync(raw)),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
}

function pngChunk(type: string, data: Buffer): Buffer {
  const typeBuffer = Buffer.from(type, "ascii");
  const body = Buffer.concat([typeBuffer, data]);
  return Buffer.concat([uint32(data.length), body, uint32(crc32(body))]);
}

function uint32(value: number): Buffer {
  const buffer = Buffer.alloc(4);
  buffer.writeUInt32BE(value >>> 0, 0);
  return buffer;
}

function crc32(buffer: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let index = 0; index < 8; index += 1) {
      crc = (crc & 1) === 1 ? (crc >>> 1) ^ 0xedb88320 : crc >>> 1;
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}
