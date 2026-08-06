import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Layout } from './layout/Layout';
import { Dashboard } from './pages/Dashboard';

// şimdilik tek rota var
function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element= {<Dashboard />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
