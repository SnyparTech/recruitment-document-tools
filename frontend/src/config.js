// Backend API Base Configuration
// Default to relative root ('') on external tunnels or remote hosts to leverage Vite proxying
export const getApiBase = () => {
  const saved = localStorage.getItem('PROFILE_BOT_API_BASE');
  if (saved) return saved.replace(/\/+$/, '');
  if (import.meta.env?.VITE_API_BASE) {
    return import.meta.env.VITE_API_BASE.replace(/\/+$/, '');
  }
  // Auto-detect production deployment (Vercel, Netlify, custom domain)
  if (
    typeof window !== 'undefined' &&
    window.location.hostname !== 'localhost' &&
    window.location.hostname !== '127.0.0.1' &&
    !window.location.hostname.startsWith('192.168.')
  ) {
    return 'https://recruitment-document-tools.onrender.com';
  }
  return '';
};

export const setApiBase = (url) => {
  const clean = (url || '').trim().replace(/\/+$/, '');
  localStorage.setItem('PROFILE_BOT_API_BASE', clean);
};

// Thin wrapper around fetch() that always sends the website session cookie
// (see backend core/web_auth.py) — required because the frontend (Vercel)
// and backend (Render) are different origins, and a cross-site request
// without credentials: 'include' silently drops the cookie, not an error.
//
// ngrok-skip-browser-warning: when the backend is tunneled through ngrok's
// free tier, ngrok intercepts any request with a browser User-Agent and
// serves its own HTML interstitial (ERR_NGROK_6024) instead of forwarding
// to the backend — which has no CORS headers, so the browser reports it as
// a CORS failure even though the backend's CORS config is fine. This header
// bypasses that interstitial; it's a no-op against any non-ngrok backend.
export const apiFetch = (url, options = {}) =>
  fetch(url, {
    ...options,
    credentials: 'include',
    headers: { 'ngrok-skip-browser-warning': 'true', ...options.headers },
  });
