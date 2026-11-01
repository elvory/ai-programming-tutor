import type { PointerEvent } from "react";

interface Props {
  direction?: "horizontal" | "vertical";
  label: string;
  value: number;
  onChange: (delta: number) => void;
}
export function SplitHandle({
  direction = "horizontal",
  label,
  value,
  onChange,
}: Props) {
  const vertical = direction === "vertical";
  function start(event: PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const parent = element.parentElement;
    if (!parent) return;
    element.setPointerCapture(event.pointerId);
    let previous = vertical ? event.clientY : event.clientX;
    const size = vertical
      ? parent.getBoundingClientRect().height
      : parent.getBoundingClientRect().width;
    const move = (moveEvent: globalThis.PointerEvent) => {
      const current = vertical ? moveEvent.clientY : moveEvent.clientX;
      onChange(((current - previous) / size) * 100);
      previous = current;
    };
    const end = () => {
      element.removeEventListener("pointermove", move);
      element.removeEventListener("pointerup", end);
      element.removeEventListener("pointercancel", end);
    };
    element.addEventListener("pointermove", move);
    element.addEventListener("pointerup", end);
    element.addEventListener("pointercancel", end);
  }
  return (
    <div
      className={`split-handle ${vertical ? "split-vertical" : ""}`}
      role="separator"
      tabIndex={0}
      aria-label={label}
      aria-orientation={vertical ? "horizontal" : "vertical"}
      aria-valuenow={Math.round(value)}
      onPointerDown={start}
      onKeyDown={(event) => {
        if (
          ["ArrowLeft", "ArrowUp", "ArrowRight", "ArrowDown"].includes(
            event.key,
          )
        ) {
          event.preventDefault();
          onChange(["ArrowLeft", "ArrowUp"].includes(event.key) ? -2 : 2);
        }
      }}
    >
      <span />
    </div>
  );
}
