import { expect, it } from "vitest";
import { fromText, toBlock, toTSV } from "./clipboard";
import { key } from "./selection";
import type { EntryJson } from "./types";

const departments = [{ id: 1, name: "Reception PMC", colour: "#2F6FB3" }];
const shift = (id: number, text = ""): EntryJson => ({
  id, kind: "shift", start: "08:00", finish: "12:00", break_minutes: 0, department: 1, department_name: "Reception PMC",
  department_colour: "#2F6FB3", text, overtime: "", wfh: false, appearance: {}, hours: 240, line: "08:00-12:00 Reception PMC" + (text ? " " + text : ""),
});
const people = [10, 11];
const days = ["2027-03-01", "2027-03-02"];
const cells: Record<string, EntryJson[]> = { "10:2027-03-01": [shift(1)], "11:2027-03-02": [shift(2, "late")] };
const entries = (k: string) => cells[k] ?? [];

it("a block is the selection's bounding rectangle, relative to its top-left", () => {
  const { block, anchor } = toBlock(new Set([key(10, "2027-03-01"), key(11, "2027-03-02")]), people, days, entries)!;
  expect(anchor).toEqual([10, "2027-03-01"]);
  expect(block.days).toBe(2);
  expect(block.rows[0][0]![0].start).toBe("08:00");
  expect(block.rows[0][1]).toEqual([]);
  expect(block.rows[1][1]![0].text).toBe("late");
});

it("cells inside the rectangle but outside the selection are left empty", () => {
  const { block } = toBlock(new Set([key(10, "2027-03-01"), key(11, "2027-03-02")]), people, days, (k) => [shift(9, k)])!;
  expect(block.rows[0][1]).toEqual([]);
  expect(block.rows[1][0]).toEqual([]);
});

it("a day the grid hides still takes its column, so the server pastes by date", () => {
  // Friday and Monday are neighbours on screen when the weekend is hidden.
  const shown = ["2027-03-05", "2027-03-08"];
  const { block } = toBlock(new Set([key(10, "2027-03-05"), key(10, "2027-03-08")]), people, shown, (k) => [shift(Number(k.length), k)])!;
  expect(block.days).toBe(4);
  // null, not []: the copy never saw Saturday and Sunday, so pasting must not clear them.
  expect(block.rows[0].map((items) => items && items.length)).toEqual([1, null, null, 1]);
  expect(toTSV(block, departments).split("\t").map((f) => f.length > 0)).toEqual([true, false, false, true]);
});

it("an empty selection makes no block", () => {
  expect(toBlock(new Set(), people, days, entries)).toBeNull();
});

it("TSV has a tab per day and a line per row, items joined by slash", () => {
  const { block } = toBlock(new Set([key(10, "2027-03-01"), key(11, "2027-03-02")]), people, days, entries)!;
  expect(toTSV(block, departments)).toBe("08:00-12:00 Reception PMC\t\n\t08:00-12:00 Reception PMC late");
});

it("plain text pastes as parsed cells, tabs rightward and lines downward", () => {
  const b = fromText("08:00-12:00\tTraining\n---", departments);
  expect(b.days).toBe(2);
  expect(b.rows[0][0]![0].kind).toBe("shift");
  expect(b.rows[0][1]![0].text).toBe("Training");
  expect(b.rows[1][0]![0].kind).toBe("separator");
});

it("text copied out of the island parses back to the same cells", () => {
  const { block } = toBlock(new Set([key(10, "2027-03-01"), key(11, "2027-03-02")]), people, days, entries)!;
  const back = fromText(toTSV(block, departments), departments);
  expect(back.days).toBe(2);
  expect(back.rows[0][0]![0]).toMatchObject({ start: "08:00", finish: "12:00", department: 1 });
  expect(back.rows[1][1]![0]).toMatchObject({ start: "08:00", department: 1, text: "late" });
});

it("a slash-joined cell comes back as separate items", () => {
  const b = fromText("08:00-12:00 / 13:00-17:00", departments);
  expect(b.rows[0][0]!.map((i) => i.start)).toEqual(["08:00", "13:00"]);
});

it("an empty line is an empty cell: later rows keep their place", () => {
  const b = fromText("08:00-12:00\r\n\r\n09:00-17:00", departments);
  expect(b.rows.map((r) => r[0] && r[0].length)).toEqual([1, 0, 1]);
});

it("one trailing line break, as a spreadsheet ends a copy, adds no row", () => {
  expect(fromText("08:00-12:00\r\n", departments).rows).toHaveLength(1);
  expect(fromText("08:00-12:00\n\n", departments).rows).toHaveLength(2);
});

it("text never produces a null cell", () => {
  expect(fromText("a\t\tb\n\n", departments).rows.flat().every((c) => Array.isArray(c))).toBe(true);
});
