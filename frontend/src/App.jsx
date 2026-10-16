import React, { useEffect, useState } from 'react';
import Navbar from './components/Navbar';
import LoginPage from './components/LoginPage';
import DossierUploadWorkspace from './dossier-compiler/DossierUploadWorkspace';
import SearchAgentView from './components/SearchAgentView';
import { getApiBase, apiFetch } from './config';

export default function App() {
  const [activeTab, setActiveTab] = useState('dossier');
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [auth, setAuth] = useState({ checked: false, authEnabled: false, email: null });

  useEffect(() => {
    const API_BASE = getApiBase();
    apiFetch(`${API_BASE}/auth/me`)
      .then((resp) => (resp.ok ? resp.json() : { auth_enabled: false, email: null }))
      .then((data) => setAuth({ checked: true, authEnabled: !!data.auth_enabled, email: data.email || null }))
      .catch(() => setAuth({ checked: true, authEnabled: false, email: null }));
  }, []);

  const handleCompileCandidate = (candidate) => {
    setSelectedCandidate(candidate);
    setActiveTab('dossier');
  };

  const handleLogout = async () => {
    const API_BASE = getApiBase();
    await apiFetch(`${API_BASE}/auth/logout`, { method: 'POST' }).catch(() => {});
    setAuth((a) => ({ ...a, email: null }));
  };

  if (!auth.checked) {
    return <div className="app-page-wrapper" />;
  }

  if (auth.authEnabled && !auth.email) {
    return <LoginPage onLoggedIn={(email) => setAuth((a) => ({ ...a, email }))} />;
  }

  return (
    <div className="app-page-wrapper">
      {/* Top Navbar with Candidates and Dossier Compiler */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        authEmail={auth.authEnabled ? auth.email : null}
        onLogout={handleLogout}
      />

      {/* Main Content Workspace */}
      <main className="main-content-centered">
        {activeTab === 'dossier' ? (
          <DossierUploadWorkspace
            initialCandidate={selectedCandidate}
            onBack={() => setActiveTab('candidates')}
          />
        ) : (
          <div className="workspace-container">
            <div className="workspace-card">
              <SearchAgentView onCompileCandidate={handleCompileCandidate} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
