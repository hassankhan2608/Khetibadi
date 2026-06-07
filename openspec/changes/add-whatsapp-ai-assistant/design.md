## Context

Khetibadi already has a dashboard AI assistant backed by the `ai-chat` service, persisted chat sessions, Redis rate limiting, and HMAC-authenticated service-to-service requests. Farmers also use WhatsApp heavily, so the new channel should be a transport into the same assistant rather than a second chatbot implementation.

The requested beta behavior is phone-number gated: a WhatsApp sender is allowed only when their normalized phone number exists on exactly one Khetibadi user. Users provide that phone number through the normal registration or profile/settings flow, the same way they provide other account details; no separate operator-only test-phone seed is needed.

OpenClaw-style behavior means a QR-linked WhatsApp Web session, a long-running listener command, typing/presence indicators while the AI is working, read receipts for inbound messages when supported, and text replies sent back to the same WhatsApp chat.

## Goals / Non-Goals

**Goals:**

- Provide a WhatsApp transport for the existing Khetibadi AI assistant.
- Link a WhatsApp Web session by QR code and reuse the saved session for listener startup.
- Resolve WhatsApp direct-message senders to registered users by normalized E.164 phone number.
- Return a clear registration error when the sender phone number is not registered.
- Enforce a Redis-backed 20 messages/second per-phone rate limit before AI work starts.
- Show WhatsApp typing/presence while processing and mark inbound messages read when WhatsApp Web allows it.
- Keep phone numbers, message bodies, and WhatsApp session credentials out of logs and source control.
- Support local beta testing by registering or updating a normal user account with the tester's phone number through the application UI/API.

**Non-Goals:**

- Building a public WhatsApp Business Cloud API integration in this change.
- Supporting unregistered WhatsApp users, OTP enrollment, or phone ownership verification during the beta.
- Supporting WhatsApp groups as an AI channel by default.
- Replacing the dashboard AI chat UI or changing the LLM prompt contract beyond channel metadata.
- Guaranteeing outbound blue ticks; WhatsApp delivery/read status is controlled by WhatsApp and recipient privacy settings. The bridge can mark inbound messages as read and send replies.

## Decisions

### Use Baileys WhatsApp Web for the beta channel

Use Baileys for an OpenClaw-style QR session and listener because it matches the requested operator workflow and provides the required socket APIs: multi-file auth state, `messages.upsert`, `sendPresenceUpdate`, `readMessages`, and `sendMessage`.

Alternative considered: Meta WhatsApp Business Cloud API. It is more official for production, but it requires business setup, webhook hosting, templates for some outbound messaging, and does not match the requested QR-session flow.

### Add a dedicated WhatsApp bridge process

Create a separate bridge process or worker entrypoint instead of embedding the WhatsApp socket in `ai-chat` or `auth`. The bridge owns WhatsApp session state, inbound message filtering, rate limiting, and channel feedback. It calls internal Khetibadi services for identity and AI responses.

Alternative considered: put WhatsApp handling in `ai-chat`. That couples a long-lived external socket and QR credential lifecycle to the LLM service, making restarts and security boundaries harder.

### Store WhatsApp auth state in a configurable data directory

Store Baileys multi-file auth state under a configured directory such as `data/whatsapp/default`, mounted as a Docker volume in Compose. The login command writes credentials there; the start command refuses to run if credentials are missing or the path is unsafe. Session files are ignored by git.

Alternative considered: storing WhatsApp credentials in PostgreSQL. Files match Baileys' native auth-state shape and keep the beta implementation simpler. A future production hardening change can move secrets into a keychain or secret manager.

### Normalize phone numbers in auth and require uniqueness

Auth becomes the source of truth for user phone numbers. It stores a normalized E.164 phone number and enforces uniqueness for non-null values. The WhatsApp bridge calls an internal lookup contract that returns exactly one user ID or a not-found/duplicate result.

