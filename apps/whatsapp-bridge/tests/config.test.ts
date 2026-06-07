import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, test } from "bun:test";

import { loadConfig, resolveSessionDir } from "../src/config";

describe("loadConfig", () => {
  test("loads listener defaults and numeric overrides", () => {
    const config = loadConfig("start", {
      HMAC_SECRET: "secret",
      WHATSAPP_RATE_LIMIT_PER_SECOND: "20",
      WHATSAPP_BRIDGE_CONCURRENCY: "2",
      WHATSAPP_AI_TIMEOUT_MS: "5000",
    });

    expect(config.command).toBe("start");
    expect(config.phoneRateLimitPerSecond).toBe(20);
    expect(config.bridgeConcurrency).toBe(2);
    expect(config.aiTimeoutMs).toBe(5000);
  });
});

describe("resolveSessionDir", () => {
  test("allows session paths inside configured roots", async () => {
    const root = await mkdtemp(join(tmpdir(), "khetibadi-wa-root-"));

    const sessionDir = await resolveSessionDir(join(root, "default"), [root]);

    expect(sessionDir.endsWith("default")).toBe(true);
  });

  test("rejects session paths outside configured roots", async () => {
    const root = await mkdtemp(join(tmpdir(), "khetibadi-wa-root-"));
    const outside = await mkdtemp(join(tmpdir(), "khetibadi-wa-outside-"));

    await expect(resolveSessionDir(join(outside, "default"), [root])).rejects.toThrow(
      "allowed application data directory",
    );
  });
});
