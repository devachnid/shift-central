/** What the menu and the keyboard do to the selection: clear, cut, copy,
 *  paste, add items, patch entries. Plain closures over the grid's state,
 *  rebuilt every render, so they always see the current selection. */
import { fromText, load, save, toBlock, toTSV } from "./clipboard";
import type { GridState, UndoStep } from "./grid";
import { addDays, bounds, key, split, type CellKey } from "./selection";
import { toItem, type Appearance, type EntryJson, type Item, type Shape } from "./types";

export function selectionActions(g: GridState) {
  const selKeys = (): CellKey[] => [...g.sel].filter(g.selectable);
  const selEntries = () => selKeys().flatMap((k) => g.cellEntries(k));
  const selShifts = () => selEntries().filter((e) => e.kind === "shift");

  /** Where a paste or a template lands: the selection's top-left (as in a
   *  spreadsheet; the focus is the far corner after a drag or Shift-click),
   *  or the focused cell when nothing is selected and it may be edited. */
  const anchorCell = (): CellKey | null => {
    const b = bounds(g.sel, g.people, g.days);
    if (b) return key(g.people[b.r0], g.days[b.d0]);
    return g.focus && g.selectable(g.focus) ? g.focus : null;
  };

  const clear = async () => {
    const keys = selKeys();
    if (!keys.length) return;
    await g.mutate("clear/", { cells: keys.map(split) }, g.snapshot(keys));
  };

  const block = () => toBlock(new Set(selKeys()), g.people, g.days, g.cellEntries);
  const copy = (): boolean => {
    const made = block();
    if (!made) return false;
    save(made.block, toTSV(made.block, g.win?.departments ?? []));
    return true;
  };
  const cut = async () => { if (copy()) await clear(); };

  /** Paste the island's own block, or `external` text when it is not just
   *  what we copied (Excel, another page) and so carries no more than text. */
  const paste = async (external?: string) => {
    const at = anchorCell();
    if (!at || !g.win) return;
    const stored = load();
    let blk = stored?.block;
    if (external !== undefined && external.trim() && (!stored || external.trim() !== stored.tsv.trim())) blk = fromText(external);
    if (!blk || !blk.rows.length) return;
    const [person, date] = split(at);
    const row = g.people.indexOf(person);
    const targets = new Set<CellKey>();
    blk.rows.forEach((cells, r) => cells.forEach((_, c) => {
      const p = g.people[row + r];
      if (p !== undefined && cells[c] !== null) targets.add(key(p, addDays(date, c)));
    }));
    // Undo covers every target in the window, hidden weekdays too (the server
    // writes them); the server skips rows the viewer may not edit and says how many.
    const inWindow = new Set(g.win.days.map((d) => d.date));
    const undoable = [...targets].filter((k) => inWindow.has(split(k)[1]) && g.selectable(k));
    const res = await g.mutate("paste/", { anchor: [person, date], block: blk, mode: g.win.options.paste, row_order: g.people }, g.snapshot(undoable));
    if (res && res.skipped) g.showBar(`${res.skipped} row${res.skipped === 1 ? "" : "s"} couldn't be pasted onto.`);
  };

  /** The menu's Paste: the system clipboard if the browser allows reading
   *  it, else our own copy. */
  const pasteFromMenu = async () => {
    let text: string | undefined;
    try { text = await navigator.clipboard.readText(); } catch { text = undefined; }
    await paste(text);
  };

  /** One post per item, the first carrying the undo step for all of them,
   *  stopping at the first that fails (the bar says why). */
  const sequence = async <T,>(list: T[], keys: CellKey[], post: (t: T, before?: UndoStep) => Promise<unknown>) => {
    const before = g.snapshot(keys);
    for (const [i, t] of list.entries()) if (!(await post(t, i === 0 ? before : undefined))) return;
  };

  /** Append items to every selected cell. */
  const addItems = (items: Item[]) =>
    sequence(selKeys(), selKeys(), (k, before) => {
      const [person, day] = split(k);
      return g.mutate("cell/items/", { person, day, items: [...g.cellEntries(k).map(toItem), ...items] }, before);
    });

  const patchEntries = (list: EntryJson[], fields: (e: EntryJson) => Partial<Item>) => {
    if (!list.length) { g.showBar("There is nothing in the selection that this applies to."); return Promise.resolve(); }
    return sequence(list, selKeys(), (e, before) => g.mutate(`entries/${e.id}/`, fields(e), before));
  };
  /** Department, break, overtime and WFH belong to shifts only. */
  const patchShifts = (fields: Partial<Item>) => patchEntries(selShifts(), () => fields);
  const toggleWfh = () => patchShifts({ wfh: !selShifts().every((e) => e.wfh) });

  const appearance = (change: Partial<Appearance>) => patchEntries(selEntries(), (e) => ({ appearance: { ...e.appearance, ...change } }));
  /** On for all unless they all have it already, so a mixed selection ends up uniform. */
  const toggleAppearance = (name: "bold" | "italic" | "underline" | "strike" | "wrap") => {
    const on = !selEntries().every((e) => e.appearance?.[name]);
    return appearance({ [name]: on });
  };
  const resetAppearance = () => patchEntries(selEntries(), () => ({ appearance: {} }));

  return { selKeys, anchorCell, clear, block, copy, cut, paste, pasteFromMenu, addItems, patchShifts, toggleWfh,
           appearance, toggleAppearance, resetAppearance };
}

export type Actions = ReturnType<typeof selectionActions>;

/** A Common or Recent shape as a new shift. */
export const shapeItem = (s: Shape): Item =>
  ({ kind: "shift", start: s.start, finish: s.finish, break_minutes: s.break_minutes, department: s.department });
