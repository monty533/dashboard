import { useEffect, useState } from 'react';
import { API_BASE, authHeaders, apiFetch, readJson } from '../api';
import Companies from './Companies';
import Credentials from './Credentials';
import Master, { getTableLabel } from './Master';
import Dashboard from './Dashboard';
import ManualPush from './ManualPush';
import UserDetails from './UserDetails';
import Settings from './Settings';

const MASTER_TABLE_ORDER = [
  'userdetails',
  'bse',
  'bse_star_mf',
  'bse_star_mf_dependency_master',
  'bse_star_mf_gender_master',
  'bse_star_mf_state_code_master',
  'bse_star_mf_tax_status_master',
  'nse',
  'cdsl',
  'ckyc',
  'ckyc_state_code_master',
  'kra',
  'kra_error_code',
  'kra_status_master',
  'kra_marital_status_master',
  'kra_gender_master',
  'nsdl',
  'cdsl_state_code_master',
  'cdsl_income_range_master',
  'nse_state_code_master',
  'nse_marital_status_master',
  'nse_occupation_master',
  'nse_income_range_master',
  'bse_income_range_master',
  'nsdl_state_code_master',
  'nsdl_income_range_master',
  'nsdl_account_type_master',
  'nsdl_country_master',
  'nsdl_gender_master',
  'nsdl_occupation_master',
  'nsdl_relation_master',
  'mcx',
  'mse',
  'mse_state_code_master',
  'mse_income_range_master',
  'mse_occupation_master',
  'mse_account_type_master',
  'mcx_state_city_master',
  'mcx_marital_status_master',
  'mcx_gender_master',
  'mcx_income_range_master',
  'mcx_occupation_master',
  'mcx_account_type_master',
  'mcx_error_code',
];


// ── MAIN MANUAL CONTAINER ─────────────────────────────────────────────────────
export default function Manual({ activeTab = 'manual', role = 'user', activeCompany = null, onCompanyVisit }) {
  const [tables, setTables] = useState([]);
  const [selected, setSelected] = useState('userdetails');
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();

    apiFetch(`${API_BASE}/api/tables/`, {
      headers: authHeaders(),
      signal: controller.signal,
    })
      .then(readJson)
      .then(d => {
        // NSDL is a registered master table. Keep it visible while a stale
        // backend response is still cached during a frontend deployment.
        const list = role === 'admin'
          ? [...new Set([...(d.tables ?? []), 'nsdl'])]
          : (d.tables ?? []);
        list.sort((a, b) => {
          const aKey = a.toLowerCase();
          const bKey = b.toLowerCase();
          const aIndex = MASTER_TABLE_ORDER.indexOf(aKey);
          const bIndex = MASTER_TABLE_ORDER.indexOf(bKey);
          const safeAIndex = aIndex === -1 ? Number.MAX_SAFE_INTEGER : aIndex;
          const safeBIndex = bIndex === -1 ? Number.MAX_SAFE_INTEGER : bIndex;

          if (safeAIndex !== safeBIndex) return safeAIndex - safeBIndex;
          return getTableLabel(a).localeCompare(getTableLabel(b));
        });
        setTables(list);
      })
      .catch(err => {
        if (err.name !== 'AbortError') setError('Could not load table list.');
      });

    return () => controller.abort();
  }, []);

  const selectedLabel = getTableLabel(selected);
  const manualTable = 'userdetails';
  const companyLabel = activeCompany?.username || activeCompany?.email || '';

  const titleMap = {
    manual: 'User Manual Report',
    master: 'User Master Schema',
    credentials: 'User Credentials',
    dashboard: 'User Dashboard',
    userdetails: 'User Details',
    settings: 'System Settings',
  };

  const subtitleMap = {
    manual: companyLabel ? `Manual data for ${companyLabel}` : 'Manual user details data entry',
    master: selectedLabel
      ? `Schema Structure - ${selectedLabel}`
      : 'Select a table to edit schema',
    credentials: 'Manage NSE, BSE, BSE Star MF, CKYC, KRA, CDSL, NSDL, MCX, and MSE credentials',
    dashboard: 'View provider push activity by date, transaction type, and status',
    userdetails: 'Enter and save validated client details for the selected account',
    users: 'Select a company to view its dashboard, master, and credentials',
    settings: 'Manage application configuration',
  };

  return (
    <section className="content-panel">
      <div className="db-header">
        <div>
          <h1 className="db-title">{titleMap[activeTab] ?? 'Dashboard'}</h1>
          <p className="db-subtitle">{subtitleMap[activeTab] ?? ''}</p>
        </div>
        {role === 'admin' && activeTab === 'master' && (
          <select
            className="db-table-select"
            value={selected}
            onChange={e => setSelected(e.target.value)}
          >
            <option value="">Select table</option>
            {tables.map(t => <option key={t} value={t}>{getTableLabel(t)}</option>)}
          </select>
        )}
      </div>

      {error && <p className="db-error">{error}</p>}

      {activeTab === 'manual' && (
        <ManualPush
          key={`${manualTable}-${activeCompany?.id ?? 'self'}`}
          tableName={manualTable}
          activeCompany={activeCompany}
        />
      )}
      {activeTab === 'master' && <Master key={selected} tableName={selected} />}
      {activeTab === 'credentials' && <Credentials key={activeCompany?.id ?? 'self'} activeCompany={activeCompany} />}
      {activeTab === 'dashboard' && <Dashboard activeCompany={activeCompany} />}
      {activeTab === 'userdetails' && <UserDetails activeCompany={activeCompany} role={role} />}
      {activeTab === 'users' && <Companies role={role} onCompanyVisit={onCompanyVisit} />}
      {activeTab === 'settings' && <Settings />}
    </section>
  );
}
