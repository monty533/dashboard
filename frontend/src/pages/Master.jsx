import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { API_BASE, authHeaders, apiFetch, readJson } from '../api';

const DEFAULT_TYPE_OPTS = ['str', 'text', 'int', 'bigint', 'float', 'bool', 'datetime'];
const TEXT_DEFAULT_LENGTH = 65535;
const SCHEMA_PAGE_SIZE = 10;
const VALUE_MASTER_PAGE_SIZE = 10;
const CONDITIONAL_PARAMETER_OPTIONS = ['individual', 'jointholder'];
const CONDITIONAL_PARAMETER_OPTIONS_BY_COLUMN = {
  account_holder_type: ['individual', 'jointholder'],
  modeoftrading: ['offline', 'online'],
  mode_of_account: ['N', 'M'],
  transaction_type: ['account_opening', 'segment_addition', 'modification'],
  activestatus: ['A', 'I'],
  bse_cash: ['true', 'false'],
  bse_currency: ['true', 'false'],
  bse_fo: ['true', 'false'],
  bse_slbm: ['true', 'false'],
  mcx: ['true', 'false'],
  nse_cash: ['true', 'false'],
  nse_currency: ['true', 'false'],
  nse_fo: ['true', 'false'],
  nse_slbm: ['true', 'false'],
  nominee_check: ['yes', 'no'],
};
const CONDITIONAL_PARAMETER_LABELS_BY_COLUMN = {
  mode_of_account: {
    N: 'N - New account',
    M: 'M - Modification',
  },
  transaction_type: {
    account_opening: 'Account Opening',
    segment_addition: 'Segment Addition',
    modification: 'Modification',
  },
  activestatus: {
    A: 'A - Active',
    I: 'I - Inactive',
  },
};
const CONDITIONAL_PARAMETER_DISPLAY_BY_COLUMN = {
  newaddress: 'addresschangeyesno',
};

function filterNsdlSchema(schema, tableName) {
  if (!schema || String(tableName ?? '').toLowerCase() !== 'nsdl') return schema;
  const modelColumns = new Set((schema.model_columns ?? []).map(String));
  return {
    ...schema,
    fields: modelColumns.size
      ? (schema.fields ?? []).filter(field => modelColumns.has(String(field.name)))
      : schema.fields,
  };
}

function conditionalParameterLabel(columnName, parameter) {
  const labels = CONDITIONAL_PARAMETER_LABELS_BY_COLUMN[String(columnName ?? '').toLowerCase()];
  return labels?.[parameter] ?? parameter;
}

const TABLE_LABELS = {
  bse: 'BSE',
  bse_star_mf: 'BSE Star MF',
  bse_star_mf_dependency_master: 'BSE Star MF Dependency Master',
  bse_star_mf_gender_master: 'BSE Star MF Gender Master',
  bse_star_mf_state_code_master: 'BSE Star MF State Code Master',
  bse_star_mf_tax_status_master: 'BSE Star MF Tax Status Master',
  cdsl: 'CDSL',
  ckyc_state_code_master: 'CKYC State Code Master',
  kra_status_master: 'KRA Status Master',
  kra_error_code: 'KRA Error Code Master',
  kra_marital_status_master: 'KRA Marital Status Master',
  kra_gender_master: 'KRA Gender Master',
  cdsl_state_code_master: 'CDSL State Code Master',
  cdsl_income_range_master: 'CDSL Income Range Master',
  nse: 'NSE',
  nse_state_code_master: 'NSE State Code Master',
  nse_marital_status_master: 'NSE Marital Status Master',
  nse_occupation_master: 'NSE Occupation Master',
  nse_income_range_master: 'NSE Income Range Master',
  bse_income_range_master: 'BSE Income Range Master',
  nsdl: 'NSDL',
  nsdl_state_code_master: 'NSDL State Code Master',
  nsdl_income_range_master: 'NSDL Income Range Master',
  nsdl_occupation_master: 'NSDL Occupation Master',
  nsdl_relation_master: 'NSDL Relation Master',
  nsdl_account_type_master: 'NSDL Account Type Master',
  nsdl_country_master: 'NSDL Country Master',
  nsdl_gender_master: 'NSDL Gender Master',
  mcx: 'MCX',
  mcx_state_city_master: 'MCX State City Master',
  mcx_marital_status_master: 'MCX Marital Status Master',
  mcx_gender_master: 'MCX Gender Master',
  mcx_income_range_master: 'MCX Income Range Master',
  mcx_occupation_master: 'MCX Occupation Master',
  mcx_account_type_master: 'MCX Account Type Master',
  mcx_error_code: 'MCX Error Code Master',
  mse: 'MSE',
  mse_state_code_master: 'MSE State Code Master',
  mse_income_range_master: 'MSE Income Range Master',
  mse_occupation_master: 'MSE Occupation Master',
  mse_account_type_master: 'MSE Account Type Master',
  userdetails: 'User Details',
};

export function getTableLabel(tableName) {
  if (!tableName) return '';
  const key = tableName.toLowerCase();
  return TABLE_LABELS[key] ?? tableName
    .replace(/_/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase());
}

const TYPE_COLOR = {
  str: { bg: '#eff6ff', color: '#1d4ed8' },
  text: { bg: '#f0fdf4', color: '#15803d' },
  int: { bg: '#fdf4ff', color: '#7e22ce' },
  bigint: { bg: '#fdf4ff', color: '#7e22ce' },
  float: { bg: '#fff7ed', color: '#c2410c' },
  bool: { bg: '#fefce8', color: '#a16207' },
  datetime: { bg: '#f0f9ff', color: '#0369a1' },
  date: { bg: '#f0f9ff', color: '#0369a1' },
};

function TypeBadge({ label }) {
  const s = TYPE_COLOR[label] ?? { bg: '#f1f5f9', color: '#475569' };
  return (
    <span style={{
      padding: '2px 10px',
      borderRadius: '999px',
      fontSize: '11px',
      fontWeight: 700,
      background: s.bg,
      color: s.color,
    }}>
      {label?.toUpperCase()}
    </span>
  );
}

function RequirementBadge({ requirement }) {
  if (!requirement) return <span style={{ color: '#94a3b8' }}>-</span>;

  const mandatory = requirement === 'mandatory';
  return (
    <span style={{
      padding: '2px 10px',
      borderRadius: '999px',
      fontSize: '11px',
      fontWeight: 700,
      background: mandatory ? '#fef2f2' : '#f0fdf4',
      color: mandatory ? '#b91c1c' : '#15803d',
    }}>
      {mandatory ? 'MANDATORY' : 'OPTIONAL'}
    </span>
  );
}

const VALUE_MASTER_CONFIG = {
  nse_state_code_master: {
    nameField: 'state_name',
    codeField: 'state_code',
    nameLabel: 'State Name',
    codeLabel: 'State Code',
    searchPlaceholder: 'Search state name or code...',
    emptyText: 'No states found.',
    noteText: 'Data type, requirement, and length apply to the whole column, across all states.',
  },
  nse_income_range_master: {
    nameField: 'income_range',
    codeField: 'income_code',
    nameLabel: 'Income Range',
    codeLabel: 'Income Code',
    searchPlaceholder: 'Search income range or code...',
    emptyText: 'No income ranges found.',
    noteText: 'Data type, requirement, and length apply to the whole column, across all income ranges.',
  },
  nse_marital_status_master: {
    nameField: 'marital_status',
    codeField: 'marital_code',
    nameLabel: 'Marital Status',
    codeLabel: 'Marital Code',
    searchPlaceholder: 'Search marital status or code...',
    emptyText: 'No marital statuses found.',
    noteText: 'Data type, requirement, and length apply to the whole column, across all marital statuses.',
  },
  bse_income_range_master: {
    nameField: 'income_range',
    codeField: 'income_code',
    nameLabel: 'Income Range',
    codeLabel: 'Income Code',
    searchPlaceholder: 'Search income range or code...',
    emptyText: 'No income ranges found.',
    noteText: 'Data type, requirement, and length apply to the whole column, across all income ranges.',
  },
  nse_occupation_master: {
    nameField: 'occupation_name',
    codeField: 'occupation_code',
    nameLabel: 'Occupation Name',
    codeLabel: 'Occupation Code',
    searchPlaceholder: 'Search occupation or code...',
    emptyText: 'No occupations found.',
    noteText: 'Data type, requirement, and length apply to the whole column, across all occupations.',
  },
};

