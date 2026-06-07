import { describe, expect, test } from "bun:test";
import type { WAMessageKey } from "@whiskeysockets/baileys";

import type { BridgeAIResponse, UserLookupResult } from "../src/clients";
import {
  handleInboundMessage,
  MessageDeduplicator,
  UNREGISTERED_REPLY,
  type InboundMessage,
  type Logger,
  type WhatsAppTransport,
} from "../src/messages";
import { phoneFromJid } from "../src/phone";
import { MemoryRateLimiter, type RateLimiter } from "../src/rate-limit";

const key: WAMessageKey = {
  id: "msg-1",
  remoteJid: "919999999999@s.whatsapp.net",
  fromMe: false,
};

const logger: Logger = {
  info: () => {},
  warn: () => {},
  error: () => {},
};

describe("phoneFromJid", () => {
  test("normalizes direct WhatsApp JIDs to E.164", () => {
    expect(phoneFromJid("919876543210@s.whatsapp.net")).toBe("+919876543210");
    expect(phoneFromJid("919876543210:0@s.whatsapp.net")).toBe("+919876543210");
    expect(phoneFromJid("919876543210")).toBe("+919876543210");
  });
});

describe("handleInboundMessage", () => {
  test("sends unregistered reply when phone lookup misses", async () => {
    const transport = new FakeTransport();

    await handleInboundMessage(message(), deps({ transport, lookup: { status: "not_found" } }));

    expect(transport.sent).toEqual([UNREGISTERED_REPLY]);
  });

  test("sends unsupported guidance for registered non-text message", async () => {
    const transport = new FakeTransport();

    await handleInboundMessage(
      message({ text: null }),
      deps({ transport, lookup: foundUser() }),
    );

    expect(transport.sent).toEqual(["Please send a text message to chat with Khetibadi AI on WhatsApp."]);
  });

  test("processes registered text with read receipt, typing, AI reply, and paused presence", async () => {
    const transport = new FakeTransport();
    const aiClient = new FakeAIClient();

    await handleInboundMessage(message(), deps({ transport, lookup: foundUser(), aiClient }));

    expect(transport.reads).toBe(1);
    expect(transport.presence).toEqual(["available", "composing", "paused"]);
    expect(transport.sent).toEqual(["AI answer"]);
    expect(aiClient.lastAccountName).toBe("Farmer");
  });

  test("deduplicates repeated message ids", async () => {
    const transport = new FakeTransport();
    const deduplicator = new MessageDeduplicator();
    const handlerDeps = deps({ transport, lookup: foundUser(), deduplicator });

    await handleInboundMessage(message(), handlerDeps);
    await handleInboundMessage(message(), handlerDeps);

    expect(transport.sent).toEqual(["AI answer"]);
  });

  test("rate limits before AI work", async () => {
    const transport = new FakeTransport();
    const aiClient = new FakeAIClient();
    const rateLimiter = new MemoryRateLimiter(0);

    await handleInboundMessage(
      message(),
      deps({ transport, lookup: foundUser(), aiClient, rateLimiter }),
    );

    expect(aiClient.calls).toBe(0);
    expect(transport.sent).toEqual(["You are sending messages too quickly. Please try again in a moment."]);
  });

  test("best-effort feedback failures do not prevent final reply", async () => {
    const transport = new FakeTransport({ failFeedback: true });

    await handleInboundMessage(message(), deps({ transport, lookup: foundUser() }));

    expect(transport.sent).toEqual(["AI answer"]);
  });
});

function deps(input: {
  transport: WhatsAppTransport;
  lookup: UserLookupResult;
  aiClient?: FakeAIClient;
  rateLimiter?: RateLimiter;
  deduplicator?: MessageDeduplicator;
}) {
  return {
    authClient: new FakeAuthClient(input.lookup),
    aiClient: input.aiClient ?? new FakeAIClient(),
    rateLimiter: input.rateLimiter ?? new MemoryRateLimiter(20),
    transport: input.transport,
    deduplicator: input.deduplicator ?? new MessageDeduplicator(),
    logger,
  };
}

function message(input: Partial<InboundMessage> = {}): InboundMessage {
  return {
    id: "msg-1",
    remoteJid: "919999999999@s.whatsapp.net",
    fromMe: false,
    text: "What should I do today?",
    key,
    ...input,
  };
}

function foundUser(): UserLookupResult {
  return {
    status: "found",
    user: {
      user_id: "user-1",
      email: "farmer@example.com",
      name: "Farmer",
      phone: "+919999999999",
    },
  };
}

class FakeAuthClient {
  constructor(private readonly result: UserLookupResult) {}

  async lookupByPhone(): Promise<UserLookupResult> {
    return this.result;
  }
}

class FakeAIClient {
  calls = 0;
  lastAccountName: string | null = null;

  async sendWhatsAppMessage(input: { accountName: string }): Promise<BridgeAIResponse> {
    this.calls += 1;
    this.lastAccountName = input.accountName;
    return {
      session_id: "session-1",
      message_id: "assistant-1",
      response: "AI answer",
      status: "complete",
    };
  }
}

class FakeTransport implements WhatsAppTransport {
  sent: string[] = [];
  presence: Array<"available" | "composing" | "paused"> = [];
  reads = 0;

  constructor(private readonly options: { failFeedback?: boolean } = {}) {}

  async sendText(_: string, text: string): Promise<void> {
    this.sent.push(text);
  }

  async readMessage(): Promise<void> {
    this.reads += 1;
    if (this.options.failFeedback === true) {
      throw new Error("read failed");
    }
  }

  async sendPresence(_: string, state: "available" | "composing" | "paused"): Promise<void> {
    this.presence.push(state);
    if (this.options.failFeedback === true) {
      throw new Error("presence failed");
    }
  }

  async resolvePhone(jid: string): Promise<string | null> {
    return phoneFromJid(jid);
  }
}
