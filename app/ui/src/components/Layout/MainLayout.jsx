import React from 'react';

export const MainLayout = ({ children }) => (
  <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#f0f2f5' }}>
    <header style={{ padding: '0 24px', background: '#001529', height: '64px', display: 'flex', alignItems: 'center' }}>
      <h1 style={{ color: '#fff', margin: 0, fontSize: '18px' }}>Momu ERP | Music Catalog</h1>
    </header>
    <main style={{ flex: 1, padding: '24px', overflow: 'hidden', position: 'relative' }}>
      {children}
    </main>
  </div>
);