import { useEffect, useState } from "preact/hooks";
import { RotaGrid, type GridProps } from "./grid";
import "../rota-grid.css";

const QUERY = "(min-width: 768px)";

/** Mounts the grid only at desktop widths; the phone list is server HTML
 *  shown by CSS below that. The registry hands every data-* over as a
 *  string, so the numbers are converted here. */
export function RotaGridIsland(p: Record<string, string>) {
  const [wide, setWide] = useState(() => matchMedia(QUERY).matches);
  useEffect(() => {
    const mq = matchMedia(QUERY);
    const on = () => setWide(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  const props: GridProps = {
    from: p.from, weeks: Number(p.weeks || 1), filters: p.filters || "", api: p.api, role: p.role,
    me: p.me || "", reorder: p.reorder || "", bar: p.bar,
  };
  return wide ? <RotaGrid {...props} /> : null;
}
