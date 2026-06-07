## Why

Farmers should be able to use the same Khetibadi AI assistant from WhatsApp, not only from the dashboard. A beta WhatsApp channel lets registered users ask farm, crop, disease, market, and account-context questions from the app they already use every day.

## What Changes

- Add a WhatsApp AI assistant transport using an OpenClaw-style WhatsApp Web session powered by Baileys.
- Add two operator commands: one command links/saves a WhatsApp session by QR code, and one command starts the WhatsApp listener from the saved session.
- Gate beta access by registered phone number: if the WhatsApp sender number exists on exactly one Khetibadi user, route the message to that user's AI context; otherwise reply with a registration error.
- Reuse the existing AI chat assistant context and response pipeline so WhatsApp and dashboard chat answer from the same user data.
- Add WhatsApp-specific feedback behavior: typing/presence while processing, read receipts/blue-tick style acknowledgements when supported by WhatsApp Web, and a visible error reply for failed processing.
- Add Redis-backed rate limiting for WhatsApp inbound messages: 20 messages per second per phone number, with bridge-level safeguards to protect the AI service.
- Add normal user-account phone capture for beta testing: users enter their phone number through registration or profile/settings UI, and WhatsApp access uses that stored number.

## Capabilities

### New Capabilities

- `whatsapp-ai-assistant`: WhatsApp session linking, listener startup, phone-number beta access, AI chat routing, message feedback, and WhatsApp rate limits.

### Modified Capabilities

- `auth`: add normalized unique user phone number support and an internal lookup contract for resolving a WhatsApp sender phone number to a Khetibadi user.

## Impact

- New WhatsApp bridge/service or worker entrypoint using Node.js/TypeScript and Baileys.
- New CLI or Make targets for `whatsapp login` and `whatsapp start` flows.
- Auth service/database/dashboard changes for phone number capture, storage, normalization, uniqueness, profile updates, and internal lookup.
- AI chat integration so WhatsApp messages are processed with the same assistant context as dashboard chat.
- Redis usage for per-phone and global rate limiting.
- Docker Compose and environment examples for WhatsApp bridge runtime, session directory, and rate-limit settings.
- Security/privacy requirements for not logging WhatsApp session credentials, full message bodies, or full phone numbers.
