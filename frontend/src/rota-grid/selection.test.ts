import { expect, it } from "vitest";
import { block, bounds, key, split } from "./selection";

const people = [1, 2, 3];
const days = ["2027-03-01", "2027-03-02", "2027-03-03"];

it("keys split back into person and date", () => {
  expect(split(key(12, "2027-03-01"))).toEqual([12, "2027-03-01"]);
});

it("a block is every cell between two corners, whichever order", () => {
  const sel = block(people, days, key(3, "2027-03-03"), key(1, "2027-03-02"));
  expect([...sel].sort()).toEqual(["1:2027-03-02", "1:2027-03-03", "2:2027-03-02", "2:2027-03-03", "3:2027-03-02", "3:2027-03-03"]);
});

it("bounds give the row and day extents", () => {
  const sel = new Set([key(2, "2027-03-01"), key(3, "2027-03-03")]);
  expect(bounds(sel, people, days)).toEqual({ r0: 1, r1: 2, d0: 0, d1: 2 });
  expect(bounds(new Set(), people, days)).toBeNull();
});
