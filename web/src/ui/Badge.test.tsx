import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import Badge from "./Badge";

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>allow</Badge>);
    expect(screen.getByText("allow")).toBeInTheDocument();
  });

  it("applies the color prop to the rendered element", () => {
    render(<Badge color="#1a7f37">allow</Badge>);
    const el = screen.getByText("allow");
    // Tinted treatment uses the color as the text color.
    expect(el).toHaveStyle({ color: "#1a7f37" });
    // And exposes it as the dot custom property for dot variants.
    expect(el.style.getPropertyValue("--badge-dot")).toBe("#1a7f37");
  });

  it("uses a solid fill when solid is set", () => {
    render(
      <Badge color="#b91c1c" solid>
        block
      </Badge>,
    );
    const el = screen.getByText("block");
    expect(el).toHaveStyle({ background: "#b91c1c", color: "#fff" });
  });

  it("adds the dot and capitalize modifier classes", () => {
    render(
      <Badge color="#7c3aed" dot capitalize>
        escalate_human_review
      </Badge>,
    );
    const el = screen.getByText("escalate_human_review");
    expect(el).toHaveClass("badge", "dot", "cap");
  });

  it("renders neutrally with no color prop (no inline color)", () => {
    render(<Badge>neutral</Badge>);
    const el = screen.getByText("neutral");
    expect(el).toHaveClass("badge");
    expect(el.style.color).toBe("");
  });
});
