import { useState, useEffect } from 'react';
import EocDashboard from './components/EocDashboard';
import { API_BASE_URL } from './config';

function App() {
  const [healthStatus, setHealthStatus] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);

  useEffect(() => {
    checkHealth();
    checkSystemStatus();
  }, []);

  const checkSystemStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/system/status`);
      if (res.ok) {
        setSystemStatus(await res.json());
      }
    } catch {}
  };

  const checkHealth = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/health`);
      if (res.ok) {
        setHealthStatus('connected');
      } else {
        setHealthStatus('offline');
      }
    } catch {
      setHealthStatus('offline');
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-slate-950">
      <EocDashboard
        systemStatus={systemStatus}
      />
    </div>
  );
}

export default App;
