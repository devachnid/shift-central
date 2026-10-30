/** The grid's keyboard, as one function over what the grid can do, so the
 *  list of keys reads in one place. */
import type { CellKey } from "./selection";

export interface KeyActions {
  /** The open editor, if any (read from a ref: the key may land before a render). */
  editing: () => { text: string } | null;
  canEdit: boolean;
  focus: CellKey | null;
  /** Moves the focused cell; true when it went anywhere. */
  move: (dr: number, dd: number, extend: boolean) => boolean;
  dayCount: number;
  selectNone: () => void;
  startEdit: (k: CellKey, seed?: string) => void;
  commitEdit: (refocus: boolean) => void;
  cancelEdit: () => void;
  typeIntoEdit: (text: string) => void;
  clear: () => void;
  undo: () => void;
  /** Copy says whether it had anything to take, so an empty selection
   *  leaves the browser's own copy alone. */
  cut: () => void;
  copy: () => boolean;
  openMenu: () => void;
  singleCell: boolean;
}

export function handleKey(e: KeyboardEvent, a: KeyActions) {
  const mod = e.ctrlKey || e.metaKey;
  const key = e.key;
  const open = a.editing();
  if (open) {
    // The editor stops its own keys, so one that gets here was typed in the
    // moment between the edit opening and the textarea taking focus: feed it
    // to the edit rather than lose it.
    if (key === "Enter" && !e.shiftKey) { e.preventDefault(); a.commitEdit(true); }
    else if (key === "Escape") { e.preventDefault(); a.cancelEdit(); }
    else if (!mod && key.length === 1) { e.preventDefault(); a.typeIntoEdit(open.text + key); }
    return;
  }
  if ((e.target as HTMLElement).closest("a")) return; // a name link keeps its own Enter
  if (key === "ArrowUp") { e.preventDefault(); a.move(-1, 0, e.shiftKey); }
  else if (key === "ArrowDown") { e.preventDefault(); a.move(1, 0, e.shiftKey); }
  else if (key === "ArrowLeft") { e.preventDefault(); a.move(0, -1, e.shiftKey); }
  else if (key === "ArrowRight") { e.preventDefault(); a.move(0, 1, e.shiftKey); }
  // Tab walks the days but lets go at either end, so the keyboard is not trapped.
  else if (key === "Tab") { if (a.move(0, e.shiftKey ? -1 : 1, false)) e.preventDefault(); }
  else if (key === "Home") { e.preventDefault(); a.move(0, -a.dayCount, e.shiftKey); }
  else if (key === "End") { e.preventDefault(); a.move(0, a.dayCount, e.shiftKey); }
  else if (key === "Escape") { a.selectNone(); }
  else if (!a.canEdit) return;
  else if (key === "ContextMenu" || (key === "F10" && e.shiftKey)) { e.preventDefault(); a.openMenu(); }
  else if (key === "Enter" || key === "F2") { e.preventDefault(); if (a.focus) a.startEdit(a.focus); }
  else if (key === "Delete" || key === "Backspace") { e.preventDefault(); a.clear(); }
  else if (mod && key.toLowerCase() === "z") { e.preventDefault(); a.undo(); }
  else if (mod && key.toLowerCase() === "c") { if (a.copy()) e.preventDefault(); }
  else if (mod && key.toLowerCase() === "x") { e.preventDefault(); a.cut(); }
  // Ctrl-V is left to the browser: it fires a paste event that carries the
  // clipboard's text without asking permission (onPaste in the grid).
  else if (!mod && key.length === 1 && a.focus && a.singleCell) { e.preventDefault(); a.startEdit(a.focus, key); }
}
