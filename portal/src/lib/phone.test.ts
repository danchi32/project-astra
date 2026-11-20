import { describe, it, expect } from "vitest";
import { normalizePhone, phoneWithCountry } from "./phone";
import { COUNTRIES } from "./countries";

describe("normalizePhone", () => {
  it.each([
    ["+91 85954 92500", "+918595492500"],
    ["0091-85954-92500", "+918595492500"],
    ["+1 (415) 555-0132", "+14155550132"],
  ])("accepts %s", (raw, stored) => {
    expect(normalizePhone(raw)).toBe(stored);
  });

  it.each(["85954 92500", "+0 85954 92500", "+91 8595 4925 0012 34", "+12345", ""])(
    "rejects %j",
    (raw) => {
      expect(normalizePhone(raw)).toBeNull();
    },
  );
});

describe("phoneWithCountry", () => {
  it.each([
    ["91", "85954 92500", "+918595492500"],
    ["44", "020 7946 0958", "+442079460958"], // trunk 0 dropped
    ["1", "(415) 555-0132", "+14155550132"],
    ["91", "+1 415 555 0132", "+14155550132"], // a typed + wins over the picker
    ["91", "0091 85954 92500", "+918595492500"],
  ])("+%s %s -> %s", (dial, number, stored) => {
    expect(phoneWithCountry(dial, number)).toBe(stored);
  });

  it.each([["91", ""], ["91", "123"], ["91", "85954 9250O"]])("rejects +%s %j", (dial, number) => {
    expect(phoneWithCountry(dial, number)).toBeNull();
  });
});

describe("COUNTRIES", () => {
  it("parses the table: India at +91, a shared code kept per country, no duplicates", () => {
    expect(COUNTRIES.find((c) => c.iso === "IN")).toEqual({ iso: "IN", name: "India", dial: "91" });
    expect(COUNTRIES.find((c) => c.iso === "CA")?.dial).toBe("1");
    expect(COUNTRIES.find((c) => c.iso === "AG")?.name).toBe("Antigua and Barbuda");
    expect(new Set(COUNTRIES.map((c) => c.iso)).size).toBe(COUNTRIES.length);
  });

  it("stays alphabetical, so the open list is scannable", () => {
    const names = COUNTRIES.map((c) => c.name);
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, "en")));
  });
});
