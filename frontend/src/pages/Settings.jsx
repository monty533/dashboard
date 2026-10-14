export default function Settings() {
  return (
    <div className="settings-shell">
      <div className="settings-panel">
        <h3 style={{ margin: '0 0 12px', fontSize: 16, color: '#0f1f45' }}>
          System Configuration
        </h3>
        <p style={{ color: '#6b7a99', fontSize: 13.5, marginBottom: 20 }}>
          Admin control panel for backend dynamic schema options and system parameters.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
            Environment: <span style={{ color: '#2563eb' }}>Production / Django Local</span>
          </label>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
            Schema Introspection: <span style={{ color: '#16a34a' }}>INFORMATION_SCHEMA Enabled</span>
          </label>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
            Max Column Page Size: <span style={{ color: '#4b5563' }}>10 columns per page</span>
          </label>
        </div>
      </div>
    </div>
  );
}
