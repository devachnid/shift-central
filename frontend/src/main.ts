import { register, mountAll } from "./registry";
import { ColourPicker } from "./colour-picker";
import { RotaGridIsland } from "./rota-grid/index";

register("colour-picker", ColourPicker as never);
register("rota-grid", RotaGridIsland as never);
mountAll();
document.addEventListener("shift-central:mounted", (e) => mountAll((e as CustomEvent).detail ?? document));
