import { Search, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { API_BASE, apiFetch, authHeaders } from '../api';

const MANUAL_PUSH_ORDER = ['NSE', 'BSE', 'NSDL', 'CDSL', 'KRA', 'MCX', 'MSE', 'CKYC', 'BSE STAR MF'];
const DASHBOARD_PAGE_SIZE = 10;
const DASHBOARD_QUERY_COLUMNS = [
  'clientcode',
  'bse_push', 'bsestarmf_push', 'nse_push', 'nsdl_push', 'mcx_push',
  'ckyc_push', 'kra_push', 'mse_push', 'cdsl_push',
  'bse_push_at', 'bsestarmf_push_at', 'nse_push_at', 'nsdl_push_at', 'cdsl_push_at',
  'mcx_push_at', 'mse_push_at', 'ckyc_push_at', 'kra_push_at',
];
const PROVIDER_PERMISSION_FIELDS = {
  BSE: 'bse_push',
  'BSE STAR MF': 'bsestarmf_push',
  NSE: 'nse_push',
  NSDL: 'nsdl_push',
  CDSL: 'cdsl_push',
  MCX: 'mcx_push',
  MSE: 'mse_push',
  CKYC: 'ckyc_push',
  KRA: 'kra_push',
};

function isSelectedFlag(value) {
  return ['1', 'true', 'yes', 'y', 'on'].includes(String(value ?? '').trim().toLowerCase());
}

function isApiSelected(row, action) {
  const permissionField = PROVIDER_PERMISSION_FIELDS[action];
  return Boolean(permissionField && isSelectedFlag(row[permissionField]));
}

function isPushComplete(row, action) {
  if (action === 'CDSL') {
    return isSelectedFlag(row.cdsl_push) && Boolean(row.cdsl_push_at);
  }
  const stateField = {
    BSE: 'bse_push',
    'BSE STAR MF': 'bsestarmf_push',
    NSE: 'nse_push',
    NSDL: 'nsdl_push',
    MCX: 'mcx_push',
    MSE: 'mse_push',
    CKYC: 'ckyc_push',
    KRA: 'kra_push',
  }[action];
  const timestampField = {
    BSE: 'bse_push_at',
    'BSE STAR MF': 'bsestarmf_push_at',
    NSE: 'nse_push_at',
    NSDL: 'nsdl_push_at',
    MCX: 'mcx_push_at',
    MSE: 'mse_push_at',
    CKYC: 'ckyc_push_at',
    KRA: 'kra_push_at',
  }[action];
  return stateField
    ? isSelectedFlag(row[stateField]) && Boolean(row[timestampField])
    : false;
}

function formatPayload(value) {
  if (value === null || value === undefined || value === '') return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function providerArtifactUrls(action, result) {
  const prefix = {
    NSE: 'nse',
    BSE: 'bse',
    NSDL: 'nsdl',
    CDSL: 'cdsl',
    KRA: 'kra',
    MCX: 'mcx',
    MSE: 'mse',
    CKYC: 'ckyc',
    'BSE STAR MF': 'bse_starmf',
  }[action];

  return {
    requestUrl: prefix ? result[`${prefix}_request_url`] ?? '' : '',
    responseUrl: prefix ? result[`${prefix}_response_url`] ?? '' : '',
    fetchRequestUrl: action === 'KRA' ? result.kra_fetch_request_url ?? '' : '',
    fetchResponseUrl: action === 'KRA' ? result.kra_fetch_response_url ?? '' : '',
  };
}

function inlineRequestPayload(action, result) {
  return result.request_payload
    ?? result.requestPayload
    ?? (action === 'NSDL' ? result.nsdl_payload : null)
    ?? result.payload
    ?? null;
}

function inlineResponsePayload(action, result) {
  const providerResponse = {
    NSE: result.nse_response,
    BSE: result.bse_response ?? result.response,
    NSDL: result.nsdl_response,
    CDSL: result.cdsl_response,
    KRA: result.kra_response,
    MCX: result.mcx_response,
    MSE: result.mse_response,
    CKYC: result.ckyc_response,
    'BSE STAR MF': result.bse_starmf_response,
  }[action];

  return result.response_payload
    ?? result.responsePayload
    ?? providerResponse
    ?? result.details
    ?? null;
}

function responsePayloadFallback(result) {
  const response = { ...result };
  delete response.request_payload;
  delete response.requestPayload;
  delete response.nsdl_payload;
  delete response.payload;
  return response;
}

function useDebouncedValue(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

export default function ManualPush({ tableName, activeCompany }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [toast, setToast] = useState('');
  const [toastType, setToastType] = useState('success');
  const [actionLoading, setActionLoading] = useState('');
  const [pushResult, setPushResult] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const pushResultIdRef = useRef(0);
  const debouncedSearch = useDebouncedValue(search);

  useEffect(() => {
    if (!tableName) return;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    const companyParam = activeCompany?.id ? `&user_id=${encodeURIComponent(activeCompany.id)}` : '';
    apiFetch(`${API_BASE}/api/table/${tableName}/data/?columns=${DASHBOARD_QUERY_COLUMNS.join(',')}&page=${page}&page_size=${DASHBOARD_PAGE_SIZE}&search=${encodeURIComponent(debouncedSearch)}${companyParam}`, {
      headers: authHeaders(),
      signal: controller.signal,
    })
      .then(r => r.json().then(d => ({ ok: r.ok, d })))
      .then(({ ok, d }) => {
        if (!ok || d.error) setError(d.error ?? 'Failed to load table records.');
        else setData(d);
      })
      .catch(err => {
        if (err.name !== 'AbortError') setError('Failed to load table records.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [tableName, page, debouncedSearch, activeCompany?.id, refreshKey]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => {
      setToast('');
      setToastType('success');
    }, toastType === 'error' ? 15000 : 3000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function showToast(message, type = 'success') {
    setToast(message);
    setToastType(type);
  }

  async function downloadProtectedFile(event, url) {
    event.preventDefault();
    try {
      const response = await apiFetch(url, { headers: authHeaders() });
      if (!response.ok) throw new Error('Download failed');
      const objectUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = objectUrl;
      const provider = url.includes('mcx')
        ? 'mcx'
        : url.includes('mse')
          ? 'mse'
          : url.includes('nsdl')
          ? 'nsdl'
          : url.includes('bse_starmf')
            ? 'bse_starmf'
            : url.includes('nse_file') || url.includes('nse_data')
              ? 'nse'
              : url.includes('bse_data') || url.includes('bse_file')
                ? 'bse'
                : url.includes('ckyc')
                  ? 'ckyc'
                  : url.includes('kra')
                    ? 'kra'
                    : 'cdsl';
      const archive = url.includes('/archive/') || url.endsWith('.zip');
      const pushLog = url.includes('/push_log/');
      const log = url.includes('/log/');
      link.download = archive
        ? `${provider}_request.zip`
        : pushLog
          ? `${provider}_push_log.txt`
          : log
            ? `${provider}_upload_log.txt`
            : (url.includes('/fetch_request/')
              ? `${provider}_fetch_request.txt`
              : url.includes('/fetch_response/')
                ? `${provider}_fetch_response.txt`
                : (url.includes('/request/') || url.endsWith('/request.txt')
              ? `${provider}_request.txt`
              : `${provider}_response.txt`));
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch {
      showToast('Could not download the integration file.', 'error');
    }
  }

  async function readArtifactText(url) {
    if (!url) return '';
    const response = await apiFetch(url, { headers: authHeaders() });
    if (!response.ok) throw new Error(`Could not load artifact (${response.status}).`);
    return response.text();
  }

  function openPushResult(action, clientcode, response, result, detailMessages = []) {
    const {
      requestUrl,
      responseUrl,
      fetchRequestUrl,
      fetchResponseUrl,
    } = providerArtifactUrls(action, result);
    const success = Boolean(response.ok && result.success !== false);
    const message = result.msg ?? result.message ?? `${action} request completed.`;
    const responseErrors = Array.isArray(result.errors)
      ? result.errors.map(item => {
        if (typeof item === 'string') return item;
        return item?.message || item?.error_description || item?.error || item?.code;
      }).filter(Boolean)
      : [];
    const errorMessages = [...new Set([
      ...detailMessages,
      result.error,
      ...responseErrors,
    ].filter(Boolean).map(String))];
    const resultId = pushResultIdRef.current + 1;
    pushResultIdRef.current = resultId;

    setPushResult({
      id: resultId,
      action,
      clientcode,
      success,
      completed: result.completed !== false,
      message,
      error: errorMessages.join('\n') || (!success ? message : ''),
      requestPayload: inlineRequestPayload(action, result),
      responsePayload: inlineResponsePayload(action, result) ?? responsePayloadFallback(result),
      requestUrl,
      responseUrl,
      fetchRequestUrl,
      fetchResponseUrl,
      requestArtifact: '',
      responseArtifact: '',
      fetchRequestArtifact: '',
      fetchResponseArtifact: '',
      requestArtifactError: '',
      responseArtifactError: '',
      fetchRequestArtifactError: '',
      fetchResponseArtifactError: '',
      artifactsLoading: Boolean(requestUrl || responseUrl || fetchRequestUrl || fetchResponseUrl),
      raw: result,
    });

    if (!requestUrl && !responseUrl && !fetchRequestUrl && !fetchResponseUrl) return;

    Promise.all([
      requestUrl
        ? readArtifactText(requestUrl)
          .then(text => ({ text, error: '' }))
          .catch(error => ({ text: '', error: error.message }))
        : Promise.resolve({ text: '', error: '' }),
      responseUrl
        ? readArtifactText(responseUrl)
          .then(text => ({ text, error: '' }))
          .catch(error => ({ text: '', error: error.message }))
        : Promise.resolve({ text: '', error: '' }),
      fetchRequestUrl
        ? readArtifactText(fetchRequestUrl)
          .then(text => ({ text, error: '' }))
          .catch(error => ({ text: '', error: error.message }))
        : Promise.resolve({ text: '', error: '' }),
      fetchResponseUrl
        ? readArtifactText(fetchResponseUrl)
          .then(text => ({ text, error: '' }))
          .catch(error => ({ text: '', error: error.message }))
        : Promise.resolve({ text: '', error: '' }),
    ]).then(([requestArtifact, responseArtifact, fetchRequestArtifact, fetchResponseArtifact]) => {
      setPushResult(current => {
        if (!current || current.id !== resultId) return current;
        return {
          ...current,
          artifactsLoading: false,
          requestArtifact: requestArtifact.text,
          responseArtifact: responseArtifact.text,
          fetchRequestArtifact: fetchRequestArtifact.text,
          fetchResponseArtifact: fetchResponseArtifact.text,
          requestArtifactError: requestArtifact.error,
          responseArtifactError: responseArtifact.error,
          fetchRequestArtifactError: fetchRequestArtifact.error,
          fetchResponseArtifactError: fetchResponseArtifact.error,
        };
      });
    });
  }

  async function handleManualAction(action, row) {
    if (actionLoading) return;
    const clientcode = row.clientcode ?? row.CLIENTCODE ?? '';
    if (!['NSE', 'BSE', 'CDSL', 'NSDL', 'MCX', 'MSE', 'BSE STAR MF', 'CKYC', 'KRA'].includes(action)) {
      showToast(`${action} integration is not configured yet.`, 'error');
      return;
    }

    if (!isApiSelected(row, action)) {
      openPushResult(
        action,
        clientcode,
        { ok: false, status: 400 },
        { success: false, message: `${action} is not selected for this client.` },
        [`${action} is not selected for this client.`],
      );
      return;
    }
    if (isPushComplete(row, action)) {
      openPushResult(
        action,
        clientcode,
        { ok: false, status: 409 },
        { success: false, message: `${action} has already been pushed for this client.` },
        [`${action} has already been pushed for this client.`],
      );
      return;
    }
    if (!clientcode) {
      showToast('Client code is missing.', 'error');
      return;
    }

    const loadingKey = `${action}-${clientcode}`;
    setActionLoading(loadingKey);

    try {
      const res = await apiFetch(
        `${API_BASE}/api/${action === 'BSE STAR MF' ? 'bse_starmf' : action.toLowerCase()}_ucc_modify/${encodeURIComponent(clientcode)}/`,
        {
          method: 'POST',
          timeout: 120000,
          headers: {
            ...authHeaders(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: activeCompany?.id,
          }),
        }
      );
      const result = await res.json().catch(() => ({}));
      const validationErrors = Array.isArray(result.details?.errors)
        ? result.details.errors.map(item => typeof item === 'string' ? item : item?.message || item?.error || String(item))
        : [];
      const providerErrors = Array.isArray(result.errors)
        ? result.errors.map(item => item.message || item.error_description || item.code).filter(Boolean)
        : [];
      const detailMessages = [...validationErrors, ...providerErrors];
      openPushResult(action, clientcode, res, result, detailMessages);
      if (res.ok && result.success !== false) setRefreshKey(current => current + 1);
    } catch (requestError) {
      openPushResult(
        action,
        clientcode,
        { ok: false, status: 0 },
        {
          success: false,
          message: `Failed to call ${action} API.`,
          error: requestError.message || `Failed to call ${action} API.`,
        },
        [requestError.message || `Failed to call ${action} API.`],
      );
    } finally {
      setActionLoading('');
    }
  }

  function renderManualAction(row, clientcode, action) {
    const isPending = actionLoading === `${action}-${clientcode}`;
    const selected = isApiSelected(row, action);
    const pushed = isPushComplete(row, action);
    const label = !selected
      ? 'Disabled'
      : pushed
        ? 'Pushed'
        : 'Push';
    return (
      <button
        type="button"
        className="dashboard-row-btn"
        onClick={() => handleManualAction(action, row)}
        disabled={Boolean(actionLoading) || pushed || !selected}
        title={pushed ? `${action} is already pushed for this client` : !selected ? `${action} is not selected for this client` : label}
      >
        {isPending ? 'Pushing…' : label}
      </button>
    );
  }

  function renderCkycAction(row, clientcode) {
    const isPending = actionLoading === `CKYC-${clientcode}`;
    const pushed = isPushComplete(row, 'CKYC');
    const selected = isApiSelected(row, 'CKYC');

    return (
      <button
        type="button"
        className="dashboard-row-btn dashboard-ckyc-btn"
        onClick={() => handleManualAction('CKYC', row)}
        disabled={Boolean(actionLoading) || pushed || !selected}
        title={pushed ? 'CKYC is already pushed for this client' : !selected ? 'CKYC push is disabled for this client' : 'Push CKYC'}
      >
        {isPending ? 'Pushing…' : !selected ? 'Disabled' : pushed ? 'Pushed' : 'Push'}
      </button>
    );
  }

  function renderCdslAction(row, clientcode) {
    const isPending = actionLoading === `CDSL-${clientcode}`;
    const selected = isApiSelected(row, 'CDSL');
    const pushed = isPushComplete(row, 'CDSL');

    return (
      <button
        type="button"
        className="dashboard-row-btn dashboard-cdsl-btn"
        onClick={() => handleManualAction('CDSL', row)}
        disabled={Boolean(actionLoading) || pushed || !selected}
        title={pushed ? 'CDSL is already pushed for this client' : !selected ? 'CDSL is not selected for this client' : 'Push CDSL'}
      >
        {isPending ? 'Pushing…' : !selected ? 'Disabled' : pushed ? 'Pushed' : 'Push'}
      </button>
    );
  }

  function renderManualPushAction(row, clientcode, action) {
    if (action === 'CKYC') return renderCkycAction(row, clientcode);
    if (action === 'CDSL') return renderCdslAction(row, clientcode);
    return renderManualAction(row, clientcode, action);
  }

  if (!tableName) return <p className="db-empty" style={{ margin: 28 }}>Select a table from the dropdown above to view records.</p>;
  if (loading && !data) return <p className="db-loading">Loading records…</p>;
  if (error) return <p className="db-error">{error}</p>;

  const rows = data?.rows ?? [];

  return (
    <>
      <div className="dashboard-data-toolbar">
        <div className="dashboard-search-group">
          <label className="dashboard-search-field">
            <Search size={16} aria-hidden="true" />
            <input
              className="db-search"
              type="search"
              placeholder="Search client code..."
              value={search}
              onChange={event => { setSearch(event.target.value); setPage(1); }}
            />
          </label>
          <span className="dashboard-record-count">
            {data ? `${data.total} total clients · Page ${data.page} of ${data.total_pages}` : ''}
          </span>
        </div>
      </div>

      <div className="manual-push-list">
        {loading && !data ? (
          <p className="db-loading">Loading clients…</p>
        ) : rows.length === 0 ? (
          <p className="db-empty">No clients found.</p>
        ) : (
          rows.map((row, index) => {
            const clientcode = row.clientcode ?? row.CLIENTCODE ?? '';
            return (
              <article key={clientcode || index} className="manual-push-card">
                <div className="manual-push-card-header">
                  <span>Client Code</span>
                  <strong>{clientcode || '—'}</strong>
                </div>
                <div className="manual-push-actions">
                  {MANUAL_PUSH_ORDER.map(action => (
                    <div key={action} className="manual-push-action">
                      <span className="manual-push-action-label">{action}</span>
                      {renderManualPushAction(row, clientcode, action)}
                    </div>
                  ))}
                </div>
              </article>
            );
          })
        )}
      </div>

      {pushResult && (
        <div className="manual-push-result-backdrop" role="presentation" onClick={() => setPushResult(null)}>
          <section
            className="manual-push-result-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="manual-push-result-title"
            onClick={event => event.stopPropagation()}
          >
            <div className="manual-push-result-header">
              <div>
                <span>Push result</span>
                <h2 id="manual-push-result-title">
                  {pushResult.action} · {pushResult.clientcode || 'Client'}
                </h2>
              </div>
              <button
                type="button"
                className="manual-push-result-close"
                onClick={() => setPushResult(null)}
                aria-label="Close push result"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            <div className={`manual-push-result-status ${pushResult.success ? 'success' : 'error'}`}>
              {pushResult.success
                ? (pushResult.completed ? 'Push completed successfully' : 'Stage completed — continue with the next CDSL check')
                : 'Push failed'}
            </div>

            {pushResult.message && (
              <p className="manual-push-result-message">{pushResult.message}</p>
            )}

            {pushResult.error && !pushResult.success && (
              <div className="manual-push-result-error">
                <h3>Error message</h3>
                <pre>{pushResult.error}</pre>
              </div>
            )}

            <div className="manual-push-result-grid">
              <section className="manual-push-payload-card">
                <div className="manual-push-payload-head">
                  <h3>Request payload</h3>
                  {pushResult.requestUrl && (
                    <a
                      href={pushResult.requestUrl}
                      onClick={event => downloadProtectedFile(event, pushResult.requestUrl)}
                    >
                      Download
                    </a>
                  )}
                </div>
                <pre className="manual-push-payload">
                  {pushResult.requestArtifact
                    || formatPayload(pushResult.requestPayload)
                    || (pushResult.artifactsLoading ? 'Loading request payload…' : 'Request payload is not available.')}
                </pre>
                {pushResult.requestArtifactError && (
                  <p className="manual-push-artifact-error">{pushResult.requestArtifactError}</p>
                )}
              </section>

              <section className="manual-push-payload-card">
                <div className="manual-push-payload-head">
                  <h3>Response payload</h3>
                  {pushResult.responseUrl && (
                    <a
                      href={pushResult.responseUrl}
                      onClick={event => downloadProtectedFile(event, pushResult.responseUrl)}
                    >
                      Download
                    </a>
                  )}
                </div>
                <pre className="manual-push-payload">
                  {pushResult.responseArtifact
                    || formatPayload(pushResult.responsePayload)
                    || (pushResult.artifactsLoading ? 'Loading response payload…' : 'Response payload is not available.')}
                </pre>
                {pushResult.responseArtifactError && (
                  <p className="manual-push-artifact-error">{pushResult.responseArtifactError}</p>
                )}
              </section>
            </div>

            {(pushResult.fetchRequestUrl || pushResult.fetchResponseUrl) && (
              <div className="manual-push-result-grid manual-push-fetch-grid">
                <section className="manual-push-payload-card">
                  <div className="manual-push-payload-head">
                    <h3>Fetch request payload</h3>
                    {pushResult.fetchRequestUrl && (
                      <a
                        href={pushResult.fetchRequestUrl}
                        onClick={event => downloadProtectedFile(event, pushResult.fetchRequestUrl)}
                      >
                        Download
                      </a>
                    )}
                  </div>
                  <pre className="manual-push-payload">
                    {pushResult.fetchRequestArtifact
                      || (pushResult.artifactsLoading ? 'Loading fetch request payload…' : 'Fetch request payload is not available.')}
                  </pre>
                  {pushResult.fetchRequestArtifactError && (
                    <p className="manual-push-artifact-error">{pushResult.fetchRequestArtifactError}</p>
                  )}
                </section>

                <section className="manual-push-payload-card">
                  <div className="manual-push-payload-head">
                    <h3>Fetch response payload</h3>
                    {pushResult.fetchResponseUrl && (
                      <a
                        href={pushResult.fetchResponseUrl}
                        onClick={event => downloadProtectedFile(event, pushResult.fetchResponseUrl)}
                      >
                        Download
                      </a>
                    )}
                  </div>
                  <pre className="manual-push-payload">
                    {pushResult.fetchResponseArtifact
                      || (pushResult.artifactsLoading ? 'Loading fetch response payload…' : 'Fetch response payload is not available.')}
                  </pre>
                  {pushResult.fetchResponseArtifactError && (
                    <p className="manual-push-artifact-error">{pushResult.fetchResponseArtifactError}</p>
                  )}
                </section>
              </div>
            )}
          </section>
        </div>
      )}

      {toast && (
        <div className={`db-toast ${toastType === 'error' ? 'error' : ''}`} role="status">
          <span>{toastType === 'error' ? '!' : '✓'}</span>
          {toast}
        </div>
      )}

      {data && data.total_pages > 1 && (
        <div className="db-pagination">
          <button className="pg-btn" onClick={() => setPage(1)} disabled={page === 1}>«</button>
          <button className="pg-btn" onClick={() => setPage(current => Math.max(1, current - 1))} disabled={page === 1}>‹</button>
          <span className="pg-info">Page {data.page} / {data.total_pages}</span>
          <button className="pg-btn" onClick={() => setPage(current => Math.min(data.total_pages, current + 1))} disabled={page === data.total_pages}>›</button>
          <button className="pg-btn" onClick={() => setPage(data.total_pages)} disabled={page === data.total_pages}>»</button>
        </div>
      )}
    </>
  );
}
