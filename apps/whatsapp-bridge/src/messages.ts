import type { WAMessage, WAMessageKey } from "@whiskeysockets/baileys";

import type { BridgeAIResponse, UserLookupResult } from "./clients";
import { maskPhone, phoneFromJid } from "./phone";
import type { RateLimiter } from "./rate-limit";

export const UNREGISTERED_REPLY =
  "Your number is not registered with Khetibadi. Please register first in the app.";

const RATE_LIMIT_REPLY = "You are sending messages too quickly. Please try again in a moment.";
const UNSUPPORTED_REPLY = "Please send a text message to chat with Khetibadi AI on WhatsApp.";
const TEMPORARY_FAILURE_REPLY =
  "Khetibadi AI is temporarily unavailable on WhatsApp. Please try again shortly.";

export interface Logger {
  info(data: Record<string, unknown>, message: string): void;
  warn(data: Record<string, unknown>, message: string): void;
  error(data: Record<string, unknown>, message: string): void;
}

export interface WhatsAppTransport {
  sendText(jid: string, text: string): Promise<void>;
  readMessage(key: WAMessageKey): Promise<void>;
  sendPresence(jid: string, state: "available" | "composing" | "paused"): Promise<void>;
  resolvePhone(jid: string): Promise<string | null>;
}

export interface UserLookupClient {
  lookupByPhone(phone: string): Promise<UserLookupResult>;
}

export interface AssistantClient {
  sendWhatsAppMessage(input: {
    userID: string;
    accountName: string;
    text: string;
    language: string;
    externalThreadID: string;
  }): Promise<BridgeAIResponse>;
}

export interface InboundMessage {
  id: string;
  remoteJid: string;
  fromMe: boolean;
  text: string | null;
  key: WAMessageKey;
}

export class MessageDeduplicator {
  private readonly seen = new Set<string>();
  private readonly order: string[] = [];

  constructor(private readonly maxEntries = 2000) {}

  accept(id: string): boolean {
    if (this.seen.has(id)) {
      return false;
    }
    this.seen.add(id);
    this.order.push(id);
    if (this.order.length > this.maxEntries) {
      const stale = this.order.shift();
      if (stale !== undefined) {
        this.seen.delete(stale);
      }
    }
    return true;
  }
}

export interface MessageHandlerDeps {
  authClient: UserLookupClient;
  aiClient: AssistantClient;
  rateLimiter: RateLimiter;
  transport: WhatsAppTransport;
  deduplicator: MessageDeduplicator;
  logger: Logger;
}

export async function handleInboundMessage(
  message: InboundMessage,
  deps: MessageHandlerDeps,
): Promise<void> {
  if (shouldIgnore(message)) {
    return;
  }
  if (!deps.deduplicator.accept(message.id)) {
    return;
  }
  deps.logger.info({ jid_server: jidServer(message.remoteJid) }, "whatsapp message received");
  await bestEffort(() => deps.transport.readMessage(message.key), deps.logger, "read receipt failed");
  const phone = await deps.transport.resolvePhone(message.remoteJid);
  if (phone === null) {
    deps.logger.warn({ jid_server: jidServer(message.remoteJid) }, "unable to normalize WhatsApp sender");
    await deps.transport.sendText(message.remoteJid, TEMPORARY_FAILURE_REPLY);
    return;
  }
  deps.logger.info({ phone: maskPhone(phone) }, "whatsapp sender resolved");
  const lookup = await deps.authClient.lookupByPhone(phone);
  deps.logger.info({ phone: maskPhone(phone), status: lookup.status }, "whatsapp phone lookup completed");
  if (await replyForDeniedLookup(lookup, message.remoteJid, deps, phone)) {
    return;
  }
  if (message.text === null || message.text.trim() === "") {
    await deps.transport.sendText(message.remoteJid, UNSUPPORTED_REPLY);
    return;
  }
  if (!await deps.rateLimiter.allow(phone)) {
    await deps.transport.sendText(message.remoteJid, RATE_LIMIT_REPLY);
    return;
  }
  const user = lookup.status === "found" ? lookup.user : null;
  if (user === null) {
    await deps.transport.sendText(message.remoteJid, TEMPORARY_FAILURE_REPLY);
    return;
  }
  await bestEffort(
    () => deps.transport.sendPresence(message.remoteJid, "available"),
    deps.logger,
    "available presence failed",
  );
  await bestEffort(
    () => deps.transport.sendPresence(message.remoteJid, "composing"),
    deps.logger,
    "composing presence failed",
  );
  try {
    const response = await deps.aiClient.sendWhatsAppMessage({
      userID: user.user_id,
      accountName: user.name,
      text: message.text.trim(),
      language: "en",
      externalThreadID: message.remoteJid,
    });
    await deps.transport.sendText(message.remoteJid, response.response);
    deps.logger.info({ phone: maskPhone(phone) }, "whatsapp message answered");
  } catch (error) {
    deps.logger.warn({ error: String(error), phone: maskPhone(phone) }, "AI bridge request failed");
    await deps.transport.sendText(message.remoteJid, TEMPORARY_FAILURE_REPLY);
  } finally {
    await bestEffort(
      () => deps.transport.sendPresence(message.remoteJid, "paused"),
      deps.logger,
      "paused presence failed",
    );
  }
}

function jidServer(jid: string): string {
  return jid.split("@")[1] ?? "unknown";
}

export function inboundFromBaileys(message: WAMessage): InboundMessage | null {
  const remoteJid = message.key.remoteJid;
  const id = message.key.id;
  if (remoteJid === undefined || remoteJid === null || id === undefined || id === null) {
    return null;
  }
  return {
    id,
    remoteJid,
    fromMe: message.key.fromMe === true,
    text: textFromMessage(message),
    key: message.key,
  };
}

function shouldIgnore(message: InboundMessage): boolean {
  return (
    message.fromMe
    || message.remoteJid === "status@broadcast"
    || message.remoteJid.endsWith("@g.us")
    || message.remoteJid.endsWith("@broadcast")
  );
}

async function replyForDeniedLookup(
  lookup: UserLookupResult,
  jid: string,
  deps: MessageHandlerDeps,
  phone: string,
): Promise<boolean> {
  switch (lookup.status) {
    case "found":
      return false;
    case "not_found":
      await deps.transport.sendText(jid, UNREGISTERED_REPLY);
      return true;
    case "duplicate":
      deps.logger.warn({ phone: maskPhone(phone) }, "duplicate registered phone denied");
      await deps.transport.sendText(jid, TEMPORARY_FAILURE_REPLY);
      return true;
    case "unauthorized":
      deps.logger.error({}, "auth lookup unauthorized");
      await deps.transport.sendText(jid, TEMPORARY_FAILURE_REPLY);
      return true;
    case "error":
      await deps.transport.sendText(jid, TEMPORARY_FAILURE_REPLY);
      return true;
  }
  return true;
}

async function bestEffort(
  action: () => Promise<void>,
  logger: Logger,
  message: string,
): Promise<void> {
  try {
    await action();
  } catch (error) {
    logger.warn({ error: String(error) }, message);
  }
}

function textFromMessage(message: WAMessage): string | null {
  const content = message.message;
  if (content?.conversation !== undefined) {
    return content.conversation;
  }
  if (content?.extendedTextMessage?.text !== undefined) {
    return content.extendedTextMessage.text;
  }
  return null;
}
