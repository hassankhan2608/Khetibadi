## Local beta run notes

1. Add or update the tester's WhatsApp number through normal app registration or dashboard settings.
2. Start the backend services needed by the bridge: auth, Redis, and AI chat.
3. Run `make whatsapp-login` once and scan the terminal QR code with the dedicated WhatsApp test number.
4. Run `make whatsapp-start` to begin listening for direct WhatsApp messages.
5. Send a text message from a registered number and verify the bridge marks the inbound message read, shows typing while AI chat runs, and replies in the same direct chat.
6. Send a text message from an unregistered number and verify the reply is exactly `Your number is not registered with Khetibadi. Please register first in the app.`

The bridge stores local Baileys credentials only under configured session data directories. Do not commit those files, copy them into logs, or share them between users.
