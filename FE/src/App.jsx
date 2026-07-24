import { useEffect, useState } from "react";
import Header from "./components/Header";
import RuleSettings from "./components/RuleSettings";
import LiveFeed from "./components/LiveFeed";
import AlertsPanel from "./components/AlertsPanel";
import GraphPanel from "./components/GraphPanel";
import { useFraudStream } from "./hooks/useFraudStream";
import "./App.css";

const BACKEND_BASE = (import.meta.env.VITE_BACKEND_URL || "http://localhost:8000").replace(/\/+$|^$/, "");
const AUTH_STORAGE_KEY = "fraudRuleAuth";

export default function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState("");
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [authConfigured, setAuthConfigured] = useState(true);
  const {
    connected,
    feed,
    alerts,
    stats,
    sendFeedback,
    graphNodes,
    graphEdges,
    ringDeviceIds,
    ringUserIds,
    ringAlerts,
  } = useFraudStream();

  useEffect(() => {
    let mounted = true;

    const restoreSession = async () => {
      setAuthLoading(true);
      setAuthError("");

      try {
        const statusResponse = await fetch(`${BACKEND_BASE}/auth/status`);
        if (statusResponse.ok) {
          const status = await statusResponse.json();
          if (!mounted) return;
          setAuthConfigured(Boolean(status.configured));

          if (!status.configured) {
            localStorage.removeItem(AUTH_STORAGE_KEY);
            setUser(null);
            setAccessToken("");
            return;
          }
        }

        const saved = JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) || "null");
        if (!saved?.accessToken) return;

        const response = await fetch(`${BACKEND_BASE}/auth/me`, {
          headers: {
            Authorization: `Bearer ${saved.accessToken}`,
          },
        });

        if (!response.ok) {
          localStorage.removeItem(AUTH_STORAGE_KEY);
          return;
        }

        const data = await response.json();
        if (!mounted) return;
        setUser(data.user || saved.user || null);
        setAccessToken(saved.accessToken);
      } catch {
        if (mounted) setAuthError("Unable to reach authentication service.");
      } finally {
        if (mounted) setAuthLoading(false);
      }
    };

    restoreSession();

    return () => {
      mounted = false;
    };
  }, []);

  const authenticate = async (email, password, mode) => {
    setAuthError("");

    try {
      const response = await fetch(`${BACKEND_BASE}/auth/${mode === "signup" ? "signup" : "signin"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "Authentication failed.";
        setAuthError(detail);
        return { success: false };
      }

      if (!data.access_token) {
        return {
          success: true,
          message: data.message || "Account created. Check your email to confirm it, then sign in.",
        };
      }

      const session = {
        accessToken: data.access_token,
        user: data.user || null,
      };
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
      setUser(session.user);
      setAccessToken(session.accessToken);
      return { success: true };
    } catch {
      setAuthError("Unable to reach authentication service.");
      return { success: false };
    }
  };

  const signOut = async () => {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    setUser(null);
    setAccessToken("");
    setSettingsOpen(false);
  };

  return (
    <div className="app">
      <Header
        connected={connected}
        stats={stats}
        onToggleSettings={() => setSettingsOpen((open) => !open)}
      />
      <RuleSettings
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        user={user}
        accessToken={accessToken}
        authLoading={authLoading}
        authError={authError}
        onAuthenticate={authenticate}
        onSignOut={signOut}
        supabaseConfigured={authConfigured}
      />
      <main>
        <LiveFeed feed={feed} />
        <AlertsPanel alerts={alerts} onFeedback={sendFeedback} />
      </main>
      <GraphPanel
        graphNodes={graphNodes}
        graphEdges={graphEdges}
        ringDeviceIds={ringDeviceIds}
        ringUserIds={ringUserIds}
        ringAlerts={ringAlerts}
        ringsDetected={stats.rings_detected}
      />
    </div>
  );
}
