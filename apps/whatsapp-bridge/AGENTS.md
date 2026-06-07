# AGENTS.md — apps/whatsapp-bridge

> TypeScript/Bun WhatsApp bridge. Reads WhatsApp Web messages via Baileys and forwards
> registered beta users to the existing AI chat service.

## Service Responsibility

Owns the WhatsApp transport only:
- QR login and Baileys multi-file session persistence.
- Registered-phone gating through auth `/internal/users/by-phone`.
- Per-phone Redis rate limiting before AI work.
- Typing/read-receipt best-effort feedback.
- Forwarding accepted text messages to ai-chat internal bridge API.

It does **not** own user records, chat memory, or LLM logic.

## Privacy Invariants

- Never commit WhatsApp credentials or session files.
- Never log message bodies, full phone numbers, session credentials, or HMAC secrets.
- Log masked phone numbers only.

## Dev Commands

```bash
bun run --cwd apps/whatsapp-bridge login
bun run --cwd apps/whatsapp-bridge start
bun run --cwd apps/whatsapp-bridge test
bun run --cwd apps/whatsapp-bridge type-check
```
