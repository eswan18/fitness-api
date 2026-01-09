import { Routes, Route} from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { OAuthCallback } from "./pages/OAuthCallback";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/oauth/callback" element={<OAuthCallback />} />
    </Routes>
  );
}

export default App;
