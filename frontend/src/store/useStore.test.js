import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "../services/api";
import { useStore } from "./useStore";

vi.mock("../services/api", () => ({
  api: {
    listDownloads: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  useStore.setState({ downloads: [], loadingDl: false, toasts: [] });
});

describe("fetchDownloads", () => {
  it("forwards opts.query as the literal query string, not the whole opts object", async () => {
    api.listDownloads.mockResolvedValue([{ id: "1" }]);
    await useStore.getState().fetchDownloads({ query: "status=failed", userInitiated: true });
    expect(api.listDownloads).toHaveBeenCalledWith("status=failed");
    expect(useStore.getState().downloads).toEqual([{ id: "1" }]);
  });

  it("passes undefined query when called with no opts (periodic polling)", async () => {
    api.listDownloads.mockResolvedValue([]);
    await useStore.getState().fetchDownloads();
    expect(api.listDownloads).toHaveBeenCalledWith(undefined);
  });

  it("only toasts on failure when userInitiated is true", async () => {
    api.listDownloads.mockRejectedValue(new Error("network down"));
    await useStore.getState().fetchDownloads();
    expect(useStore.getState().toasts).toHaveLength(0);

    await useStore.getState().fetchDownloads({ userInitiated: true });
    expect(useStore.getState().toasts).toHaveLength(1);
    expect(useStore.getState().toasts[0].message).toMatch(/network down/);
  });
});
