import { Download, FileText, RefreshCw, RotateCcw, Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { API_BASE, apiFetch, authHeaders } from '../api';

const TRANSACTION_TYPE_OPTIONS = [
  { value: 'account_opening', label: 'Account Opening' },
  { value: 'modification', label: 'Modification/Re-KYC' },
];

const DEFAULT_FILTERS = {
  fromDate: '',
  toDate: '',
  clientCode: '',
  apiType: 'ALL',
  transactionType: '',
  status: 'ALL',
};

const RETRY_ENDPOINTS = {
  BSE: 'bse_ucc_modify',
  BSE_STAR_MF: 'bse_starmf_ucc_modify',
  NSE: 'nse_ucc_modify',
  NSDL: 'nsdl_ucc_modify',
  CDSL: 'cdsl_ucc_modify',
  MCX: 'mcx_ucc_modify',
  MSE: 'mse_ucc_modify',
  CKYC: 'ckyc_ucc_modify',
  KRA: 'kra_ucc_modify',
};

function dashboardQuery(filters, page, pageSize, companyId) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    api_type: filters.apiType,
    status: filters.status,
  });
  if (filters.fromDate) params.set('from_date', filters.fromDate);
  if (filters.toDate) params.set('to_date', filters.toDate);
  if (filters.clientCode.trim()) params.set('client_code', filters.clientCode.trim());
  if (filters.transactionType) params.set('transaction_type', filters.transactionType);
  if (companyId) params.set('user_id', String(companyId));
  return params;
}

