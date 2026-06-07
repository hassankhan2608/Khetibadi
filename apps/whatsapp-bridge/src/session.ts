import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { Boom } from "@hapi/boom";
import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
  type WAMessageKey,
  type WASocket,
} from "@whiskeysockets/baileys";
import pino from "pino";
import qrcode from "qrcode-terminal";

import { phoneFromJid } from "./phone";

const baileysLogger = pino({ level: process.env.WHATSAPP_BAILEYS_LOG_LEVEL ?? "silent" });

export interface SocketOptions {
  sessionDir: string;
  printQR: boolean;
}

export async function createWhatsAppSocket(options: SocketOptions): Promise<WASocket> {
  const { state, saveCreds } = await useMultiFileAuthState(options.sessionDir);
  const { version } = await fetchLatestBaileysVersion();
  const socket = makeWASocket({
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, baileysLogger),
    },
    browser: ["khetibadi", "whatsapp-bridge", "2.0"],
    logger: baileysLogger,
    markOnlineOnConnect: false,
    printQRInTerminal: false,
    syncFullHistory: false,
    version,
  });
  socket.ev.on("creds.update", saveCreds);
  if (options.printQR) {
    socket.ev.on("connection.update", (update) => {
      if (update.qr !== undefined) {
        qrcode.generate(update.qr, { small: true });
      }
      if (update.connection === "open") {
        console.info("WhatsApp linked successfully. You can now run the listener.");
      }
    });
  }
  return socket;
}

export function shouldReconnect(error: unknown): boolean {
  const statusCode = disconnectStatusCode(error);
  return statusCode !== DisconnectReason.loggedOut;
}

export function disconnectStatusCode(error: unknown): number | undefined {
  return error instanceof Boom ? error.output.statusCode : undefined;
}

export class BaileysTransport {
  constructor(
    private readonly socket: WASocket,
    private readonly sessionDir: string,
  ) {}

  async sendText(jid: string, text: string): Promise<void> {
    await this.socket.sendMessage(jid, { text });
  }

  async readMessage(key: WAMessageKey): Promise<void> {
    await this.socket.readMessages([key]);
  }

  async sendPresence(jid: string, state: "available" | "composing" | "paused"): Promise<void> {
    await this.socket.sendPresenceUpdate(state, jid);
  }

  async resolvePhone(jid: string): Promise<string | null> {
    const phone = phoneFromJid(jid);
    if (phone !== null) {
      return phone;
    }
    if (!jid.endsWith("@lid") && !jid.endsWith("@hosted.lid")) {
      return null;
    }
    const mappedJid = await this.socket.signalRepository.lidMapping.getPNForLID(jid);
    if (mappedJid !== null) {
      return phoneFromJid(mappedJid);
    }
    const mappedPhone = await this.resolvePhoneFromSavedLIDMapping(jid);
    return mappedPhone === null ? null : phoneFromJid(`${mappedPhone}@s.whatsapp.net`);
  }

  private async resolvePhoneFromSavedLIDMapping(jid: string): Promise<string | null> {
    const lid = jid.split("@")[0];
    if (lid === undefined || lid === "") {
      return null;
    }
    try {
      const raw = await readFile(join(this.sessionDir, `lid-mapping-${lid}_reverse.json`), "utf8");
      const value: unknown = JSON.parse(raw);
      return typeof value === "string" ? value : null;
    } catch {
      return null;
    }
  }
}
