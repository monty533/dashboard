import { useEffect, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { API_BASE, authHeaders, apiFetch, readJson } from '../api';

export default function Companies({ role = 'user', onCompanyVisit }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showRegister, setShowRegister] = useState(false);
  const [registerLoading, setRegisterLoading] = useState(false);
  const [registerError, setRegisterError] = useState('');
  const [issuedApiKey, setIssuedApiKey] = useState('');
  const [copied, setCopied] = useState(false);
  const [showVerify, setShowVerify] = useState(false);
  const [verifyApiKeyValue, setVerifyApiKeyValue] = useState('');
  const [showVerifyApiKey, setShowVerifyApiKey] = useState(false);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyError, setVerifyError] = useState('');
  const [verifiedClient, setVerifiedClient] = useState(null);
  const [form, setForm] = useState({
    email: '',
    password: '',
    company_name: '',
    phone: '',
    address: '',
  });

  useEffect(() => {
    if (role !== 'admin') return undefined;
    const controller = new AbortController();

    apiFetch(`${API_BASE}/api/users/`, {
      headers: authHeaders(),
      signal: controller.signal,
    })
      .then(readJson)
      .then(d => {
        if (d.error) setError(d.error);
        else setUsers(d.users ?? []);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError('Failed to load user accounts.');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [role]);

  function updateForm(event) {
    const { name, value } = event.target;
    setForm(current => ({ ...current, [name]: value }));
  }

  function closeRegister() {
    if (registerLoading) return;
    setShowRegister(false);
    setIssuedApiKey('');
    setCopied(false);
    setRegisterError('');
    setForm({ email: '', password: '', company_name: '', phone: '', address: '' });
  }

  function closeVerify() {
    if (verifyLoading) return;
    setShowVerify(false);
    setVerifyApiKeyValue('');
    setShowVerifyApiKey(false);
    setVerifyError('');
    setVerifiedClient(null);
  }

  async function registerCompany(event) {
    event.preventDefault();
    setRegisterLoading(true);
    setRegisterError('');

    try {
      const response = await apiFetch(`${API_BASE}/api/register/`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(form),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || 'Unable to register the company.');
      }

      setUsers(current => [{
        ...data.user,
        company_name: data.profile?.company_name || '',
      }, ...current]);
      setIssuedApiKey(data.api_key || '');
    } catch (err) {
      setRegisterError(err.message || 'Unable to register the company.');
    } finally {
      setRegisterLoading(false);
    }
  }

  async function copyApiKey() {
    if (!issuedApiKey) return;
    try {
      await navigator.clipboard.writeText(issuedApiKey);
      setCopied(true);
    } catch {
      setRegisterError('Copy failed. Please copy the API key manually.');
    }
  }

  async function verifyClientApiKey(event) {
    event.preventDefault();
    const apiKey = verifyApiKeyValue.trim();
    if (!apiKey) {
      setVerifyError('API key is required.');
      return;
    }

    setVerifyLoading(true);
    setVerifyError('');
    setVerifiedClient(null);

    try {
      const response = await apiFetch(`${API_BASE}/api/client/me/`, {
        headers: { 'X-API-Key': apiKey },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || data.error || 'API key verification failed.');
      }
      setVerifiedClient(data);
    } catch (err) {
      setVerifyError(err.message || 'API key verification failed.');
    } finally {
      setVerifyLoading(false);
    }
  }

  if (role !== 'admin') return null;
  if (loading) return <p className="db-loading">Loading users...</p>;
  if (error) return <p className="db-error">{error}</p>;

  return (
    <>
      <div className="companies-toolbar">
        <div>
          <strong>Client companies</strong>
          <span>Create an account and issue its API key.</span>
        </div>
        <div className="companies-toolbar-actions">
          <button
            type="button"
            className="company-verify-toolbar-btn"
            onClick={() => {
              setVerifyError('');
              setVerifiedClient(null);
              setShowVerifyApiKey(false);
              setShowVerify(true);
            }}
          >
            Verify API Key
          </button>
          <button
            type="button"
            className="company-register-btn"
            onClick={() => {
              setRegisterError('');
              setShowRegister(true);
            }}
          >
            + Register Company
          </button>
        </div>
      </div>

      <div className="companies-table-wrap">
        <table className="db-table companies-table">
          <thead>
            <tr>
              <th style={{ width: '60px' }}>ID</th>
              <th style={{ width: '22%' }}>Company</th>
              <th style={{ width: '30%' }}>Email</th>
              <th style={{ width: '15%' }}>Role</th>
              <th style={{ width: '15%' }}>Status</th>
              <th style={{ width: '14%' }}>Joined</th>
              <th style={{ width: '110px' }}>Visit</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u, i) => (
              <tr key={u.id} className={i % 2 === 0 ? 'row-even' : 'row-odd'}>
                <td style={{ color: '#9ca3af', fontSize: 12 }}>{u.id}</td>
                <td className="db-cell" style={{ fontWeight: 600 }}>{u.company_name || ''}</td>
                <td style={{ fontSize: 13, color: '#4b5563' }}>{u.email || '-'}</td>
                <td>
                  <span style={{
                    padding: '2px 10px',
                    borderRadius: '12px',
                    fontSize: '11px',
                    fontWeight: 700,
                    background: u.role === 'admin' ? '#dbeafe' : '#f3f4f6',
                    color: u.role === 'admin' ? '#1e40af' : '#4b5563',
                  }}>
                    {u.role ? u.role.toUpperCase() : 'USER'}
                  </span>
                </td>
                <td style={{ color: u.is_active ? '#15803d' : '#dc2626', fontWeight: 600, fontSize: 12 }}>
                  {u.is_active ? 'Active' : 'Disabled'}
                </td>
                <td style={{ color: '#6b7a99', fontSize: 12 }}>{u.date_joined}</td>
                <td>
                  <button
                    type="button"
                    className="dashboard-row-btn"
                    onClick={() => onCompanyVisit?.(u)}
                  >
                    Visit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showRegister && (
        <div className="company-register-backdrop" role="presentation">
          <div
            className="company-register-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="company-register-title"
          >
            {!issuedApiKey ? (
              <>
                <div className="company-register-heading">
                  <div>
                    <p className="company-register-eyebrow">Admin action</p>
                    <h2 id="company-register-title">Register company</h2>
                    <p>Create the login and profile that will own incoming client records.</p>
                  </div>
                  <button type="button" className="company-modal-close" onClick={closeRegister} aria-label="Close">
                    ×
                  </button>
                </div>

                <form className="company-register-form" onSubmit={registerCompany}>
                  <label>
                    <span>Email address *</span>
                    <input name="email" type="email" value={form.email} onChange={updateForm} required autoComplete="off" />
                  </label>
                  <label>
                    <span>Temporary password *</span>
                    <input name="password" type="password" value={form.password} onChange={updateForm} minLength={8} required autoComplete="new-password" />
                  </label>
                  <label>
                    <span>Company name</span>
                    <input name="company_name" value={form.company_name} onChange={updateForm} maxLength={255} />
                  </label>
                  <label>
                    <span>Phone</span>
                    <input name="phone" value={form.phone} onChange={updateForm} maxLength={20} />
                  </label>
                  <label className="company-register-full-field">
                    <span>Address</span>
                    <textarea name="address" value={form.address} onChange={updateForm} rows={3} />
                  </label>

                  {registerError && <p className="company-register-error" role="alert">{registerError}</p>}

                  <div className="company-register-actions">
                    <button type="button" className="company-modal-secondary" onClick={closeRegister} disabled={registerLoading}>
                      Cancel
                    </button>
                    <button type="submit" className="company-modal-primary" disabled={registerLoading}>
                      {registerLoading ? 'Creating…' : 'Create & Issue API Key'}
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <div className="company-key-success">
                <div className="company-key-icon">✓</div>
                <p className="company-register-eyebrow">Company registered</p>
                <h2 id="company-register-title">Save this API key</h2>
                <p>This key is shown once. Give it securely to the company so it can call your API.</p>
                <div className="company-key-box">{issuedApiKey}</div>
                <button type="button" className="company-modal-primary company-copy-btn" onClick={copyApiKey}>
                  {copied ? 'Copied' : 'Copy API Key'}
                </button>
                {registerError && <p className="company-register-error" role="alert">{registerError}</p>}
                <button type="button" className="company-modal-secondary company-done-btn" onClick={closeRegister}>
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {showVerify && (
        <div className="company-register-backdrop" role="presentation">
          <div
            className="company-register-modal company-verify-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="verify-api-key-title"
          >
            {!verifiedClient ? (
              <>
                <div className="company-register-heading">
                  <div>
                    <p className="company-register-eyebrow">Client authentication</p>
                    <h2 id="verify-api-key-title">Verify API key</h2>
                    <p>Send the client key to retrieve its user and profile details.</p>
                  </div>
                  <button type="button" className="company-modal-close" onClick={closeVerify} aria-label="Close">
                    ×
                  </button>
                </div>

                <form className="company-register-form" onSubmit={verifyClientApiKey}>
                  <label className="company-register-full-field">
                    <span>Client API key *</span>
                    <div className="company-api-key-input-wrap">
                      <input
                        type={showVerifyApiKey ? 'text' : 'password'}
                        value={verifyApiKeyValue}
                        onChange={event => setVerifyApiKeyValue(event.target.value)}
                        placeholder="dsh_..."
                        autoComplete="off"
                        required
                      />
                      <button
                        type="button"
                        className="company-api-key-view-btn"
                        onClick={() => setShowVerifyApiKey(value => !value)}
                        aria-label={showVerifyApiKey ? 'Hide API key' : 'Show API key'}
                        title={showVerifyApiKey ? 'Hide API key' : 'Show API key'}
                      >
                        {showVerifyApiKey
                          ? <EyeOff size={17} aria-hidden="true" />
                          : <Eye size={17} aria-hidden="true" />}
                      </button>
                    </div>
                  </label>
                  {verifyError && <p className="company-register-error" role="alert">{verifyError}</p>}
                  <div className="company-register-actions">
                    <button type="button" className="company-modal-secondary" onClick={closeVerify} disabled={verifyLoading}>
                      Cancel
                    </button>
                    <button type="submit" className="company-modal-primary" disabled={verifyLoading}>
                      {verifyLoading ? 'Verifying…' : 'Verify & Fetch Details'}
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <div className="company-api-details">
                <div className="company-register-heading">
                  <div>
                    <p className="company-register-eyebrow">Verified successfully</p>
                    <h2 id="verify-api-key-title">User and profile details</h2>
                  </div>
                  <button type="button" className="company-modal-close" onClick={closeVerify} aria-label="Close">
                    ×
                  </button>
                </div>

                {['user', 'profile'].map(section => (
                  <section className="company-detail-section" key={section}>
                    <h3>{section === 'user' ? 'User' : 'Profile'}</h3>
                    <div className="company-detail-grid">
                      {Object.entries(verifiedClient[section] || {}).map(([field, value]) => (
                        <div className="company-detail-row" key={field}>
                          <span>{field.replaceAll('_', ' ')}</span>
                          <strong>{value === null || value === '' ? '—' : String(value)}</strong>
                        </div>
                      ))}
                    </div>
                  </section>
                ))}

                <button type="button" className="company-modal-secondary company-done-btn" onClick={closeVerify}>
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
