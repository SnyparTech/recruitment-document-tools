// Backend API Base Configuration
// Default to relative root ('') on external tunnels or remote hosts to leverage Vite proxying
export const getApiBase = () => {
  const saved = localStorage.getItem('PROFILE_BOT_API_BASE');
  if (saved) return saved;
  if (import.meta.env?.VITE_API_BASE) {
    return import.meta.env.VITE_API_BASE;
  }
  return '';
};

export const setApiBase = (url) => {
  localStorage.setItem('PROFILE_BOT_API_BASE', url);
};
