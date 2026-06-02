import type { CSSProperties, ReactNode } from "react";

export interface BadgeProps {
  /**
   * Solid color for the badge (any CSS color — hex, hsl(), or a var()). Drives
   * a tinted background + matching text + (optional) leading dot. When omitted,
   * the badge uses the neutral surface treatment. OutcomeBadge passes the
   * outcome→color / risk→color values from lib/outcomes.ts.
   */
  color?: string;
  /** Solid fill (white text on the full color) instead of the tinted default. */
  solid?: boolean;
  /** Show a leading status dot in the badge color. */
  dot?: boolean;
  /** Capitalize the label (engine outcomes arrive lower_snake). */
  capitalize?: boolean;
  className?: string;
  title?: string;
  children: ReactNode;
}

/**
 * Thin, token-driven badge. The tinted look mirrors the Evidentia severity
 * badges (12–15% color background, full-strength color text, subtle border).
 * `color` is applied via inline custom properties so callers can pass any
 * engine-semantic color without a class explosion.
 */
export function Badge({
  color,
  solid = false,
  dot = false,
  capitalize = false,
  className,
  title,
  children,
}: BadgeProps) {
  const style: CSSProperties & Record<string, string> = {};
  if (color) {
    if (solid) {
      style.background = color;
      style.color = "#fff";
      style.borderColor = color;
    } else {
      // Tinted treatment: low-opacity fill + full-strength text. color-mix keeps
      // the tint relative to the passed color and works for hex/hsl/var alike.
      style.background = `color-mix(in srgb, ${color} 14%, transparent)`;
      style.color = color;
      style.borderColor = `color-mix(in srgb, ${color} 32%, transparent)`;
    }
    style["--badge-dot"] = color;
  }

  const classes = ["badge"];
  if (dot) classes.push("dot");
  if (capitalize) classes.push("cap");
  if (className) classes.push(className);

  return (
    <span className={classes.join(" ")} style={style} title={title}>
      {children}
    </span>
  );
}

export default Badge;
