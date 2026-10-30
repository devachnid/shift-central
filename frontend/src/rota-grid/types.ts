export type Kind = "shift" | "comment" | "separator";
export type Overtime = "" | "paid" | "toil";

export interface Appearance {
  bg?: string; fg?: string; bold?: boolean; italic?: boolean; underline?: boolean;
  strike?: boolean; wrap?: boolean; size?: "sm" | "md" | "lg";
}

/** What the server stores and sends back for one item in a cell. */
export interface EntryJson {
  id: number; kind: Kind; start: string | null; finish: string | null; break_minutes: number;
  department: number | null; department_name: string; department_colour: string | null;
  text: string; overtime: Overtime; wfh: boolean; appearance: Appearance; hours: number; line: string;
}

/** An item as the parser, the clipboard and cell/items/ carry it. */
export interface Item {
  kind: Kind; start?: string; finish?: string; break_minutes?: number; department?: number | null;
  text?: string; wfh?: boolean; overtime?: Overtime; appearance?: Appearance;
}

export interface SessionJson { part: string; label: string; site: string; note: string }
export interface DayJson { date: string; label: string; today: boolean; weekend: boolean }
export interface Department { id: number; name: string; colour: string }
export interface Shape { start: string; finish: string; break_minutes: number; department: number | null; label: string }

export interface Row {
  person: number; name: string; colour: string; job_title: string; team: string; is_gp: boolean;
  editable: boolean; cells: Record<string, EntryJson[]>; sessions: Record<string, SessionJson[]>;
}

export interface Options {
  staff_colours: boolean; job_titles: boolean; department_colours: boolean; float_headers: boolean;
  my_shifts_on_top: boolean; only_my_shifts: boolean; hide_no_shifts: boolean;
  font_size: "sm" | "md" | "lg"; spacing: "tight" | "normal" | "loose"; days: number[]; paste: "replace" | "add";
}

export interface WindowJson {
  from: string; weeks: number; days: DayJson[]; rows: Row[]; departments: Department[];
  common: Shape[]; recent: Shape[]; options: Options; unnotified: number; can_edit: boolean;
}

export interface Changed { cells: Record<string, Record<string, EntryJson[]>>; skipped: number; unnotified: number }
/** A block cell is its items, or null for a day the copy did not see (hidden
 *  in the grid): pasting leaves the target there alone, where [] clears it. */
export type BlockCell = Item[] | null;
export interface Block { days: number; rows: BlockCell[][] }

export const toItem = (e: EntryJson): Item => ({
  kind: e.kind, start: e.start ?? undefined, finish: e.finish ?? undefined, break_minutes: e.break_minutes,
  department: e.department, text: e.text, wfh: e.wfh, overtime: e.overtime, appearance: e.appearance,
});
