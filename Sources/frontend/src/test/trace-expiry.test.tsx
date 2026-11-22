import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HelpPanel } from "@/components/chat/HelpPanel";
import { TooltipProvider } from "@/components/ui/primitives";

afterEach(() => vi.unstubAllGlobals());

function help() {
  render(<TooltipProvider><HelpPanel onClose={vi.fn()} onExample={vi.fn()} disabled={false} /></TooltipProvider>);
}

describe("delete stored history", () => {
  it("shows an in-page count and Cancel makes no deletion request", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ count: 3 })));
    const confirm = vi.fn();
    vi.stubGlobal("fetch", fetch);
    vi.stubGlobal("confirm", confirm);
    help();
    fireEvent.click(screen.getByRole("button", { name: "Delete stored history" }));
    expect(await screen.findByRole("group", { name: "Confirm deleting stored history" })).toHaveTextContent(
      "Delete all 3 stored request traces on this computer? This cannot be undone.");
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith("/api/traces", expect.objectContaining({ headers: { "Content-Type": "application/json" } }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("group")).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(confirm).not.toHaveBeenCalled();
  });

  it("Delete sends DELETE once and reports the actual deleted count", async () => {
    let finishDelete!: (response: Response) => void;
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ count: 3 })))
      .mockImplementationOnce(() => new Promise<Response>((resolve) => { finishDelete = resolve; }));
    vi.stubGlobal("fetch", fetch);
    help();
    fireEvent.click(screen.getByRole("button", { name: "Delete stored history" }));
    const remove = await screen.findByRole("button", { name: "Delete" });
    fireEvent.click(remove);
    expect(remove).toBeDisabled();
    fireEvent.click(remove);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch).toHaveBeenLastCalledWith("/api/traces", expect.objectContaining({ method: "DELETE" }));
    finishDelete(new Response(JSON.stringify({ deleted: 2 })));
    expect(await screen.findByRole("status")).toHaveTextContent("Deleted 2 stored traces.");
    expect(screen.queryByRole("group")).toBeNull();
  });

  it("can confirm an empty history", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ count: 0 }))));
    help();
    fireEvent.click(screen.getByRole("button", { name: "Delete stored history" }));
    expect(await screen.findByRole("group")).toHaveTextContent("Delete all 0 stored request traces");
  });

  it.each(["count", "delete"])("shows the error text if the %s request fails", async (step) => {
    const fetch = vi.fn();
    if (step === "delete") fetch.mockResolvedValueOnce(new Response(JSON.stringify({ count: 3 })));
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Stored history can only be managed from localhost" }), { status: 403 }));
    vi.stubGlobal("fetch", fetch);
    help();
    fireEvent.click(screen.getByRole("button", { name: "Delete stored history" }));
    if (step === "delete") fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Stored history can only be managed from localhost");
    await waitFor(() => expect(screen.getByRole("button", { name: step === "delete" ? "Delete" : "Delete stored history" })).toBeEnabled());
  });
});
