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
