## 1. Auth Phone Support

- [x] 1.1 Add a database migration for nullable normalized user phone numbers with a unique non-null constraint.
- [x] 1.2 Update auth domain, repository, and SQL accessors to read/write normalized phone numbers.
- [x] 1.3 Add phone-number normalization and validation utilities with unit tests for E.164 output and invalid input.
- [x] 1.4 Update registration request handling to accept optional phone number and return `phone_taken` on duplicate normalized phone numbers.
- [x] 1.5 Add an internal service-authenticated phone lookup endpoint or repository-backed contract for resolving normalized phone number to user ID.
- [x] 1.6 Add authenticated account-profile phone update support with duplicate and invalid phone handling.
- [x] 1.7 Add auth tests for registration with phone, phone profile update, duplicate phone, invalid phone, phone lookup success, phone lookup not found, and unauthorized lookup.

## 2. AI Chat Channel Reuse

- [x] 2.1 Add channel metadata support for AI chat sessions and messages without changing existing dashboard behavior.
- [x] 2.2 Add or expose an internal bridge-safe API for sending a message through the existing AI assistant pipeline for a resolved user.
- [x] 2.3 Ensure WhatsApp-channel messages reuse farm, weather, market, RAG, and chat-history context from the existing AI chat service.
- [x] 2.4 Add tests proving WhatsApp-channel submissions persist user and assistant messages under the resolved user.
- [x] 2.5 Add timeout and degraded-error handling for bridge-originated AI requests.

## 3. WhatsApp Bridge Foundation

- [x] 3.1 Create a WhatsApp bridge package or service entrypoint using TypeScript and Baileys.
- [x] 3.2 Add dependencies for Baileys, QR rendering, phone parsing, Redis, and internal HTTP clients.
- [x] 3.3 Implement configuration loading for session directory, Redis URL, auth/AI service URLs, rate limits, and bridge concurrency.
- [x] 3.4 Add a safe session-directory resolver that rejects paths outside allowed application data directories.
- [x] 3.5 Add gitignore rules for WhatsApp session credential directories.

## 4. WhatsApp Login Command

- [x] 4.1 Implement the WhatsApp login command that creates a Baileys socket and renders the QR code for scanning.
- [x] 4.2 Persist Baileys multi-file auth state and save credential updates reliably.
- [x] 4.3 Fail clearly when the configured credential path is unsafe or not writable.
- [x] 4.4 Add tests for session path validation and login configuration handling.

## 5. WhatsApp Listener and Message Handling

- [x] 5.1 Implement the WhatsApp listener command that starts only when saved credentials exist.
- [x] 5.2 Subscribe to inbound direct-message events and ignore status, broadcast, group, from-self, and empty duplicate events by default.
- [x] 5.3 Normalize sender WhatsApp JIDs to E.164 phone numbers before auth lookup.
- [x] 5.4 Implement registered-phone gating with unregistered, duplicate, and unauthorized lookup handling.
- [x] 5.5 Implement unsupported-message guidance for empty or non-text-only messages.
- [x] 5.6 Add message de-duplication by WhatsApp message key to avoid double processing.
- [x] 5.7 Add unit tests for accepted, unregistered, duplicate, unsupported, and duplicate-message flows.

## 6. WhatsApp Feedback and Rate Limits

- [x] 6.1 Implement Redis per-phone rate limiting at 20 messages per second before AI work begins.
- [x] 6.2 Add bridge-wide concurrency and per-chat queue safeguards.
- [x] 6.3 Send read receipts for accepted inbound messages with best-effort failure handling.
- [x] 6.4 Send composing presence while AI processing is active and paused presence in all terminal paths.
- [x] 6.5 Send final assistant, rate-limit, registration, unsupported-message, and temporary-failure replies to the same WhatsApp direct chat.
- [x] 6.6 Add tests for rate-limit allow/block behavior and best-effort feedback failures.

## 7. Normal Phone Entry Flow

- [x] 7.1 Update dashboard registration UI and validation to accept a normal user phone-number field.
- [x] 7.2 Update dashboard account settings/profile UI so existing users can add or change their phone number.
- [x] 7.3 Show duplicate-phone and invalid-phone validation errors clearly in registration and settings flows.
- [x] 7.4 Add frontend tests for registration with phone and account-settings phone update.

## 8. Runtime Integration

- [x] 8.1 Add Docker Compose configuration for the WhatsApp bridge with a persistent session volume.
- [x] 8.2 Add Make targets or package scripts for WhatsApp login and WhatsApp listener start.
- [x] 8.3 Add health/readiness logging for WhatsApp bridge startup without exposing credentials or full phone numbers.
- [x] 8.4 Document local beta run steps in project docs or change notes.

## 9. Verification

- [x] 9.1 Run auth unit and integration tests for phone registration and lookup.
- [x] 9.2 Run AI chat tests proving existing dashboard chat behavior remains unchanged.
- [x] 9.3 Run WhatsApp bridge unit tests for login config, sender gating, rate limiting, feedback calls, and reply routing.
- [x] 9.4 Run `bun run lint`, `bun run type-check`, and bridge package tests.
- [x] 9.5 Run `make go-test`, `make py-test`, and relevant service builds.
- [ ] 9.6 Perform a local beta smoke test: register or update a normal user with the tester's phone number through the app, QR-link WhatsApp, send a registered-number message, verify typing/read feedback and AI reply, then send an unregistered-number message and verify the registration error.
