import { useEffect, useState } from "react";
import DemoControls from "./DemoControls";

const BACKEND_BASE = (import.meta.env.VITE_BACKEND_URL || "http://localhost:8000").replace(/\/+$|^$/, "");
console.log("VITE_BACKEND_URL/BACKEND_BASE", BACKEND_BASE);
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
  const [activeTab, setActiveTab] = useState("menu");
  const [settings, setSettings] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [logoutMessage, setLogoutMessage] = useState("");
  const isOpen = Boolean(open);

  const tabConfig = {
    rules: {
      title: "Rule config",
      description: "Tune fraud detection thresholds and weights in real time.",
    },
    demo: {
      title: "Demo controls",
      description: "Trigger live scenarios from the menu instead of the main page.",
    },
    logout: {
      title: "Logout",
      description: "End the current session and return to the application entry point.",
    },
  };

  const drawerTitle = activeTab === "menu" ? "Menu" : tabConfig[activeTab]?.title;
  const drawerDescription = activeTab === "menu"
    ? "Choose one of the three menu options to continue."
    : tabConfig[activeTab]?.description;

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
    const loadingTitle = activeTab === "menu" ? "Menu" : tabConfig[activeTab]?.title;
    return (
      <>
        <div className={`settings-backdrop ${isOpen ? "visible" : ""}`} onClick={onClose} />
        <section className={`settings-panel drawer ${isOpen ? "open" : ""}`}>
          <div className="settings-drawer-header">
            <div>
              <div className="panel-title">{loadingTitle}</div>
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
            <div className="panel-title">{drawerTitle}</div>
            <div className="panel-description">
              {drawerDescription}
            </div>
          </div>
          <div className="settings-header-actions">
            <button
              className="close-settings-button"
              onClick={onClose}
              aria-label="Close menu"
            >
              ✕
            </button>
            {activeTab === "rules" && (
              <button
                className="save-settings-button"
                disabled={!dirty || saving}
                onClick={handleSave}
              >
                {saving ? "Saving…" : "Save"}
              </button>
            )}
          </div>
        </div>

        {activeTab === "menu" ? (
          <div className="settings-menu-list">
            {Object.entries(tabConfig).map(([key, item]) => (
              <button
                key={key}
                type="button"
                className="settings-menu-item"
                onClick={() => setActiveTab(key)}
              >
                <div className="menu-item-label">{item.title}</div>
                <div className="menu-item-description">{item.description}</div>
              </button>
            ))}
          </div>
        ) : (
          <>
            <div className="settings-menu-back">
              <button type="button" className="back-button" onClick={() => setActiveTab("menu")}>← Back to menu</button>
            </div>

            {activeTab === "demo" && (
              <div className="settings-panel-section">
                <DemoControls />
              </div>
            )}

            {activeTab === "logout" && (
              <div className="settings-panel-section logout-panel">
                <div className="panel-title">Logout</div>
                <div className="panel-description">Ready to leave the dashboard.</div>
                <p>If your deployment supports authentication, use the logout button below.</p>
                <button
                  type="button"
                  className="logout-button"
                  onClick={() => {
                    setLogoutMessage("Logged out. Reloading app...");
                    window.location.reload();
                  }}
                >
                  Logout now
                </button>
                {logoutMessage && <div className="logout-message">{logoutMessage}</div>}
              </div>
            )}

            {activeTab === "rules" && (
              <>
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
              </>
            )}

            {message && <div className="settings-message">{message}</div>}
          </>
        )}
      </section>
    </>
  );
}