VALUE_MASTER_CONFIG.bse_star_mf_dependency_master = {
  nameField: 'dependency',
  codeField: 'dependency_code',
  nameLabel: 'Dependency',
  codeLabel: 'Dependency Code',
  searchPlaceholder: 'Search dependency or code...',
  emptyText: 'No dependencies found.',
  noteText: 'BSE Star MF uses this dependency code when generating the UCC payload.',
};
VALUE_MASTER_CONFIG.bse_star_mf_gender_master = {
  nameField: 'gender',
  codeField: 'gender_code',
  nameLabel: 'Gender',
  codeLabel: 'Gender Code',
  searchPlaceholder: 'Search gender or code...',
  emptyText: 'No genders found.',
  noteText: 'BSE Star MF uses this gender code when generating the UCC payload.',
};
VALUE_MASTER_CONFIG.bse_star_mf_state_code_master = {
  ...VALUE_MASTER_CONFIG.nse_state_code_master,
  noteText: 'BSE Star MF uses this state code when generating the UCC payload.',
};
VALUE_MASTER_CONFIG.bse_star_mf_tax_status_master = {
  nameField: 'tax_status',
  codeField: 'tax_code',
  nameLabel: 'Tax Status',
  codeLabel: 'Tax Code',
  searchPlaceholder: 'Search tax status or code...',
  emptyText: 'No tax statuses found.',
  noteText: 'BSE Star MF uses this tax code when generating the UCC payload.',
};
VALUE_MASTER_CONFIG.ckyc_state_code_master = {
  ...VALUE_MASTER_CONFIG.nse_state_code_master,
  noteText: 'CKYC uses this state code when generating the KYC payload.',
};
VALUE_MASTER_CONFIG.kra_status_master = {
  extraField: 'update_flag',
  extraLabel: 'Update Flag',
  nameField: 'app_status',
  codeField: 'kra_code',
  nameLabel: 'APP Status / Prefix',
  codeLabel: 'KRA Code',
  searchPlaceholder: 'Search APP status or KRA code...',
  emptyText: 'No KRA status mappings found.',
  noteText: 'Exact status rows are checked first, then one-character prefix rows, then the * default row.',
};
VALUE_MASTER_CONFIG.kra_marital_status_master = {
  nameField: 'marital_status',
  codeField: 'marital_code',
  nameLabel: 'Marital Status',
  codeLabel: 'Marital Code',
  searchPlaceholder: 'Search marital status or code...',
  emptyText: 'No KRA marital statuses found.',
  noteText: 'KRA uses this marital-status code when generating the payload.',
};
VALUE_MASTER_CONFIG.kra_gender_master = {
  nameField: 'gender',
  codeField: 'gender_code',
  nameLabel: 'Gender',
  codeLabel: 'Gender Code',
  searchPlaceholder: 'Search gender or code...',
  emptyText: 'No KRA genders found.',
  noteText: 'KRA uses this gender code when generating the payload.',
};
VALUE_MASTER_CONFIG.kra_error_code = {
  nameField: 'code',
  codeField: 'message',
  nameLabel: 'Error Code',
  codeLabel: 'Error Message',
  searchPlaceholder: 'Search error code or message...',
  emptyText: 'No KRA error codes found.',
  noteText: 'KRA error messages are editable. Length shows the database column limit.',
};
VALUE_MASTER_CONFIG.cdsl_state_code_master = { ...VALUE_MASTER_CONFIG.nse_state_code_master };
VALUE_MASTER_CONFIG.cdsl_income_range_master = { ...VALUE_MASTER_CONFIG.nse_income_range_master };
VALUE_MASTER_CONFIG.nsdl_state_code_master = { ...VALUE_MASTER_CONFIG.nse_state_code_master };
VALUE_MASTER_CONFIG.nsdl_income_range_master = { ...VALUE_MASTER_CONFIG.nse_income_range_master };
VALUE_MASTER_CONFIG.nsdl_occupation_master = { ...VALUE_MASTER_CONFIG.nse_occupation_master };
VALUE_MASTER_CONFIG.nsdl_relation_master = {
  nameField: 'relation_name',
  codeField: 'relation_code',
  nameLabel: 'Relation name',
  codeLabel: 'Relation code',
  searchPlaceholder: 'Search relation or code...',
  emptyText: 'No relations found.',
  noteText: 'Data type, requirement, and length apply to the whole column, across all relations.',
};
VALUE_MASTER_CONFIG.nsdl_account_type_master = {
  nameField: 'account_type',
  codeField: 'account_code',
  nameLabel: 'Account Type',
  codeLabel: 'Account Code',
  searchPlaceholder: 'Search account type or code...',
  emptyText: 'No NSDL account types found.',
  noteText: 'NSDL uses this account code when generating the payload.',
};
VALUE_MASTER_CONFIG.nsdl_country_master = {
  nameField: 'country',
  codeField: 'country_code',
  nameLabel: 'Country',
  codeLabel: 'Country Code',
  searchPlaceholder: 'Search country or code...',
  emptyText: 'No NSDL countries found.',
  noteText: 'NSDL uses this country code when generating the payload.',
};
VALUE_MASTER_CONFIG.nsdl_gender_master = {
  nameField: 'gender',
  codeField: 'gender_code',
  nameLabel: 'Gender',
  codeLabel: 'Gender Code',
  searchPlaceholder: 'Search gender or code...',
  emptyText: 'No NSDL genders found.',
  noteText: 'NSDL uses this gender code when generating the payload.',
};
VALUE_MASTER_CONFIG.mcx_state_city_master = {
  extraField: 'state',
  extraLabel: 'State',
  nameField: 'city',
  codeField: 'state_city_code',
  nameLabel: 'City',
  codeLabel: 'State-city Code',
  searchPlaceholder: 'Search state, city, or code...',
  emptyText: 'No MCX state-city mappings found.',
  noteText: 'MCX uses the state-city code when generating the KYC payload.',
};
VALUE_MASTER_CONFIG.mcx_marital_status_master = {
  nameField: 'marital_status',
  codeField: 'marital_code',
  nameLabel: 'Marital Status',
  codeLabel: 'Marital Code',
  searchPlaceholder: 'Search marital status or code...',
  emptyText: 'No MCX marital statuses found.',
  noteText: 'MCX uses this code when generating the KYC payload.',
};
VALUE_MASTER_CONFIG.mcx_gender_master = {
  nameField: 'gender',
  codeField: 'gender_code',
  nameLabel: 'Gender',
  codeLabel: 'Gender Code',
  searchPlaceholder: 'Search gender or code...',
  emptyText: 'No MCX genders found.',
  noteText: 'MCX uses this code when generating the KYC payload.',
};
VALUE_MASTER_CONFIG.mcx_income_range_master = {
  nameField: 'income_range',
  codeField: 'income_code',
  nameLabel: 'Income Range',
  codeLabel: 'Income Code',
  searchPlaceholder: 'Search income range or code...',
  emptyText: 'No MCX income ranges found.',
  noteText: 'MCX uses this code when generating the KYC payload.',
};
VALUE_MASTER_CONFIG.mcx_occupation_master = {
  nameField: 'occupation_name',
  codeField: 'occupation_code',
  nameLabel: 'Occupation Name',
  codeLabel: 'Occupation Code',
  searchPlaceholder: 'Search occupation or code...',
  emptyText: 'No MCX occupations found.',
  noteText: 'MCX uses this code when generating the KYC payload.',
};
VALUE_MASTER_CONFIG.mcx_account_type_master = {
  nameField: 'account_type',
  codeField: 'account_code',
  nameLabel: 'Account Type',
  codeLabel: 'Account Code',
  searchPlaceholder: 'Search account type or code...',
  emptyText: 'No MCX account types found.',
  noteText: 'MCX uses this code when generating the KYC payload.',
};
VALUE_MASTER_CONFIG.mcx_error_code = {
  nameField: 'code',
  codeField: 'message',
  nameLabel: 'Error Code',
  codeLabel: 'Error Message',
  searchPlaceholder: 'Search error code or message...',
  emptyText: 'No MCX error codes found.',
  noteText: 'MCX error messages are editable and are used in provider responses.',
};
VALUE_MASTER_CONFIG.mse_state_code_master = {
  ...VALUE_MASTER_CONFIG.nse_state_code_master,
  noteText: 'MSE uses this state code when generating the UCC payload.',
};
VALUE_MASTER_CONFIG.mse_income_range_master = {
  ...VALUE_MASTER_CONFIG.nse_income_range_master,
  noteText: 'MSE uses this income code when generating the UCC payload.',
};
VALUE_MASTER_CONFIG.mse_occupation_master = {
  ...VALUE_MASTER_CONFIG.nse_occupation_master,
  noteText: 'MSE uses this occupation code when generating the UCC payload.',
};
VALUE_MASTER_CONFIG.mse_account_type_master = {
  nameField: 'account_type',
  codeField: 'account_code',
  nameLabel: 'Account Type',
  codeLabel: 'Account Code',
  searchPlaceholder: 'Search account type or code...',
  emptyText: 'No MSE account types found.',
  noteText: 'MSE uses this account code when generating the UCC payload.',
};

