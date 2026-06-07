import { mkdir, realpath } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, isAbsolute, resolve } from "node:path";

const DEFAULT_SESSION_DIR = "data/whatsapp/default";

export type BridgeCommand = "login" | "start";

export interface BridgeConfig {
  command: BridgeCommand;
  sessionDir: string;
  authURL: string;
  aiChatURL: string;
  redisURL: string;
  hmacSecret: string;
  phoneRateLimitPerSecond: number;
  bridgeConcurrency: number;
  aiTimeoutMs: number;
  allowedSessionRoots: string[];
}

export interface EnvSource {
  [key: string]: string | undefined;
}

export function loadConfig(command: BridgeCommand, env: EnvSource = process.env): BridgeConfig {
  const phoneRateLimitPerSecond = positiveInt(env.WHATSAPP_RATE_LIMIT_PER_SECOND, 20);
  return {
    command,
    sessionDir: env.WHATSAPP_SESSION_DIR ?? DEFAULT_SESSION_DIR,
    authURL: trimTrailingSlash(env.AUTH_SERVICE_URL ?? "http://localhost:8000"),
    aiChatURL: trimTrailingSlash(env.AI_CHAT_URL ?? "http://localhost:8012"),
    redisURL: env.REDIS_URL ?? "redis://localhost:6379/0",
    hmacSecret: env.HMAC_SECRET ?? "",
    phoneRateLimitPerSecond,
    bridgeConcurrency: positiveInt(env.WHATSAPP_BRIDGE_CONCURRENCY, 4),
    aiTimeoutMs: positiveInt(env.WHATSAPP_AI_TIMEOUT_MS, 60_000),
    allowedSessionRoots: allowedSessionRoots(env),
  };
}

export async function resolveSessionDir(path: string, roots: string[]): Promise<string> {
  const target = resolvePath(path);
  const allowedRoots = await Promise.all(roots.map((root) => ensureRealDirectory(resolvePath(root))));
  const parent = await ensureRealDirectory(dirname(target));
  const normalizedTarget = resolve(parent, target.slice(dirname(target).length + 1));
  if (!allowedRoots.some((root) => isSubpath(normalizedTarget, root))) {
    throw new Error("WhatsApp session directory must be inside an allowed application data directory");
  }
  await mkdir(normalizedTarget, { recursive: true, mode: 0o700 });
  return realpath(normalizedTarget);
}

function allowedSessionRoots(env: EnvSource): string[] {
  const configured = env.WHATSAPP_ALLOWED_SESSION_ROOTS;
  if (configured !== undefined && configured.trim() !== "") {
    return configured.split(",").map((item) => item.trim()).filter(Boolean);
  }
  return ["data/whatsapp", "apps/whatsapp-bridge/data", `${homedir()}/.khetibadi/whatsapp`];
}

async function ensureRealDirectory(path: string): Promise<string> {
  await mkdir(path, { recursive: true, mode: 0o700 });
  return realpath(path);
}

function isSubpath(path: string, root: string): boolean {
  return path === root || path.startsWith(`${root}/`);
}

function resolvePath(path: string): string {
  if (path.startsWith("~/")) {
    return resolve(homedir(), path.slice(2));
  }
  return isAbsolute(path) ? resolve(path) : resolve(process.cwd(), path);
}

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function positiveInt(value: string | undefined, fallback: number): number {
  if (value === undefined || value.trim() === "") {
    return fallback;
  }
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`expected positive integer, got ${value}`);
  }
  return parsed;
}
