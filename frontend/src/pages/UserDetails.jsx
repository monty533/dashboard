import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, RotateCcw, Save, UserRound, XCircle } from 'lucide-react';
import { API_BASE, apiFetch, authHeaders, readJson } from '../api';

const USER_DETAILS_ENDPOINT = '/api/client/userupdatedata/';

const READ_ONLY_FIELDS = new Set([
  'id', 'user', 'user_id', 'created_at', 'updated_at',
  'cdslresponse',
]);

const PUSH_PERMISSION_FIELDS = new Set([
  'bse_push',
  'bsestarmf_push', 'nse_push', 'nsdl_push', 'cdsl_push',
  'mcx_push', 'mse_push', 'ckyc_push', 'kra_push',
]);

const PUSH_TIMESTAMP_LABELS = {
  bse_push_at: 'BSE push date',
  bsestarmf_push_at: 'BSE Star MF push date',
  nse_push_at: 'NSE push date',
  nsdl_push_at: 'NSDL push date',
  cdsl_push_at: 'CDSL push date',
  mcx_push_at: 'MCX push date',
  mse_push_at: 'MSE push date',
  ckyc_push_at: 'CKYC push date',
  kra_push_at: 'KRA push date',
};
const PUSH_TIMESTAMP_NAMES = new Set(Object.keys(PUSH_TIMESTAMP_LABELS));

const LEGACY_SEGMENT_FIELDS = new Set([
  'bse_cash', 'bse_currency', 'bse_fo', 'bse_slbm', 'mcx',
  'nse_cash', 'nse_currency', 'nse_fo', 'nse_slbm',
  'bse_cash_push', 'bse_currency_push', 'bse_fo_push', 'bse_slbm_push',
  'nse_cash_push', 'nse_currency_push', 'nse_fo_push', 'nse_slbm_push',
]);

const CONDITIONAL_OPTIONS = {
  account_holder_type: ['individual', 'jointholder'],
  modeoftrading: ['offline', 'online'],
  mode_of_account: ['N', 'M'],
  transaction_type: ['account_opening', 'segment_addition', 'modification'],
  activestatus: ['A', 'I'],
  bse_push: ['true', 'false'],
  bsestarmf_push: ['true', 'false'],
  nse_push: ['true', 'false'],
  nsdl_push: ['true', 'false'],
  cdsl_push: ['true', 'false'],
  mcx_push: ['true', 'false'],
  mse_push: ['true', 'false'],
  ckyc_push: ['true', 'false'],
  kra_push: ['true', 'false'],
  nominee_check: ['yes', 'no'],
};

const CONDITIONAL_OPTION_LABELS = {
  transaction_type: {
    account_opening: 'Account Opening',
    segment_addition: 'Segment Addition',
    modification: 'Modification',
  },
  bse_push: {
    true: 'Allow BSE push',
    false: 'Do not push BSE',
  },
  bsestarmf_push: { true: 'Allow BSE Star MF push', false: 'Do not push BSE Star MF' },
  nse_push: { true: 'Allow NSE push', false: 'Do not push NSE' },
  nsdl_push: { true: 'Allow NSDL push', false: 'Do not push NSDL' },
  cdsl_push: { true: 'Allow CDSL push', false: 'Do not push CDSL' },
  mcx_push: { true: 'Allow MCX push', false: 'Do not push MCX' },
  mse_push: { true: 'Allow MSE push', false: 'Do not push MSE' },
  ckyc_push: { true: 'Allow CKYC push', false: 'Do not push CKYC' },
  kra_push: { true: 'Allow KRA push', false: 'Do not push KRA' },
};

const DATE_FIELDS = new Set([
  'networth_date',
  'annual_income_date',
  'aadhaar_dob',
  'nominee1_dob',
  'nominee2_dob',
  'nominee3_dob',
]);

const TEXTAREA_FIELDS = new Set([
  'addressline1', 'addressline2', 'addressline3', 'bankaddress', 'aadhaar_address',
  'nominee1_address1', 'nominee1_address2', 'nominee2_address1', 'nominee2_address2',
  'nominee3_address1', 'nominee3_address2',
]);

