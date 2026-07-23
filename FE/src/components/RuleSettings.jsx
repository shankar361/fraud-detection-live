import { useEffect, useState } from "react";

const BACKEND_BASE = (import.meta.env.VITE_BACKEND_URL || "http://localhost:8000").replace(/\/+$|^$/, "");
const RULE_PARAM_CONFIG = {
  velocity: [
    { name: "window_seconds", label: "Window (seconds)", type: "number", step: 1, min: 1 },
    { name: "max_txns", label: "Max transactions", type: "number", step: 1, min: 1 },
  ],
  impossible_travel: [
    { name: "max_speed_kmh", label: "Max speed (km/h)", type: "number", step: 50, min: 100 },
    { name: "min_distance_km", label: "Min distance (km)", type: "number", step: 10, min: 0 },
  ],
  amount_deviation: [
    { name: "zscore_threshold", label: "Z-score threshold", type: "number", step: 0.1, min: 0 },
  ],
  transaction_distance: [
    { name: "min_distance_km", label: "Min distance (km)", type: "number", step: 50, min: 100 },
  ],
  new_payment_method: [],
  new_merchant_category: [],
  country_mismatch: [],
};

const RULE_DESCRIPTIONS = {
  velocity:
    "Flags rapid transaction bursts from the same user within a short time window.",
  impossible_travel:
    "Flags transactions that imply impossible movement speed between locations.",
  amount_deviation:
    "Flags unusually large spend amounts compared to the user's recent transaction history.",
  transaction_distance:
    "Flags transactions that are unusually far from the user’s last known location.",
  new_payment_method:
    "Flags use of a payment method the user has never used before.",
  new_merchant_category:
    "Flags transactions in merchant categories the user has not used before.",
  country_mismatch:
    "Flags transactions from a different country than the user's prior activity.",
};

export default function RuleSettings({ open, onClose }) {
  const [settings, setSettings] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const isOpen = Boolean(open);

  useEffect(() => {
    fetch(`${BACKEND_BASE}/rule-settings`)
      .then((res) => res.ok ? res.json() : Promise.reject())
      .then((data) => {
        setSettings(data);
      })
      .catch(() => {
        setMessage("Unable to load rule settings from backend.");
      });
  }, []);

  const updateRule = (ruleId, field, value) => {
    setSettings((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rules: {
          ...prev.rules,
          [ruleId]: {
            ...prev.rules[ruleId],
            [field]: value,
          },
        },
      };
    });
    setDirty(true);
    setMessage("");
  };

  const updateGlobalSetting = (field, value) => {
    setSettings((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        [field]: value,
      };
    });
    setDirty(true);
    setMessage("");
  };

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setMessage("");

    try {
      const response = await fetch(`${BACKEND_BASE}/rule-settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!response.ok) {
        throw new Error("Save failed");
      }
      const result = await response.json();
      setSettings(result.settings || settings);
      setDirty(false);
      setMessage("Rule settings saved successfully.");
    } catch (error) {
      setMessage("Failed to save rule settings. Try again.");
    } finally {
      setSaving(false);
    }
  };

  if (!settings) {
    return (
      <>
        <div className={`settings-backdrop ${isOpen ? "visible" : ""}`} onClick={onClose} />
        <section className={`settings-panel drawer ${isOpen ? "open" : ""}`}>
          <div className="settings-drawer-header">
            <div>
              <div className="panel-title">Fraud detection Rule setup</div>
              <div className="panel-description">Loading rule settings…</div>
            </div>
            <button className="close-settings-button" onClick={onClose} aria-label="Close rule settings">✕</button>
          </div>
        </section>
      </>
    );
  }

  return (
    <>
      <div className={`settings-backdrop ${isOpen ? "visible" : ""}`} onClick={onClose} />
      <section className={`settings-panel drawer ${isOpen ? "open" : ""}`}>
      <div className="settings-header">
        <div>
          <div className="panel-title">Fraud detection Rule setup</div>
          <div className="panel-description">
            Tune fraud detection thresholds and weights in real time.
          </div>
        </div>
        <div className="settings-header-actions">
          <button
            className="close-settings-button"
            onClick={onClose}
            aria-label="Close rule settings"
          >
            ✕
          </button>
          <button
            className="save-settings-button"
            disabled={!dirty || saving}
            onClick={handleSave}
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      <div className="rule-field global-field">
        <label>Flag threshold (%)</label>
        <input
          type="number"
          min="0"
          max="100"
          step="1"
          value={settings.flag_threshold_pct ?? 40}
          onChange={(event) => updateGlobalSetting("flag_threshold_pct", Number(event.target.value))}
        />
      </div>
      <div className="settings-grid">
        {Object.entries(settings.rules).map(([ruleId, rule]) => (
          <div className="rule-card" key={ruleId}>
            <div className="rule-card-header">
              <div>
                <div className="rule-name">{ruleId.replace(/_/g, " ")}</div>
                <div className="rule-subtitle">Weight: {rule.weight}</div>
              </div>
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={rule.enabled}
                  onChange={(event) => updateRule(ruleId, "enabled", event.target.checked)}
                />
                Enabled
              </label>
            </div>

            <div className="rule-field">
              <label>Weight</label>
              <input
                type="number"
                min="0"
                step="0.05"
                value={rule.weight}
                onChange={(event) => updateRule(ruleId, "weight", Number(event.target.value))}
              />
            </div>

            {RULE_PARAM_CONFIG[ruleId]?.map((param) => (
              <div className="rule-field" key={param.name}>
                <label>{param.label}</label>
                <input
                  type={param.type}
                  min={param.min}
                  step={param.step}
                  value={rule[param.name] ?? ""}
                  onChange={(event) => updateRule(ruleId, param.name, Number(event.target.value))}
                />
              </div>
            ))}

            <div className="rule-description">{RULE_DESCRIPTIONS[ruleId]}</div>
          </div>
        ))}
      </div>

      {message && <div className="settings-message">{message}</div>}
    </section>
    </>
  );
}
