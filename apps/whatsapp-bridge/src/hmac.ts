import { createHmac } from "node:crypto";

export function serviceHeaders(secret: string, userID: string): Record<string, string> {
  const timestamp = Math.floor(Date.now() / 1000).toString();
  return {
    "X-User-ID": userID,
    "X-Timestamp": timestamp,
    "X-HMAC-Signature": createHmac("sha256", secret)
      .update(`${userID}:${timestamp}`)
      .digest("hex"),
  };
}
