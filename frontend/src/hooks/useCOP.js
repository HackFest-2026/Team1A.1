import { useState, useEffect, useCallback } from 'react';
import { fetchCopSnapshot } from '../api/cop';

/**
 * Custom React Hook for consuming the unified AEGIS-COP snapshot data.
 * Manages single polling loop interval feeding all COP visual components.
 * 
 * @param {number} pollIntervalMs - Polling interval in milliseconds (default: 10000)
 */
export function useCOP(pollIntervalMs = 10000) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const snapshot = await fetchCopSnapshot();
      setData(snapshot);
      setError(null);
    } catch (err) {
      console.error('Failed to refresh COP snapshot:', err);
      setError(err.message || 'Unable to load COP data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    if (pollIntervalMs > 0) {
      const interval = setInterval(refresh, pollIntervalMs);
      return () => clearInterval(interval);
    }
  }, [refresh, pollIntervalMs]);

  return { data, loading, error, refresh };
}