const FIELD_ORDER = [
  'clientcode', 'pan', 'fathername', 'mothername', 'mobile', 'email', 'account_holder_type',
  'addressline1', 'addressline2', 'addressline3',
  'networth', 'networth_date', 'modeoftrading', 'mode_of_account', 'transaction_type', 'dpid', 'dptype', 'education',
  'bse_push', 'bsestarmf_push', 'nse_push', 'nsdl_push', 'cdsl_push', 'mcx_push', 'mse_push', 'ckyc_push', 'kra_push',
  'uploadpan', 'uploadsignature', 'pdf_file_kra', 'aadhar_xml',
  'annual_income', 'annual_income_date', 'occupation', 'marital_status',
  'bankname', 'ifsc', 'micr', 'branchname', 'bankaddress', 'bank_city', 'bank_state', 'bank_pincode',
  'bankaccountnumber', 'accounttype',
  'aadhaar_name', 'aadhaar_dob', 'aadhaar_gender', 'aadhaar_house', 'aadhaar_dist', 'aadhaar_state',
  'aadhaar_country', 'aadhaar_image', 'aadhaar_file', 'aadhaar_pincode', 'aadhaar_address', 'aadhaar_no',
  'isdppoa', 'bsda_flag', 'pledge_standing_instruction', 'cdslresponse',
  'nominee_check',
  ...Array.from({ length: 3 }, (_, index) => {
    const number = index + 1;
    return [
      `nominee${number}_firstname`, `nominee${number}_middlename`, `nominee${number}_lastname`,
      `nominee${number}_pan`, `nominee${number}_dob`, `nominee${number}_relation`,
      `nominee${number}_address1`, `nominee${number}_address2`, `nominee${number}_city`,
      `nominee${number}_state`, `nominee${number}_country`, `nominee${number}_pincode`,
      `nominee${number}_mobile`, `nominee${number}_email`, `nominee${number}_percentage`,
    ];
  }).flat(),
];

const FIELD_LABELS = {
  clientcode: 'Client code',
  account_holder_type: 'Account holder type',
  modeoftrading: 'Mode of trading',
  mode_of_account: 'Mode of account',
  dpid: 'DP ID / BO ID',
  dptype: 'Depository type',
  bse_push: 'BSE push permission',
  bsestarmf_push: 'BSE Star MF push permission',
  nse_push: 'NSE push permission',
  nsdl_push: 'NSDL push permission',
  cdsl_push: 'CDSL push permission',
  mcx_push: 'MCX push permission',
  mse_push: 'MSE push permission',
  ckyc_push: 'CKYC push permission',
  kra_push: 'KRA push permission',
  aadhaar_name: 'Aadhaar name',
  aadhaar_dob: 'Aadhaar date of birth',
  aadhaar_dist: 'Aadhaar district',
  aadhaar_pincode: 'Aadhaar PIN code',
  aadhaar_no: 'Aadhaar number',
  uploadpan: 'PAN document reference',
  pdf_file_kra: 'KRA PDF document reference',
  aadhar_xml: 'Aadhaar XML document reference',
  uploadsignature: 'Signature document reference',
  bsda_flag: 'BSDA flag',
  isdppoa: 'ISD / POA',
  cdslresponse: 'CDSL response',
  nominee_check: 'Nominee enabled',
  bank_city: 'Bank city',
  bank_state: 'Bank state',
  bank_pincode: 'Bank PIN code',
  nominee1_percentage: 'Nominee 1 percentage',
  nominee2_percentage: 'Nominee 2 percentage',
  nominee3_percentage: 'Nominee 3 percentage',
};

const SECTION_CONFIG = [
  {
    id: 'identity',
    title: 'Identity & contact',
    description: 'Primary client identity and contact details.',
    matches: name => ['clientcode', 'pan', 'fathername', 'mothername', 'mobile', 'email', 'account_holder_type'].includes(name),
  },
  {
    id: 'address',
    title: 'Address',
    description: 'Correspondence address for the client.',
    matches: name => name.startsWith('addressline'),
  },
  {
    id: 'trading',
    title: 'Trading & account',
    description: 'Trading profile, depository and account configuration.',
    matches: name => ['networth', 'networth_date', 'modeoftrading', 'mode_of_account', 'transaction_type', 'dpid', 'dptype', 'education'].includes(name),
  },
  {
    id: 'providerPermissions',
    title: 'Provider push permissions',
    description: 'Choose which provider APIs may receive this client.',
    matches: name => [
      'bse_push', 'bsestarmf_push', 'nse_push', 'nsdl_push', 'cdsl_push',
      'mcx_push', 'mse_push', 'ckyc_push', 'kra_push',
    ].includes(name),
  },
  {
    id: 'providerPushDates',
    title: 'Provider push dates',
    description: 'Optional date and time recorded for each provider push.',
    matches: name => PUSH_TIMESTAMP_NAMES.has(name),
  },
  {
    id: 'documents',
    title: 'Documents',
    description: 'References or paths for uploaded documents.',
    matches: name => ['uploadpan', 'uploadsignature', 'pdf_file_kra', 'aadhar_xml'].includes(name),
  },
  {
    id: 'profile',
    title: 'Profile & KYC',
    description: 'Income, occupation and KYC profile information.',
    matches: name => ['annual_income', 'annual_income_date', 'occupation', 'marital_status'].includes(name),
  },
  {
    id: 'bank',
    title: 'Bank details',
    description: 'Primary bank account information.',
    matches: name => name.startsWith('bank') || ['ifsc', 'micr', 'branchname', 'accounttype'].includes(name),
  },
  {
    id: 'aadhaar',
    title: 'Aadhaar details',
    description: 'Aadhaar identity and address information.',
    matches: name => name.startsWith('aadhaar_'),
  },
  {
    id: 'nominee',
    title: 'Nominee details',
    description: 'Nomination choice and up to three nominees.',
    matches: name => name === 'nominee_check' || name.startsWith('nominee'),
  },
  {
    id: 'preferences',
    title: 'Other preferences',
    description: 'Additional account flags and provider information.',
    matches: name => ['isdppoa', 'bsda_flag', 'pledge_standing_instruction', 'cdslresponse'].includes(name),
  },
];

