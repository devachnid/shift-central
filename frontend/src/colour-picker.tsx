import { useEffect, useState } from "preact/hooks";
import "./colour-picker.css";

/** The swatch grid and hex field for a person's name colour and a
 *  department's colour. Writes to the hidden input named by data-input;
 *  data-label names the field's <label>, which titles the swatch group.
 *
 *  The swatches are a group of toggle buttons (aria-pressed), not a
 *  listbox: each is a plain button that Tab reaches and Enter or Space
 *  presses, so no arrow-key handling is owed. */
export function ColourPicker({ input, label }: { input: string; label?: string }) {
  const target = document.getElementById(input) as HTMLInputElement | null;
  const swatches = getComputedStyle(document.documentElement)
    .getPropertyValue("--swatches").split(",").map((s) => s.trim()).filter(Boolean);
  const [value, setValue] = useState(target?.value || swatches[0] || "#143D5C");

  // The picker shows a selected colour at once, so the hidden input (which
  // the form posts) must carry it too, or a new department posts nothing.
  useEffect(() => { if (target && !target.value) target.value = value; }, []);

  function choose(hex: string) {
    setValue(hex);
    if (target) target.value = hex;
  }

  return (
    <div class="colour-picker">
      <div class="colour-picker-swatches" role="group" aria-labelledby={label}>
        {swatches.map((hex) => (
          <button type="button" aria-pressed={hex.toUpperCase() === value.toUpperCase()} aria-label={hex}
                  class="colour-picker-swatch" style={{ background: hex }} title={hex}
                  onClick={() => choose(hex)} />
        ))}
      </div>
      <label class="colour-picker-hex">
        <span class="colour-picker-preview" style={{ background: value }} />
        <input type="text" value={value} maxLength={7} pattern="#[0-9a-fA-F]{6}" aria-label="Hex colour"
               onInput={(e) => { const v = (e.target as HTMLInputElement).value; if (/^#[0-9a-fA-F]{6}$/.test(v)) choose(v); }} />
      </label>
    </div>
  );
}
