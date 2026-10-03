import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Button, StatusPill, ProgressBar, IconButton, formatBytes, formatSpeed, formatETA } from "./ui";

describe("formatBytes", () => {
  it("shows an em-dash for falsy input", () => {
    expect(formatBytes(0)).toBe("—");
    expect(formatBytes(null)).toBe("—");
  });
  it("formats bytes, KB, MB, GB at the right thresholds", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 ** 2)).toBe("5.0 MB");
    expect(formatBytes(1.5 * 1024 ** 3)).toBe("1.50 GB");
  });
});

describe("formatSpeed", () => {
  it("appends /s to a byte-rate string", () => {
    expect(formatSpeed(1024)).toBe("1.0 KB/s");
  });
  it("shows an em-dash for falsy input", () => {
    expect(formatSpeed(0)).toBe("—");
  });
});

describe("formatETA", () => {
  it("formats seconds, minutes, and hours", () => {
    expect(formatETA(0)).toBe("—");
    expect(formatETA(45)).toBe("45s");
    expect(formatETA(125)).toBe("2m 5s");
    expect(formatETA(3725)).toBe("1h 2m");
  });
});

describe("Button", () => {
  it("renders children and fires onClick", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click me</Button>);
    fireEvent.click(screen.getByText("Click me"));
    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe("StatusPill", () => {
  it("renders the status label", () => {
    render(<StatusPill status="downloading" />);
    expect(screen.getByText(/downloading/)).toBeInTheDocument();
  });
  it("falls back gracefully for an unknown status", () => {
    render(<StatusPill status="something-new" />);
    expect(screen.getByText(/something-new/)).toBeInTheDocument();
  });
});

// FE-5: status/progress here was previously conveyed by color alone —
// these assert the accessible (non-color) equivalent actually exists.
describe("ProgressBar (FE-5 accessibility)", () => {
  it("exposes value and status through ARIA, not just color", () => {
    render(<ProgressBar value={42} status="downloading" />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "42");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(bar.getAttribute("aria-label")).toMatch(/downloading.*42%/);
  });
});

describe("IconButton (FE-5 accessibility)", () => {
  it("exposes its title as an aria-label for icon-only buttons", () => {
    render(<IconButton title="Pause">⏸</IconButton>);
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
  });
});
