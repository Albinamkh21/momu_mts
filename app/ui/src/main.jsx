import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';

// Глобальные стили (можно создать пустой файл index.css, если Vite будет ругаться)
// import './index.css'; 

const container = document.getElementById('root');
const root = createRoot(container);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);