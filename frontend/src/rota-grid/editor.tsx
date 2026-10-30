import { useEffect, useRef } from "preact/hooks";

/** The in-place editor: Enter saves, Shift-Enter adds a line, Escape
 *  cancels, leaving the cell saves. */
export function CellEditor(p: { text: string; onText: (t: string) => void; onCommit: (refocus: boolean) => void; onCancel: () => void }) {
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
