import { useCallback, useEffect, useMemo, useRef, useState } from "preact/hooks";
import { ApiError, getWindow, post } from "./api";
import { overlaps, SessionTile, Tile } from "./cell";
import { block, key, split, type CellKey } from "./selection";
import { toItem, type Changed, type DayJson, type EntryJson, type Item, type Row, type WindowJson } from "./types";

export interface GridProps { from: string; weeks: number; filters: string; api: string; role: string; me: string; reorder: string; bar: string }

interface CellState { person: number; date: string; items: Item[] }
type UndoStep = CellState[];

/** The island's state and the operations every part of it shares. */
export function useGridState(props: GridProps) {
  const [win, setWin] = useState<WindowJson | null>(null);
  const [sel, setSel] = useState<Set<CellKey>>(new Set());
  const [anchor, setAnchor] = useState<CellKey | null>(null);
  const [focus, setFocus] = useState<CellKey | null>(null);
  const [editing, setEditing] = useState<{ key: CellKey; text: string } | null>(null);
  const undo = useRef<UndoStep[]>([]);
  const barEl = () => document.getElementById(props.bar);

  const showBar = useCallback((message: string, signIn = false) => {
    const el = barEl();
    if (!el) return;
    el.textContent = message + " ";
    if (signIn) {
      const a = document.createElement("a");
      a.href = "/accounts/login/?next=" + encodeURIComponent(location.pathname + location.search);
      a.textContent = "Sign in";
      el.appendChild(a);
    }
    el.hidden = false;
  }, [props.bar]);
  const hideBar = () => { const el = barEl(); if (el) el.hidden = true; };

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError) showBar(e.signedOut ? "Your session ended." : `That change wasn't saved: ${e.message}`, e.signedOut);
    else showBar("That change wasn't saved.");
  }, [showBar]);

  const load = useCallback(async () => {
    try {
      const w = await getWindow(props.api, props.from, props.weeks, props.filters);
      setWin(w); hideBar(); setUnnotified(w.unnotified);
    } catch (e) {
      if (e instanceof ApiError && e.signedOut) showBar("Your session ended.", true);
      else showBar("The rota couldn't be loaded. Check your connection and try again.");
    }
  }, [props.api, props.from, props.weeks, props.filters]);

  useEffect(() => { load(); }, [load]);
  // modal.js says "refresh" after a dialog (options, filters, templates...) answered.
  useEffect(() => {
    const on = () => { load(); };
    document.addEventListener("shift-central:refresh", on);
    return () => document.removeEventListener("shift-central:refresh", on);
  }, [load]);

  const people = useMemo(() => (win ? win.rows.map((r) => r.person) : []), [win]);
  // The server sends every day of the window; the Options dialog's weekday
  // choice is applied here, so `days` is exactly the columns on screen and
  // keyboard moves, blocks and (later) paste never land on a hidden one.
  const shownDays = useMemo<DayJson[]>(() => {
    if (!win) return [];
    // options.days counts Monday as 0; Date.getDay() counts Sunday as 0.
    return win.days.filter((d) => win.options.days.includes((new Date(d.date + "T00:00:00").getDay() + 6) % 7));
  }, [win]);
  const days = useMemo(() => shownDays.map((d) => d.date), [shownDays]);
  const rowOf = (person: number): Row | undefined => win?.rows.find((r) => r.person === person);
  const cellEntries = (k: CellKey): EntryJson[] => { const [p, d] = split(k); return rowOf(p)?.cells[d] ?? []; };
  const editable = (k: CellKey) => !!rowOf(split(k)[0])?.editable;

  /** What the given cells hold now, for undo. */
  const snapshot = (keys: Iterable<CellKey>): UndoStep =>
    [...keys].map((k) => { const [person, date] = split(k); return { person, date, items: cellEntries(k).map(toItem) }; });
  const pushUndo = (step: UndoStep) => { undo.current.push(step); if (undo.current.length > 50) undo.current.shift(); };

  const applyChanged = useCallback((c: Changed) => {
    setWin((w) => {
      if (!w) return w;
      const rows = w.rows.map((r) => {
        const mine = c.cells[String(r.person)];
        if (!mine) return r;
        const cells = { ...r.cells };
        for (const [date, entries] of Object.entries(mine)) { if (entries.length) cells[date] = entries; else delete cells[date]; }
        return { ...r, cells };
      });
      return { ...w, rows, unnotified: c.unnotified };
    });
    setUnnotified(c.unnotified);
  }, []);

  /** Post a mutation; on success patch the cells in, on failure show why.
   *  `before` is what to put back if the person undoes it. */
  const mutate = useCallback(async (path: string, body: unknown, before?: UndoStep) => {
    try {
      const c = await post(props.api, path, body);
      if (before) pushUndo(before);
      applyChanged(c);
      hideBar();
      return c;
    } catch (e) { fail(e); return null; }
  }, [props.api, applyChanged, fail]);

  const undoLast = useCallback(async () => {
    const step = undo.current.pop();
    if (!step) return;
    for (const cell of step) {
      const c = await mutate("cell/items/", { person: cell.person, day: cell.date, items: cell.items });
      if (!c) break; // the bar says why; the cells not yet restored stay as they are
    }
  }, [mutate]);

  const select = (k: CellKey, mode: "set" | "extend" | "toggle") => {
    if (mode === "extend" && anchor) setSel(block(people, days, anchor, k));
    else if (mode === "toggle") setSel((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
    else { setSel(new Set([k])); setAnchor(k); }
    setFocus(k);
  };

  return { win, sel, setSel, anchor, setAnchor, focus, setFocus, editing, setEditing, people, days, shownDays,
           rowOf, cellEntries, editable, snapshot, pushUndo, mutate, undoLast, load, showBar, hideBar, select };
}

/** The top bar's "Notify staff (n)" follows the server's count. */
function setUnnotified(n: number) {
  document.querySelectorAll("[data-unnotified]").forEach((el) => { el.textContent = String(n); });
  const btn = document.getElementById("notify-staff");
  if (btn) btn.classList.toggle("is-hidden", n === 0);
}

export type GridState = ReturnType<typeof useGridState>;

/** The in-place editor: Enter saves, Shift-Enter adds a line, Escape
 *  cancels, leaving the cell saves. */
function CellEditor(p: { text: string; onText: (t: string) => void; onCommit: (refocus: boolean) => void; onCancel: () => void }) {
  const el = useRef<HTMLTextAreaElement>(null);
  // autofocus only works at page load, so focus by hand, caret at the end.
  useEffect(() => {
    const t = el.current;
    if (!t) return;
    t.focus();
    t.setSelectionRange(t.value.length, t.value.length);
  }, []);
  return (
    <textarea class="rota-editor" ref={el} value={p.text} rows={Math.max(2, p.text.split("\n").length)}
              aria-label="Shifts for this day, one per line"
              onInput={(e) => p.onText((e.target as HTMLTextAreaElement).value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); p.onCommit(true); }
                else if (e.key === "Escape") { e.preventDefault(); p.onCancel(); }
                e.stopPropagation(); // the grid's own keys are not for the editor
              }}
              onBlur={() => p.onCommit(false)} />
  );
}