Alternative considered: bridge-local phone allowlist. That would not ensure WhatsApp and dashboard use the same user account data, and it would drift from the auth database.

### Capture phone numbers in the normal user flow

Registration and profile/settings flows should accept a user phone number as a normal account field. This lets a tester enter their phone number during signup or account update, then immediately use WhatsApp as that registered user.

Alternative considered: an operator-only beta seed command. The user rejected this because the test phone should be entered like normal user data, not supplied through a separate setup path.

### Route WhatsApp messages into the existing AI chat pipeline

The bridge creates or reuses a channel-specific AI chat session for the resolved user and submits the WhatsApp text to the existing assistant flow. Responses are persisted as normal chat messages with channel metadata so dashboard history and WhatsApp history can be audited consistently.

Alternative considered: directly calling Groq from the bridge. That would duplicate prompt assembly, farm/weather/market/RAG context fetching, persistence, and rate-limit behavior.

### Apply rate limits before acknowledging expensive work

The bridge checks Redis before creating sessions or invoking AI. The primary limit is 20 messages per second per normalized phone number. A lower global concurrency cap and per-conversation queue protect Groq and the `ai-chat` service from burst amplification.

Alternative considered: relying only on the existing `ai-chat` 30 messages/minute per-user limit. That is too slow to stop WhatsApp spam bursts before they consume bridge and socket resources.

### Treat WhatsApp feedback as best-effort side effects

The bridge calls `readMessages([message.key])` when accepting an inbound message, sends `sendPresenceUpdate('composing', jid)` while processing, sends `sendPresenceUpdate('paused', jid)` in a `finally` block, and replies with `sendMessage(jid, { text })`. Failures in these feedback calls are logged with redacted identifiers and must not prevent AI processing unless sending the final reply fails.

Alternative considered: tightly coupling AI processing success to every feedback API call. That would make the user experience brittle because WhatsApp Web presence and receipt features can fail transiently or be restricted by privacy settings.

## Risks / Trade-offs

- WhatsApp Web/Baileys is less official than Cloud API → keep the integration beta-gated, use a dedicated number, isolate credentials, and document a future Cloud API migration path.
- Phone number access without OTP can link the wrong account if stale phone data exists → require E.164 normalization, unique database constraint, duplicate-deny behavior, and user-visible phone update controls.
- High message bursts can overload AI dependencies → enforce per-phone Redis limits, per-chat queues, and a global bridge concurrency cap before LLM calls.
- Session credentials are sensitive → keep them in a gitignored volume/path, redact logs, and refuse unsafe credential directories.
- Read receipts/blue-tick behavior is not fully controllable → define it as best-effort marking of inbound messages as read when supported by WhatsApp Web.
- User messages may contain sensitive farm data → do not log full message bodies; store only through the existing chat persistence path with user ownership.

## Migration Plan

1. Add nullable normalized phone fields and uniqueness to auth users.
2. Add internal auth lookup by phone and registration/update support for phone numbers.
3. Add the WhatsApp bridge package/service with login and start commands.
4. Add Redis rate limiting and per-chat queue behavior.
5. Add AI chat channel session support or bridge-specific API path that reuses existing assistant logic.
6. Update dashboard registration/profile forms so a tester can enter their phone number as normal account data.
7. Add Docker Compose/env examples and gitignore rules for WhatsApp session state.
8. For beta, register or update the test user through the normal app flow with the tester's phone number.
9. Link WhatsApp by QR code and run the listener against the local stack.

Rollback is to stop the WhatsApp bridge, remove the saved WhatsApp session directory, and leave nullable auth phone columns unused. Existing dashboard auth and AI chat behavior remains unchanged.

## Open Questions

- Should dashboard registration require phone number immediately, or should phone number remain optional until WhatsApp beta is enabled?
- Should WhatsApp conversations appear in the dashboard AI chat session list by default, or behind a channel filter?
- What production secret store should replace the local Baileys credential directory after beta?
