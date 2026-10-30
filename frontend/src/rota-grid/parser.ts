/** Free-typed cell text into items: the mirror of shifts/services/parse.py,
 *  kept in step with it. parser.cases.json is the contract both are tested
 *  against; when a rule changes, change both and add a row. */
import type { Department, Item, Overtime } from "./types";

// 'am'/'pm' only counts as a marker when no word character follows, so
// '9-5 amazing' is not 9-5am. Digits are [0-9], as in parse.py, where \d
// would be any Unicode digit.
const SIDE = (p: string) => `(?<${p}h>[0-9]{1,2})(?:[:.]?(?<${p}m>[0-9]{2}))?\\s*(?<${p}ap>(?:am|pm)(?!\\w))?`;
const RANGE_SOURCE = `(?<![0-9:.])${SIDE("a")}\\s*(?:-|–|—|to|until)\\s*${SIDE("b")}(?![0-9])(?![:.][0-9])`;
const SEPARATOR = /^\s*-{3,}\s*$/;
// The word 'break' is required on the hour and minute forms, so
// '1 hour training' stays a comment; only the bare 'N m' shorthand stands alone.
const BREAK_SOURCE =
  "(?<!\\w)(?:(?<h>[0-9]+)\\s*(?:hours?|hrs?|h)\\s+break" +
  "|(?<m>[0-9]+)\\s*(?:minutes?|mins?)\\s+break" +
  "|break\\s+(?<n>[0-9]+)" +
  "|(?<s>[0-9]+)\\s*m)(?!\\w)";
const WFH_SOURCE = "(?<!\\w)wfh(?!\\w)";
const TOIL = /(?<!\w)toil(?!\w)/i;
const PAID = /(?<!\w)(?:ot paid|overtime paid|paid overtime|ot)(?!\w)/i;
const BREAKS = [0, 15, 30, 45, 60];

type Time = [number, number];

function hm(h: string, m: string | undefined, ap: string | undefined): Time | null {
  let hour = parseInt(h, 10);
  const minute = m ? parseInt(m, 10) : 0;
  if (hour > 23 || minute > 59) return null;
  const marker = (ap || "").toLowerCase();
  if (marker === "pm" && hour < 12) hour += 12;
  if (marker === "am" && hour === 12) hour = 0;
  return [hour, minute];
}

const pad = (n: number) => String(n).padStart(2, "0");
const fmt = (t: Time) => `${pad(t[0])}:${pad(t[1])}`;
const minutes = (t: Time) => t[0] * 60 + t[1];

/** The two times, or null. A finish with no am/pm that is not after a start
 *  before 13:00 is read as pm (8-4 is 08:00-16:00, 12:30-1 is 12:30-13:00); a
 *  start at or after 13:00 is 24-hour, so 16:00-08:00 is not a shift. A start
 *  with no marker, before noon, under a pm finish is read as pm too when that
 *  still ends before the finish (1-5pm is 13:00-17:00; 8-4pm stays
 *  08:00-16:00). If the finish still is not after the start, it is not a
 *  shift either. */
function range(g: Record<string, string | undefined>): [string, string] | null {
  let start = hm(g.ah!, g.am, g.aap);
  let finish = hm(g.bh!, g.bm, g.bap);
  if (!start || !finish) return null;
  if (!g.bap && start[0] < 13 && minutes(finish) <= minutes(start) && finish[0] < 12) finish = [finish[0] + 12, finish[1]];
  if (g.bap && !g.aap && start[0] < 12) {
    const pmStart: Time = [start[0] + 12, start[1]];
    if (minutes(pmStart) < minutes(finish)) start = pmStart;
  }
  if (minutes(finish) <= minutes(start)) return null;
  return [fmt(start), fmt(finish)];
}

/** The first range in the text that reads as a shift, with its times. Ranges
 *  that do not read are left in the text as comment. */
