import Badge from "../ui/Badge";
import { outcomeColor, outcomeLabel } from "../lib/outcomes";

export interface OutcomeBadgeProps {
  /** Engine outcome string (lower_snake, e.g. "escalate_human_review"). */
  outcome: string;
  /** Render a leading status dot in the outcome color. */
  dot?: boolean;
  /** Solid fill (white text on the full color) instead of the tinted default. */
  solid?: boolean;
  className?: string;
}

/**
 * The engine outcome as a token-driven badge: the outcome→color from
 * lib/outcomes drives the tint, and outcomeLabel humanizes the lower_snake
 * value (e.g. "escalate_human_review" → "Escalate Human Review"). Thin wrapper
 * so every route renders an outcome identically.
 */
export function OutcomeBadge({
  outcome,
  dot = true,
  solid = false,
  className,
}: OutcomeBadgeProps) {
  return (
    <Badge
      color={outcomeColor(outcome)}
      dot={dot}
      solid={solid}
      className={className}
      title={outcome}
    >
      {outcomeLabel(outcome)}
    </Badge>
  );
}

export default OutcomeBadge;
