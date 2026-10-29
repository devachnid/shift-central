import { h, render, type ComponentType } from "preact";

type Props = Record<string, string>;
const components = new Map<string, ComponentType<Props>>();

export function register(name: string, component: ComponentType<Props>) {
  components.set(name, component);
}

/** Mount every [data-component] under root whose name is registered,
 *  passing its data-* attributes as props. Called on load and after a
 *  dialog is fetched (modal.js dispatches "shift-central:mounted"). */
export function mountAll(root: ParentNode = document) {
  root.querySelectorAll<HTMLElement>("[data-component]").forEach((el) => {
    if (el.dataset.mounted) return;
    const component = components.get(el.dataset.component ?? "");
    if (!component) return;
    el.dataset.mounted = "1";
    render(h(component, { ...el.dataset } as Props), el);
  });
}