function fieldLabel(name) {
  if (FIELD_LABELS[name]) return FIELD_LABELS[name];
  return name
    .replaceAll('_', ' ')
    .replace(/\b\w/g, character => character.toUpperCase());
}

function defaultFieldValue(name) {
  return PUSH_PERMISSION_FIELDS.has(name) ? 'false' : '';
}

function formatPushTimestamp(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 19);
  const pad = number => String(number).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
    + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function sectionForField(name) {
  return SECTION_CONFIG.find(section => section.matches(name))?.id ?? 'other';
}

function errorText(value) {
  if (Array.isArray(value)) return value.join(' ');
  if (value && typeof value === 'object') return Object.values(value).flat().join(' ');
  return String(value ?? '');
}

function backendErrorMessage(data, fallback) {
  const fieldErrors = Object.entries(data?.errors ?? {})
    .map(([name, value]) => `${fieldLabel(name)}: ${errorText(value)}`)
    .filter(Boolean);
  const message = data?.message || data?.error || data?.detail || fallback;
  return fieldErrors.length ? `${message} ${fieldErrors.join(' ')}` : message;
}

function buildTargetQuery(role, selectedUserId, extra = {}) {
  const params = new URLSearchParams(extra);
  if (role === 'admin' && selectedUserId) params.set('user_id', selectedUserId);
  return params.toString();
}

function userDetailsHeaders(apiKey = '') {
  return {
    ...authHeaders(),
    ...(apiKey ? { 'X-API-Key': apiKey } : {}),
  };
}

function sortFields(fields) {
  const order = new Map(FIELD_ORDER.map((name, index) => [name, index]));
  return fields
    .filter(field => (
      field?.name
      && !READ_ONLY_FIELDS.has(field.name)
      && !LEGACY_SEGMENT_FIELDS.has(field.name)
    ))
    .sort((left, right) => (order.get(left.name) ?? 999) - (order.get(right.name) ?? 999));
}

