import type { ReactNode } from "react";

type CardVariant = "default" | "dest" | "prim";

export interface CardProps {
  variant?: CardVariant;
  /** 3px federal-blue top accent (Evidentia card-accent-top). */
  accentTop?: boolean;
  hover?: boolean;
  className?: string;
  children: ReactNode;
}

const VARIANT_CLASS: Record<CardVariant, string> = {
  default: "",
  dest: "border-dest",
  prim: "border-prim",
};

/** Token-driven surface card (Evidentia .card family). */
export function Card({
  variant = "default",
  accentTop = false,
  hover = false,
  className,
  children,
}: CardProps) {
  const classes = ["card"];
  if (VARIANT_CLASS[variant]) classes.push(VARIANT_CLASS[variant]);
  if (accentTop) classes.push("card-accent-top");
  if (hover) classes.push("card-hover");
  if (className) classes.push(className);
  return <div className={classes.join(" ")}>{children}</div>;
}

export function CardHead({
  title,
  desc,
  children,
}: {
  title?: ReactNode;
  desc?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="card-head">
      {title != null && <h3 className="card-title">{title}</h3>}
      {desc != null && <p className="card-desc">{desc}</p>}
      {children}
    </div>
  );
}

export function CardBody({
  children,
  flush = false,
}: {
  children: ReactNode;
  /** Remove top padding when stacking directly under a CardHead. */
  flush?: boolean;
}) {
  return <div className={flush ? "card-body pt-0" : "card-body"}>{children}</div>;
}

export default Card;