export function RotaGrid(props: GridProps) {
  const g = useGridState(props);
  const { win, sel, focus, editing, people, days, shownDays } = g;
  const table = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  // The editor can be left three ways at once (Enter, then the blur its
  // removal causes; Escape, then the blur); the ref makes the first one win.
  const editingRef = useRef(editing);
  editingRef.current = editing;
  const canEdit = !!win?.can_edit;
  const editableSel = () => [...sel].filter(g.editable);

  const setEdit = (next: { key: CellKey; text: string } | null) => { editingRef.current = next; g.setEditing(next); };
  const startEdit = (k: CellKey, seed = "") => {
    if (!g.editable(k)) return;
    setEdit({ key: k, text: seed || g.cellEntries(k).map((e) => e.line).join("\n") });
  };
  const cancelEdit = () => { setEdit(null); table.current?.focus(); };
  const commitEdit = async (refocus: boolean) => {
    const cur = editingRef.current;
    if (!cur) return;
    setEdit(null);
    if (refocus) table.current?.focus();
    const [person, date] = split(cur.key);
    if (cur.text.trim() === g.cellEntries(cur.key).map((e) => e.line).join("\n").trim()) return; // nothing changed
    const saved = await g.mutate("cell/", { person, day: date, text: cur.text }, g.snapshot([cur.key]));
    if (!saved) setEdit(cur); // not saved: give the typing back rather than lose it
  };
  const clearSel = async () => {
    const keys = editableSel();
    if (!keys.length) return;
    await g.mutate("clear/", { cells: keys.map(split) }, g.snapshot(keys));
  };

  /** Move the focused cell; true when it went anywhere. */
  const move = (dr: number, dd: number, extend: boolean): boolean => {
    if (!people.length || !days.length) return false;
    if (!focus) { g.select(key(people[0], days[0]), "set"); return true; }
    const [p, d] = split(focus);
    const r = Math.min(Math.max(people.indexOf(p) + dr, 0), people.length - 1);
    const c = Math.min(Math.max(days.indexOf(d) + dd, 0), days.length - 1);
    const next = key(people[r], days[c]);
    if (next === focus && !extend) return false;
    g.select(next, extend ? "extend" : "set");
    return true;
  };

  // A drag that starts on a cell selects the block under the pointer until
  // the button comes up, wherever it comes up.
  useEffect(() => {
    const up = () => { dragging.current = false; };
    document.addEventListener("mouseup", up);
    return () => document.removeEventListener("mouseup", up);
  }, []);

  // Keep the focused cell in view as the keyboard moves it.
  useEffect(() => {
    if (!focus) return;
    table.current?.querySelector(`[data-cell="${focus}"]`)?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [focus]);

  const onKey = (e: KeyboardEvent) => {
    const mod = e.ctrlKey || e.metaKey;
    const open = editingRef.current;
    if (open) {
      // The editor stops its own keys, so one that gets here was typed in the
      // moment between the edit opening and the textarea taking focus: feed it
      // to the edit rather than lose it.
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); commitEdit(true); }
      else if (e.key === "Escape") { e.preventDefault(); cancelEdit(); }
      else if (!mod && e.key.length === 1) { e.preventDefault(); setEdit({ ...open, text: open.text + e.key }); }
      return;
    }
    if ((e.target as HTMLElement).closest("a")) return; // a name link keeps its own Enter
    if (e.key === "ArrowUp") { e.preventDefault(); move(-1, 0, e.shiftKey); }
    else if (e.key === "ArrowDown") { e.preventDefault(); move(1, 0, e.shiftKey); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); move(0, -1, e.shiftKey); }
    else if (e.key === "ArrowRight") { e.preventDefault(); move(0, 1, e.shiftKey); }
    // Tab walks the days but lets go at either end, so the keyboard is not trapped.
    else if (e.key === "Tab") { if (move(0, e.shiftKey ? -1 : 1, false)) e.preventDefault(); }
    else if (e.key === "Home") { e.preventDefault(); move(0, -days.length, e.shiftKey); }
    else if (e.key === "End") { e.preventDefault(); move(0, days.length, e.shiftKey); }
    else if (e.key === "Escape") { g.setSel(new Set()); }
    else if (!canEdit) return;
    else if (e.key === "Enter" || e.key === "F2") { e.preventDefault(); if (focus) startEdit(focus); }
    else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); clearSel(); }
    else if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); g.undoLast(); }
    else if (!mod && e.key.length === 1 && focus && sel.size === 1) { e.preventDefault(); startEdit(focus, e.key); }
    // Ctrl-X/C/V, the menu key and Shift-F10 are Task 7's.
  };

  if (!win) return <div class="rota-loading">Loading the rota…</div>;
  const o = win.options;
  const cls = ["rota-grid", `is-${o.font_size}`, `is-${o.spacing}`, o.float_headers && "is-float", canEdit && "can-edit"].filter(Boolean).join(" ");

  return (
    <div class="rota-wrap" ref={table} tabIndex={0} role="grid" aria-label="Rota" onKeyDown={onKey}>
      <table class={cls}>
        <thead><tr>
          <th class="rota-name-head"></th>
          {shownDays.map((d) => (
            <th key={d.date} class={[d.today && "is-today", d.weekend && "is-weekend"].filter(Boolean).join(" ")}
                onClick={() => { const col = win.rows.filter((r) => r.editable).map((r) => key(r.person, d.date)); g.setSel(new Set(col)); g.setFocus(col[0] ?? null); }}>
              {d.label}
            </th>
          ))}
        </tr></thead>
        <tbody>
          {win.rows.map((r) => (
            <tr key={r.person} data-person={r.person} class={r.editable ? "" : "is-readonly"}>
              <th class="rota-name" scope="row"
                  onClick={(e) => { if ((e.target as HTMLElement).closest("a")) return; if (!r.editable) return; const row = shownDays.map((d) => key(r.person, d.date)); g.setSel(new Set(row)); g.setFocus(row[0]); }}>
                <a href={`/staff/${r.person}/profile/`} data-dialog class={o.staff_colours ? "chip" : "rota-plain-name"} style={o.staff_colours ? { background: r.colour } : {}}>{r.name}</a>
                {o.job_titles && r.job_title ? <div class="rota-job">{r.job_title}</div> : null}
              </th>
              {shownDays.map((d) => {
                const k = key(r.person, d.date);
                const entries = r.cells[d.date] ?? [];
                const sessions = r.sessions[d.date] ?? [];
                const isEditing = editing?.key === k;
                return (
                  <td key={k} role="gridcell" aria-selected={sel.has(k)} data-cell={k}
                      class={[sel.has(k) && "is-selected", focus === k && "is-focus", d.today && "is-today", overlaps(entries) && "has-overlap"].filter(Boolean).join(" ")}
                      title={overlaps(entries) ? "These shifts overlap" : undefined}
                      onMouseDown={(e) => {
                        // a click inside the open editor is the editor's, not a new selection
                        if (e.button !== 0 || (e.target as HTMLElement).closest("textarea")) return;
                        const mode = e.shiftKey ? "extend" : e.ctrlKey || e.metaKey ? "toggle" : "set";
                        g.select(k, mode);
                        dragging.current = mode !== "toggle";
                        table.current?.focus();
                      }}
                      onMouseEnter={() => { if (dragging.current) g.select(k, "extend"); }}
                      onDblClick={() => startEdit(k)}>
                    {sessions.map((s, i) => <SessionTile key={i} session={s} />)}
                    {isEditing ? (
                      <CellEditor text={editing!.text} onText={(text) => setEdit({ key: k, text })}
                                  onCommit={commitEdit} onCancel={cancelEdit} />
                    ) : entries.map((e) => <Tile key={e.id} entry={e} options={o} />)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
