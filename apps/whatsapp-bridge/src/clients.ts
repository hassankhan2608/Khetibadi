import { serviceHeaders } from "./hmac";

export interface ResolvedUser {
  user_id: string;
  email: string;
  name: string;
  phone: string;
}

export type UserLookupResult =
  | { status: "found"; user: ResolvedUser }
  | { status: "not_found" }
  | { status: "duplicate" }
  | { status: "unauthorized" }
  | { status: "error" };

export interface BridgeAIResponse {
  session_id: string;
  message_id: string;
  response: string;
  status: "complete" | "incomplete";
}

interface ApiEnvelope<T> {
  data?: T;
  message?: T;
  error?: string;
}

export class AuthClient {
  constructor(
    private readonly baseURL: string,
    private readonly hmacSecret: string,
    private readonly serviceUserID = "whatsapp-bridge",
  ) {}

  async lookupByPhone(phone: string): Promise<UserLookupResult> {
    const url = `${this.baseURL}/internal/users/by-phone?phone=${encodeURIComponent(phone)}`;
    const response = await fetch(url, {
      headers: serviceHeaders(this.hmacSecret, this.serviceUserID),
    });
    if (response.status === 404) {
      return { status: "not_found" };
    }
    if (response.status === 401 || response.status === 403) {
      return { status: "unauthorized" };
    }
    if (response.status === 409) {
      return { status: "duplicate" };
    }
    if (!response.ok) {
      return { status: "error" };
    }
    const payload = await response.json() as ApiEnvelope<ResolvedUser>;
    if (payload.data === undefined) {
      return { status: "error" };
    }
    return { status: "found", user: payload.data };
  }
}

export class AIChatClient {
  constructor(
    private readonly baseURL: string,
    private readonly hmacSecret: string,
    private readonly timeoutMs: number,
  ) {}

  async sendWhatsAppMessage(input: {
    userID: string;
    accountName: string;
    text: string;
    language: string;
    externalThreadID: string;
  }): Promise<BridgeAIResponse> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(`${this.baseURL}/ai/chat/internal/bridge/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...serviceHeaders(this.hmacSecret, input.userID),
        },
        body: JSON.stringify({
          message: input.text,
          language: input.language,
          channel: "whatsapp",
          external_thread_id: input.externalThreadID,
          account_name: input.accountName,
        }),
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`ai-chat returned ${response.status}`);
      }
      const payload = await response.json() as ApiEnvelope<BridgeAIResponse>;
      if (payload.message === undefined) {
        throw new Error("ai-chat response missing message envelope");
      }
      return payload.message;
    } finally {
      clearTimeout(timeout);
    }
  }
}
