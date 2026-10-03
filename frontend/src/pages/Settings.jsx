// src/pages/Settings.jsx
import React, { useEffect, useState } from "react";
import { useStore } from "../store/useStore";
import { api, getApiKey, setApiKey } from "../services/api";
import { Button, Label, Input, Select, Spinner } from "../components/ui";

function SettingsSection({ title, children }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden mb-3">
      <div className="px-4 py-2.5 border-b border-gray-800 text-xs font-semibold text-gray-300 uppercase tracking-wide">{title}</div>
      <div>{children}</div>
    </div>
  );
}

function SettingsRow({ label, hint, children }) {
  return (
    <div className="flex items-center px-4 py-3 border-b border-gray-800/50 last:border-0">
      <div className="flex-1">
        <div className="text-sm text-gray-300">{label}</div>
        {hint && <div className="text-xs text-gray-600 mt-0.5">{hint}</div>}
      </div>
      <div className="ml-4">{children}</div>
    </div>
  );
}

// SEC-5: GET /settings masks these (see backend/api/routes_settings.py) —
// mirror that list here so the mask string never gets treated as a real,
// editable value and silently re-saved over the actual secret.
const SENSITIVE_KEYS = ["proxy", "cookies_file"];

export default function Settings() {
  const { settings, fetchSettings, toast } = useStore();
  const [vals, setVals] = useState({});
  const [saving, setSaving] = useState(false);
  // Which sensitive fields the user has actually typed into this session —
  // only these get sent on Save. An untouched sensitive field stays blank
  // in the input (there's nothing to show; the real value never reaches the
  // browser) and is simply omitted from the save payload, leaving whatever
  // is already stored on the server untouched.
  const [touchedSensitive, setTouchedSensitive] = useState(() => new Set());
  // The API key is a client-side credential (stored in this browser's
  // localStorage), separate from every other setting on this page — those
  // are all server-side config saved through the (now key-protected)
  // /settings/bulk endpoint. This one has to work standalone, including
  // before the browser has a valid key stored, so it never touches the API.
  const [apiKeyInput, setApiKeyInput] = useState(() => getApiKey());

  function saveApiKey() {
    setApiKey(apiKeyInput.trim());
    toast(apiKeyInput.trim() ? "API key saved to this browser" : "API key cleared", "success");
  }

  useEffect(() => {
    fetchSettings();
  }, []);

  useEffect(() => {
    const flat = {};
    for (const [k, v] of Object.entries(settings)) {
      // Sensitive fields arrive masked (e.g. "••••••••"), not as the real
      // value — never put that mask into an editable input, or leaving it
      // untouched and hitting Save would overwrite the real secret with the
      // literal mask string.
      flat[k] = SENSITIVE_KEYS.includes(k) ? "" : (v.value || "");
    }
    setVals(flat);
    setTouchedSensitive(new Set());
  }, [settings]);

  const set = (k, v) => {
    setVals(p => ({ ...p, [k]: v }));
    if (SENSITIVE_KEYS.includes(k)) {
      setTouchedSensitive(prev => new Set(prev).add(k));
    }
  };

  async function save() {
    setSaving(true);
    try {
      const payload = { ...vals };
      for (const k of SENSITIVE_KEYS) {
        if (!touchedSensitive.has(k)) delete payload[k];
      }
      const res = await api.bulkSettings(payload);
      if (res?.restart_required_keys?.length) {
        toast(`Saved — ${res.restart_required_keys.join(", ")} needs a backend restart to take effect`, "info");
      } else {
        toast("Settings saved", "success");
      }
      await fetchSettings();
    } catch (e) { toast(e.message, "error"); }
    finally { setSaving(false); }
  }

  const S = (key) => vals[key] ?? "";
  const B = (key) => S(key) === "true";

  return (
    <div className="max-w-xl space-y-3">
      <SettingsSection title="Download">
        <SettingsRow label="Download Folder" hint={S("download_folder")}>
          <div className="flex gap-2">
            <Input value={S("download_folder")} onChange={e => set("download_folder", e.target.value)} className="w-52" />
          </div>
        </SettingsRow>
        <SettingsRow label="Default Quality">
          <Select value={S("default_quality")} onChange={e => set("default_quality", e.target.value)} className="w-44">
            <option value="bestvideo+bestaudio/best">Best available</option>
            <option value="bestvideo[height<=1080]+bestaudio/best">1080p</option>
            <option value="bestvideo[height<=720]+bestaudio/best">720p</option>
            <option value="bestaudio/best">Audio only</option>
          </Select>
        </SettingsRow>
        <SettingsRow label="Concurrent Downloads" hint="Max simultaneous downloads">
          <div className="flex items-center gap-2">
            <input type="range" min={1} max={8} value={S("max_concurrent") || 4}
              onChange={e => set("max_concurrent", e.target.value)} className="w-24 accent-indigo-500" />
            <span className="text-xs font-mono text-gray-400 w-3">{S("max_concurrent")}</span>
          </div>
        </SettingsRow>
        <SettingsRow label="Retry Attempts">
          <div className="flex items-center gap-2">
            <input type="range" min={0} max={10} value={S("max_retries") || 5}
              onChange={e => set("max_retries", e.target.value)} className="w-24 accent-indigo-500" />
            <span className="text-xs font-mono text-gray-400 w-3">{S("max_retries")}</span>
          </div>
        </SettingsRow>
        <SettingsRow label="Speed Limit (KB/s)" hint="0 = unlimited">
          <Input type="number" value={S("rate_limit")} onChange={e => set("rate_limit", e.target.value)} className="w-28" min={0} />
        </SettingsRow>
      </SettingsSection>

      <SettingsSection title="Audio & Format">
        <SettingsRow label="Default Audio Format">
          <Select value={S("audio_format")} onChange={e => set("audio_format", e.target.value)} className="w-32">
            {["mp3","aac","flac","ogg","opus","wav"].map(f => <option key={f} value={f}>{f.toUpperCase()}</option>)}
          </Select>
        </SettingsRow>
        <SettingsRow label="Embed Metadata">
          <input type="checkbox" checked={B("write_metadata")} onChange={e => set("write_metadata", String(e.target.checked))} className="w-4 h-4 accent-indigo-500" />
        </SettingsRow>
        <SettingsRow label="Save Thumbnail">
          <input type="checkbox" checked={B("write_thumbnail")} onChange={e => set("write_thumbnail", String(e.target.checked))} className="w-4 h-4 accent-indigo-500" />
        </SettingsRow>
        <SettingsRow label="Use aria2c Accelerator">
          <input type="checkbox" checked={B("use_aria2")} onChange={e => set("use_aria2", String(e.target.checked))} className="w-4 h-4 accent-indigo-500" />
        </SettingsRow>
      </SettingsSection>

      <SettingsSection title="Network">
        <SettingsRow
          label="Proxy URL"
          hint={settings.proxy?.is_set
            ? "Currently set (hidden for security) — type a new value to replace it"
            : "http:// or socks5:// — not currently set"}
        >
          <Input
            value={S("proxy")} onChange={e => set("proxy", e.target.value)}
            placeholder={settings.proxy?.is_set ? "•••••••• (leave blank to keep)" : "Leave blank to disable"}
            className="w-52"
          />
        </SettingsRow>
        <SettingsRow
          label="Cookies File"
          hint={settings.cookies_file?.is_set
            ? "Currently set (hidden for security) — type a new path to replace it"
            : "Path to cookies.txt — not currently set"}
        >
          <Input
            value={S("cookies_file")} onChange={e => set("cookies_file", e.target.value)}
            placeholder={settings.cookies_file?.is_set ? "•••••••• (leave blank to keep)" : "/path/to/cookies.txt"}
            className="w-52"
          />
        </SettingsRow>
      </SettingsSection>

      <SettingsSection title="Subtitles">
        <SettingsRow label="Default Language">
          <Input value={S("subtitle_lang")} onChange={e => set("subtitle_lang", e.target.value)} placeholder="en" className="w-20" />
        </SettingsRow>
        <SettingsRow label="Embed Subtitles">
          <input type="checkbox" checked={B("embed_subtitles")} onChange={e => set("embed_subtitles", String(e.target.checked))} className="w-4 h-4 accent-indigo-500" />
        </SettingsRow>
      </SettingsSection>

      <Button variant="primary" onClick={save} disabled={saving} size="md">
        {saving ? <Spinner /> : "Save Settings"}
      </Button>

      <SettingsSection title="Security">
        <SettingsRow
          label="API Key"
          hint="Only needed if the server has SV_API_KEY set. Stored in this browser only — never sent anywhere except as the X-API-Key header on requests to this StreamVault server."
        >
          <div className="flex gap-2">
            <Input
              type="password" value={apiKeyInput} onChange={e => setApiKeyInput(e.target.value)}
              placeholder="Leave blank if the server has no key configured" className="w-64"
            />
            <Button onClick={saveApiKey}>Save</Button>
          </div>
        </SettingsRow>
      </SettingsSection>
    </div>
  );
}
