import { useEffect, useRef, useState } from "react";

/** Counts a number up when it first scrolls into view.
 *
 * Driven by requestAnimationFrame against a wall-clock start rather than a
 * fixed per-frame increment, so the duration is the same on a 60Hz and a 120Hz
 * display and a backgrounded tab does not finish the count at the wrong speed.
 * Eased out, because a linear count reads as a loading spinner rather than a
 * value arriving.
 */
export function CountUp({
  to,
  duration = 1400,
  decimals = 0,
  prefix = "",
  suffix = "",
}: {
  to: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [value, setValue] = useState(0);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setValue(to);
      return;
    }

    let frame = 0;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();
        const start = performance.now();
        const step = (now: number) => {
          const t = Math.min(1, Math.max(0, (now - start) / duration));
          setValue(to * (1 - Math.pow(1 - t, 3)));
          if (t < 1) frame = requestAnimationFrame(step);
        };
        frame = requestAnimationFrame(step);
      },
      // Fires on the first visible pixel rather than at 40%: these sit in a
      // grid that is often half on screen, and a tile that shows a flat "0"
      // while you look straight at it reads as a broken number, not as one
      // waiting its turn.
      { threshold: 0 },
    );
    observer.observe(node);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [to, duration]);

  return (
    <span ref={ref} className="mono">
      {prefix}
      {value.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
}
