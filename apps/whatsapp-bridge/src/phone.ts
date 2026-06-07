import { parsePhoneNumberFromString } from "libphonenumber-js";

export function normalizePhone(input: string): string | null {
  const trimmed = input.trim();
  if (trimmed === "") {
    return null;
  }
  const explicit = parsePhoneNumberFromString(trimmed);
  if (explicit?.isValid() === true) {
    return explicit.number;
  }
  const indian = parsePhoneNumberFromString(trimmed, "IN");
  if (indian?.isValid() === true) {
    return indian.number;
  }
  return null;
}

export function phoneFromJid(jid: string): string | null {
  const localPart = jid.split("@")[0];
  if (localPart === undefined || localPart === "") {
    return null;
  }
  const phonePart = localPart.split(":")[0];
  return phonePart === undefined ? null : normalizePhone(phonePart.replace(/\D/g, ""));
}

export function maskPhone(phone: string): string {
  if (phone.length <= 5) {
    return "***";
  }
  return `${phone.slice(0, 3)}***${phone.slice(-2)}`;
}
