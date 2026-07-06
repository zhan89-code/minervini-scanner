import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import Disclaimer from "./components/Disclaimer";
import ScanTable from "./pages/ScanTable";
import Settings from "./pages/Settings";
import StockDetail from "./pages/StockDetail";
import Watchlist from "./pages/Watchlist";
import "./App.css";

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app">
          <h1>Minervini SEPA Scanner</h1>
          <nav className="nav">
            <Link to="/">Scan</Link>
            <Link to="/watchlist">Watchlist</Link>
            <Link to="/settings">Settings</Link>
          </nav>
          <Disclaimer />
          <Routes>
            <Route path="/" element={<ScanTable />} />
            <Route path="/stock/:symbol" element={<StockDetail />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
