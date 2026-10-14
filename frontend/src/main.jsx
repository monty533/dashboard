import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import Sidebar from './components/Sidebar';
import Manual from './pages/Manual';
import Login from './pages/Login';
import './styles.css';
import { API_BASE, apiFetch, authHeaders } from './api';

function withoutApiCredentials(company) {
  if (!company) return null;
  const {
    api_key: _apiKey,
    api_key_prefix: _apiKeyPrefix,
    api_key_available: _apiKeyAvailable,
    ...safeCompany
  } = company;
  return safeCompany;
}

const NAVIGATION_VERSION = 'dashboard-manual-swap-v1';

function getInitialActiveTab() {
  const role = localStorage.getItem('auth_role') || 'user';
  if (role !== 'admin') return 'dashboard';

  let savedTab = localStorage.getItem('active_tab');
  if (localStorage.getItem('navigation_version') !== NAVIGATION_VERSION) {
    const legacyTabMap = { report: 'dashboard', dashboard: 'manual' };
    savedTab = legacyTabMap[savedTab] || savedTab;
    localStorage.setItem('navigation_version', NAVIGATION_VERSION);
    if (savedTab) localStorage.setItem('active_tab', savedTab);
  }

  return savedTab || 'users';
}

function App() {
  const [authUser, setAuthUser] = useState(() => {
    const token = localStorage.getItem('auth_token');
    const username = localStorage.getItem('auth_username');
    const role = localStorage.getItem('auth_role') || 'user';
    return token ? { token, username, role } : null;
  });

  const [activeTab, setActiveTab] = useState(() => {
    return getInitialActiveTab();
  });
  const [activeCompany, setActiveCompany] = useState(() => {
    const saved = localStorage.getItem('active_company');
    if (!saved) return null;
    try {
      return withoutApiCredentials(JSON.parse(saved));
    } catch {
      localStorage.removeItem('active_company');
      return null;
    }
  });

  function handleLoginSuccess(data) {
    setAuthUser(data);
    setActiveTab(data.role === 'admin' ? 'users' : 'dashboard');
    setActiveCompany(null);
    localStorage.removeItem('active_tab');
    localStorage.removeItem('active_company');
  }

  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState('');

  useEffect(() => {
    window.addEventListener('auth-expired', clearSession);
    return () => window.removeEventListener('auth-expired', clearSession);
  }, []);

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError('');
    try {
      const response = await apiFetch(`${API_BASE}/api/logout/`, { method: 'POST', headers: authHeaders() });
      if (!response.ok && response.status !== 401) throw new Error('Logout failed');
      clearSession();
    } catch {
      setLogoutError('Unable to log out. Please retry.');
    } finally {
      setLoggingOut(false);
    }
  }

  function clearSession() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_username');
    localStorage.removeItem('auth_role');
    localStorage.removeItem('active_tab');
    localStorage.removeItem('active_company');
    setAuthUser(null);
    setActiveCompany(null);
  }

  function handleCompanyVisit(company) {
    const safeCompany = withoutApiCredentials(company);
    setActiveCompany(safeCompany);
    setActiveTab('manual');
    localStorage.setItem('active_company', JSON.stringify(safeCompany));
    localStorage.setItem('active_tab', 'manual');
  }

  function handleCompaniesClick() {
    setActiveCompany(null);
    setActiveTab('users');
    localStorage.removeItem('active_company');
    localStorage.setItem('active_tab', 'users');
  }

  function handleTabChange(tab) {
    setActiveTab(tab);
    if (authUser?.role === 'admin') {
      localStorage.setItem('active_tab', tab);
    }
  }

  if (!authUser) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  const currentTab = activeTab;

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div className="topbar-user">
            <strong className="welcome">
              Welcome,
              <span className={`welcome-badge ${authUser.role === 'admin' ? 'admin' : ''}`}>
                {authUser.username}
              </span>
            </strong>
          </div>
          <div className="topbar-actions">
            {logoutError && <span role="alert">{logoutError}</span>}
            {authUser.role === 'admin' && activeCompany && (
              <button type="button" className="logout-btn" onClick={handleCompaniesClick}>
                Companies
              </button>
            )}
            <button type="button" className="logout-btn" onClick={handleLogout} disabled={loggingOut}>
              {loggingOut ? 'Logging out…' : 'Logout'}
            </button>
          </div>
        </header>

        <div className={`dashboard-layout ${authUser.role === 'admin' && currentTab === 'users' ? 'company-listing-layout' : ''}`}>
          <Sidebar role={authUser.role} activeTab={currentTab} onTabChange={handleTabChange} />
          <Manual
            activeTab={currentTab}
            role={authUser.role}
            activeCompany={activeCompany}
            onCompanyVisit={handleCompanyVisit}
          />
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
