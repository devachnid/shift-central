import { expect, it } from "vitest";
import { leaveLabel, leaveMenuItems, selectableWithLeave } from "./leave";
import type { LeaveJson } from "./types";

const base: LeaveJson = { id: 1, type: "Holiday", colour: "#2F6FB3", part: "whole", label: "Holiday", status: "approved" };

it("labels a whole day by its label, a half day with its half, times with its span", () => {
  expect(leaveLabel(base)).toBe("Holiday");
  expect(leaveLabel({ ...base, part: "am" })).toBe("Holiday · ½ am");
  expect(leaveLabel({ ...base, part: "pm", label: "Spring" })).toBe("Spring · ½ pm");
  expect(leaveLabel({ ...base, part: "times", times: "14:00–15:30" })).toBe("Holiday · 14:00–15:30");
  expect(leaveLabel({ ...base, status: "pending" })).toBe("Holiday · requested");
});

it("approved leave makes the cell read-only; a pending request does not", () => {
  expect(selectableWithLeave(true, base)).toBe(false);
  expect(selectableWithLeave(true, { ...base, status: "pending" })).toBe(true);
  expect(selectableWithLeave(true, undefined)).toBe(true);
  expect(selectableWithLeave(false, undefined)).toBe(false);
});

it("a free day offers Time off…, leave offers View and, on an editable row, Cancel", () => {
  expect(leaveMenuItems(undefined, true, 7, "2026-11-03")).toEqual([{ label: "Time off…", href: "/time-off/add/?person=7&day=2026-11-03" }]);
  expect(leaveMenuItems(base, true, 7, "2026-11-03")).toEqual([
    { label: "View time off", href: "/time-off/1/" },
    { label: "Cancel time off", href: "/time-off/1/cancel/" },
  ]);
  expect(leaveMenuItems(base, false, 7, "2026-11-03")).toEqual([{ label: "View time off", href: "/time-off/1/" }]);
});
