
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Overview } from './pages/Overview';
import { Incidents } from './pages/Incidents';
import { Alerts } from './pages/Alerts';
import { Environment } from './pages/Environment';
import { System } from './pages/System';
import { IncidentDetail } from './pages/IncidentDetail/IncidentDetail';
import { Upload } from './pages/Upload';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="upload" element={<Upload />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="incidents/:id" element={<IncidentDetail />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="environment" element={<Environment />} />
          <Route path="system" element={<System />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
