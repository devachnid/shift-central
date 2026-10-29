import { register, mountAll } from "./registry";
import { ColourPicker } from "./colour-picker";

register("colour-picker", ColourPicker as never);
mountAll();
document.addEventListener("shift-central:mounted", (e) => mountAll((e as CustomEvent).detail ?? document));
