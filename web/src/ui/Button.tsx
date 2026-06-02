import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "default" | "outline" | "secondary" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  full?: boolean;
  children: ReactNode;
}

/** Token-driven button (Evidentia .btn family). */
export function Button({
  variant = "default",
  size = "md",
  full = false,
  className,
  type = "button",
  children,
  ...rest
}: ButtonProps) {
  const classes = ["btn", variant];
  if (size === "sm") classes.push("sm");
  if (size === "lg") classes.push("lg");
  if (full) classes.push("full");
  if (className) classes.push(className);
  return (
    <button type={type} className={classes.join(" ")} {...rest}>
      {children}
    </button>
  );
}

export default Button;
