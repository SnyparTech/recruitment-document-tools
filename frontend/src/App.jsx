import React, { useState } from 'react';
import Navbar from './components/Navbar';
import DossierUploadWorkspace from './dossier-compiler/DossierUploadWorkspace';
import SearchAgentView from './components/SearchAgentView';
import ResumeConverterWorkspace from './components/ResumeConverterWorkspace';

export default function App() {
  const [activeTab, setActiveTab] = useState('resume-converter');
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  const handleCompileCandidate = (candidate) => {
    setSelectedCandidate(candidate);
    setActiveTab('dossier');
  };

  return (
    <div className="app-page-wrapper">
      {/* Top Navbar with Candidates, Dossier Compiler, and AI Resume Converter */}
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main Content Workspace */}
      <main className="main-content-centered">
        {activeTab === 'resume-converter' ? (
          <div className="workspace-container">
            <ResumeConverterWorkspace />
          </div>
        ) : activeTab === 'dossier' ? (
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