function csvValue(value) {
  const text = value == null ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

export default function Dashboard({ activeCompany = null }) {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(DEFAULT_FILTERS);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [retryingKey, setRetryingKey] = useState('');
  const [logLoadingKey, setLogLoadingKey] = useState('');
  const [logModal, setLogModal] = useState(null);
  const [page, setPage] = useState(1);

  const companyId = activeCompany?.id ?? null;
  const columnWidths = ['17%', '17%', '12%', '15%', '11%', '12%', '8%', '8%'];
  const rows = data?.rows ?? [];
  const columnCount = 8;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setData(null);
    setError('');

    const query = dashboardQuery(appliedFilters, page, 25, companyId);
    apiFetch(`${API_BASE}/api/dashboard/?${query.toString()}`, {
      headers: authHeaders(),
      signal: controller.signal,
    })
      .then(async response => {
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.error || 'Could not load dashboard data.');
        return result;
      })
      .then(setData)
      .catch(err => {
        if (err.name !== 'AbortError') setError(err.message || 'Could not load dashboard data.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [appliedFilters, companyId, page]);

  const summary = data?.summary ?? { total_clients: 0, success: 0, failure: 0, pending: 0 };

  function updateFilter(event) {
    const { name, value } = event.target;
    const nextFilters = { ...filters, [name]: value };
    setFilters(nextFilters);

    // Dropdown filters are applied immediately unless the dashboard is being
    // filtered by date, which still requires the Search button.
    if (event.target.tagName === 'SELECT' && !nextFilters.fromDate && !nextFilters.toDate) {
      setPage(1);
      setError('');
      setAppliedFilters(nextFilters);
    }
  }

  function submitFilters(event) {
    event.preventDefault();
    const hasDateFilter = Boolean(filters.fromDate || filters.toDate);
    if (hasDateFilter && filters.apiType === 'ALL') {
      setError('Select one API Type before searching by date.');
      return;
    }
    if (hasDateFilter && (!filters.fromDate || !filters.toDate)) {
      setError('Select both From Date and To Date before searching.');
      return;
    }
    if (filters.fromDate && filters.toDate && filters.fromDate > filters.toDate) {
      setError('From Date cannot be later than To Date.');
      return;
    }
    setPage(1);
    setError('');
    setAppliedFilters({ ...filters });
  }

  function resetFilters() {
    setFilters({ ...DEFAULT_FILTERS });
    setAppliedFilters({ ...DEFAULT_FILTERS });
    setPage(1);
  }

  async function exportDashboard() {
    setExporting(true);
    try {
      const query = dashboardQuery(appliedFilters, 1, 1000, companyId);
      const response = await apiFetch(`${API_BASE}/api/dashboard/?${query.toString()}`, {
        headers: authHeaders(),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || 'Could not export dashboard data.');

      const headers = ['Client Code', 'Client Name'];
      headers.push('Transaction Type');
      headers.push('API Type', 'Push Date', 'Status', 'Account Holder Type');
      const lines = [headers.map(csvValue).join(',')];
      (result.rows ?? []).forEach(row => {
        const values = [row.client_code, row.client_name];
        values.push(row.transaction_type);
        values.push(row.api_type, row.push_date, row.status, row.account_holder_type);
        lines.push(values.map(csvValue).join(','));
      });

      const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'api_push_dashboard.csv';
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || 'Could not export dashboard data.');
    } finally {
      setExporting(false);
    }
  }

  async function retryRow(row) {
    const rowKey = `${row.id}-${row.api_type}`;
    const endpoint = RETRY_ENDPOINTS[row.api_type];
    if (!endpoint || !row.client_code || retryingKey) return;

    setRetryingKey(rowKey);
    setError('');
    setActionMessage('');
    try {
      const response = await apiFetch(
        `${API_BASE}/api/${endpoint}/${encodeURIComponent(row.client_code)}/`,
        {
          method: 'POST',
          timeout: 120000,
          headers: authHeaders(),
          body: JSON.stringify({ user_id: row.user_id }),
        },
      );
      const result = await response.json().catch(() => ({}));
      const message = result.msg || result.message || 'Retry request failed.';
      if (!response.ok || result.success === false) throw new Error(message);

      setActionMessage(`${row.api_type} retry completed for ${row.client_code}.`);
      setAppliedFilters(current => ({ ...current }));
    } catch (err) {
      setError(err.message || 'Retry request failed.');
    } finally {
      setRetryingKey('');
    }
  }

  async function viewLog(row) {
    const rowKey = `${row.id}-${row.api_type}`;
    setLogLoadingKey(rowKey);
    setLogModal({ row, loading: true, error: '' });
    try {
      const query = new URLSearchParams({
        client_id: String(row.id),
        api_type: row.api_type,
        user_id: String(row.user_id),
      });
      const response = await apiFetch(`${API_BASE}/api/dashboard/log/?${query.toString()}`, {
        headers: authHeaders(),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || 'Could not load the log.');
      setLogModal({ row, loading: false, error: '', ...result });
    } catch (err) {
      setLogModal({ row, loading: false, error: err.message || 'Could not load the log.' });
    } finally {
      setLogLoadingKey('');
    }
  }

  function logText(details) {
    if (typeof details === 'string') return details;
    return JSON.stringify(details ?? {}, null, 2);
  }

  return (
    <div className="report-page">
      <form className="report-filter-panel" onSubmit={submitFilters}>
        <label>
          <span>From Date</span>
          <input type="date" name="fromDate" value={filters.fromDate} onChange={updateFilter} />
        </label>
        <label>
          <span>To Date</span>
          <input type="date" name="toDate" value={filters.toDate} onChange={updateFilter} />
        </label>
        <label>
          <span>Client Code</span>
          <input
            type="search"
            name="clientCode"
            value={filters.clientCode}
            onChange={updateFilter}
            placeholder="Enter client code"
          />
        </label>
        <label>
          <span>API Type</span>
          <select name="apiType" value={filters.apiType} onChange={updateFilter}>
            <option value="ALL">All API Types</option>
            <option value="BSE">BSE</option>
            <option value="BSE STAR MF">BSE Star MF</option>
            <option value="NSE">NSE</option>
            <option value="NSDL">NSDL</option>
            <option value="CDSL">CDSL</option>
            <option value="MCX">MCX</option>
            <option value="MSE">MSE</option>
            <option value="CKYC">CKYC</option>
            <option value="KRA">KRA</option>
          </select>
        </label>
        <label>
          <span>Transaction Type</span>
          <select name="transactionType" value={filters.transactionType} onChange={updateFilter}>
            <option value="">All Transaction Types</option>
            {TRANSACTION_TYPE_OPTIONS.map(transactionType => (
              <option key={transactionType.value} value={transactionType.value}>{transactionType.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Status</span>
          <select name="status" value={filters.status} onChange={updateFilter}>
            <option value="ALL">All Statuses</option>
            <option value="FAILURE">Failure</option>
            <option value="PENDING">Pending</option>
            <option value="SUCCESS">Success</option>
          </select>
        </label>
        <div className="report-filter-actions">
          <button type="submit" className="report-primary-btn">
            <Search size={15} aria-hidden="true" /> Search
          </button>
          <button type="button" className="report-secondary-btn" onClick={exportDashboard} disabled={exporting}>
            <Download size={15} aria-hidden="true" /> {exporting ? 'Exporting…' : 'Export'}
          </button>
          <button type="button" className="report-secondary-btn" onClick={resetFilters}>
            <RotateCcw size={15} aria-hidden="true" /> Reset
          </button>
        </div>
      </form>

      {error && <p className="db-error" role="alert">{error}</p>}
      {actionMessage && <p className="report-action-message" role="status">{actionMessage}</p>}

      <div className="report-summary-grid" aria-label="Dashboard summary">
        <div className="report-summary-card">
          <span>Total Clients</span>
          <strong>{summary.total_clients}</strong>
        </div>
        <div className="report-summary-card success">
          <span>Successful</span>
          <strong>{summary.success}</strong>
        </div>
        <div className="report-summary-card failure">
          <span>With Failures</span>
          <strong>{summary.failure}</strong>
        </div>
        <div className="report-summary-card pending">
          <span>Pending</span>
          <strong>{summary.pending}</strong>
        </div>
      </div>

      <div className="report-results-bar">
        <div>
          <span>Showing:</span>
          <mark>{appliedFilters.apiType === 'ALL' ? 'All APIs' : appliedFilters.apiType}</mark>
          {appliedFilters.transactionType && (
            <mark>{TRANSACTION_TYPE_OPTIONS.find(option => option.value === appliedFilters.transactionType)?.label}</mark>
          )}
          {appliedFilters.status !== 'ALL' && <mark>{appliedFilters.status}</mark>}
        </div>
        <button type="button" className="report-refresh-btn" onClick={() => setAppliedFilters(current => ({ ...current }))} disabled={loading}>
          <RefreshCw size={14} aria-hidden="true" /> Refresh
        </button>
      </div>

      <div className="report-table-wrap">
        <table className="report-table">
          <colgroup>
            {columnWidths.map((width, index) => (
              <col key={`dashboard-column-${index}`} style={{ width }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th>Client / Name</th>
              <th>Transaction Type</th>
              <th>API Type</th>
              <th>Push Date</th>
              <th>Status</th>
              <th>Account Holder Type</th>
              <th>Action</th>
              <th>Logs</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data ? (
              <tr><td colSpan={columnCount} className="report-empty">Loading dashboard…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={columnCount} className="report-empty">No dashboard records found.</td></tr>
            ) : rows.map((row, index) => (
              <tr key={`${row.id}-${row.api_type}-${index}`}>
                <td>
                  <strong>{row.client_code || '—'}</strong>
                  <small>{row.client_name || 'Name unavailable'}</small>
                </td>
                <td>{row.transaction_type || '—'}</td>
                <td><span className={`report-api-badge ${row.api_type.toLowerCase().replaceAll(' ', '-')}`}>{row.api_type}</span></td>
                <td>{row.push_date || '—'}</td>
                <td><span className={`report-status-badge ${row.status}`}>{row.status}</span></td>
                <td>{row.account_holder_type || '—'}</td>
                <td>
                  {row.status === 'failure' ? (
                    <button
                      type="button"
                      className="report-retry-btn"
                      onClick={() => retryRow(row)}
                      disabled={Boolean(retryingKey)}
                    >
                      <RotateCcw size={13} aria-hidden="true" />
                      {retryingKey === `${row.id}-${row.api_type}` ? 'Retrying…' : 'Retry'}
                    </button>
                  ) : '—'}
                </td>
                <td>
                  {row.status === 'failure' ? (
                    <button
                      type="button"
                      className="report-log-btn"
                      onClick={() => viewLog(row)}
                      disabled={Boolean(logLoadingKey)}
                    >
                      <FileText size={13} aria-hidden="true" />
                      {logLoadingKey === `${row.id}-${row.api_type}` ? 'Loading…' : 'Logs'}
                    </button>
                  ) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data && data.total_pages > 1 && (
        <div className="report-pagination">
          <button type="button" onClick={() => setPage(1)} disabled={page === 1}>«</button>
          <button type="button" onClick={() => setPage(current => Math.max(1, current - 1))} disabled={page === 1}>‹</button>
          <span>Page {data.page} / {data.total_pages}</span>
          <button type="button" onClick={() => setPage(current => Math.min(data.total_pages, current + 1))} disabled={page === data.total_pages}>›</button>
          <button type="button" onClick={() => setPage(data.total_pages)} disabled={page === data.total_pages}>»</button>
        </div>
      )}

      {logModal && (
        <div className="report-log-backdrop" role="presentation" onClick={() => setLogModal(null)}>
          <section
            className="report-log-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="report-log-title"
            onClick={event => event.stopPropagation()}
          >
            <div className="report-log-heading">
              <div>
                <p>Provider error log</p>
                <h2 id="report-log-title">
                  {logModal.row.api_type} · {logModal.row.client_code}
                </h2>
              </div>
              <button type="button" className="report-log-close" onClick={() => setLogModal(null)} aria-label="Close logs">
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            {logModal.loading ? (
              <p className="report-log-loading">Loading log…</p>
            ) : logModal.error ? (
              <p className="db-error" role="alert">{logModal.error}</p>
            ) : (
              <>
                <p className="report-log-message">
                  <strong>Actual error:</strong> {logModal.message}
                </p>
                <p className="report-log-file">File: {logModal.file_name}</p>
                <pre className="report-log-content">{logModal.raw_log || logText(logModal.details)}</pre>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
