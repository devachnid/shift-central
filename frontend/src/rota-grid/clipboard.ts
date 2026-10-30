/** Blocks (spec, section 5): the selection's bounding rectangle as rows of
 *  day offsets, kept in the island and in sessionStorage (practice PCs are
 *  shared, so a copy goes when the browser closes), and written to the
 *  system clipboard as tab-separated text for Excel. */
import { renderLine } from "./parser";
import { addDays, bounds, dayDiff, key, type CellKey } from "./selection";
import { toItem, type Block, type BlockCell, type Department, type EntryJson } from "./types";

const STORE = "shift-central.clipboard";

/** Columns are calendar days from the left edge, because the server pastes
 *  by date. A day the Options dialog hides still takes its place, as null:
 *  the copy never saw it, so a paste must not clear what is there. A cell
 *  inside the rectangle that was not selected is null too; a selected cell
 *  with nothing in it is [], which clears. */
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
      row.push(days.includes(date) && sel.has(k) ? entries(k).map(toItem) : null);
    }
    rows.push(row);
  }
  return { block: { days: span, rows } as Block, anchor: [people[b.r0], first] as [number, string] };
}

/** A cell as one TSV field: items joined by " / "; a text cell is its own
 *  text, its lines joined the same way so the field stays on one line. */
const field = (cell: BlockCell, departments: Department[]): string =>
  typeof cell === "string" ? cell.split("\n").join(" / ")
    : (cell ?? []).map((i) => renderLine(i, departments)).join(" / ");

export function toTSV(block: Block, departments: Department[]): string {
  return block.rows.map((row) => row.map((cell) => field(cell, departments)).join("\t")).join("\n");
}

/** Text from outside the island: tabs are days, lines are rows, " / "
 *  separates items within a cell. Each cell is sent as its text, one item
 *  per line, and the server parses it (spec: the server parses; the
 *  island's parser is only a preview). An empty field is "", which clears. */
export function fromText(text: string): Block {
  // One trailing line break is how a copy ends; an empty line before it is an
  // empty cell and must keep its place, or every row below lands one too high.
  const lines = text.replace(/\r/g, "").replace(/\n$/, "").split("\n");
  const rows = lines.map((line) => line.split("\t").map((cell) => cell.split(" / ").join("\n")));
  const days = Math.max(1, ...rows.map((r) => r.length));
  return { days, rows: rows.map((r): BlockCell[] => { while (r.length < days) r.push(""); return r; }) };
}

export interface Stored { block: Block; tsv: string }

/** Keep the block for pasting back in (its dates, departments and colours
 *  survive, which text would lose) and offer the text to other programs. */
export function save(block: Block, tsv: string) {
  try { sessionStorage.setItem(STORE, JSON.stringify({ block, tsv })); } catch { /* private window */ }
  try { navigator.clipboard?.writeText(tsv).catch(() => { /* no permission */ }); } catch { /* no clipboard */ }
}

export function load(): Stored | null {
  try {
    const raw = sessionStorage.getItem(STORE);
    const s = raw ? JSON.parse(raw) : null;
    return s && Array.isArray(s.block?.rows) && typeof s.tsv === "string" ? s : null;
  } catch { return null; }
}
