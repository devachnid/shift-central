/** A selection is a Set of "person:date" keys; blocks are rectangles over
 *  the grid's row order and day list. */
export type CellKey = string;

export const key = (person: number, date: string): CellKey => `${person}:${date}`;
export function split(k: CellKey): [number, string] {
  const i = k.indexOf(":");
  return [parseInt(k.slice(0, i), 10), k.slice(i + 1)];
}

export function block(people: number[], days: string[], a: CellKey, b: CellKey): Set<CellKey> {
  const [pa, da] = split(a), [pb, db] = split(b);
  const r0 = Math.min(people.indexOf(pa), people.indexOf(pb)), r1 = Math.max(people.indexOf(pa), people.indexOf(pb));
  const d0 = Math.min(days.indexOf(da), days.indexOf(db)), d1 = Math.max(days.indexOf(da), days.indexOf(db));
  const out = new Set<CellKey>();
  if (r0 < 0 || d0 < 0) return out;
  for (let r = r0; r <= r1; r++) for (let d = d0; d <= d1; d++) out.add(key(people[r], days[d]));
  return out;
}

export function bounds(sel: Set<CellKey>, people: number[], days: string[]) {
  let r0 = Infinity, r1 = -1, d0 = Infinity, d1 = -1;
  for (const k of sel) {
    const [p, d] = split(k);
    const r = people.indexOf(p), c = days.indexOf(d);
    if (r < 0 || c < 0) continue;
    r0 = Math.min(r0, r); r1 = Math.max(r1, r); d0 = Math.min(d0, c); d1 = Math.max(d1, c);
  }
  return r1 < 0 ? null : { r0, r1, d0, d1 };
}

// Days are counted on the calendar, in UTC so a clock change never moves one.
const ms = (iso: string) => Date.parse(iso + "T00:00:00Z");
export const addDays = (iso: string, n: number): string => new Date(ms(iso) + n * 86400000).toISOString().slice(0, 10);
export const dayDiff = (a: string, b: string): number => Math.round((ms(b) - ms(a)) / 86400000);

/** The shown days in the Monday-to-Sunday week that holds `date`. */
export function weekOf(days: string[], date: string): string[] {
  const start = addDays(date, -((new Date(ms(date)).getUTCDay() + 6) % 7));
  return days.filter((d) => { const n = dayDiff(start, d); return n >= 0 && n < 7; });
}
