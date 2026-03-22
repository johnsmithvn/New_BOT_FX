import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import Navbar from './components/Navbar';
import Overview from './pages/Overview';
import Analytics from './pages/Analytics';
import Channels from './pages/Channels';
import Symbols from './pages/Symbols';
import Trades from './pages/Trades';
import Signals from './pages/Signals';
import Settings from './pages/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Navbar />
        <AnimatePresence mode="wait">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/channels" element={<Channels />} />
            <Route path="/symbols" element={<Symbols />} />
            <Route path="/trades" element={<Trades />} />
            <Route path="/signals" element={<Signals />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </AnimatePresence>
        <footer className="footer">
          <span>Forex Bot Dashboard V2</span>
          <span>v0.16.1</span>
        </footer>
      </div>
    </BrowserRouter>
  );
}
