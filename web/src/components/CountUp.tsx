import { useEffect, useRef, useState } from "react";

interface Props {
  value: number;
  decimals?: number;
  suffix?: string;
  duration?: number;
}

/** Animated number for the landing hero only.
 *
 * Counting is decoration, so it is confined to the page that is read once and
 * never applied to a figure in the workbench — a metric that animates whenever
 * it updates is harder to read, not easier. Honours prefers-reduced-motion by
 * jumping straight to the value.
 */
export function CountUp({ value, decimals = 0, suffix = "", duration = 900 }: Props) {
  const [shown, setShown] = useState(0);
  const frame = useRef<number>(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(value);
      return;
    }
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      // Ease-out cubic: fast at first, settles rather than stopping dead.
      setShown(value * (1 - Math.pow(1 - t, 3)));
      if (t < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [value, duration]);

  return (
    <span className="mono">
      {shown.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
}
