import { access } from "node:fs/promises";
import pino from "pino";

import { AIChatClient, AuthClient } from "./clients";
import { loadConfig, resolveSessionDir, type BridgeCommand } from "./config";
import { handleInboundMessage, inboundFromBaileys, MessageDeduplicator } from "./messages";
import { PerChatQueue } from "./queue";
import { RedisRateLimiter } from "./rate-limit";
import { BaileysTransport, createWhatsAppSocket, disconnectStatusCode, shouldReconnect } from "./session";

const logger = pino({ level: process.env.LOG_LEVEL ?? "info" });
filterNoisySignalLogs();

async function main(): Promise<void> {
  const command = parseCommand(process.argv[2]);
  const config = loadConfig(command);
  const sessionDir = await resolveSessionDir(config.sessionDir, config.allowedSessionRoots);
  if (command === "login") {
    await login(sessionDir);
    return;
  }
  await start(config, sessionDir);
}

async function login(sessionDir: string): Promise<void> {
  logger.info({ session_dir: sessionDir }, "starting WhatsApp QR login");
  const socket = await createWhatsAppSocket({ sessionDir, printQR: true });
  await new Promise<void>((resolve, reject) => {
    socket.ev.on("connection.update", (update) => {
      if (update.connection === "open") {
        logger.info("WhatsApp login completed");
        resolve();
      }
      if (update.connection === "close" && !shouldReconnect(update.lastDisconnect?.error)) {
        reject(new Error("WhatsApp login closed before linking"));
      }
    });
  });
}

async function start(config: ReturnType<typeof loadConfig>, sessionDir: string): Promise<void> {
  if (config.hmacSecret === "") {
    throw new Error("HMAC_SECRET is required for the WhatsApp listener");
  }
  await requireSavedCredentials(sessionDir);
  logger.info({ session_dir: sessionDir }, "starting WhatsApp listener");
  const queue = new PerChatQueue(config.bridgeConcurrency);
  const rateLimiter = new RedisRateLimiter(config.redisURL, config.phoneRateLimitPerSecond);
  const authClient = new AuthClient(config.authURL, config.hmacSecret);
  const aiClient = new AIChatClient(config.aiChatURL, config.hmacSecret, config.aiTimeoutMs);
  let stopping = false;
  process.once("SIGINT", () => {
    stopping = true;
    void rateLimiter.close().finally(() => process.exit(0));
  });

  while (!stopping) {
    const reconnect = await runSocket(sessionDir, queue, authClient, aiClient, rateLimiter);
    if (!reconnect || stopping) {
      break;
    }
    await delay(2_000);
  }
}

async function runSocket(
  sessionDir: string,
  queue: PerChatQueue,
  authClient: AuthClient,
  aiClient: AIChatClient,
  rateLimiter: RedisRateLimiter,
): Promise<boolean> {
  const socket = await createWhatsAppSocket({ sessionDir, printQR: false });
  const transport = new BaileysTransport(socket, sessionDir);
  socket.ev.on("messages.upsert", (event) => {
    for (const raw of event.messages) {
      const inbound = inboundFromBaileys(raw);
      if (inbound === null) {
        continue;
      }
      void queue
        .run(inbound.remoteJid, async () => {
          await handleInboundMessage(inbound, {
            authClient,
            aiClient,
            rateLimiter,
            transport,
            deduplicator: globalDeduplicator,
            logger,
          });
        })
        .catch((error: unknown) => logger.error({ error: String(error) }, "message handling failed"));
    }
  });
  return new Promise<boolean>((resolve) => {
    socket.ev.on("connection.update", (update) => {
      if (update.connection === "open") {
        logger.info("WhatsApp listener connected");
      }
      if (update.connection === "close") {
        const reconnect = shouldReconnect(update.lastDisconnect?.error);
        logger.warn(
          { reconnect, status_code: disconnectStatusCode(update.lastDisconnect?.error) },
          "WhatsApp socket closed",
        );
        resolve(reconnect);
      }
    });
  });
}

async function delay(ms: number): Promise<void> {
  await new Promise<void>((resolve) => setTimeout(resolve, ms));
}

const globalDeduplicator = new MessageDeduplicator();

async function requireSavedCredentials(sessionDir: string): Promise<void> {
  try {
    await access(`${sessionDir}/creds.json`);
  } catch (error) {
    throw new Error("WhatsApp credentials not found. Run `bun run login` first.", { cause: error });
  }
}

function parseCommand(value: string | undefined): BridgeCommand {
  if (value === "login" || value === "start") {
    return value;
  }
  throw new Error("usage: bun run src/main.ts <login|start>");
}

function filterNoisySignalLogs(): void {
  const originalInfo = console.info.bind(console);
  console.info = (...args: unknown[]) => {
    const first = args[0];
    if (typeof first === "string" && first.startsWith("Closing open session")) {
      return;
    }
    if (typeof first === "string" && first.startsWith("Closing session:")) {
      return;
    }
    originalInfo(...args);
  };
}

main().catch((error: unknown) => {
  logger.error({ error: String(error) }, "WhatsApp bridge failed");
  process.exit(1);
});
