import { expect, it } from "vitest";
import { addDays, block, bounds, dayDiff, key, split, weekOf } from "./selection";

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

it("calendar days are counted, not columns: a hidden weekend still takes its place", () => {
  expect(addDays("2027-03-05", 3)).toBe("2027-03-08");
  expect(addDays("2027-03-01", -1)).toBe("2027-02-28");
  expect(dayDiff("2027-03-05", "2027-03-08")).toBe(3);
  expect(dayDiff("2027-03-08", "2027-03-05")).toBe(-3);
});

it("a week is Monday to Sunday, whichever of its days are shown", () => {
  const shown = ["2027-02-26", "2027-03-01", "2027-03-02", "2027-03-05", "2027-03-08"];
  expect(weekOf(shown, "2027-03-02")).toEqual(["2027-03-01", "2027-03-02", "2027-03-05"]);
  expect(weekOf(shown, "2027-02-26")).toEqual(["2027-02-26"]);
});