export default function UserDetails({ activeCompany = null, role = 'user' }) {
  const [fields, setFields] = useState([]);
  const [form, setForm] = useState({});
  const [clients, setClients] = useState([]);
  const [clientsLoading, setClientsLoading] = useState(true);
  const [clientListError, setClientListError] = useState('');
  const [selectedClientCode, setSelectedClientCode] = useState('');
  const [editingClientCode, setEditingClientCode] = useState('');
  const [users, setUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState(activeCompany?.id ? String(activeCompany.id) : '');
  const [schemaLoading, setSchemaLoading] = useState(true);
  const [usersLoading, setUsersLoading] = useState(role === 'admin');
  const [loadingError, setLoadingError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [toast, setToast] = useState({ message: '', type: 'success' });
  const [apiKeyCopied, setApiKeyCopied] = useState(false);
  const [apiKeyVerification, setApiKeyVerification] = useState({ status: 'idle', message: '' });
  const [verifiedApiKeyDetails, setVerifiedApiKeyDetails] = useState(null);
  const [validationModalMessage, setValidationModalMessage] = useState('');
  const [validationModalType, setValidationModalType] = useState('error');
  const [openSections, setOpenSections] = useState(() => new Set(['identity', 'address']));

  useEffect(() => {
    if (!toast.message) return undefined;
    const timer = window.setTimeout(() => {
      setToast({ message: '', type: 'success' });
    }, toast.type === 'error' ? 15000 : 3000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function showToast(message, type = 'success') {
    setToast({ message, type });
  }

  function showValidationModal(message, type = 'error') {
    setValidationModalType(type);
    setValidationModalMessage(message);
  }

  useEffect(() => {
    if (!verifiedApiKeyDetails) return undefined;
    const timer = window.setTimeout(() => {
      setVerifiedApiKeyDetails(null);
      setApiKeyVerification({ status: 'idle', message: '' });
    }, 10000);
    return () => window.clearTimeout(timer);
  }, [verifiedApiKeyDetails]);

  useEffect(() => {
    if (!validationModalMessage) return undefined;
    const timer = window.setTimeout(() => setValidationModalMessage(''), 10000);
    return () => window.clearTimeout(timer);
  }, [validationModalMessage]);

  useEffect(() => {
    const controller = new AbortController();
    setSchemaLoading(true);
    setLoadingError('');
    apiFetch(`${API_BASE}/api/table/userdetails/schema/`, {
      headers: authHeaders(),
      signal: controller.signal,
    })
      .then(readJson)
      .then(data => {
        const nextFields = sortFields(data.fields ?? []);
        setFields(nextFields);
        setForm(current => nextFields.reduce((next, field) => {
          next[field.name] = current[field.name] ?? defaultFieldValue(field.name);
          return next;
        }, {}));
      })
      .catch(error => {
        if (error.name !== 'AbortError') {
          const message = error.message || 'Could not load UserDetails fields.';
          setLoadingError(message);
          showToast(message, 'error');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setSchemaLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (role !== 'admin') {
      setUsersLoading(false);
      return undefined;
    }
    const controller = new AbortController();
    setUsersLoading(true);
    apiFetch(`${API_BASE}/api/users/`, {
      headers: authHeaders(),
      signal: controller.signal,
    })
      .then(readJson)
      .then(data => setUsers(data.users ?? []))
      .catch(error => {
        if (error.name !== 'AbortError') {
          const message = error.message || 'Could not load companies.';
          setLoadingError(message);
          showToast(message, 'error');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setUsersLoading(false);
      });
    return () => controller.abort();
  }, [role]);

  useEffect(() => {
    setSelectedUserId(activeCompany?.id ? String(activeCompany.id) : '');
  }, [activeCompany?.id]);

  const companyOptions = useMemo(() => {
    const options = [...users];
    if (activeCompany?.id && !options.some(user => String(user.id) === String(activeCompany.id))) {
      options.unshift(activeCompany);
    }
    return options;
  }, [users, activeCompany]);

  const selectedOwner = useMemo(
    () => companyOptions.find(user => String(user.id) === String(selectedUserId)) ?? null,
    [companyOptions, selectedUserId],
  );
  const selectedApiKey = role === 'admin'
    ? selectedOwner?.api_key || (String(activeCompany?.id) === String(selectedUserId) ? activeCompany?.api_key : '') || ''
    : '';
  const selectedApiKeyPrefix = selectedOwner?.api_key_prefix
    || (String(activeCompany?.id) === String(selectedUserId) ? activeCompany?.api_key_prefix : '')
    || '';

  useEffect(() => {
    if (role === 'admin' && !selectedUserId) {
      setClients([]);
      setClientsLoading(false);
      setClientListError('');
      return undefined;
    }

    const controller = new AbortController();
    const query = buildTargetQuery(role, selectedUserId);
    setClientsLoading(true);
    setClientListError('');
    apiFetch(`${API_BASE}${USER_DETAILS_ENDPOINT}${query ? `?${query}` : ''}`, {
      headers: userDetailsHeaders(selectedApiKey),
      signal: controller.signal,
    })
      .then(readJson)
      .then(data => setClients(data.clients ?? []))
      .catch(error => {
        if (error.name !== 'AbortError') {
          const message = error.message || 'Could not load client codes.';
          setClientListError(message);
          showToast(message, 'error');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setClientsLoading(false);
      });

    return () => controller.abort();
  }, [role, selectedUserId, selectedApiKey]);

  useEffect(() => {
    setSelectedClientCode('');
    setEditingClientCode('');
    setSaveError('');
    setFieldErrors({});
    setApiKeyCopied(false);
    setApiKeyVerification({ status: 'idle', message: '' });
    setVerifiedApiKeyDetails(null);
    setValidationModalMessage('');
    setForm(current => fields.reduce((next, field) => {
      next[field.name] = defaultFieldValue(field.name);
      return next;
    }, {}));
  }, [selectedUserId]);

  const payload = useMemo(() => fields.reduce((result, field) => {
    const value = form[field.name] ?? '';
    result[field.name] = PUSH_TIMESTAMP_NAMES.has(field.name) && value === ''
      ? null
      : field.db_type === 'tinyint' && value === ''
        ? false
        : value;
    return result;
  }, {}), [fields, form]);

  const groupedFields = useMemo(() => {
    const groups = new Map(SECTION_CONFIG.map(section => [section.id, []]));
    groups.set('other', []);
    fields.forEach(field => groups.get(sectionForField(field.name)).push(field));
    return [...SECTION_CONFIG, { id: 'other', title: 'Additional fields', description: 'Other fields available in the UserDetails model.', matches: () => true }]
      .map(section => ({ ...section, fields: groups.get(section.id) ?? [] }))
      .filter(section => section.fields.length > 0);
  }, [fields]);

  function revealErrorSections(errors) {
    const errorNames = new Set(Object.keys(errors ?? {}));
    setOpenSections(current => {
      const next = new Set(current);
      fields.forEach(field => {
        if (errorNames.has(field.name)) next.add(sectionForField(field.name));
      });
      return next;
    });
  }

  function updateField(event) {
    const { name, value } = event.target;
    setForm(current => {
      const next = { ...current, [name]: value };
      if (name === 'nominee_check' && value !== 'yes') {
        fields.forEach(field => {
          if (field.name.startsWith('nominee') && field.name !== 'nominee_check') {
            next[field.name] = '';
          }
        });
      }
      return next;
    });
    setFieldErrors(current => {
      if (!current[name]) return current;
      const next = { ...current };
      delete next[name];
      return next;
    });
  }

  async function openClient(clientcode) {
    setSelectedClientCode(clientcode);
    setClientListError('');
    setSaveError('');
    setFieldErrors({});
    try {
      const query = buildTargetQuery(role, selectedUserId, { clientcode });
      const response = await apiFetch(`${API_BASE}${USER_DETAILS_ENDPOINT}?${query}`, {
        headers: userDetailsHeaders(selectedApiKey),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(backendErrorMessage(data, 'Could not load this client.'));
      }
      const record = data.data ?? {};
      setForm(fields.reduce((next, field) => {
        const recordValue = record[field.name];
        next[field.name] = recordValue == null
          ? defaultFieldValue(field.name)
          : PUSH_PERMISSION_FIELDS.has(field.name)
            ? String(recordValue).toLowerCase()
            : String(recordValue);
        return next;
      }, {}));
      setEditingClientCode(record.clientcode || clientcode);
      document.getElementById('userdetails-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) {
      const message = error.message || 'Could not load this client.';
      setClientListError(message);
      showToast(message, 'error');
    }
  }

  function updateClientList(record, previousClientCode = '') {
    if (!record?.clientcode) return;
    const summary = {
      id: record.id,
      clientcode: record.clientcode,
      aadhaar_name: record.aadhaar_name || '',
      pan: record.pan || '',
      email: record.email || '',
    };
    setClients(current => [
      ...current.filter(client => (
        client.clientcode !== previousClientCode && String(client.id) !== String(record.id)
      )),
      summary,
    ].sort((left, right) => left.clientcode.localeCompare(right.clientcode)));
  }

  async function saveUserDetails(event) {
    event.preventDefault();
    if (role === 'admin' && !selectedUserId) {
      const message = 'Select a company before saving UserDetails.';
      setSaveError(message);
      showValidationModal(message);
      return;
    }
    if (role === 'admin' && !selectedApiKey) {
      const message = 'No active API key is available for the selected company.';
      setSaveError(message);
      showValidationModal(message);
      return;
    }

    setSaving(true);
    setSaveError('');
    setFieldErrors({});
    const method = editingClientCode ? 'PATCH' : 'POST';

    try {
      const verified = selectedApiKey ? await fetchVerifiedApiKeyDetails() : null;
      if (verified) {
        setApiKeyVerification({ status: 'success', message: `API key verified for user ID ${verified.userId}.` });
      }
      if (role === 'admin' && String(selectedUserId) !== verified.userId) {
        throw new Error('The API key belongs to a different company than the selected company.');
      }

      const query = buildTargetQuery(
        role,
        verified?.userId ?? selectedUserId,
        editingClientCode ? { clientcode: editingClientCode } : {},
      );
      const response = await apiFetch(`${API_BASE}${USER_DETAILS_ENDPOINT}${query ? `?${query}` : ''}`, {
        method,
        headers: userDetailsHeaders(selectedApiKey),
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const errors = data.errors ?? {};
        setFieldErrors(errors);
        revealErrorSections(errors);
        throw new Error(backendErrorMessage(data, 'Could not save UserDetails.'));
      }
      const savedRecord = data.data ?? {};
      updateClientList(savedRecord, editingClientCode);
      setEditingClientCode(savedRecord.clientcode || editingClientCode || form.clientcode || '');
      setSelectedClientCode(savedRecord.clientcode || editingClientCode || form.clientcode || '');
      showValidationModal(
        editingClientCode
          ? 'UserDetails updated successfully.'
          : 'UserDetails saved successfully.',
        'success',
      );
    } catch (error) {
      const message = error.message || 'Could not save UserDetails.';
      setSaveError(message);
      showValidationModal(message);
    } finally {
      setSaving(false);
    }
  }

  async function copyApiKey() {
    if (!selectedApiKey) return;
    try {
      await navigator.clipboard.writeText(selectedApiKey);
      setApiKeyCopied(true);
      showToast('API key copied to clipboard.');
    } catch {
      showToast('Clipboard access is unavailable.', 'error');
    }
  }

  async function fetchVerifiedApiKeyDetails() {
    const response = await apiFetch(`${API_BASE}/api/client/me/`, {
      headers: { 'X-API-Key': selectedApiKey },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || data.error || 'API key verification failed.');
    }
    const userId = data.user?.id;
    if (!userId) throw new Error('The API key response did not include a user ID.');
    return { data, userId: String(userId) };
  }

  async function verifyApiKey() {
    if (!selectedApiKey || apiKeyVerification.status === 'checking') return;
    setApiKeyVerification({ status: 'checking', message: 'Verifying API key…' });
    try {
      const { data } = await fetchVerifiedApiKeyDetails();
      const owner = data.profile?.company_name || data.user?.email || 'this company';
      const message = `API key verified for ${owner}.`;
      setApiKeyVerification({ status: 'success', message });
      setVerifiedApiKeyDetails(data);
      showToast(message);
    } catch (error) {
      const message = error.message || 'API key verification failed.';
      setApiKeyVerification({ status: 'error', message });
      showToast(message, 'error');
    }
  }

  function resetForm() {
    setForm(fields.reduce((result, field) => {
      result[field.name] = defaultFieldValue(field.name);
      return result;
    }, {}));
    setSelectedClientCode('');
    setEditingClientCode('');
    setSaveError('');
    setFieldErrors({});
    setApiKeyCopied(false);
    setApiKeyVerification({ status: 'idle', message: '' });
    setVerifiedApiKeyDetails(null);
    setValidationModalMessage('');
  }

  function closeApiKeyDetails() {
    setVerifiedApiKeyDetails(null);
    setApiKeyVerification({ status: 'idle', message: '' });
  }

  function closeValidationModal() {
    setValidationModalMessage('');
  }

  const knownFieldNames = new Set(fields.map(field => field.name));
  const generalErrors = Object.entries(fieldErrors).filter(([name]) => !knownFieldNames.has(name));
  const nomineeEnabled = form.nominee_check === 'yes';

  if (schemaLoading) {
    return <div className="userdetails-state">Loading UserDetails form…</div>;
  }

  if (loadingError && !fields.length) {
    return (
      <div className="userdetails-state userdetails-state-error">
        <strong>{loadingError}</strong>
        <p>Refresh the page and try again.</p>
      </div>
    );
  }

  return (
    <div className="userdetails-page">
      {toast.message && (
        <div
          className={`db-toast ${toast.type === 'error' ? 'error' : ''}`}
          role={toast.type === 'error' ? 'alert' : 'status'}
        >
          <span>{toast.type === 'error' ? <XCircle size={16} /> : <CheckCircle2 size={16} />}</span>
          {toast.message}
        </div>
      )}
      <div className="userdetails-intro">
        <div>
          <span className="userdetails-eyebrow"><UserRound size={14} /> Client onboarding</span>
          <h2>{editingClientCode ? `Edit ${editingClientCode}` : 'Enter UserDetails'}</h2>
          <p>Complete the form below. The UI sends the same JSON payload as the client API and saves it to the selected user.</p>
        </div>
        <div className="userdetails-endpoint-card">
          <span>POST endpoint</span>
          <code>{USER_DETAILS_ENDPOINT}</code>
          <small>{editingClientCode ? 'PATCH updates this client' : 'Validated before saving'}</small>
        </div>
      </div>

      <div className="userdetails-owner-card">
        <div>
          <span className="userdetails-card-label">Record owner</span>
          <strong>{role === 'admin' ? 'Choose the company that will own this record' : 'Your account'}</strong>
        </div>
        {role === 'admin' ? (
          <select
            value={selectedUserId}
            onChange={event => {
              setSelectedUserId(event.target.value);
              resetForm();
            }}
            disabled={usersLoading}
            aria-label="Select company"
          >
            <option value="">Select company…</option>
            {companyOptions.map(user => (
              <option key={user.id} value={user.id}>
                {user.company_name || user.username || user.email} · {user.email}
              </option>
            ))}
          </select>
        ) : (
          <span className="userdetails-owner-badge">{localStorage.getItem('auth_username') || 'Signed-in user'}</span>
        )}
      </div>

      <div className="userdetails-api-key-card">
        <div className="userdetails-api-key-heading">
          <div>
            <span className="userdetails-card-label">Client API key</span>
            <strong>{selectedApiKey ? 'Used in the X-API-Key header for this company' : 'No active API key found'}</strong>
          </div>
          {selectedApiKey && (
            <div className="userdetails-api-key-actions">
              <button
                type="button"
                className="userdetails-verify-key-btn"
                onClick={verifyApiKey}
                disabled={apiKeyVerification.status === 'checking'}
              >
                {apiKeyVerification.status === 'checking' ? 'Verifying…' : 'Verify API key'}
              </button>
              <button type="button" className="userdetails-copy-key-btn" onClick={copyApiKey}>
                {apiKeyCopied ? 'Copied' : 'Copy API key'}
              </button>
            </div>
          )}
        </div>
        {role === 'admin' && !selectedUserId ? (
          <p className="userdetails-api-key-empty">Select a company to load its API key.</p>
        ) : selectedApiKey ? (
          <div className="userdetails-api-key-values">
            <div>
              <span>Prefix</span>
              <code>{selectedApiKeyPrefix || '—'}</code>
            </div>
            <div className="userdetails-api-key-value">
              <span>X-API-Key</span>
              <code>{selectedApiKey}</code>
            </div>
          </div>
        ) : (
          <p className="userdetails-api-key-empty">This user has no active API key. Create a new company key first.</p>
        )}
        {apiKeyVerification.message && (
          <p className={`userdetails-api-key-status ${apiKeyVerification.status}`} role="status">
            {apiKeyVerification.message}
          </p>
        )}
      </div>

      {validationModalMessage && (
        <div className="company-register-backdrop" role="presentation">
          <div
            className="company-register-modal userdetails-validation-modal"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="userdetails-validation-title"
          >
            <div className="company-register-heading">
              <div>
                <p className={`company-register-eyebrow ${validationModalType === 'success' ? 'userdetails-validation-success-eyebrow' : 'userdetails-validation-eyebrow'}`}>
                  {validationModalType === 'success' ? 'Saved successfully' : 'Validation error'}
                </p>
                <h2 id="userdetails-validation-title">
                  {validationModalType === 'success' ? 'UserDetails saved successfully' : 'Could not save UserDetails'}
                </h2>
                <p>
                  {validationModalType === 'success'
                    ? 'Your changes have been saved.'
                    : 'Correct the highlighted fields and try again.'}
                </p>
              </div>
              <button type="button" className="company-modal-close" onClick={closeValidationModal} aria-label="Close">
                ×
              </button>
            </div>
            <div className={`userdetails-modal-error-message ${validationModalType === 'success' ? 'userdetails-modal-success-message' : ''}`}>
              {validationModalMessage}
            </div>
            <button type="button" className="company-modal-secondary company-done-btn" onClick={closeValidationModal}>
              Done
            </button>
          </div>
        </div>
      )}

      {verifiedApiKeyDetails && (
        <div className="company-register-backdrop" role="presentation">
          <div
            className="company-register-modal company-api-details"
            role="dialog"
            aria-modal="true"
            aria-labelledby="userdetails-api-key-details-title"
          >
            <div className="company-register-heading">
              <div>
                <p className="company-register-eyebrow">Verified successfully</p>
                <h2 id="userdetails-api-key-details-title">API key details</h2>
                <p>The API key is valid and belongs to the selected company.</p>
              </div>
              <button type="button" className="company-modal-close" onClick={closeApiKeyDetails} aria-label="Close">
                ×
              </button>
            </div>

            <div className="company-key-box">{selectedApiKey}</div>
            {['user', 'profile'].map(section => (
              <section className="company-detail-section" key={section}>
                <h3>{section === 'user' ? 'User' : 'Profile'}</h3>
                <div className="company-detail-grid">
                  {Object.entries(verifiedApiKeyDetails[section] || {}).map(([field, value]) => (
                    <div className="company-detail-row" key={field}>
                      <span>{field.replaceAll('_', ' ')}</span>
                      <strong>{value === null || value === '' ? '—' : String(value)}</strong>
                    </div>
                  ))}
                </div>
              </section>
            ))}

            <button type="button" className="company-modal-secondary company-done-btn" onClick={closeApiKeyDetails}>
              Done
            </button>
          </div>
        </div>
      )}

      <div className="userdetails-client-browser">
        <div className="userdetails-client-browser-head">
          <div>
            <span className="userdetails-card-label">Saved client codes</span>
            <strong>{editingClientCode ? `Editing ${editingClientCode}` : 'Select a client code to open its details'}</strong>
          </div>
          <button type="button" className="userdetails-new-btn" onClick={resetForm} disabled={saving}>
            + New client
          </button>
        </div>
        {role === 'admin' && !selectedUserId ? (
          <p className="userdetails-client-empty">Select a company above to load its client codes.</p>
        ) : clientsLoading ? (
          <p className="userdetails-client-empty">Loading client codes…</p>
        ) : clients.length === 0 ? (
          <p className="userdetails-client-empty">No saved client codes yet. Start with the form below.</p>
        ) : (
          <div className="userdetails-client-list">
            {clients.map(client => (
              <button
                type="button"
                key={client.id || client.clientcode}
                className={`userdetails-client-card ${selectedClientCode === client.clientcode ? 'active' : ''}`}
                onClick={() => openClient(client.clientcode)}
              >
                <strong>{client.clientcode}</strong>
                <span>{client.aadhaar_name || 'Name unavailable'}</span>
                <small>{client.pan || client.email || 'Client details'}</small>
              </button>
            ))}
          </div>
        )}
        {clientListError && <p className="userdetails-client-error" role="alert">{clientListError}</p>}
      </div>

      {loadingError && <p className="userdetails-alert" role="alert">{loadingError}</p>}
      {generalErrors.length > 0 && (
        <div className="userdetails-validation-summary" role="alert">
          {generalErrors.map(([name, value]) => <p key={name}><strong>{fieldLabel(name)}:</strong> {errorText(value)}</p>)}
        </div>
      )}

      <form id="userdetails-form" noValidate onSubmit={saveUserDetails}>
        <div className="userdetails-section-list">
          {groupedFields.map((section, index) => (
            <details
              className="userdetails-section"
              key={section.id}
              open={openSections.has(section.id) || (section.id === 'nominee' && nomineeEnabled)}
              onToggle={event => {
                const isOpen = event.currentTarget.open;
                setOpenSections(current => {
                  const next = new Set(current);
                  if (isOpen) next.add(section.id);
                  else next.delete(section.id);
                  return next;
                });
              }}
            >
              <summary>
                <span>
                  <strong>{section.title}</strong>
                  <small>{section.description}</small>
                </span>
                <em>{section.fields.filter(field => field.requirement === 'mandatory').length} required</em>
              </summary>
              <div className="userdetails-field-grid">
                {section.fields
                  .filter(field => section.id !== 'nominee' || field.name === 'nominee_check' || nomineeEnabled)
                  .map(field => {
                  const name = field.name;
                  if (section.id === 'providerPushDates') {
                    return (
                      <label className="userdetails-field" key={name}>
                        <span>{PUSH_TIMESTAMP_LABELS[name]}</span>
                        <input
                          name={name}
                          type="datetime-local"
                          step="1"
                          value={formatPushTimestamp(form[name])}
                          onChange={updateField}
                        />
                      </label>
                    );
                  }
                  const options = CONDITIONAL_OPTIONS[name];
                  const isRequired = field.requirement === 'mandatory';
                  const fieldError = errorText(fieldErrors[name]);
                  const inputProps = {
                    name,
                    value: form[name] ?? '',
                    onChange: updateField,
                    required: isRequired,
                    maxLength: field.max_length && field.max_length < 65535 ? field.max_length : undefined,
                    placeholder: `Enter ${fieldLabel(name).toLowerCase()}`,
                  };

                  return (
                    <label className={`userdetails-field ${TEXTAREA_FIELDS.has(name) ? 'wide' : ''}`} key={name}>
                      <span>{fieldLabel(name)} {isRequired && <b>*</b>}</span>
                      {options ? (
                        <select {...inputProps}>
                          <option value="">Select {fieldLabel(name).toLowerCase()}</option>
                          {options.map(option => (
                            <option key={option} value={option}>
                              {CONDITIONAL_OPTION_LABELS[name]?.[option] ?? option}
                            </option>
                          ))}
                        </select>
                      ) : TEXTAREA_FIELDS.has(name) ? (
                        <textarea {...inputProps} rows={2} />
                      ) : (
                        <input
                          {...inputProps}
                          type={DATE_FIELDS.has(name) ? 'date' : name === 'email' ? 'email' : name === 'mobile' ? 'tel' : 'text'}
                        />
                      )}
                      {fieldError && <small className="userdetails-field-error">{fieldError}</small>}
                    </label>
                  );
                })}
              </div>
            </details>
          ))}
        </div>

        <details className="userdetails-payload-preview">
          <summary>Preview JSON payload ({fields.length} fields)</summary>
          <pre>{JSON.stringify(payload, null, 2)}</pre>
        </details>

        <div className="userdetails-actions">
          <button type="button" className="userdetails-reset-btn" onClick={resetForm} disabled={saving}>
            <RotateCcw size={15} /> Reset
          </button>
          <button type="submit" className="userdetails-save-btn" disabled={saving || (role === 'admin' && (!selectedUserId || !selectedApiKey))}>
            <Save size={15} /> {saving ? 'Saving…' : editingClientCode ? 'Validate & Update UserDetails' : 'Validate & Save UserDetails'}
          </button>
        </div>
      </form>
    </div>
  );
}
