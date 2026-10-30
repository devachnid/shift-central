/** Sort mode ("Options → Sort staff", ?reorder=1): drag a name's handle onto
 *  another row; the new order is saved, then the page's own load confirms it. */
import { useRef } from "preact/hooks";
import { post } from "./api";
import type { GridState } from "./grid";

export function useSort(g: GridState, api: string, on: boolean) {
  const dragged = useRef<number | null>(null);

  const dropOn = async (target: number) => {
    const from = dragged.current;
    dragged.current = null;
    if (from === null || from === target) return;
    const before = g.people;
    const next = before.filter((p) => p !== from);
    // Moving down puts the row after its target, moving up before it: it takes the target's place.
    next.splice(before.indexOf(target), 0, from);
    g.reorder(next);
    try {
      await post(api, "order/", { people: next });
      await g.load();
    } catch (e) {
      g.reorder(before);
      g.fail(e);
    }
  };

  return {
    on,
    handleProps: (person: number) => ({
      draggable: true,
      onDragStart: (e: DragEvent) => {
        dragged.current = person;
        if (e.dataTransfer) {
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", String(person)); // Firefox starts no drag without data
          const row = (e.currentTarget as HTMLElement).closest("tr");
          if (row) e.dataTransfer.setDragImage(row, 16, 16);
        }
      },
    }),
    rowProps: (person: number) => ({
      onDragOver: (e: DragEvent) => { if (dragged.current !== null) e.preventDefault(); },
      onDrop: (e: DragEvent) => { e.preventDefault(); void dropOn(person); },
    }),
  };
}
