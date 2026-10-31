import { expect, it } from "vitest";
import { LeaveTile } from "./cell";
import { inkOn, leaveLabel, leaveMenuItems, pasteSkipMessage, selectableWithLeave } from "./leave";
import type { Actions } from "./actions";
import type { GridState } from "./grid";
import { menuItems } from "./menu-items";
import { key } from "./selection";
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
    { label: "Shift behind the leave…", href: "/rota/shift/7/2026-11-03/" },
  ]);
  expect(leaveMenuItems({ ...base, status: "pending" }, true, 7, "2026-11-03").map((i) => i.label)).toEqual(["View time off", "Cancel time off"]);
  expect(leaveMenuItems(base, false, 7, "2026-11-03")).toEqual([{ label: "View time off", href: "/time-off/1/" }]);
});

it("a pending request on a read-only row offers View only", () => {
  expect(leaveMenuItems({ ...base, status: "pending" }, false, 7, "2026-11-03")).toEqual([{ label: "View time off", href: "/time-off/1/" }]);
});

it("menuItems gives leave cells that cannot be selected the leave items alone", () => {
  const pending: LeaveJson = { ...base, status: "pending" };
  const grid = (leave: LeaveJson | undefined, selectable: boolean, editable: boolean) =>
    ({ leaveAt: () => leave, selectable: () => selectable, rowOf: () => ({ editable }) }) as unknown as GridState;
  const labels = (g: GridState) => menuItems(g, {} as Actions, key(7, "2026-11-03"), () => undefined).map((i) => i.label);
  expect(labels(grid(base, false, true))).toEqual(["View time off", "Cancel time off", "Shift behind the leave…"]); // approved
  expect(labels(grid(pending, false, false))).toEqual(["View time off"]); // pending, read-only row
});

it("approved leave on an editable row offers the shift behind it, at the shift dialog's address", () => {
  const labels = (l: LeaveJson, editable: boolean) => leaveMenuItems(l, editable, 7, "2026-11-03").map((i) => i.label);
  expect(leaveMenuItems(base, true, 7, "2026-11-03")[2]).toEqual({ label: "Shift behind the leave…", href: "/rota/shift/7/2026-11-03/" });
  expect(labels(base, false)).not.toContain("Shift behind the leave…");
  expect(labels({ ...base, status: "pending" }, true)).not.toContain("Shift behind the leave…");
});

it("a timed day offers the day's shift, not the shift behind the leave, at the same address", () => {
  const timed: LeaveJson = { ...base, part: "times", times: "14:00–15:30" };
  expect(leaveMenuItems(timed, true, 7, "2026-11-03")).toEqual([
    { label: "View time off", href: "/time-off/1/" },
    { label: "Cancel time off", href: "/time-off/1/cancel/" },
    { label: "Edit the day's shift…", href: "/rota/shift/7/2026-11-03/" },
  ]);
  for (const part of ["whole", "am", "pm"] as const)
    expect(leaveMenuItems({ ...base, part }, true, 7, "2026-11-03")[2].label).toBe("Shift behind the leave…");
  expect(leaveMenuItems({ ...timed, status: "pending" }, true, 7, "2026-11-03").map((i) => i.label)).toEqual(["View time off", "Cancel time off"]);
  expect(leaveMenuItems(timed, false, 7, "2026-11-03").map((i) => i.label)).toEqual(["View time off"]);
});

it("inkOn gives the seeded light colours the page's ink and a dark colour white", () => {
  for (const light of ["#D98FB3", "#E0A458", "#9E9E9E", "#B58B4C", "#6C8EAD", "#FFE66D"]) expect(inkOn(light)).toBe("var(--ink)");
  for (const dark of ["#2F6FB3", "#1B1F27", "#000000", "#7A1F3D"]) expect(inkOn(dark)).toBe("#fff");
  expect(inkOn("#d98fb3")).toBe("var(--ink)");   // case does not matter
  expect(inkOn("red")).toBe("var(--ink)");        // not #RRGGBB: the ink
});

it("inkOn picks whichever of white and ink has the higher WCAG contrast", () => {
  const lum = (hex: string) => {
    const [r, g, b] = [1, 3, 5].map((i) => { const c = parseInt(hex.slice(i, i + 2), 16) / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const contrast = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  for (const hex of ["#D98FB3", "#E0A458", "#9E9E9E", "#B58B4C", "#6C8EAD", "#FFE66D", "#2F6FB3", "#808080", "#7F7F7F"]) {
    const picked = inkOn(hex) === "#fff" ? "#ffffff" : "#1B1F27";
    const other = picked === "#ffffff" ? "#1B1F27" : "#ffffff";
    expect(contrast(hex, picked)).toBeGreaterThanOrEqual(contrast(hex, other));
  }
});

it("an approved tile takes its text colour from inkOn; a pending one is ink text with a thick edge in the colour", () => {
  const style = (l: LeaveJson) => (LeaveTile({ leave: l }) as unknown as { props: { style: Record<string, string> } }).props.style;
  expect(style({ ...base, colour: "#D98FB3" })).toEqual({ background: "#D98FB3", color: "var(--ink)" });
  expect(style({ ...base, colour: "#2F6FB3" })).toEqual({ background: "#2F6FB3", color: "#fff" });
  expect(style({ ...base, colour: "#D98FB3", status: "pending" })).toEqual({ borderColor: "#D98FB3", borderLeft: "3px solid #D98FB3", color: "var(--ink)" });
});

it("the paste bar counts rows and leave days apart", () => {
  expect(pasteSkipMessage(1, 0)).toBe("1 row couldn't be pasted onto.");
  expect(pasteSkipMessage(3, 0)).toBe("3 rows couldn't be pasted onto.");
  expect(pasteSkipMessage(1, 1)).toBe("1 leave day couldn't be pasted onto.");
  expect(pasteSkipMessage(3, 2)).toBe("1 row and 2 leave days couldn't be pasted onto.");
  expect(pasteSkipMessage(4, 4)).toBe("4 leave days couldn't be pasted onto.");
});
