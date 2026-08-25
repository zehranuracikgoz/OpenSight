import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Layout } from './layout/Layout';
import { Dashboard } from './pages/Dashboard';
import { ThresholdConfig } from './pages/ThresholdConfig';

// Korelasyonlu Olay Detay Paneli ayrı bir sayfa değil, Dashboard içinde açılıyor
function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element= {<Dashboard />} />
          <Route path="/settings" element={<ThresholdConfig />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
