import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, getApiKey, setApiKey, openDownloadedFile } from "./api";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("getApiKey / setApiKey", () => {
  it("round-trips through localStorage", () => {
    expect(getApiKey()).toBe("");
    setApiKey("s3cr3t");
    expect(getApiKey()).toBe("s3cr3t");
  });
  it("clears the stored key when set to an empty string", () => {
    setApiKey("s3cr3t");
    setApiKey("");
    expect(getApiKey()).toBe("");
  });
});

describe("api request helper", () => {
  it("attaches X-API-Key when a key is stored", async () => {
    setApiKey("s3cr3t");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ([]),
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.listDownloads();

    expect(fetchMock).toHaveBeenCalledOnce();
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers["X-API-Key"]).toBe("s3cr3t");
  });

  it("omits X-API-Key when no key is stored", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ([]) });
    vi.stubGlobal("fetch", fetchMock);

    await api.listDownloads();

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers["X-API-Key"]).toBeUndefined();
  });

  it("surfaces a clear message on 401 instead of the raw body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: async () => ({ detail: "Missing X-API-Key header" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.listDownloads()).rejects.toThrow(/Settings.*Security/);
  });

  it("propagates the server's detail message on other errors", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({ detail: "Invalid output_folder" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.createDownload({ url: "x" })).rejects.toThrow("Invalid output_folder");
  });
});

describe("openDownloadedFile (FE-2)", () => {
  it("fetches with the auth header and opens an object URL, not the raw endpoint URL", async () => {
    setApiKey("s3cr3t");
    const fakeBlob = new Blob(["fake video bytes"]);
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => fakeBlob });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:fake-object-url"), revokeObjectURL: vi.fn() });
    const openMock = vi.fn();
    vi.stubGlobal("open", openMock);

    await openDownloadedFile("abc123");

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain("/download/abc123/file");
    expect(opts.headers["X-API-Key"]).toBe("s3cr3t");
    expect(openMock).toHaveBeenCalledWith("blob:fake-object-url", "_blank");
  });

  it("raises a clear error when no file exists on disk (404)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 404 });
    vi.stubGlobal("fetch", fetchMock);

    await expect(openDownloadedFile("abc123")).rejects.toThrow(/not found/i);
  });
});
