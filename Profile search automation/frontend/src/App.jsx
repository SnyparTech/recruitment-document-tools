import React from 'react';
import Navbar from './components/Navbar';
import SearchAgentView from './components/SearchAgentView';

export default function App() {
  return (
    <div className="app-container">
      <Navbar activeTab="search" setActiveTab={() => {}} title="Profile Search Automation" />
      <main style={{ marginTop: '20px' }}>
        <SearchAgentView />
      </main>
    </div>
  );
}
