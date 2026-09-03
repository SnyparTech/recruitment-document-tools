import React from 'react';
import Navbar from './components/Navbar';
import DossierCompiler from './dossier-compiler';

export default function App() {
  return (
    <div className="app-container">
      <Navbar activeTab="dossier" setActiveTab={() => {}} title="Dossier Compiler" />
      <main style={{ marginTop: '20px' }}>
        <DossierCompiler />
      </main>
    </div>
  );
}
