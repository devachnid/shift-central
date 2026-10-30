/** The right-click menu (spec, section 3): a navy panel with submenus,
 *  closed by Escape, a click away or an action. Items that open a window
 *  are plain data-dialog anchors, so modal.js handles them. */
import type { ComponentChildren } from "preact";
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import type { Department, Shape } from "./types";

export interface MenuItem {
  label: string; action?: () => void; children?: MenuItem[]; disabled?: boolean; note?: string;
  /** A leading colour square (departments) or, in a palette, the whole item. */
  swatch?: string;
  /** A link: a dialog by default, a whole page when `page` is set. */
  href?: string; page?: boolean;
  /** Show the children as a grid of colour squares. */
  palette?: boolean;
}
export interface MenuProps { x: number; y: number; items: MenuItem[]; onClose: () => void }

const MENU_WIDTH = 240, SUB_ROOM = 440;

export function Menu({ x, y, items, onClose }: MenuProps) {
  const ref = useRef<HTMLDivElement>(null);
  // The grid hands a new onClose every render; the listeners must not be
  // re-bound (nor the focus moved) each time it redraws under the menu.
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const away = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) close.current(); };
    // Capture, so the grid and the dialog layer never see the key that closes it.
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); close.current(); } };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc, true);
    ref.current?.querySelector<HTMLElement>("li > :is(button, a):not(:disabled)")?.focus();
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc, true); };
  }, []);
  // Keep the panel on screen, and open submenus leftwards when there is no room to the right.
  const left = Math.max(0, Math.min(x, window.innerWidth - MENU_WIDTH)), top = Math.max(0, Math.min(y, window.innerHeight - 20 - items.length * 28));
  const flip = left > window.innerWidth - SUB_ROOM;
  return (
    <div class={flip ? "rota-menu is-flip" : "rota-menu"} ref={ref} style={{ left, top }} role="menu">
      <List items={items} onClose={onClose} />
    </div>
  );
}

/** Arrow keys: up and down walk a list, right enters a submenu, left leaves it. */
function walk(e: KeyboardEvent, ul: HTMLElement, leave: () => void) {
  const mine = [...ul.children].map((li) => li.querySelector<HTMLElement>(":scope > :is(button, a):not(:disabled)")).filter((el): el is HTMLElement => !!el);
  const at = mine.indexOf(document.activeElement as HTMLElement);
  if (e.key === "ArrowDown") mine[(at + 1) % mine.length]?.focus();
  else if (e.key === "ArrowUp") mine[(at - 1 + mine.length) % mine.length]?.focus();
  else if (e.key === (document.dir === "rtl" ? "ArrowRight" : "ArrowLeft")) leave();
  else return false;
  return true;
}

function List({ items, onClose, palette = false, leave }: { items: MenuItem[]; onClose: () => void; palette?: boolean; leave?: () => void }) {
  const [open, setOpen] = useState<number | null>(null);
  const ul = useRef<HTMLUListElement>(null);
  const enter = useRef(false); // a keyboard opening focuses the submenu's first item
  return (
    <ul ref={ul} class={palette ? "is-palette" : undefined} onKeyDown={(e) => {
      const i = items.findIndex((_, n) => ul.current?.children[n]?.contains(e.target as Node));
      if (e.key === "ArrowRight" && items[i]?.children) { e.preventDefault(); e.stopPropagation(); enter.current = true; setOpen(i); return; }
      if (walk(e, ul.current!, () => { if (leave) { e.stopPropagation(); leave(); } })) { e.preventDefault(); e.stopPropagation(); }
    }}>
      {items.map((it, i) => {
        const cls = [it.children && "has-sub", it.disabled && "is-disabled", palette && !it.swatch && "is-wide"].filter(Boolean).join(" ");
        return (
          <li key={i} class={cls} onMouseEnter={() => { enter.current = false; setOpen(it.children ? i : null); }}>
            {it.href ? (
              <a href={it.href} data-dialog={it.page ? undefined : ""} role="menuitem" onClick={() => setTimeout(onClose, 0)}>{it.label}</a>
            ) : (
              <button type="button" role="menuitem" disabled={it.disabled} aria-haspopup={it.children ? "menu" : undefined}
                      aria-expanded={it.children ? open === i : undefined}
                      class={palette && it.swatch ? "rota-menu-chip" : undefined} title={palette && it.swatch ? it.label : undefined}
                      aria-label={palette && it.swatch ? it.label : undefined}
                      onClick={() => { if (it.children) { enter.current = true; setOpen(i); return; } it.action?.(); onClose(); }}>
                {it.swatch ? <span class="rota-menu-swatch" style={{ background: it.swatch }} /> : null}
                {palette && it.swatch ? null : it.label}{it.note ? <span class="rota-menu-note">{it.note}</span> : null}
              </button>
            )}
            {it.children && open === i ? (
              <Sub focusFirst={enter.current} leaf={!it.children.some((c) => c.children)}>
                <List items={it.children} onClose={onClose} palette={it.palette}
                      leave={() => { setOpen(null); ul.current?.children[i]?.querySelector<HTMLElement>(":scope > button")?.focus(); }} />
              </Sub>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

/** A submenu, nudged up if it would run off the bottom of the window. A list
 *  with no submenus of its own may scroll (a scrolling box would clip theirs). */
function Sub({ children, focusFirst, leaf }: { children: ComponentChildren; focusFirst: boolean; leaf: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [lift, setLift] = useState(0);
  useLayoutEffect(() => {
    const r = ref.current?.getBoundingClientRect();
    if (r && r.bottom > window.innerHeight - 8) setLift(Math.min(r.bottom - window.innerHeight + 8, Math.max(0, r.top - 8)));
    if (focusFirst) ref.current?.querySelector<HTMLElement>("li > :is(button, a):not(:disabled)")?.focus();
  }, []);
  return <div class={leaf ? "rota-menu-sub is-leaf" : "rota-menu-sub"} ref={ref} style={lift ? { marginTop: -lift } : undefined}>{children}</div>;
}

/** The swatches managers pick from: tokens.css lists them once. */
export const swatches = (): string[] =>
  getComputedStyle(document.documentElement).getPropertyValue("--swatches").split(",").map((s) => s.trim()).filter(Boolean);

export const departmentItems = (departments: Department[], pick: (id: number | null) => void): MenuItem[] => [
  ...departments.map((d) => ({ label: d.name, swatch: d.colour, action: () => pick(d.id) })),
  { label: "None", action: () => pick(null) },
  // A page, not a dialog: it leaves the rota.
  { label: "More departments…", href: "/departments/", page: true },
];

export const shapeItems = (shapes: Shape[], pick: (s: Shape) => void): MenuItem[] =>
  shapes.length ? shapes.map((s) => ({ label: s.label, action: () => pick(s) })) : [{ label: "Nothing yet", disabled: true }];
