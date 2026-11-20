/**
 * "+91 85954 92500" / "0091-85954-92500" -> "+918595492500", or null if it isn't a
 * number with a country code. Same rule as the backend's `normalize_phone`, which is the
 * one that decides; this one only saves a round trip.
 */
export function normalizePhone(value: string): string | null {
  let phone = value.replace(/[\s\-.()]/g, "");
  if (phone.startsWith("00")) phone = "+" + phone.slice(2);
  return /^\+[1-9]\d{6,14}$/.test(phone) ? phone : null;
}

/**
 * The picked country's dial code + the number as typed. A leading trunk 0 is dropped
 * ("020 7946 0958" in the UK is +44 20 7946 0958). A number typed with its own + or 00
 * wins over the picker, so pasting a full international number still works.
 */
export function phoneWithCountry(dial: string, number: string): string | null {
  const typed = number.trim();
  if (typed.startsWith("+") || typed.startsWith("00")) return normalizePhone(typed);
  return normalizePhone(`+${dial}${typed.replace(/^[\s0]+/, "")}`);
}
