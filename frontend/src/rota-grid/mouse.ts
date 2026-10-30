/** The pointer on the grid: click, drag out a block, and drag a selected
 *  block somewhere else (Ctrl-drag copies it). */
import { useEffect, useRef, useState } from "preact/hooks";
import type { GridState } from "./grid";
import { addDays, dayDiff, key, split, type CellKey } from "./selection";

interface Drag { from: CellKey; copy: boolean; over: CellKey }

export function useMouse(g: GridState, focusGrid: () => void) {
  const drag = useRef<Drag | null>(null);
  const selecting = useRef(false);
  const [over, setOver] = useState<CellKey | null>(null);

  /** The selection translated by whole rows and calendar days: the cells
   *  that are on the grid, and whether every one is and may be edited. */
  const landing = ({ rows, days }: { rows: number; days: number }) => {
    const from = [...g.sel].filter(g.selectable);
    const cells: CellKey[] = [];
    for (const k of from) {
      const [p, d] = split(k);
      const person = g.people[g.people.indexOf(p) + rows], date = addDays(d, days);
      if (person !== undefined && g.days.includes(date)) cells.push(key(person, date));
    }
    return { cells, ok: cells.length === from.length && cells.every(g.selectable) };
  };
  const offset = (from: CellKey, to: CellKey) => {
    const [pf, df] = split(from), [pt, dt] = split(to);
    return { rows: g.people.indexOf(pt) - g.people.indexOf(pf), days: dayDiff(df, dt) };
  };

  const drop = async (d: Drag, to: CellKey) => {
    const by = offset(d.from, to);
    const cells = [...g.sel].filter(g.selectable);
    const target = landing(by);
    if (!target.ok) { g.showBar("That can't be moved there."); return; }
    const moved = await g.mutate("move/", { cells: cells.map(split), days: by.days, rows: by.rows, copy: d.copy, row_order: g.people },
                                 g.snapshot(new Set([...cells, ...target.cells])));
    // The selection goes with the block, as in a spreadsheet.
    if (moved) { g.setSel(new Set(target.cells)); g.setFocus(to); g.setAnchor(to); }
  };

  // The button can come up anywhere, so the end of a gesture is a document
  // listener; it reads the latest closure through a ref.
  const finish = useRef<() => void>(() => {});
  finish.current = () => {
    selecting.current = false;
    const d = drag.current;
    drag.current = null;
    setOver(null);
    if (!d) return;
    if (d.over !== d.from) void drop(d, d.over);
    else g.select(d.from, d.copy ? "toggle" : "set"); // ended where it began: it was a click
  };
  useEffect(() => {
    const up = () => finish.current();
    document.addEventListener("mouseup", up);
    return () => document.removeEventListener("mouseup", up);
  }, []);

  const onDown = (k: CellKey, e: MouseEvent) => {
    // a click inside the open editor is the editor's, not a new selection
    if (e.button !== 0 || (e.target as HTMLElement).closest("textarea")) return;
    const modKey = e.ctrlKey || e.metaKey;
    focusGrid();
    if (!e.shiftKey && g.sel.has(k) && g.selectable(k)) {
      // On the selection: this may become a drag, so nothing changes until the
      // pointer leaves the cell (or comes up, which makes it a click).
      drag.current = { from: k, copy: modKey, over: k };
      return;
    }
    g.select(k, e.shiftKey ? "extend" : modKey ? "toggle" : "set");
    selecting.current = !modKey || e.shiftKey;
  };
  const onEnter = (k: CellKey) => {
    const d = drag.current;
    if (d) { d.over = k; setOver(k); }
    else if (selecting.current) g.select(k, "extend");
  };

  const d = drag.current;
  const moving = d && over && over !== d.from ? landing(offset(d.from, over)) : null;
  return {
    onDown, onEnter,
    /** The cells the dragged block would land on, and whether it may. */
    dropCells: moving ? new Set(moving.cells) : null,
    dropOk: !!moving?.ok,
  };
}
