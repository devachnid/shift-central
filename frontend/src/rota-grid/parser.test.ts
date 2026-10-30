import { describe, expect, it } from "vitest";
import cases from "./parser.cases.json";
import { parseCell, parseLine, renderLine } from "./parser";

const departments = cases.departments.map((name, i) => ({ id: i + 1, name, colour: "#2F6FB3" }));
const byName = (name: string | null) => (name ? departments.find((d) => d.name === name)!.id : null);

describe("parseLine against the shared table", () => {
  for (const c of cases.cases) {
    it(c.line, () => {
      const got = parseLine(c.line, departments);
      const expect_ = { ...c.expect } as Record<string, unknown>;
      if (expect_.kind === "shift") expect_.department = byName(expect_.department as string | null);
      expect(got).toEqual(expect_);
    });
  }
});

it("a cell is one item per line, blank lines skipped", () => {
  expect(parseCell("08:00-12:00\n\n---\nTraining", departments).map((i) => i.kind)).toEqual(["shift", "separator", "comment"]);
});

it("renderLine round-trips through parseLine", () => {
  const item = { kind: "shift" as const, start: "08:00", finish: "16:15", break_minutes: 60, department: byName("HCA"),
                 text: "flu clinic", wfh: true, overtime: "toil" as const };
  const line = renderLine(item, departments);
  expect(line).toBe("08:00-16:15 1 hour break HCA WFH TOIL flu clinic");
  expect(parseLine(line, departments)).toEqual(item);
});
