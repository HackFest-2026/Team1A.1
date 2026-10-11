import { API_BASE_URL } from '../config';

/**
 * Common Operating Picture (COP) Frontend Data Adapter.
 * Consumes the unified COP snapshot API endpoints.
 */

export async function fetchCopSnapshot() {
  const response = await fetch(`${API_BASE_URL}/cop`);
  if (!response.ok) {
    throw new Error(`Failed to fetch COP snapshot: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchCopSummary() {
  const response = await fetch(`${API_BASE_URL}/cop/summary`);
  if (!response.ok) {
    throw new Error(`Failed to fetch COP summary: ${response.statusText}`);
  }
  return response.json();
}
