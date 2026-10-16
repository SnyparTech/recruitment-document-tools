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
export const apiFetch = (url, options = {}) =>
  fetch(url, { ...options, credentials: 'include' });
