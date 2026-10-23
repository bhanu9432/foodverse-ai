// All calls go to /api. In dev, Vite proxies them to FastAPI; in production FastAPI serves this app itself.
async function req(path, opts) {
  let res;
  try {
    res = await fetch(path, opts);
  } catch {
    throw new Error('Cannot reach the server. Start the backend on port 8000 and try again.');
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const d = data && data.detail;
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join('; ') : '';
    throw new Error(msg || `Request failed (${res.status}).`);
  }
  return data;
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const tzOffset = () => -new Date().getTimezoneOffset(); // minutes east of UTC

export const api = {
  health: () => req('/api/health'),
  insights: () => req(`/api/insights?tz_offset=${tzOffset()}`),
  summary: () => req(`/api/insights/summary?tz_offset=${tzOffset()}`, { method: 'POST' }),
  records: (limit = 12) => req(`/api/records?limit=${limit}`),
  deleteRecord: (id) => req(`/api/records/${id}`, { method: 'DELETE' }),
  analyzeFood: (fd) => req('/api/food/analyze', { method: 'POST', body: fd }),
  analyzeFreshness: (fd) => req('/api/freshness/analyze', { method: 'POST', body: fd }),
  analyzeHygiene: (fd) => req('/api/hygiene/analyze', { method: 'POST', body: fd }),
  suggestRecipes: (body) => req('/api/cooking/suggest', json('POST', body)),
  cookingChat: (body) => req('/api/cooking/chat', json('POST', body)),
  getProfile: () => req('/api/planner/profile'),
  generatePlan: (body) => req('/api/planner/generate', json('POST', body)),
  transcribe: (blob) => {
    const fd = new FormData();
    fd.append('audio', blob, 'note.webm');
    return req('/api/audio/transcribe', { method: 'POST', body: fd });
  },
};
