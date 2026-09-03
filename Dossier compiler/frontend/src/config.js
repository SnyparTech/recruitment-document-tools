// Backend API Base Configuration
// Defaulting to 127.0.0.1:8001 to prevent conflict with other projects on port 8000
export const getApiBase = () => {
  return localStorage.getItem('PROFILE_BOT_API_BASE') || 'http://127.0.0.1:8001';
};

export const setApiBase = (url) => {
  localStorage.setItem('PROFILE_BOT_API_BASE', url);
};
