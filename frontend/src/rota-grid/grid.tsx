import { useCallback, useEffect, useMemo, useRef, useState } from "preact/hooks";
import { selectionActions } from "./actions";
import { ApiError, getWindow, post } from "./api";
import { LeaveTile, overlaps, SessionTile, Tile } from "./cell";
import { CellEditor } from "./editor";
import { handleKey } from "./keys";
import { selectableWithLeave } from "./leave";
import { Menu } from "./menu";
import { menuItems } from "./menu-items";
import { useMouse } from "./mouse";
import { block, key, split, type CellKey } from "./selection";
import { useSort } from "./sort";
import { toItem, type Changed, type DayJson, type EntryJson, type Item, type LeaveJson, type Row, type WindowJson } from "./types";

export interface GridProps { from: string; weeks: number; filters: string; api: string; role: string; me: string; reorder: string; bar: string }

interface CellState { person: number; date: string; items: Item[] }
export type UndoStep = CellState[];

/** The island's state and the operations every part of it shares. */
export function useGridState(props: GridProps) {
  const [win, setWin] = useState<WindowJson | null>(null);
  const [sel, setSel] = useState<Set<CellKey>>(new Set());
  const [anchor, setAnchor] = useState<CellKey | null>(null);
  const [focus, setFocus] = useState<CellKey | null>(null);
  const [editing, setEditing] = useState<{ key: CellKey; text: string } | null>(null);
  const undo = useRef<UndoStep[]>([]);
  const barEl = () => document.getElementById(props.bar);

  const showBar = useCallback((message: string, signIn = false, retry?: () => void) => {
    const el = barEl();
    if (!el) return;
    el.textContent = message + " ";
    if (signIn) {
      const a = document.createElement("a");
      a.href = "/accounts/login/?next=" + encodeURIComponent(location.pathname + location.search);
      a.textContent = "Sign in";
      el.appendChild(a);
    }
    if (retry) {
      const a = document.createElement("a");
      a.href = "#";
      a.textContent = "Retry";
      a.addEventListener("click", (e) => { e.preventDefault(); retry(); });
      el.appendChild(a);
    }
    el.hidden = false;
  }, [props.bar]);
  const hideBar = () => { const el = barEl(); if (el) el.hidden = true; };

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError) showBar(e.signedOut ? "Your session ended." : `That change wasn't saved: ${e.message}`, e.signedOut);
    else showBar("That change wasn't saved.");
  }, [showBar]);

  // Mutations go through one queue (below); `applied` counts the posts whose
  // answer is in the cells, so a window answer that was asked for before one
  // finished can be told from one that already includes it.
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const applied = useRef(0);
  const loadSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++loadSeq.current;
    for (;;) {
      const seen = applied.current;
      let w: WindowJson;
      try {
        w = await getWindow(props.api, props.from, props.weeks, props.filters);
      } catch (e) {
        if (seq !== loadSeq.current) return; // a newer load speaks for the grid
        if (e instanceof ApiError && e.signedOut) showBar("Your session ended.", true);
        else showBar("The rota couldn't be loaded. Check your connection and try again.", false, () => { load(); });
        return;
      }
      if (seq !== loadSeq.current) return;
      // A save finished while this was in flight, so the answer may predate
      // it and would put the old cells back: ask again.
      if (seen !== applied.current) continue;
      setWin(w); hideBar(); setUnnotified(w.unnotified);
      return;
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
  const leaveAt = (k: CellKey): LeaveJson | undefined => { const [p, d] = split(k); return rowOf(p)?.leave?.[d]; };
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

  /** One POST, its answer patched in, or the reason shown. Null on failure. */
  const send = useCallback(async (path: string, body: unknown): Promise<Changed | null> => {
    try {
      const c = await post(props.api, path, body);
      applyChanged(c);
      // Counted here, once per post whose answer is in the cells, so a window
      // load cannot slip in between the restores of a multi-cell undo.
      applied.current++;
      hideBar();
      return c;
    } catch (e) { fail(e); return null; }
  }, [props.api, applyChanged, fail]);

  /** Run jobs one after another, so saves and undos reach the server in the
   *  order they were asked for and the undo stack matches what it holds. */
  const enqueue = useCallback(<T,>(job: () => Promise<T>): Promise<T> => {
    const run = queue.current.then(job);
    queue.current = run.catch(() => undefined);
    return run;
  }, []);

  /** Post a mutation; on success patch the cells in, on failure show why.
   *  `before` (what the cells held) is the undo step: it goes on the stack as
   *  the mutation is queued, so a Ctrl-Z straight after undoes this change,
   *  and comes off again if the save fails. */
  const mutate = useCallback((path: string, body: unknown, before?: UndoStep) => {
    if (before) pushUndo(before);
    return enqueue(async () => {
      const c = await send(path, body);
      if (!c && before) undo.current = undo.current.filter((s) => s !== before);
      return c;
    });
  }, [enqueue, send]);

  const undoLast = useCallback(async () => {
    const step = undo.current.pop();
    if (!step) return;
    await enqueue(async () => {
      for (const cell of step) {
        const c = await send("cell/items/", { person: cell.person, day: cell.date, items: cell.items });
        if (!c) break; // the bar says why; the cells not yet restored stay as they are
      }
    });
  }, [enqueue, send]);

  /** Sort mode: show the rows in this order now; the load that follows the
   *  save says what the server holds. */
  const reorder = (ids: number[]) => setWin((w) => {
    if (!w) return w;
    const byPerson = new Map(w.rows.map((r) => [r.person, r]));
    return { ...w, rows: ids.map((id) => byPerson.get(id)).filter((r): r is Row => !!r) };
  });

  /** The selection only ever holds cells the viewer may edit; a read-only
   *  row, a read-only viewer or a day of approved leave gets the focus ring
   *  and nothing selected. */
  const selectable = (k: CellKey) => !!win?.can_edit && selectableWithLeave(editable(k), leaveAt(k));
  const keepSelectable = (keys: Iterable<CellKey>) => new Set([...keys].filter(selectable));

  const select = (k: CellKey, mode: "set" | "extend" | "toggle") => {
    if (mode === "extend" && anchor) setSel(keepSelectable(block(people, days, anchor, k)));
    else if (mode === "toggle") {
      if (selectable(k)) setSel((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
    } else { setSel(keepSelectable([k])); setAnchor(k); }
    setFocus(k);
  };

  return { win, sel, setSel, anchor, setAnchor, focus, setFocus, editing, setEditing, people, days, shownDays,
           rowOf, cellEntries, leaveAt, editable, selectable, keepSelectable, snapshot, pushUndo, mutate, undoLast, load, showBar, hideBar, fail, reorder, select };
}

/** The top bar's "Notify staff (n)" follows the server's count. */
function setUnnotified(n: number) {
  document.querySelectorAll("[data-unnotified]").forEach((el) => { el.textContent = String(n); });
  const btn = document.getElementById("notify-staff");
  if (btn) btn.classList.toggle("is-hidden", n === 0);
}

export type GridState = ReturnType<typeof useGridState>;


export function RotaGrid(props: GridProps) {
  const g = useGridState(props);
  const { win, sel, focus, editing, people, days, shownDays } = g;
  const table = useRef<HTMLDivElement>(null);
  // The editor can be left three ways at once (Enter, then the blur its
  // removal causes; Escape, then the blur); the ref makes the first one win.
  const editingRef = useRef(editing);
  editingRef.current = editing;
  const [menu, setMenu] = useState<{ x: number; y: number; key: CellKey } | null>(null);
  const sort = useSort(g, props.api, props.reorder === "1");
  // In sort mode the cells are inert: no selection, no menu, no editing.
  const canEdit = !!win?.can_edit && !sort.on;
  const act = selectionActions(g);
  const focusGrid = () => table.current?.focus();
  const mouse = useMouse(g, focusGrid);

  const setEdit = (next: { key: CellKey; text: string } | null) => { editingRef.current = next; g.setEditing(next); };
  const startEdit = (k: CellKey, seed = "") => {
    if (!g.editable(k) || g.leaveAt(k)?.status === "approved") return;
    setEdit({ key: k, text: seed || g.cellEntries(k).map((e) => e.line).join("\n") });
  };
  const cancelEdit = () => { setEdit(null); focusGrid(); };
  const commitEdit = async (refocus: boolean) => {
    const cur = editingRef.current;
    if (!cur) return;
    setEdit(null);
    if (refocus) focusGrid();
    const [person, date] = split(cur.key);
    if (cur.text.trim() === g.cellEntries(cur.key).map((e) => e.line).join("\n").trim()) return; // nothing changed
    const saved = await g.mutate("cell/", { person, day: date, text: cur.text }, g.snapshot([cur.key]));
    if (!saved) setEdit(cur); // not saved: give the typing back rather than lose it
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

  // Keep the focused cell in view as the keyboard moves it.
  useEffect(() => {
    if (!focus) return;
    table.current?.querySelector(`[data-cell="${focus}"]`)?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [focus]);

  // The top bar's Templates link is outside the island and has no idea which
  // cell is selected: tell it just before modal.js reads its href.
  const anchor = act.anchorCell();
  useEffect(() => {
    const on = (e: MouseEvent) => {
      const link = (e.target as Element | null)?.closest?.("[data-grid-templates]");
      if (!link) return;
      const base = (link.getAttribute("href") ?? "").split("?")[0];
      link.setAttribute("href", anchor ? `${base}?cell=${encodeURIComponent(anchor)}&row_order=${people.join(",")}` : base);
    };
    document.addEventListener("click", on, true);
    return () => document.removeEventListener("click", on, true);
  }, [anchor, people]);

  // Those two dialogs act on the selection but open on a short URL (a whole
  // block in a query string overflows the server's request line): when a
  // dialog arrives with its hidden field empty, fill it from the selection.
  const fillDialog = useRef<(dialog: Element) => void>(() => {});
  fillDialog.current = (dialog) => {
    const fill = (name: string, value: () => string | undefined) => {
      const input = dialog.querySelector<HTMLInputElement>(`input[name="${name}"]`);
      if (input && !input.value) input.value = value() ?? "";
    };
    fill("block", () => { const made = act.block(); return made ? JSON.stringify(made.block) : undefined; });
    fill("cells", () => act.selKeys().join(","));
  };
  useEffect(() => {
    const on = (e: Event) => fillDialog.current((e as CustomEvent<Element>).detail);
    document.addEventListener("shift-central:mounted", on);
    return () => document.removeEventListener("shift-central:mounted", on);
  }, []);

  const openMenu = (k: CellKey, x: number, y: number) => {
    if (!canEdit || !(g.selectable(k) || g.leaveAt(k))) return;
    // A day of approved leave is not selectable: the menu opens there with
    // only the leave items, and the selection is left as it was.
    if (!g.selectable(k)) g.setFocus(k);
    else if (!sel.has(k)) g.select(k, "set");
    setMenu({ x, y, key: k });
  };
  const openMenuAtFocus = () => {
    const box = focus ? table.current?.querySelector(`[data-cell="${focus}"]`)?.getBoundingClientRect() : null;
    if (focus && box) openMenu(focus, box.left + box.width / 2, box.top + box.height / 2);
  };
  // Back to the grid, unless the click that closed the menu already put focus somewhere else.
  const closeMenu = useCallback(() => {
    setMenu(null);
    const at = document.activeElement;
    if (!at || at === document.body || at.closest(".rota-menu")) table.current?.focus();
  }, []);

  const onKey = (e: KeyboardEvent) => handleKey(e, {
    editing: () => editingRef.current, canEdit, focus, move, dayCount: days.length, singleCell: sel.size === 1,
    selectNone: () => g.setSel(new Set()), startEdit, commitEdit, cancelEdit,
    typeIntoEdit: (text) => { if (editingRef.current) setEdit({ ...editingRef.current, text }); },
    clear: act.clear, undo: g.undoLast, cut: act.cut, copy: act.copy, openMenu: openMenuAtFocus,
  });

  // Ctrl-V and the browser's own Paste arrive here with the clipboard's text,
  // which needs no permission, unlike reading the clipboard ourselves.
  const onPaste = (e: ClipboardEvent) => {
    if (!canEdit || editingRef.current || (e.target as HTMLElement).closest("textarea, input")) return;
    e.preventDefault();
    void act.paste(e.clipboardData?.getData("text") ?? "");
  };

  if (!win) return <div class="rota-loading">Loading the rota…</div>;
  const o = win.options;
  const cls = ["rota-grid", `is-${o.font_size}`, `is-${o.spacing}`, o.float_headers && "is-float", canEdit && "can-edit", sort.on && "is-sorting"].filter(Boolean).join(" ");
  const pick = (cells: CellKey[]) => { g.setSel(g.keepSelectable(cells)); g.setFocus(cells[0] ?? null); };

  return (
    <>
      <div class="rota-wrap" ref={table} tabIndex={0} onKeyDown={onKey} onPaste={onPaste}>
        <table class={cls} role="grid" aria-label="Rota">
          <thead><tr>
            <th class="rota-name-head"></th>
            {shownDays.map((d) => (
              <th key={d.date} class={[d.today && "is-today", d.weekend && "is-weekend"].filter(Boolean).join(" ")}
                  onClick={sort.on ? undefined : () => pick(win.rows.map((r) => key(r.person, d.date)))}>
                {d.label}
              </th>
            ))}
          </tr></thead>
          <tbody>
            {win.rows.map((r) => (
              <tr key={r.person} data-person={r.person} class={r.editable ? "" : "is-readonly"} {...(sort.on ? sort.rowProps(r.person) : {})}>
                <th class="rota-name" scope="row"
                    onClick={sort.on ? undefined : (e) => { if (!(e.target as HTMLElement).closest("a")) pick(shownDays.map((d) => key(r.person, d.date))); }}>
                  {sort.on ? <span class="rota-handle" title="Drag to reorder" {...sort.handleProps(r.person)}>≡</span> : null}
                  <a href={`/staff/${r.person}/profile/`} data-dialog tabIndex={-1} class={o.staff_colours ? "chip" : "rota-plain-name"} style={o.staff_colours ? { background: r.colour } : {}}>{r.name}</a>
                  {o.job_titles && r.job_title ? <div class="rota-job">{r.job_title}</div> : null}
                </th>
                {shownDays.map((d) => {
                  const k = key(r.person, d.date);
                  const entries = r.cells[d.date] ?? [];
                  const sessions = r.sessions[d.date] ?? [];
                  const leave = r.leave?.[d.date];
                  const isEditing = editing?.key === k;
                  const picked = sel.has(k) && g.selectable(k);
                  const dropping = mouse.dropCells?.has(k);
                  return (
                    <td key={k} role="gridcell" aria-selected={picked} data-cell={k}
                        class={[picked && "is-selected", focus === k && "is-focus", d.today && "is-today", leave && leave.status === "approved" && "is-leave", overlaps(entries) && "has-overlap",
                                dropping && (mouse.dropOk ? "is-drop" : "is-nodrop")].filter(Boolean).join(" ")}
                        title={overlaps(entries) ? "These shifts overlap" : undefined}
                        onMouseDown={sort.on ? undefined : (e) => mouse.onDown(k, e)}
                        onMouseEnter={sort.on ? undefined : () => mouse.onEnter(k)}
                        onContextMenu={sort.on ? undefined : (e) => {
                          // inside the editor (or while one is open) the browser's own menu is the right one
                          if (editingRef.current || (e.target as Element).closest("textarea")) return;
                          e.preventDefault(); openMenu(k, e.clientX, e.clientY);
                        }}
                        onDblClick={sort.on ? undefined : (e) => { if (!(e.target as Element).closest("textarea")) startEdit(k); }}>
                      {leave ? <LeaveTile leave={leave} /> : null}
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
      {/* Outside the wrap, so its keys and clicks are not the grid's. */}
      {menu ? <Menu x={menu.x} y={menu.y} onClose={closeMenu}
                    items={menuItems(g, act, menu.key, (k, seed) => startEdit(k, seed))} /> : null}
    </>
  );
}
