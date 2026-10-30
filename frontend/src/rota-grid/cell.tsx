import type { Appearance, EntryJson, Options, SessionJson } from "./types";

const dash = (s: string) => s.replace("-", "–");

/** The only inline style the grid uses: a tile's colours, which managers
 *  choose per item or per department. */
export function tileStyle(e: EntryJson, options: Options): Record<string, string> {
  const a: Appearance = e.appearance || {};
  const style: Record<string, string> = {};
  if (a.bg) style.background = a.bg;
  else if (e.kind === "shift" && options.department_colours && e.department_colour) style.background = e.department_colour;
  if (a.fg) style.color = a.fg;
  return style;
}

export function Tile({ entry, options }: { entry: EntryJson; options: Options }) {
  const a = entry.appearance || {};
  const cls = ["tile", `tile-${entry.kind}`, a.bold && "is-bold", a.italic && "is-italic", a.underline && "is-underline",
               a.strike && "is-strike", a.wrap && "is-wrap", a.size && `is-${a.size}`, entry.overtime && "is-overtime"]
    .filter(Boolean).join(" ");
  if (entry.kind === "separator") return <hr class="tile-separator" />;
  if (entry.kind === "comment") return <div class={cls} style={tileStyle(entry, options)}>{entry.text}</div>;
  return (
    <div class={cls} style={tileStyle(entry, options)}>
      <div>{dash(`${entry.start}-${entry.finish}`)}</div>
      {entry.break_minutes ? <div>{entry.break_minutes === 60 ? "1 hour break" : `${entry.break_minutes} min break`}</div> : null}
      {entry.department_name || entry.text ? <div>{[entry.department_name, entry.text].filter(Boolean).join(" · ")}</div> : null}
      {entry.wfh || entry.overtime ? <div class="tile-marks">{[entry.wfh && "WFH", entry.overtime === "paid" && "OT paid", entry.overtime === "toil" && "TOIL"].filter(Boolean).join(" · ")}</div> : null}
    </div>
  );
}

export function SessionTile({ session }: { session: SessionJson }) {
  return <div class="tile tile-session" title="From the GP rota app">{[session.part, session.label, session.site].filter(Boolean).join(" · ")}</div>;
}

/** Two shifts in one cell that overlap in time. */
export function overlaps(entries: EntryJson[]): boolean {
  const shifts = entries.filter((e) => e.kind === "shift" && e.start && e.finish);
  for (let i = 0; i < shifts.length; i++) for (let j = i + 1; j < shifts.length; j++) {
    if (shifts[i].start! < shifts[j].finish! && shifts[j].start! < shifts[i].finish!) return true;
  }
  return false;
}
