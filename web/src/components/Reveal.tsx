import { useEffect, useState } from "react";

interface Props extends React.HTMLAttributes<HTMLElement> {
  children: React.ReactNode;
  delay?: number;
  as?: "div" | "section" | "li" | "header";
}

/** Reveal-on-scroll, one IntersectionObserver per element.
 *
 * Per-element rather than one shared observer because the pages have a few
 * dozen reveals, not a few thousand, and a shared observer would need a
 * WeakMap of callbacks for no measurable gain. Each observer disconnects the
 * moment it fires: these are entrances, and re-hiding content on scroll-up is
 * the single most irritating version of this effect.
 */
export function Reveal({ children, delay = 0, as: Tag = "div", className, style, ...rest }: Props) {
  // The observed element is held in *state*, not a ref, and the effect depends
  // on it. A ref plus `[]` deps looks equivalent and is not: sibling Reveals
  // that appear conditionally are matched by position and type, so React hands
  // a mounted instance a different DOM node, the ref quietly updates, and the
  // effect -- which never re-runs -- keeps observing the node it first saw.
  // The symptom is one card that stays invisible forever, and it only shows up
  // once the data it is gated on arrives after first paint.
  const [node, setNode] = useState<HTMLElement | null>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setShown(true);
        observer.disconnect();
      },
      // Fires a little before the element is fully on screen, so the animation
      // is already finishing by the time it reaches comfortable reading height.
      { rootMargin: "0px 0px -12% 0px", threshold: 0.08 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [node]);

  return (
    <Tag
      ref={setNode as never}
      className={["reveal", shown && "is-in", className].filter(Boolean).join(" ")}
      style={{ ["--reveal-delay" as string]: `${delay}ms`, ...style } as React.CSSProperties}
      {...rest}
    >
      {children}
    </Tag>
  );
}
