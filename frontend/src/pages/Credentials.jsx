import { useEffect, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { API_BASE, authHeaders, apiFetch, readJson } from '../api';

const CREDENTIAL_PROVIDERS = ['NSE', 'BSE', 'BSE STAR MF', 'CKYC', 'KRA', 'KRA SFTP', 'CDSL', 'NSDL', 'MCX', 'MSE'];
const CREDENTIAL_EDITABLE_PROVIDERS = CREDENTIAL_PROVIDERS;
const MCX_AES_KEY_PATTERN = /^(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{48}|[0-9a-fA-F]{64})$/;

const PROVIDER_FIELDS = {
  NSE: [
    { key: 'username', label: 'Username', type: 'text' },
    { key: 'password', label: 'Password', type: 'password' },
    { key: 'apiName', label: 'ApiName', type: 'text' },
  ],

  BSE: [
    { key: 'MemberCode', label: 'Member Code', type: 'text' },
    { key: 'UserID', label: 'User ID', type: 'text' },
    { key: 'Password', label: 'Password', type: 'password' },
  ],

  'BSE STAR MF': [
    { key: 'environment', label: 'Environment (uat/live)', type: 'text', placeholder: 'uat' },
    { key: 'MemberId', label: 'Member ID', type: 'text' },
    { key: 'UserId', label: 'User ID', type: 'text' },
    { key: 'Password', label: 'Password', type: 'password' },
  ],

  CKYC: [
    { key: 'username', label: 'CKYC Username', type: 'text' },
    { key: 'password', label: 'CKYC Password', type: 'password' },
    { key: 'ckyc_base_url', label: 'CKYC Base URL', type: 'text' },
    { key: 'auth_api_key', label: 'Auth API Key', type: 'text' },
    { key: 'ficode_ckyc', label: 'FI Code', type: 'text' },
    { key: 'region_or_branch_code_ckyc', label: 'Region / Branch Code', type: 'text' },
    { key: 'userid_ckyc', label: 'User ID', type: 'text' },
    { key: 'KYCVerificationName', label: 'KYC Verification Name', type: 'text' },
    { key: 'KYCVerificationDesignation', label: 'KYC Verification Designation', type: 'text' },
    { key: 'KYCVerificationBranch', label: 'KYC Verification Branch', type: 'text' },
    { key: 'KYCVerificationEMPcode', label: 'KYC Verification EMP Code', type: 'text' },
    { key: 'OrganisationName', label: 'Organisation Name', type: 'text' },
    { key: 'OrganisationCode', label: 'Organisation Code', type: 'text' },
  ],

  KRA: [
    { key: 'environment', label: 'Environment (uat/live)', type: 'text', placeholder: 'uat' },
    { key: 'token_url', label: 'Get Token URL', type: 'text' },
    { key: 'pan_status_url', label: 'PAN Status URL', type: 'text' },
    { key: 'fetch_data_url', label: 'Fetch KRA Data URL', type: 'text' },
    { key: 'insert_data_url', label: 'Insert / Update KYC URL', type: 'text' },
    { key: 'api_key', label: 'API Key', type: 'password' },
    { key: 'username', label: 'Username', type: 'text' },
    { key: 'poscode', label: 'POS Code', type: 'text' },
    { key: 'cvlkra_password', label: 'CVL KRA Password', type: 'password' },
    {
      key: 'aes_key',
      label: 'AES Key (base64)',
      type: 'password',
      title: 'Base64 key that decodes to 16, 24, or 32 bytes.',
      placeholder: 'Base64 AES key',
    },
  ],

  'KRA SFTP': [
    { key: 'environment', label: 'Environment (uat/live)', type: 'text', placeholder: 'uat' },
    { key: 'sftp_host', label: 'KRA SFTP Host', type: 'text' },
    { key: 'sftp_port', label: 'KRA SFTP Port', type: 'text', placeholder: '22' },
    { key: 'sftp_username', label: 'KRA SFTP Username', type: 'text' },
    { key: 'sftp_password', label: 'KRA SFTP Password', type: 'password' },
    { key: 'sftp_base_path', label: 'KRA SFTP Base Path', type: 'text', placeholder: '.' },
  ],

  CDSL: [
    { key: 'DPID', label: 'DP ID', type: 'text' },
    { key: 'AES_key', label: 'AES Key', type: 'password' },
    { key: 'UserID', label: 'User ID', type: 'text' },
    { key: 'Password', label: 'Password', type: 'password' },
  ],

  NSDL: [
    { key: 'requesterid', label: 'Requester ID', type: 'text' },
    { key: 'certificate_file_name', label: 'Certificate File', type: 'text' },
    { key: 'private_key_file_password', label: 'Private Key Password', type: 'password' },
    { key: 'private_key_filename', label: 'Private Key File', type: 'text' },
    { key: 'ddpi_id', label: 'DDPI ID', type: 'text' },
  ],

  MCX: [
    { key: 'environment', label: 'Environment (uat/live)', type: 'text' },
    { key: 'member_id', label: 'Member ID', type: 'text' },
    { key: 'api_key', label: 'API Key', type: 'password' },
    {
      key: 'aes_key',
      label: 'AES Key (hex)',
      type: 'password',
      maxLength: 64,
      inputMode: 'text',
      pattern: '[0-9a-fA-F]{32}|[0-9a-fA-F]{48}|[0-9a-fA-F]{64}',
      title: 'Enter 32, 48, or 64 hexadecimal characters.',
      placeholder: '32, 48, or 64 hex characters',
    },
  ],

  MSE: [
    { key: 'environment', label: 'Environment (uat/live)', type: 'text', placeholder: 'uat' },
    { key: 'login_id', label: 'Login ID', type: 'text' },
    { key: 'password', label: 'Password', type: 'password' },
  ],
};

function createEmptyCredentials() {
  return CREDENTIAL_PROVIDERS.reduce((acc, provider) => ({
    ...acc,
    [provider]: PROVIDER_FIELDS[provider].reduce((fields, field) => ({
      ...fields,
      [field.key]: '',
    }), {}),
  }), {});
}

function credentialEndpoint(provider) {
  if (provider === 'BSE STAR MF') return 'bse_starmf';
  if (provider === 'KRA SFTP') return 'kra';
  return provider.toLowerCase();
}

export default function Credentials({ activeCompany }) {
  const [activeProvider, setActiveProvider] = useState('NSE');
  const companyName = activeCompany?.username ?? '';

  const [credentials, setCredentials] = useState(
    createEmptyCredentials
  );

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState({
    message: '',
    type: 'success',
  });

  const providerFields = PROVIDER_FIELDS[activeProvider] ?? [];

  const providerValues =
    credentials[activeProvider] ?? {};

  useEffect(() => {
    if (!toast.message) return undefined;

    const timer = window.setTimeout(
      () => setToast({
        message: '',
        type: 'success',
      }),
      toast.type === 'error' ? 15000 : 3000
    );

    return () => window.clearTimeout(timer);
  }, [toast]);

  function showToast(message, type = 'success') {
    setToast({ message, type });
  }

  useEffect(() => {
    if (!CREDENTIAL_EDITABLE_PROVIDERS.includes(activeProvider)) return undefined;
    const controller = new AbortController();
    const companyParam = activeCompany?.id ? `?user_id=${encodeURIComponent(activeCompany.id)}` : '';
    const endpoint = credentialEndpoint(activeProvider);
    setLoading(true);
    setError('');
    apiFetch(`${API_BASE}/api/${endpoint}_credentials/${companyParam}`, {
      headers: authHeaders(),
      signal: controller.signal,
    })
      .then(readJson)
      .then(data => setCredentials(current => ({
        ...current,
        [activeProvider]: { ...current[activeProvider], ...(data.credentials ?? {}) },
      })))
      .catch(err => {
        if (err.name !== 'AbortError') setError(`Failed to load ${activeProvider} credentials.`);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [activeProvider, activeCompany?.id]);

  function updateCredential(field, value) {
    setCredentials(current => ({
      ...current,
      [activeProvider]: {
        ...current[activeProvider],
        [field]: value,
      },
    }));
  }

  const [saving, setSaving] = useState(false);
  const [visiblePasswords, setVisiblePasswords] = useState({});

  function togglePassword(fieldKey) {
    const passwordKey = `${activeProvider}.${fieldKey}`;
    setVisiblePasswords(current => ({
      ...current,
      [passwordKey]: !current[passwordKey],
    }));
  }

  async function handleSave() {
    if (saving || loading || !CREDENTIAL_EDITABLE_PROVIDERS.includes(activeProvider)) return;
    if (
      activeProvider === 'MCX' &&
      providerValues.aes_key &&
      !MCX_AES_KEY_PATTERN.test(providerValues.aes_key.trim())
    ) {
      const message = 'MCX AES key must contain 32, 48, or 64 hexadecimal characters.';
      setError(message);
      showToast(message, 'error');
      return;
    }
    setSaving(true);
    setError('');

    try {
      const endpoint = `${credentialEndpoint(activeProvider)}_credentials`;
      const sftpOnly = activeProvider === 'KRA SFTP';

      const res = await apiFetch(
        `${API_BASE}/api/${endpoint}/`,
        {
          method: 'POST',
          headers: {
            ...authHeaders(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            user_id: activeCompany?.id,
            ...(sftpOnly ? { sftp_only: true } : {}),
            ...providerValues,
          }),
        }
      );

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const message =
          data.error ??
          'Failed to save credentials.';

        setError(message);
        showToast(message, 'error');
        return;
      }

      if (data.credentials) {
        setCredentials(current => ({
          ...current,
          [activeProvider]: {
            ...current[activeProvider],
            ...data.credentials,
          },
        }));
      }

      showToast(
        `${activeProvider} credentials saved for ${data.company}`
      );
    } catch {
      setError('Failed to save credentials.');

      showToast(
        'Failed to save credentials.',
        'error'
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="credentials-shell">

        {companyName && (
          <div className="credentials-company-banner">
            Company: <strong>{companyName}</strong>
          </div>
        )}

        <div className="credential-tabs">
          {CREDENTIAL_PROVIDERS.map(provider => (
            <button
              key={provider}
              type="button"
              className={`credential-tab ${activeProvider === provider
                ? 'active'
                : ''
                }`}
              onClick={() =>
                setActiveProvider(provider)
              }
            >
              {provider}
            </button>
          ))}
        </div>

        <div className="credentials-panel">

          <div className="credentials-panel-header">
            <h3>
              {activeProvider} Credentials
            </h3>

            <span>
              {loading
                ? 'Loading'
                : (companyName || activeProvider)}
            </span>
          </div>

          <div className="credentials-grid">

            {providerFields.map(field => (
              <label
                key={field.key}
                className="credential-field"
              >
                <span>{field.label}</span>

                {field.type === 'password' ? (
                  <div className="credential-password-wrap">
                    <input
                      type={visiblePasswords[`${activeProvider}.${field.key}`] ? 'text' : 'password'}
                      value={providerValues[field.key] ?? ''}
                      onChange={e =>
                        updateCredential(
                          field.key,
                          e.target.value
                        )
                      }
                      maxLength={field.maxLength}
                      pattern={field.pattern}
                      title={field.title}
                      inputMode={field.inputMode}
                      placeholder={field.placeholder ?? 'Leave blank to keep saved password'}
                      disabled={loading || saving || !CREDENTIAL_EDITABLE_PROVIDERS.includes(activeProvider)}
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      className="credential-password-toggle"
                      onClick={() => togglePassword(field.key)}
                      disabled={loading || saving || !CREDENTIAL_EDITABLE_PROVIDERS.includes(activeProvider)}
                      aria-label={visiblePasswords[`${activeProvider}.${field.key}`] ? 'Hide password' : 'Show password'}
                      title={visiblePasswords[`${activeProvider}.${field.key}`] ? 'Hide password' : 'Show password'}
                    >
                      {visiblePasswords[`${activeProvider}.${field.key}`]
                        ? <EyeOff size={17} />
                        : <Eye size={17} />}
                    </button>
                  </div>
                ) : (
                  <input
                    type={field.type}
                    value={providerValues[field.key] ?? ''}
                    onChange={e =>
                      updateCredential(
                        field.key,
                        e.target.value
                      )
                    }
                    maxLength={field.maxLength}
                    pattern={field.pattern}
                    title={field.title}
                    inputMode={field.inputMode}
                    placeholder={field.placeholder ?? `Enter ${field.label.toLowerCase()}`}
                    disabled={loading || saving || !CREDENTIAL_EDITABLE_PROVIDERS.includes(activeProvider)}
                    autoComplete="off"
                  />
                )}
              </label>
            ))}

          </div>

          <div className="credentials-actions">
            <button
              type="button"
              className="credential-primary-btn"
              onClick={handleSave}
              disabled={saving || loading || !CREDENTIAL_EDITABLE_PROVIDERS.includes(activeProvider)}
            >
              Save
            </button>
          </div>

        </div>
      </div>

      {toast.message && (
        <div
          className={`db-toast ${toast.type === 'error'
            ? 'error'
            : ''
            }`}
        >
          <span>
            {toast.type === 'error'
              ? '!'
              : '✓'}
          </span>

          {' '}{toast.message}
        </div>
      )}
    </>
  );
}
