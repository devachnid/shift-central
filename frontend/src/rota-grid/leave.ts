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
 *  View (and, on a row the viewer may edit, Cancel) where leave is booked. */
export function leaveMenuItems(leave: LeaveJson | undefined, rowEditable: boolean, person: number, day: string): MenuItem[] {
  if (!leave) return [{ label: "Time off…", href: `/time-off/add/?person=${person}&day=${day}` }];
  return [
    { label: "View time off", href: `/time-off/${leave.id}/` },
    ...(rowEditable ? [{ label: "Cancel time off", href: `/time-off/${leave.id}/cancel/` }] : []),
  ];
}
