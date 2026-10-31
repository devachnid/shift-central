/** The right-click menu's contents, in FindMyShift's order. */
import { shapeItem, type Actions } from "./actions";
import type { GridState } from "./grid";
import { leaveMenuItems } from "./leave";
import { departmentItems, shapeItems, swatches, type MenuItem } from "./menu";
import { key, split, weekOf, type CellKey } from "./selection";

const BREAKS = [0, 15, 30, 45, 60];
const breakLabel = (m: number) => (m === 0 ? "None" : m === 60 ? "1 hour" : `${m} minutes`);
const SIZES = [["sm", "Small"], ["md", "Normal"], ["lg", "Large"]] as const;

export function menuItems(g: GridState, act: Actions, k: CellKey, editCell: (k: CellKey, seed: string) => void): MenuItem[] {
  const [p, d] = split(k);
  const leave = g.leaveAt(k);
  const leaveItems = leaveMenuItems(leave, !!g.rowOf(p)?.editable, p, d);
  // Leave on a cell the viewer cannot select (approved leave, or any leave on
  // a read-only row) gets only the leave items: nothing else may act on it.
  if (leave && !g.selectable(k)) return leaveItems;

  const win = g.win!;
  const colours = swatches();
  const selectCells = (keys: CellKey[]) => g.setSel(g.keepSelectable(keys));
  const column = (day: string) => g.people.map((pp) => key(pp, day));
  const first = g.rowOf(p)?.name.split(" ")[0] ?? "";
  const palette = (pick: (hex: string | undefined) => void, none: string): MenuItem[] => [
    ...colours.map((hex) => ({ label: hex, swatch: hex, action: () => pick(hex) })),
    { label: none, action: () => pick(undefined) },
  ];

  return [
    ...leaveItems,
    { label: "Add", children: [
      { label: "Shift…", href: `/rota/shift/${p}/${d}/` },
      // A new line in the cell's editor; what is typed there is parsed like any cell.
      { label: "Comment", action: () => editCell(k, g.cellEntries(k).map((e) => e.line).concat("").join("\n")) },
      { label: "Separator", action: () => act.addItems([{ kind: "separator" }]) },
      { label: "Department", children: departmentItems(win.departments, (id) => act.patchShifts({ department: id })) },
      { label: "Break", children: BREAKS.map((m) => ({ label: breakLabel(m), action: () => act.patchShifts({ break_minutes: m }) })) },
      { label: "Common", children: shapeItems(win.common, (s) => act.addItems([shapeItem(s)])) },
      { label: "Recent", children: shapeItems(win.recent, (s) => act.addItems([shapeItem(s)])) },
      { label: "Overtime", children: [
        { label: "None", action: () => act.patchShifts({ overtime: "" }) },
        { label: "Paid", action: () => act.patchShifts({ overtime: "paid" }) },
        { label: "TOIL", action: () => act.patchShifts({ overtime: "toil" }) },
      ] },
      { label: "WFH", action: act.toggleWfh },
    ] },
    { label: "Appearance", children: [
      { label: "Background", palette: true, children: palette((bg) => act.appearance({ bg }), "None") },
      { label: "Text colour", palette: true, children: palette((fg) => act.appearance({ fg }), "Default") },
      { label: "Bold", action: () => act.toggleAppearance("bold") },
      { label: "Underline", action: () => act.toggleAppearance("underline") },
      { label: "Italic", action: () => act.toggleAppearance("italic") },
      { label: "Strikethrough", action: () => act.toggleAppearance("strike") },
      { label: "Wrap text", action: () => act.toggleAppearance("wrap") },
      { label: "Font size", children: SIZES.map(([size, label]) => ({ label, action: () => act.appearance({ size }) })) },
      { label: "Reset appearance", action: act.resetAppearance },
    ] },
    // The dialogs open on a short URL; the grid fills in the selection (see fillDialog in grid.tsx).
    { label: "Find & Replace…", href: "/rota/replace/" },
    { label: "Cut", action: act.cut },
    { label: "Copy", action: () => { act.copy(); } },
    { label: "Paste", action: act.pasteFromMenu },
    { label: "Delete", action: act.clear },
    { label: "Select", children: [
      { label: "Row", action: () => selectCells(g.days.map((dd) => key(p, dd))) },
      { label: "Column", action: () => selectCells(column(d)) },
      { label: "Week", action: () => selectCells(weekOf(g.days, d).flatMap(column)) },
      { label: "All", action: () => selectCells(g.days.flatMap(column)) },
    ] },
    { label: "Save selection as template…", href: "/rota/templates/save/" },
    { label: "Print", action: () => window.print() },
    { label: `Message ${first}`.trim(), disabled: true, note: "coming later" },
  ];
}