export function DownloadSchemaButton({ tableName, schema, includeRows = true }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');

  async function downloadSchema() {
    setDownloading(true);
    setError('');
    try {
      const { createSchemaPdf } = await import('../schemaPdf');
      const exportSchema = filterNsdlSchema(schema ?? await apiFetch(
        `${API_BASE}/api/table/${tableName}/schema/`,
        { headers: authHeaders() }
      ).then(readJson), tableName);
      const config = VALUE_MASTER_CONFIG[tableName.toLowerCase()];
      let rowData;
      if (includeRows && config) {
        const rows = [];
        let page = 1;
        let totalPages = 1;
        do {
          const data = await apiFetch(
            `${API_BASE}/api/table/${tableName}/data/?page=${page}&page_size=100`,
            { headers: authHeaders() }
          ).then(readJson);
          rows.push(...data.rows);
          totalPages = data.total_pages;
          page += 1;
        } while (page <= totalPages);
        rowData = {
          columns: [
            ...(config.extraField ? [{ name: config.extraField, label: config.extraLabel }] : []),
            { name: config.nameField, label: config.nameLabel },
            { name: config.codeField, label: config.codeLabel },
          ],
          rows,
        };
      }
      const doc = createSchemaPdf(
        exportSchema.fields,
        getTableLabel(tableName),
        rowData,
        tableName,
      );
      await doc.save(`${tableName.toLowerCase()}-schema.pdf`, { returnPromise: true });
    } catch {
      setError('Failed to download schema PDF. Please try again.');
    } finally {
      setDownloading(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="schema-apply-btn"
        onClick={downloadSchema}
        disabled={downloading || (schema && !schema.fields.some(field => field.name.toLowerCase() !== 'id'))}
      >
        {downloading ? 'Downloading...' : 'Download Schema'}
      </button>
      {error && <span className="schema-err" role="alert">{error}</span>}
    </>
  );
}

function ValueMaster({ tableName, schema, updateSchemaField, typeOptions }) {
  const config = VALUE_MASTER_CONFIG[tableName];
  const valueFields = [
    ...(config.extraField ? [config.extraField] : []),
    config.nameField,
    config.codeField,
  ];
  const formDefaults = () => Object.fromEntries(valueFields.map(field => [field, '']));
  const [data, setData] = useState(null);
  const [form, setForm] = useState(formDefaults);
  const [editingRows, setEditingRows] = useState({});
  const [drafts, setDrafts] = useState({});
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rowSaving, setRowSaving] = useState({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  function fieldMeta(fieldName) {
    return schema?.fields?.find(field => field.name === fieldName) ?? {};
  }

  const rowRequest = useRef(null);
  useEffect(() => () => rowRequest.current?.abort(), []);

  async function loadRows(nextPage = page, nextSearch = search) {
    rowRequest.current?.abort();
    const controller = new AbortController();
    rowRequest.current = controller;
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch(
        `${API_BASE}/api/table/${tableName}/data/?page=${nextPage}&page_size=${VALUE_MASTER_PAGE_SIZE}&search=${encodeURIComponent(nextSearch)}`,
        { headers: authHeaders(), signal: controller.signal }
      );
      const payload = await res.json();
      if (!res.ok) {
        setError(payload.error ?? 'Failed to load records.');
        return;
      }
      setData(payload);
    } catch (err) {
      if (err.name !== 'AbortError') setError('Failed to load records.');
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  useEffect(() => {
    loadRows(page, search);
  }, [tableName, page]);

  function pageWindow() {
    const totalPages = data?.total_pages ?? 1;
    const currentPage = data?.page ?? page;
    const half = 3;
    const start = Math.max(1, Math.min(currentPage - half, totalPages - half * 2));
    const end = Math.min(totalPages, start + half * 2);
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  }

  function updateForm(field, value) {
    setForm(current => ({ ...current, [field]: value }));
    setError('');
    setMessage('');
  }

  function updateDraft(id, field, value) {
    setDrafts(current => ({
      ...current,
      [id]: {
        ...(current[id] ?? {}),
        [field]: value,
      },
    }));
    setError('');
    setMessage('');
  }

  function payloadFrom(source, includeId = false) {
    return {
      ...(includeId ? { id: source.id } : {}),
      ...Object.fromEntries(valueFields.map(field => [field, String(source[field] ?? '').trim()])),
    };
  }

  function updateMetadata(id, field, key, value) {
    setDrafts(current => ({
      ...current,
      [id]: {
        ...current[id],
        metadata: {
          ...current[id]?.metadata,
          [field]: {
            ...current[id]?.metadata?.[field],
            [key]: value,
            ...(key === 'new_type' ? { max_length: undefined } : {}),
          },
        },
      },
    }));
    setError('');
    setMessage('');
  }

  function metadataControl(row, field, key) {
    const meta = fieldMeta(field);
    if (key === 'max_length') {
      const selectedType = drafts[row.id]?.metadata?.[field]?.new_type ?? meta.label;
      const canEditLength = ['str', 'varchar'].includes(selectedType);
      return (
        <input
          className="schema-type-select"
          type="number"
          min="1"
          max="65535"
          step="1"
          aria-label={`${field} length for ${row[config.nameField]}`}
          placeholder={canEditLength ? 'Length' : '-'}
          value={canEditLength
            ? (drafts[row.id]?.metadata?.[field]?.max_length ??
              (meta.label === 'text' ? meta.value_max_length ?? 255 : meta.max_length) ?? '')
            : selectedType === 'text' ? TEXT_DEFAULT_LENGTH : ''}
          disabled={!canEditLength || saving || Object.values(rowSaving).some(Boolean)}
          onChange={event => updateMetadata(row.id, field, key, event.target.value)}
        />
      );
    }
    const value = drafts[row.id]?.metadata?.[field]?.[key]
      ?? (key === 'new_type' ? meta.label : meta.requirement);
    return (
      <select
        className="schema-type-select"
        aria-label={`${field} ${key === 'new_type' ? 'data type' : 'requirement'} for ${row[config.nameField]}`}
        value={value ?? ''}
        disabled={saving || Object.values(rowSaving).some(Boolean)}
        onChange={event => updateMetadata(row.id, field, key, event.target.value)}
      >
        {(key === 'new_type' ? typeOptions : ['mandatory', 'optional']).map(option => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
    );
  }

  async function saveRecord(event) {
    event.preventDefault();
    const payload = payloadFrom(form);
    if (valueFields.some(field => !payload[field])) {
      setError(`${config.nameLabel} and ${config.codeLabel} are required.`);
      return;
    }

    setSaving(true);
    setError('');
    setMessage('');
    try {
      const res = await apiFetch(`${API_BASE}/api/table/${tableName}/data/`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });
      const response = await res.json();
      if (!res.ok) {
        setError(response.error ?? 'Failed to save record.');
        return;
      }
      setForm(formDefaults());
      setMessage('Record saved.');
      setPage(1);
      await loadRows(1, search);
    } catch (err) {
      setError(err.message || 'Failed to save record.');
    } finally {
      setSaving(false);
    }
  }

  function startEdit(row) {
    setEditingRows(current => ({ ...current, [row.id]: true }));
    setDrafts(current => ({
      ...current,
      [row.id]: {
        id: row.id,
        ...Object.fromEntries(valueFields.map(field => [field, row[field]])),
      },
    }));
  }

  function cancelEdit(id) {
    setEditingRows(current => {
      const next = { ...current };
      delete next[id];
      return next;
    });
    setDrafts(current => {
      const next = { ...current };
      delete next[id];
      return next;
    });
  }

  function hasRecordChanges(row) {
    const draft = drafts[row.id];
    if (!draft) return false;
    return valueFields.some(field => {
      const meta = fieldMeta(field);
      const changes = draft.metadata?.[field] ?? {};
      const selectedType = changes.new_type ?? meta.label;
      return String(draft[field] ?? '').trim() !== String(row[field] ?? '').trim()
        || selectedType !== meta.label
        || (changes.requirement ?? meta.requirement) !== meta.requirement
        || (['str', 'varchar'].includes(selectedType)
          && changes.max_length !== undefined
          && Number(changes.max_length) !== Number(meta.max_length));
    });
  }

  async function updateRecord(row) {
    if (!hasRecordChanges(row)) return;
    const draft = drafts[row.id] ?? row;
    const payload = payloadFrom(draft, true);
    if (valueFields.some(field => !payload[field])) {
      setError(`${config.nameLabel} and ${config.codeLabel} are required.`);
      return;
    }

    for (const field of [config.nameField, config.codeField]) {
      const changes = draft.metadata?.[field];
      const selectedType = changes?.new_type ?? fieldMeta(field).label;
      if (changes?.max_length !== undefined && ['str', 'varchar'].includes(selectedType)) {
        const length = Number(changes.max_length);
        if (!Number.isInteger(length) || length < 1 || length > 65535) {
          setError('Length must be a whole number between 1 and 65535.');
          return;
        }
        if (payload[field].length > length) {
          setError(`${field === config.nameField ? config.nameLabel : config.codeLabel} exceeds the selected length.`);
          return;
        }
      }
    }

    setRowSaving(current => ({ ...current, [row.id]: true }));
    setError('');
    setMessage('');
    try {
      const res = await apiFetch(`${API_BASE}/api/table/${tableName}/data/`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });
      const response = await res.json();
      if (!res.ok) {
        setError(response.error ?? 'Failed to update record.');
        return;
      }

      setData(current => current ? {
        ...current,
        rows: current.rows.map(item => String(item.id) === String(row.id) ? response.row : item),
      } : current);

      try {
        for (const field of [config.nameField, config.codeField]) {
          const changes = { ...draft.metadata?.[field] };
          if (!['str', 'varchar'].includes(changes.new_type ?? fieldMeta(field).label)) {
            delete changes.max_length;
          }
          if (Object.keys(changes).length === 0) continue;
          const saved = await apiFetch(`${API_BASE}/api/table/${tableName}/schema/`, {
            method: 'PATCH',
            headers: authHeaders(),
            body: JSON.stringify({ field, ...changes }),
          }).then(readJson);
          updateSchemaField(saved.updated_field);
        }
      } catch (err) {
        throw new Error(`Values saved, but column settings could not be fully saved: ${err.message}`);
      }

      cancelEdit(row.id);
      setMessage('Record updated.');
    } catch (err) {
      setError(err.message || 'Failed to update record.');
    } finally {
      setRowSaving(current => {
        const next = { ...current };
        delete next[row.id];
        return next;
      });
    }
  }

  async function deleteRecord(row) {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const res = await apiFetch(`${API_BASE}/api/table/${tableName}/data/`, {
        method: 'DELETE',
        headers: authHeaders(),
        body: JSON.stringify({ id: row.id }),
      });
      const response = await res.json();
      if (!res.ok) {
        setError(response.error ?? 'Failed to delete record.');
        return;
      }
      setDeleteTarget(null);
      setMessage('Record deleted.');
      await loadRows(page, search);
    } catch {
      setError('Failed to delete record.');
    } finally {
      setSaving(false);
    }
  }

  const rows = data?.rows ?? [];
  const nameMeta = fieldMeta(config.nameField);
  const codeMeta = fieldMeta(config.codeField);
  const hasRecordValues = Boolean(
    String(form[config.nameField] ?? '').trim() &&
    String(form[config.codeField] ?? '').trim()
  );
  const tableColSpan = 9 + (config.extraField ? 1 : 0);

  return (
    <>
      <div className="schema-toolbar">
        <input
          className="db-search"
          type="search"
          placeholder={config.searchPlaceholder}
          value={search}
          onChange={event => {
            const value = event.target.value;
            setSearch(value);
            setPage(1);
            loadRows(1, value);
          }}
        />
        <span style={{ fontSize: 12.5, color: '#6b7a99' }}>
          {loading
            ? 'Loading records...'
            : data
              ? `${data.total} total records · Page ${data.page} / ${data.total_pages}`
              : ''}
        </span>
        <DownloadSchemaButton tableName={tableName} schema={schema} />
      </div>

      <form
        className="schema-add-form schema-add-form-linear"
        style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'end' }}
        onSubmit={saveRecord}
      >
        {valueFields.map(field => (
          <label key={field} className="schema-add-field" style={{ flex: '1 1 240px' }}>
            <span>{field === config.extraField ? config.extraLabel : field === config.nameField ? config.nameLabel : config.codeLabel}</span>
            <input
              className="schema-type-select"
              type="text"
              placeholder={`Add ${field === config.extraField ? config.extraLabel.toLowerCase() : field === config.nameField ? config.nameLabel.toLowerCase() : config.codeLabel.toLowerCase()}`}
              aria-label={field === config.extraField ? config.extraLabel : field === config.nameField ? config.nameLabel : config.codeLabel}
              required
              maxLength={Number(fieldMeta(field).value_max_length ?? fieldMeta(field).max_length) || undefined}
              value={form[field]}
              disabled={saving}
              onChange={event => updateForm(field, event.target.value)}
            />
          </label>
        ))}
        <button className="schema-apply-btn" type="submit" disabled={saving || !hasRecordValues}>
          {saving ? 'Adding...' : 'Add Record'}
        </button>
        {(message || error) && <div style={{ flexBasis: '100%' }}>
          {message && <span className="schema-ok" role="status">{message}</span>}
          {error && <span className="schema-err" role="alert">{error}</span>}
        </div>}
      </form>

      <div className="db-table-wrap schema-table-wrap">
        {Object.keys(editingRows).length > 0 && (
          <p className="schema-toolbar" role="note">
            {config.noteText}
          </p>
        )}
        <table className="db-table value-master-table">
          <thead>
            <tr>
              {config.extraField && <th>{config.extraLabel}</th>}
              <th>{config.nameLabel}</th>
              <th>Current Type</th>
              <th>Requirement</th>
              <th>Length</th>
              <th>{config.codeLabel}</th>
              <th>Current Type</th>
              <th>Requirement</th>
              <th>Length</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {!data ? (
              <tr>
                <td className="db-empty" colSpan={tableColSpan}>Loading records...</td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td className="db-empty" colSpan={tableColSpan}>{config.emptyText}</td>
              </tr>
            ) : rows.map((row, index) => {
              const editing = Boolean(editingRows[row.id]);
              const draft = drafts[row.id] ?? row;

              return (
                <tr key={row.id} className={`${index % 2 === 0 ? 'row-even' : 'row-odd'}${editing ? ' value-master-editing' : ''}`}>
                  {config.extraField && (
                    <td className="db-cell">
                      {editing ? (
                        <input
                          className="schema-type-select"
                          type="text"
                          aria-label={`${config.extraLabel} for ${row[config.nameField]}`}
                          disabled={rowSaving[row.id]}
                          value={draft[config.extraField] ?? ''}
                          onChange={event => updateDraft(row.id, config.extraField, event.target.value)}
                        />
                      ) : row[config.extraField]}
                    </td>
                  )}
                  <td className="db-cell">
                    {editing ? (
                      <input
                        className="schema-type-select"
                        type="text"
                        aria-label={`${config.nameLabel} for ${row[config.nameField]}`}
                        maxLength={Number(nameMeta.value_max_length ?? nameMeta.max_length) || undefined}
                        disabled={rowSaving[row.id]}
                        value={draft[config.nameField] ?? ''}
                        onChange={event => updateDraft(row.id, config.nameField, event.target.value)}
                      />
                    ) : row[config.nameField]}
                  </td>
                  <td>
                    {editing ? metadataControl(row, config.nameField, 'new_type') : <TypeBadge label={nameMeta.label} />}
                  </td>
                  <td>
                    {editing ? metadataControl(row, config.nameField, 'requirement') : <RequirementBadge requirement={nameMeta.requirement} />}
                  </td>
                  <td>
                    {editing ? metadataControl(row, config.nameField, 'max_length') : <span className="value-master-meta">{nameMeta.max_length ?? '-'}</span>}
                  </td>
                  <td className="db-cell">
                    {editing ? (
                      <input
                        className="schema-type-select"
                        type="text"
                        aria-label={`${config.codeLabel} for ${row[config.nameField]}`}
                        maxLength={Number(codeMeta.value_max_length ?? codeMeta.max_length) || undefined}
                        disabled={rowSaving[row.id]}
                        value={draft[config.codeField] ?? ''}
                        onChange={event => updateDraft(row.id, config.codeField, event.target.value)}
                      />
                    ) : row[config.codeField]}
                  </td>
                  <td>
                    {editing ? metadataControl(row, config.codeField, 'new_type') : <TypeBadge label={codeMeta.label} />}
                  </td>
                  <td>
                    {editing ? metadataControl(row, config.codeField, 'requirement') : <RequirementBadge requirement={codeMeta.requirement} />}
                  </td>
                  <td>
                    {editing ? metadataControl(row, config.codeField, 'max_length') : <span className="value-master-meta">{codeMeta.max_length ?? '-'}</span>}
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {editing ? (
                        <>
                          <button className="schema-apply-btn" type="button" disabled={!hasRecordChanges(row) || rowSaving[row.id] || valueFields.some(field => !String(draft[field] ?? '').trim())} onClick={() => updateRecord(row)}>
                            {rowSaving[row.id] ? 'Saving...' : 'Save'}
                          </button>
                          <button className="schema-delete-btn" type="button" disabled={rowSaving[row.id]} onClick={() => cancelEdit(row.id)}>
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <button className="schema-apply-btn" type="button" disabled={saving || rowSaving[row.id]} onClick={() => startEdit(row)}>
                            Edit
                          </button>
                          <button className="schema-delete-btn" type="button" disabled={saving || rowSaving[row.id]} onClick={() => setDeleteTarget(row)}>
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {data && data.total_pages > 1 && (
        <div className="db-pagination">
          <button className="pg-btn" onClick={() => setPage(1)} disabled={data.page === 1}>«</button>
          <button className="pg-btn" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={data.page === 1}>‹</button>
          {pageWindow().map(p => (
            <button
              key={p}
              className={`pg-btn${p === data.page ? ' pg-active' : ''}`}
              onClick={() => setPage(p)}
            >
              {p}
            </button>
          ))}
          <button className="pg-btn" onClick={() => setPage(p => Math.min(data.total_pages, p + 1))} disabled={data.page === data.total_pages}>›</button>
          <button className="pg-btn" onClick={() => setPage(data.total_pages)} disabled={data.page === data.total_pages}>»</button>
          <span className="pg-info">Page {data.page} / {data.total_pages}</span>
        </div>
      )}

      {deleteTarget && (
        <div className="schema-confirm-backdrop" role="presentation">
          <div className="schema-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-record-title">
            <h3 id="delete-record-title">Delete Record</h3>
            <p>
              Are you sure you want to delete <strong>{deleteTarget[config.nameField]}</strong>?
            </p>
            <div className="schema-confirm-actions">
              <button
                type="button"
                className="schema-confirm-cancel"
                onClick={() => setDeleteTarget(null)}
                disabled={saving}
              >
                Cancel
              </button>
              <button
                type="button"
                className="schema-confirm-delete"
                onClick={() => deleteRecord(deleteTarget)}
                disabled={saving}
              >
                {saving ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default function Master({ tableName }) {
  const isStateCodeMaster = tableName?.toLowerCase() === 'nse_state_code_master';
  const isRecordTable = ['nse', 'bse', 'bse_star_mf', 'cdsl', 'nsdl', 'mcx', 'mse'].includes(tableName?.toLowerCase());
  const [records, setRecords] = useState(null);
  const [recordPage, setRecordPage] = useState(1);
  const [recordIndex, setRecordIndex] = useState(0);
  const [recordError, setRecordError] = useState('');
  const [recordRefresh, setRecordRefresh] = useState(0);
  useEffect(() => { setRecordPage(1); setRecordIndex(0); }, [tableName]);
  useEffect(() => {
    if (!isRecordTable) return;
    const controller = new AbortController();
    setRecords(null);
    setRecordError('');
    apiFetch(`${API_BASE}/api/table/${tableName}/data/?page=${recordPage}&page_size=20`, {
      headers: authHeaders(), signal: controller.signal,
    }).then(readJson).then(data => setRecords(data)).catch(err => {
      if (err.name !== 'AbortError') setRecordError(err.message);
    });
    return () => controller.abort();
  }, [tableName, isRecordTable, recordPage, recordRefresh]);
  const selectedRecord = records?.rows[recordIndex];
  const [schema, setSchema] = useState(null);
  const [pending, setPending] = useState({});
  const [editingFields, setEditingFields] = useState({});
  const [saving, setSaving] = useState({});
  const [msgs, setMsgs] = useState({});
  const [addColumn, setAddColumn] = useState({
    field: '',
    data_type: '',
    requirement: '',
    conditional_parameter: '',
    max_length: '',
    has_default: false,
    default_value: '',
  });
  const [adding, setAdding] = useState(false);
  const [addMsg, setAddMsg] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!tableName) return;

    setSchema(null);
    setError('');
    setPending({});
    setEditingFields({});
    setMsgs({});
    setAddMsg('');
    setAddColumn({
      field: '',
      data_type: '',
      requirement: '',
      conditional_parameter: '',
      max_length: '',
      has_default: false,
      default_value: '',
    });
    setSearch('');
    setPage(1);

    const controller = new AbortController();

    apiFetch(`${API_BASE}/api/table/${tableName}/schema/`, {
      headers: authHeaders(),
      signal: controller.signal,
    })
      .then(readJson)
      .then(data => setSchema(filterNsdlSchema(data, tableName)))
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError('Failed to load schema.');
        }
      });

    return () => controller.abort();
  }, [tableName]);

  useEffect(() => {
    setPage(1);
  }, [search]);

  function handleFieldChange(field, key, val) {
    setPending(p => ({
      ...p,
      [field]: {
        ...(p[field] ?? {}),
        [key]: val,
      },
    }));
    setMsgs(m => ({ ...m, [field]: '' }));
  }

  function handleTypeChange(field, value) {
    setPending(current => {
      const nextField = {
        ...(current[field] ?? {}),
        new_type: value,
      };
      delete nextField.max_length;
      return { ...current, [field]: nextField };
    });
    setMsgs(current => ({ ...current, [field]: '' }));
  }

  function startFieldEdit(field) {
    setEditingFields(current => ({ ...current, [field]: true }));
    setMsgs(current => ({ ...current, [field]: '' }));
  }

  function cancelFieldEdit(field) {
    setEditingFields(current => {
      const next = { ...current };
      delete next[field];
      return next;
    });
    setPending(current => {
      const next = { ...current };
      delete next[field];
      return next;
    });
    setMsgs(current => ({ ...current, [field]: '' }));
  }

  async function applyChange(field) {
    const change = { ...(pending[field] ?? {}) };
    if (Object.prototype.hasOwnProperty.call(change, 'row_value')) {
      setSaving(s => ({ ...s, [field]: true }));
      try {
        const saved = await apiFetch(`${API_BASE}/api/table/${tableName}/data/`, {
          method: selectedRecord ? 'PATCH' : 'POST', headers: authHeaders(),
          body: JSON.stringify(isStateCodeMaster
            ? { id: selectedRecord?.id, [field]: change.row_value }
            : { field, id: selectedRecord?.ID ?? selectedRecord?.id, value: change.row_value }),
        }).then(readJson);
        const savedId = selectedRecord?.ID ?? selectedRecord?.id ?? saved.id;
        setRecords(current => {
          if (!current) return current;
          const exists = current.rows.some(row => String(row.ID ?? row.id) === String(savedId));
          return {
            ...current,
            rows: exists
              ? current.rows.map(row => String(row.ID ?? row.id) === String(savedId)
                ? saved.row
                : row)
              : [...current.rows, saved.row],
            total: current.total + (exists ? 0 : 1),
          };
        });
        delete change.row_value;
        if (Object.keys(change).length === 0) {
          cancelFieldEdit(field);
          setMsgs(m => ({ ...m, [field]: 'ok' }));
          return;
        }
      } catch (err) {
        setMsgs(m => ({ ...m, [field]: err.message }));
        return;
      } finally { setSaving(s => ({ ...s, [field]: false })); }
    }
    const payload = { field };

    if (change.new_type) payload.new_type = change.new_type;
    if (Object.prototype.hasOwnProperty.call(change, 'max_length') && change.new_type !== 'text') {
      payload.max_length = change.max_length;
    }
    if (Object.prototype.hasOwnProperty.call(change, 'default_value')) {
      payload.default_value = change.default_value;
    }
    if (Object.prototype.hasOwnProperty.call(change, 'requirement')) {
      payload.requirement = change.requirement;
    }
    if (Object.prototype.hasOwnProperty.call(change, 'conditional_parameter')) {
      payload.conditional_parameter = change.conditional_parameter;
    }

    if (Object.keys(payload).length === 1) {
      cancelFieldEdit(field);
      return;
    }

    setSaving(s => ({ ...s, [field]: true }));

    try {
      const res = await apiFetch(`${API_BASE}/api/table/${tableName}/schema/`, {
        method: 'PATCH',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (res.ok) {
        setMsgs(m => ({ ...m, [field]: 'ok' }));

        updateSchemaField(data.updated_field);
        setEditingFields(current => {
          const next = { ...current };
          delete next[field];
          return next;
        });
        setPending(p => {
          const next = { ...p };
          delete next[field];
          return next;
        });
      } else {
        setMsgs(m => ({
          ...m,
          [field]: data.error ?? 'Failed',
        }));
      }
    } catch {
      setMsgs(m => ({
        ...m,
        [field]: 'Network error',
      }));
    } finally {
      setSaving(s => ({ ...s, [field]: false }));


    }
  }

  async function deleteColumn(field) {
    setSaving(s => ({ ...s, [field]: true }));
    setMsgs(m => ({ ...m, [field]: '' }));

    try {
      const res = await apiFetch(`${API_BASE}/api/table/${tableName}/schema/`, {
        method: 'DELETE',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ field }),
      });
      const data = await res.json();

      if (!res.ok) {
        setMsgs(m => ({
          ...m,
          [field]: data.error ?? 'Failed to delete.',
        }));
        return;
      }

      await refreshSchema();
      setDeleteTarget(null);
    } catch {
      setMsgs(m => ({
        ...m,
        [field]: 'Network error',
      }));
    } finally {
      setSaving(s => ({ ...s, [field]: false }));
    }
  }

  function refreshSchema() {
    return apiFetch(`${API_BASE}/api/table/${tableName}/schema/`, {
      headers: authHeaders(),
    })
      .then(readJson)
      .then(data => setSchema(filterNsdlSchema(data, tableName)));
  }

  function updateSchemaField(updatedField) {
    if (!updatedField) return;
    setSchema(current => current ? {
      ...current,
      fields: current.fields.map(field => field.name === updatedField.name
        ? { ...field, ...updatedField } : field),
    } : current);
  }

  function handleAddColumnChange(key, value) {
    setAddColumn(current => ({
      ...current,
      [key]: value,
      ...(key === 'data_type' && value !== 'str' ? { max_length: '' } : {}),
    }));
    setAddMsg('');
  }

  async function submitAddColumn(e) {
    e.preventDefault();
    if (!addColumn.field.trim()) {
      setAddMsg('Column name is required.');
      return;
    }
    if (!addColumn.data_type) {
      setAddMsg('Please select column type.');
      return;
    }
    if (!addColumn.requirement) {
      setAddMsg('Please select mandatory or optional.');
      return;
    }
    if (addColumn.data_type === 'str' && Number(addColumn.max_length) <= 0) {
      setAddMsg('Max length must be greater than 0.');
      return;
    }

    setAdding(true);
    setAddMsg('');

    const payload = {
      field: addColumn.field.trim(),
      data_type: addColumn.data_type,
      requirement: addColumn.requirement,
      has_default: showDefaultColumn && addColumn.has_default,
      ...(showConditionalParameter && addColumn.conditional_parameter
        ? { conditional_parameter: addColumn.conditional_parameter }
        : {}),
      ...(addColumn.data_type === 'str' ? { max_length: addColumn.max_length } : {}),
      ...(showDefaultColumn && addColumn.has_default ? { default_value: addColumn.default_value } : {}),
    };

    try {
      const res = await apiFetch(`${API_BASE}/api/table/${tableName}/schema/`, {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (!res.ok) {
        setAddMsg(data.error ?? 'Failed to add column.');
        return;
      }

      setAddColumn({
        field: '',
        data_type: '',
        requirement: '',
        conditional_parameter: '',
        max_length: '',
        has_default: false,
        default_value: '',
      });
      setAddMsg('Column added.');
      await refreshSchema();
    } catch {
      setAddMsg('Network error.');
    } finally {
      setAdding(false);
    }
  }

  const tableKey = tableName?.toLowerCase();
  const requirementTables = ['bse', 'bse_star_mf', 'nse', 'cdsl', 'kra', 'nsdl', 'mcx', 'mse', 'userdetails', 'nse_state_code_master'];
  const isRequirementTable = requirementTables.includes(tableKey);
  const isEditableSchemaTable = ['bse', 'bse_star_mf', 'nse', 'cdsl', 'kra', 'nsdl', 'mcx', 'mse', 'userdetails', 'nse_state_code_master'].includes(tableKey);
  const hideDefaultControls = tableKey === 'userdetails' || isRecordTable;
  const showDefaultColumn = !hideDefaultControls;
  const showConditionalParameter = tableKey === 'userdetails';
  const canEditSchema = true;
  const canEditType = isEditableSchemaTable || !isRequirementTable;
  const canEditRequirement = isEditableSchemaTable;
  const schemaFields = schema?.fields ?? [];

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();

    const fields = isRequirementTable
      ? schemaFields.filter(f =>
        ![
          'sequence',
          'action',
          'change_to',
          'change to',
        ].includes(f.name.toLowerCase())
      )
      : schemaFields;

    if (!term) return fields;

    return fields.filter(f =>
      [f.name, f.payload_key, f.payload_path]
        .filter(Boolean)
        .some(value => value.toLowerCase().includes(term))
    );
  }, [schemaFields, search, isRequirementTable]);

  const nsdlPages = useMemo(() => {
    if (tableKey !== 'nsdl') return [];

    const groups = new Map();
    const structuralFields = [];
    filtered.forEach(field => {
      if (!field.payload_group) {
        structuralFields.push(field);
        return;
      }
      const groupKey = `${field.payload_group_path ?? ''}|${field.payload_group ?? field.name}`;
      if (!groups.has(groupKey)) groups.set(groupKey, []);
      groups.get(groupKey).push(field);
    });

    if (structuralFields.length > 0) {
      const firstGroupKey = groups.keys().next().value;
      if (firstGroupKey) {
        groups.set(firstGroupKey, [
          ...structuralFields,
          ...groups.get(firstGroupKey),
        ]);
      } else {
        groups.set('__structural__', structuralFields);
      }
    }

    const pages = [];
    let currentPage = [];
    let currentSize = 0;
    groups.forEach(group => {
      if (currentPage.length > 0 && currentSize + group.length > SCHEMA_PAGE_SIZE) {
        pages.push(currentPage);
        currentPage = [];
        currentSize = 0;
      }
      currentPage.push(...group);
      currentSize += group.length;
    });
    if (currentPage.length > 0) pages.push(currentPage);
    return pages;
  }, [filtered, tableKey]);

  const totalPages = tableKey === 'nsdl'
    ? Math.max(1, nsdlPages.length)
    : Math.max(1, Math.ceil(filtered.length / SCHEMA_PAGE_SIZE));
  const safePage = Math.min(page, totalPages);

  const pageFields = useMemo(
    () => tableKey === 'nsdl'
      ? (nsdlPages[safePage - 1] ?? [])
      : filtered.slice(
        (safePage - 1) * SCHEMA_PAGE_SIZE,
        safePage * SCHEMA_PAGE_SIZE
      ),
    [filtered, nsdlPages, safePage, tableKey]
  );

  const typeOptions = schema?.valid_types?.length
    ? schema.valid_types
    : DEFAULT_TYPE_OPTS;
  const conditionalParameterOptions = schema?.conditional_parameters?.length
    ? schema.conditional_parameters
    : CONDITIONAL_PARAMETER_OPTIONS;
  const conditionalParameterOptionsByColumn = {
    ...CONDITIONAL_PARAMETER_OPTIONS_BY_COLUMN,
    ...schema?.conditional_parameters_by_column,
  };
  const addConditionalParameterOptions = conditionalParameterOptionsByColumn[addColumn.field.trim().toLowerCase()]
    ?? conditionalParameterOptions;
  const schemaColumnCount = 3 + (showConditionalParameter ? 1 : 0)
    + (canEditSchema ? 2 + (showDefaultColumn || isRecordTable ? 1 : 0) : 0);

  if (!tableName) return <p className="db-empty" style={{ margin: 0 }}>Select a table to edit schema.</p>;
  if (error) return <p className="db-error">{error}</p>;
  if (!schema) return <p className="db-loading">Loading schema...</p>;
  if (VALUE_MASTER_CONFIG[tableKey]) {
    return <ValueMaster key={tableKey} tableName={tableKey} schema={schema} updateSchemaField={updateSchemaField} typeOptions={typeOptions} />;
  }
  function pageWindow() {
    const half = 3;
    const start = Math.max(1, Math.min(safePage - half, totalPages - half * 2));
    const end = Math.min(totalPages, start + half * 2);
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  }

  return (
    <>
      <div className="schema-toolbar">
        <input
          className="db-search"
          type="search"
          placeholder="Search column name..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />

        <span style={{ fontSize: 12.5, color: '#6b7a99' }}>
          {filtered.length} of {schema.fields.length} columns
          {totalPages > 1 && ` · Page ${safePage} / ${totalPages}`}
        </span>
        {tableKey === 'nsdl' && (
          <span className="schema-payload-hint">
            Nested payload keys are shown above their columns
          </span>
        )}
        <DownloadSchemaButton key={tableKey} tableName={tableName} schema={schema} />
      </div>

      <form
        onSubmit={submitAddColumn}
        className={`schema-add-form schema-add-form-linear${hideDefaultControls ? ' schema-add-form-no-default' : ''}`}
      >
        <label className="schema-add-field schema-add-column-field">
          <span>Column name</span>
          <input
            className="schema-type-select"
            type="text"
            placeholder="Column name"
            value={addColumn.field}
            onChange={e => handleAddColumnChange('field', e.target.value)}
          />
        </label>

        <label className="schema-add-field schema-add-type-field">
          <span>Data type</span>
          <select
            className="schema-type-select"
            value={addColumn.data_type}
            onChange={e => handleAddColumnChange('data_type', e.target.value)}
          >
            <option value="">Select type</option>
            {typeOptions.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </label>

        <label className="schema-add-field schema-add-requirement-field">
          <span>Requirement</span>
          <select
            className="schema-type-select"
            value={addColumn.requirement}
            onChange={e => handleAddColumnChange('requirement', e.target.value)}
          >
            <option value="">Select</option>
            <option value="optional">optional</option>
            <option value="mandatory">mandatory</option>
          </select>
        </label>

        {showConditionalParameter && (
          <label className="schema-add-field schema-add-conditional-field">
            <span>Conditional Based Parameter</span>
            <select
              className="schema-type-select"
              value={addColumn.conditional_parameter}
              onChange={e => handleAddColumnChange('conditional_parameter', e.target.value)}
            >
              <option value="">Select parameter</option>
              {addConditionalParameterOptions.map(parameter => (
                <option key={parameter} value={parameter}>
                  {conditionalParameterLabel(addColumn.field, parameter)}
                </option>
              ))}
            </select>
          </label>
        )}

        {(!addColumn.data_type || addColumn.data_type === 'str') && (
          <label className="schema-add-field schema-add-length-field">
            <span>Length</span>
            <input
              className="schema-type-select"
              type="number"
              min="0"
              max="65535"
              placeholder="Length"
              value={addColumn.max_length}
              onChange={e => handleAddColumnChange('max_length', e.target.value)}
            />
          </label>
        )}

        {showDefaultColumn && (
          <>
            <label className="schema-add-checkbox">
              <input
                type="checkbox"
                checked={addColumn.has_default}
                onChange={e => handleAddColumnChange('has_default', e.target.checked)}
              />
              <span>Has default</span>
            </label>

            {addColumn.has_default && (
              <label className="schema-add-field schema-add-default-field">
                <span>Default value</span>
                <input
                  className="schema-type-select"
                  type="text"
                  placeholder="Default value"
                  value={addColumn.default_value}
                  onChange={e => handleAddColumnChange('default_value', e.target.value)}
                />
              </label>
            )}
          </>
        )}

        <button
          type="submit"
          className="schema-apply-btn"
          disabled={adding || !addColumn.field.trim()}
        >
          {adding ? 'Adding...' : 'Add Column'}
        </button>

        {addMsg && (
          <span className={addMsg === 'Column added.' ? 'schema-ok' : 'schema-err'}>
            {addMsg}
          </span>
        )}
      </form>

      <div className="db-table-wrap schema-table-wrap">
        <table className={`db-table schema-table${tableKey === 'userdetails' ? ' userdetails-schema-table' : ''}`}>
          <thead>
            <tr>
              <th>Column</th>
              <th className="schema-current-type-cell">Current Type</th>
              {!isRequirementTable && <th>Nullable</th>}
              {isRequirementTable && <th>Requirement</th>}
              {showConditionalParameter && <th>Conditional Based Parameter</th>}
              {canEditSchema && <th>Length</th>}
              {canEditSchema && showDefaultColumn && <th>Default value</th>}
              {isRecordTable && <th>Column value</th>}
              {canEditSchema && <th>Action</th>}
            </tr>
          </thead>

          <tbody>
            {pageFields.length === 0 ? (
              <tr>
                <td colSpan={schemaColumnCount} className="db-empty">
                  No columns match "{search}"
                </td>
              </tr>
            ) : (
              pageFields.map((f, i) => {
                const chosen = pending[f.name] ?? {};
                const defaultValue = Object.prototype.hasOwnProperty.call(chosen, 'default_value')
                  ? chosen.default_value : f.default;
                const msg = msgs[f.name];
                const hasChange = Object.keys(chosen).length > 0;
                const selectedType = chosen.new_type ?? f.label;
                const canEditLength = selectedType === 'str' || selectedType === 'varchar';
                const isEditing = isEditableSchemaTable && Boolean(editingFields[f.name]);
                const columnKey = f.name.toLowerCase();
                const conditionalOptions = conditionalParameterOptionsByColumn[columnKey]
                  ?? conditionalParameterOptions;
                const hasConditionalParameterDropdown = Boolean(
                  conditionalParameterOptionsByColumn[columnKey]
                );
                const displayedConditionalParameter = f.conditional_parameter
                  || CONDITIONAL_PARAMETER_DISPLAY_BY_COLUMN[columnKey]
                  || '-';
                const previousField = pageFields[i - 1];
                const payloadGroupKey = field => (
                  `${field?.payload_group_path ?? ''}|${field?.payload_group ?? field?.name ?? ''}`
                );
                const showPayloadGroup = tableKey === 'nsdl'
                  && f.payload_group
                  && (!previousField || payloadGroupKey(previousField) !== payloadGroupKey(f));

                return (
                  <Fragment key={f.name}>
                    {showPayloadGroup && (
                      <tr className="schema-payload-group-row">
                        <td colSpan={schemaColumnCount}>
                          <span className="schema-payload-group-label">Payload key</span>
                          <strong>{f.payload_group}</strong>
                          {(f.payload_group_path || f.payload_path) && (
                            <code>{f.payload_group_path || f.payload_path.split('.').slice(0, -1).join('.')}</code>
                          )}
                        </td>
                      </tr>
                    )}
                    <tr
                      className={`${i % 2 === 0 ? 'row-even' : 'row-odd'}${isEditing ? ' schema-editing-row' : ''}`}
                    >
                    <td
                      className="db-cell"
                      title={tableKey === 'nsdl'
                        ? `${f.payload_path || f.name} | DB column: ${f.name}`
                        : f.name}
                      style={{
                        fontFamily: 'monospace',
                        color: '#0f1f45',
                        maxWidth: tableKey === 'nsdl' ? '360px' : 'none',
                        overflow: 'visible',
                        whiteSpace: tableKey === 'nsdl' ? 'normal' : 'nowrap',
                        overflowWrap: tableKey === 'nsdl' ? 'anywhere' : 'normal',
                      }}
                    >
                      <div>{tableKey === 'nsdl' ? (f.payload_key || f.name) : f.name}</div>
                    </td>

                    <td className="schema-current-type-cell" style={{ padding: '9px 14px' }}>
                      {canEditType && (isEditing || !isEditableSchemaTable) ? (
                        <select
                          className="schema-type-select schema-current-type-select"
                          aria-label={`Current type for ${f.name}`}
                          value={chosen.new_type ?? f.label ?? ''}
                          onChange={e => handleTypeChange(f.name, e.target.value)}
                        >
                          <option value="">- select -</option>
                          {typeOptions.map(t => (
                            <option key={t} value={t}>{t}</option>
                          ))}
                        </select>
                      ) : (
                        <TypeBadge label={f.label} />
                      )}
                    </td>

                    {!isRequirementTable && (
                      <td style={{
                        color: f.nullable ? '#15803d' : '#9ca3af',
                        fontWeight: 600,
                        fontSize: 12,
                        padding: '9px 14px',
                      }}>
                        {f.nullable ? 'YES' : 'NO'}
                      </td>
                    )}

                    {isRequirementTable && (
                      <td style={{ padding: '9px 14px' }}>
                        {isEditing && canEditRequirement ? (
                          <select
                            className="schema-type-select"
                            value={chosen.requirement ?? f.requirement ?? ''}
                            onChange={e => handleFieldChange(f.name, 'requirement', e.target.value)}
                          >
                            <option value="">Select</option>
                            <option value="optional">optional</option>
                            <option value="mandatory">mandatory</option>
                          </select>
                        ) : (
                          <RequirementBadge requirement={f.requirement} />
                        )}
                      </td>
                    )}

                    {showConditionalParameter && (
                      <td style={{ padding: '9px 14px' }}>
                        {hasConditionalParameterDropdown && isEditing ? (
                          <select
                            className="schema-type-select"
                            aria-label={`Conditional based parameter for ${f.name}`}
                            value={chosen.conditional_parameter ?? f.conditional_parameter ?? ''}
                            onChange={e => handleFieldChange(f.name, 'conditional_parameter', e.target.value)}
                          >
                            <option value="">Select</option>
                            {conditionalOptions.map(parameter => (
                              <option key={parameter} value={parameter}>
                                {conditionalParameterLabel(columnKey, parameter)}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className="schema-value-text">{displayedConditionalParameter}</span>
                        )}
                      </td>
                    )}

                    {canEditSchema && (
                      <td style={{ padding: '9px 14px' }}>
                        {isEditing || !isEditableSchemaTable ? (
                          <input
                            className="schema-type-select"
                            type="number"
                            min="1"
                            max="65535"
                            disabled={!canEditLength}
                            placeholder={f.max_length ? String(f.max_length) : '-'}
                            value={selectedType === 'text'
                              ? (f.label === 'text' ? f.max_length ?? TEXT_DEFAULT_LENGTH : TEXT_DEFAULT_LENGTH)
                              : canEditLength ? chosen.max_length ?? (f.label === 'text' ? 255 : f.max_length ?? '') : ''}
                            onChange={e => handleFieldChange(f.name, 'max_length', e.target.value)}
                            style={{ width: 96 }}
                          />
                        ) : (
                          <span className="schema-value-text">{f.max_length ?? '-'}</span>
                        )}
                      </td>
                    )}

                    {isRecordTable && <td style={{ padding: '9px 14px' }}>
                      {isEditing && records && (selectedRecord || records.total === 0) &&
                        (!isStateCodeMaster || (selectedRecord && ['state_name', 'state_code'].includes(f.name))) ? <input className="schema-type-select schema-column-value-input"
                          aria-label={`Column value for ${f.name}`} maxLength={Number(chosen.max_length ?? f.max_length) || undefined}
                          disabled={Object.values(saving).some(Boolean)}
                          placeholder="Enter column value"
                          value={chosen.row_value ?? selectedRecord?.[f.name] ?? ''}
                          onChange={event => handleFieldChange(f.name, 'row_value', event.target.value)} />
                        : <span className="schema-value-text">{selectedRecord
                          ? (selectedRecord[f.name] === '' || selectedRecord[f.name] == null ? 'Empty' : selectedRecord[f.name])
                          : 'No record'}</span>}
                    </td>}
                    {canEditSchema && showDefaultColumn && (
                      <td style={{ padding: '9px 14px' }}>
                        {f.name.toLowerCase() === 'id' ? (
                          <span className="schema-value-text">Auto-generated</span>
                        ) : isEditing || !isEditableSchemaTable ? (
                          <div>
                            <input
                              className="schema-type-select"
                              type="text"
                              aria-label={`Default value for ${f.name}`}
                              maxLength={canEditLength ? Number(chosen.max_length ?? f.max_length) || undefined : undefined}
                              placeholder={f.default ?? 'No default'}
                              value={defaultValue ?? ''}
                              onChange={e => handleFieldChange(f.name, 'default_value', e.target.value)}
                              style={{ width: 150 }}
                            />
                            <label style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                              <input
                                type="checkbox"
                                aria-label={`No default for ${f.name}`}
                                checked={defaultValue == null}
                                onChange={e => handleFieldChange(f.name, 'default_value', e.target.checked ? null : '')}
                              />
                              No default
                            </label>
                          </div>
                        ) : (
                          <span className="schema-value-text">{f.default ?? 'No default'}</span>
                        )}
                      </td>
                    )}

                    {canEditSchema && (
                      <td style={{ padding: '9px 14px' }}>
                        {f.name.toLowerCase() !== 'id' && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            {isEditableSchemaTable && !isEditing ? (
                              <button
                                type="button"
                                className="schema-apply-btn"
                                disabled={saving[f.name]}
                                onClick={() => startFieldEdit(f.name)}
                              >
                                Edit
                              </button>
                            ) : (
                              <>
                                <button
                                  type="button"
                                  className="schema-apply-btn"
                                  disabled={!hasChange || Object.values(saving).some(Boolean)}
                                  onClick={() => applyChange(f.name)}
                                >
                                  {saving[f.name] ? '...' : isEditableSchemaTable ? 'Save' : 'Apply'}
                                </button>
                                {isEditableSchemaTable && (
                                  <button
                                    type="button"
                                    className="schema-delete-btn"
                                    disabled={saving[f.name]}
                                    onClick={() => cancelFieldEdit(f.name)}
                                  >
                                    Cancel
                                  </button>
                                )}
                              </>
                            )}
                            {!isEditing && (
                              <button
                                type="button"
                                className="schema-delete-btn"
                                disabled={saving[f.name]}
                                onClick={() => setDeleteTarget(f.name)}
                              >
                                Delete
                              </button>
                            )}
                            {msg === 'ok' ? (
                              <span className="schema-ok">Saved</span>
                            ) : msg ? (
                              <span className="schema-err" role="alert">{msg}</span>
                            ) : null}
                          </div>
                        )}
                      </td>
                    )}
                    </tr>
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="db-pagination">
          <button className="pg-btn" onClick={() => setPage(1)} disabled={safePage === 1}>
            «
          </button>
          <button className="pg-btn" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={safePage === 1}>
            ‹
          </button>

          {pageWindow().map(p => (
            <button
              key={p}
              className={`pg-btn${p === safePage ? ' pg-active' : ''}`}
              onClick={() => setPage(p)}
            >
              {p}
            </button>
          ))}

          <button className="pg-btn" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={safePage === totalPages}>
            ›
          </button>
          <button className="pg-btn" onClick={() => setPage(totalPages)} disabled={safePage === totalPages}>
            »
          </button>

          <span className="pg-info">
            Page {safePage} / {totalPages}
          </span>
        </div>
      )}

      {deleteTarget && (
        <div className="schema-confirm-backdrop" role="presentation">
          <div className="schema-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-column-title">
            <h3 id="delete-column-title">Delete Column</h3>
            <p>
              Are you sure you want to delete <strong>{deleteTarget}</strong>? This will remove the column and its data from the table.
            </p>
            <div className="schema-confirm-actions">
              <button
                type="button"
                className="schema-confirm-cancel"
                onClick={() => setDeleteTarget(null)}
                disabled={saving[deleteTarget]}
              >
                Cancel
              </button>
              <button
                type="button"
                className="schema-confirm-delete"
                onClick={() => deleteColumn(deleteTarget)}
                disabled={saving[deleteTarget]}
              >
                {saving[deleteTarget] ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
