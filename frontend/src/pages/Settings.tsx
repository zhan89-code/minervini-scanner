// pages/Settings.tsx (CODE_BLUEPRINT.md §4/§7) -- form over GET/PUT
// /api/settings. All thresholds referenced by the screens are adjustable
// here rather than hardcoded, per §7.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { fetchSettings, updateSettings, type SettingsResponse } from "../api";

function toEditString(value: unknown, type: string): string {
  if (type === "list" || type === "object") return JSON.stringify(value);
  return String(value);
}

function fromEditString(text: string, type: string): unknown {
  if (type === "list" || type === "object") return JSON.parse(text);
  if (type === "float") return Number(text);
  if (type === "int") return parseInt(text, 10);
  return text;
}

export default function Settings() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  const [edits, setEdits] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!data) return;
    const initial: Record<string, string> = {};
    for (const [key, { value, type }] of Object.entries(data)) {
      initial[key] = toEditString(value, type);
    }
    setEdits(initial);
  }, [data]);

  if (isLoading) return <p className="loading">Loading settings…</p>;
  if (isError || !data) return <p className="loading">Failed to load settings.</p>;

  const handleSave = async () => {
    setError(null);
    setSaved(false);
    const changes: Record<string, unknown> = {};
    for (const [key, { type }] of Object.entries(data as SettingsResponse)) {
      try {
        changes[key] = fromEditString(edits[key], type);
      } catch {
        setError(`Invalid value for ${key}`);
        return;
      }
    }
    try {
      await updateSettings(changes);
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div>
      <h2>Settings</h2>
      <p className="disclaimer">
        These thresholds are judgment calls, not fixed constants -- adjust as market
        conditions change.
      </p>
      {error && <p className="settings-error">{error}</p>}
      {saved && <p className="settings-saved">Saved.</p>}
      <div className="table-card">
        <table>
          <tbody>
            {Object.entries(data).map(([key, { type }]) => (
              <tr key={key}>
                <td><code>{key}</code></td>
                <td>
                  <input
                    value={edits[key] ?? ""}
                    onChange={(e) => setEdits({ ...edits, [key]: e.target.value })}
                  />
                </td>
                <td className="detail">{type}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn-primary" onClick={handleSave}>
        Save
      </button>
    </div>
  );
}
