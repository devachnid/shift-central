import type { MenuItem } from "./menu";
import type { LeaveJson } from "./types";

export function leaveLabel(l: LeaveJson): string {
  const parts = [l.label];
  if (l.part === "am") parts.push("½ am");
  else if (l.part === "pm") parts.push("½ pm");
  else if (l.part === "times" && l.times) parts.push(l.times);
  if (l.status === "pending") parts.push("requested");
  return parts.join(" · ");
}

/** Approved leave owns the cell: nothing is typed, pasted or dragged there. */
export function selectableWithLeave(editable: boolean, l: LeaveJson | undefined): boolean {
  return editable && !(l && l.status === "approved");
}

/** The leave entries of the right-click menu: "Time off…" on a free day,
 *  View (and, on a row the viewer may edit, Cancel, and for approved leave the shift behind it) where leave is booked. */
export function leaveMenuItems(leave: LeaveJson | undefined, rowEditable: boolean, person: number, day: string): MenuItem[] {
  if (!leave) return [{ label: "Time off…", href: `/time-off/add/?person=${person}&day=${day}` }];
  return [
    { label: "View time off", href: `/time-off/${leave.id}/` },
    ...(rowEditable ? [{ label: "Cancel time off", href: `/time-off/${leave.id}/cancel/` }] : []),
    // Approved leave only; a pending cell is edited as usual. The address is the shift dialog's:
    // for a whole or half day it sets the shift the person would have worked (writing it re-costs a
    // day that was costed on an average day); on a timed day the leave has only shortened the visible
    // shift, and the dialog edits that.
    ...(rowEditable && leave.status === "approved"
      ? [{ label: leave.part === "times" ? "Edit the day's shift…" : "Shift behind the leave…", href: `/rota/shift/${person}/${day}/` }]
      : []),
  ];
}

const INK = "#1B1F27";   // --ink, the page's text colour

function luminance(hex: string): number | null {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return null;
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(m[1].slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Text colour for a filled tile: white or the page's ink, whichever contrasts
 *  more with the fill (WCAG relative luminance). A value that is not #RRGGBB gets the ink. */
export function inkOn(hex: string): string {
  const l = luminance(hex);
  if (l === null) return "var(--ink)";
  const white = 1.05 / (l + 0.05);
  const ink = (l + 0.05) / (luminance(INK)! + 0.05);
  return white > ink ? "#fff" : "var(--ink)";
}

/** The bar after a paste: rows the viewer may not edit and leave days are counted apart. */
export function pasteSkipMessage(skipped: number, leaveDays: number): string {
  const rows = skipped - leaveDays;
  const parts = [];
  if (rows > 0) parts.push(`${rows} row${rows === 1 ? "" : "s"}`);
  if (leaveDays > 0) parts.push(`${leaveDays} leave day${leaveDays === 1 ? "" : "s"}`);
  return `${parts.join(" and ")} couldn't be pasted onto.`;
}
