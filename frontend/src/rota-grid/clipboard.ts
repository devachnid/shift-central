/** Blocks (spec, section 5): the selection's bounding rectangle as rows of
 *  day offsets, kept in the island and in localStorage, and written to the
 *  system clipboard as tab-separated text for Excel. */
import { parseCell, renderLine } from "./parser";
import { addDays, bounds, dayDiff, key, type CellKey } from "./selection";
import { toItem, type Block, type BlockCell, type Department, type EntryJson } from "./types";

const STORE = "shift-central.clipboard";

/** Columns are calendar days from the left edge, because the server pastes
 *  by date. A day the Options dialog hides still takes its place, as null:
 *  the copy never saw it, so a paste must not clear what is there. */
export function toBlock(sel: Set<CellKey>, people: number[], days: string[], entries: (k: CellKey) => EntryJson[]) {
  const b = bounds(sel, people, days);
  if (!b) return null;
  const first = days[b.d0], span = dayDiff(first, days[b.d1]) + 1;
  const rows: BlockCell[][] = [];
  for (let r = b.r0; r <= b.r1; r++) {
    const row: BlockCell[] = [];
    for (let c = 0; c < span; c++) {
      const date = addDays(first, c);
      const k = key(people[r], date);
      // A hole in the rectangle (a cell the viewer did not select) is empty.
      row.push(!days.includes(date) ? null : sel.has(k) ? entries(k).map(toItem) : []);
    }
    rows.push(row);
  }
  return { block: { days: span, rows } as Block, anchor: [people[b.r0], first] as [number, string] };
}

export function toTSV(block: Block, departments: Department[]): string {
  return block.rows.map((row) => row.map((items) => (items ?? []).map((i) => renderLine(i, departments)).join(" / ")).join("\t")).join("\n");
}

/** Text from outside the island: tabs are days, lines are rows, " / "
 *  separates items within a cell. */
export function fromText(text: string, departments: Department[]): Block {
  // One trailing line break is how a copy ends; an empty line before it is an
  // empty cell and must keep its place, or every row below lands one too high.
  const lines = text.replace(/\r/g, "").replace(/\n$/, "").split("\n");
  const rows = lines.map((line) =>
    line.split("\t").map((cell) => parseCell(cell.split(" / ").join("\n"), departments)));
  const days = Math.max(1, ...rows.map((r) => r.length));
  return { days, rows: rows.map((r): BlockCell[] => { while (r.length < days) r.push([]); return r; }) };
}

export interface Stored { block: Block; tsv: string }

/** Keep the block for pasting back in (its dates, departments and colours
 *  survive, which text would lose) and offer the text to other programs. */
export function save(block: Block, tsv: string) {
  try { localStorage.setItem(STORE, JSON.stringify({ block, tsv })); } catch { /* private window */ }
  try { navigator.clipboard?.writeText(tsv).catch(() => { /* no permission */ }); } catch { /* no clipboard */ }
}

export function load(): Stored | null {
  try {
    const raw = localStorage.getItem(STORE);
    const s = raw ? JSON.parse(raw) : null;
    return s && Array.isArray(s.block?.rows) && typeof s.tsv === "string" ? s : null;
  } catch { return null; }
}
