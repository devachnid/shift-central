import { useEffect, useState } from "preact/hooks";
import "./colour-picker.css";

/** The swatch grid and hex field for a person's name colour and a
 *  department's colour. Writes to the hidden input named by data-input. */
export function ColourPicker({ input }: { input: string }) {
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
      <div class="colour-picker-swatches" role="listbox" aria-label="Colour">
        {swatches.map((hex) => (
          <button type="button" role="option" aria-selected={hex.toUpperCase() === value.toUpperCase()}
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
