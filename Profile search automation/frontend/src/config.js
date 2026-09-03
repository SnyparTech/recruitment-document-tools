// Backend API Base Configuration for Profile Search Automation
// Defaults to 127.0.0.1:8002 to avoid collision with Dossier Compiler (:8001)
export const getApiBase = () => {
  return localStorage.getItem('PROFILE_SEARCH_API_BASE') || 'http://127.0.0.1:8002';
};

export const setApiBase = (url) => {
  localStorage.setItem('PROFILE_SEARCH_API_BASE', url);
};