function firstRange(text: string): { index: number; length: number; times: [string, string] } | null {
  for (const m of text.matchAll(new RegExp(RANGE_SOURCE, "gi"))) {
    const times = range(m.groups!);
    if (times) return { index: m.index!, length: m[0].length, times };
  }
  return null;
}

/** The break in minutes and the text without it, or 0 and the text
 *  unchanged when the length is not one ROTA-01 allows. */
function takeBreak(rest: string): [number, string] {
  for (const m of rest.matchAll(new RegExp(BREAK_SOURCE, "gi"))) {
    const g = m.groups!;
    const mins = g.h ? parseInt(g.h, 10) * 60 : parseInt(g.m || g.n || g.s, 10);
    if (BREAKS.includes(mins)) return [mins, rest.slice(0, m.index) + " " + rest.slice(m.index! + m[0].length)];
  }
  return [0, rest];
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** The longest department name present as a whole phrase, and the text
 *  without it. */
function takeDepartment(rest: string, departments: Department[]): [number | null, string] {
  for (const d of [...departments].sort((a, b) => b.name.length - a.name.length)) {
    const m = new RegExp(`(?<!\\w)${escape(d.name)}(?!\\w)`, "i").exec(rest);
    if (m) return [d.id, rest.slice(0, m.index) + " " + rest.slice(m.index + m[0].length)];
  }
  return [null, rest];
}

/** Whitespace collapsed and cut at 200 characters (code points, as Python
 *  counts them): a comment line as typed. */
const comment = (text: string) => [...text.split(/\s+/).filter(Boolean).join(" ")].slice(0, 200).join("");

/** What is left of a shift line once its parts are taken out, with the
 *  punctuation left at either end dropped. Only a shift's leftover is
 *  tidied: a pure comment such as 'OFF.' or '...' keeps what was typed. */
const leftover = (text: string) => comment(text).replace(/^[ ,.:;]+|[ ,.:;]+$/g, "");

/** Runs of whitespace collapsed (and the ends trimmed) before matching, as
 *  the server does, so the range pattern cannot backtrack on a long run. */
const collapse = (text: string) => text.split(/\s+/).filter(Boolean).join(" ");

export function parseLine(text: string, departments: Department[]): Item {
  text = collapse(text);
  if (SEPARATOR.test(text)) return { kind: "separator" };
  const found = firstRange(text);
  if (!found) return { kind: "comment", text: comment(text) };
  let rest = text.slice(0, found.index) + " " + text.slice(found.index + found.length);
  let break_minutes: number;
  [break_minutes, rest] = takeBreak(rest);
  const wfh = new RegExp(WFH_SOURCE, "i").test(rest);
  rest = rest.replace(new RegExp(WFH_SOURCE, "gi"), " ");
  let overtime: Overtime = "";
  if (TOIL.test(rest)) { overtime = "toil"; rest = rest.replace(TOIL, " "); }
  else if (PAID.test(rest)) { overtime = "paid"; rest = rest.replace(PAID, " "); }
  let department: number | null;
  [department, rest] = takeDepartment(rest, departments);
  return { kind: "shift", start: found.times[0], finish: found.times[1], break_minutes, department, text: leftover(rest), wfh, overtime };
}

export function parseCell(text: string, departments: Department[]): Item[] {
  return text.split(/\r?\n/).filter((l) => l.trim()).map((l) => parseLine(l, departments));
}

/** The canonical line, as shifts/services/render.py writes it. */
export function renderLine(item: Item, departments: Department[]): string {
  if (item.kind === "separator") return "---";
  if (item.kind === "comment") return item.text || "";
  const parts = [`${item.start}-${item.finish}`];
  if (item.break_minutes === 60) parts.push("1 hour break");
  else if (item.break_minutes) parts.push(`${item.break_minutes} min break`);
  const dept = departments.find((d) => d.id === item.department);
  if (dept) parts.push(dept.name);
  if (item.wfh) parts.push("WFH");
  if (item.overtime) parts.push(item.overtime === "paid" ? "OT paid" : "TOIL");
  if (item.text) parts.push(item.text);
  return parts.join(" ");
}
