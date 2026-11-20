import { describe, expect, it } from "vitest";
import { DNS_FILTERS, changesOf } from "./policy-editor";

describe("filtering DNS", () => {
  it("offers exactly the levels the backend accepts", () => {
    expect(DNS_FILTERS.map((f) => f.value)).toEqual(["off", "security", "family"]);
  });

  it("shows in an exception's summary only when the exception sets it", () => {
    expect(changesOf({ dns_filter: "family" })).toContain("Filtering DNS");
    expect(changesOf({ dns_filter: "off" })).toContain("Filtering DNS");
    expect(changesOf({ dns_filter: null })).not.toContain("Filtering DNS");
    expect(changesOf({})).toEqual([]);
  });
});
