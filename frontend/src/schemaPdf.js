import { jsPDF } from 'jspdf';
import { autoTable } from 'jspdf-autotable';

const DEFAULT_SCHEMA_EXCLUDED_COLUMNS = new Set(['id']);
const USERDETAILS_SCHEMA_EXCLUDED_COLUMNS = new Set([
  'id',
  'user',
  'user_id',
  'created_at',
  'updated_at',
]);
const USERDETAILS_CONDITIONAL_VALUES = {
  account_holder_type: 'individual / joinholder',
  modeoftrading: 'offline / online',
  mode_of_account: 'N - New Account / M - Modification',
  transaction_type: 'account opening / segment addition / modification',
  activestatus: 'A - Active / I - Inactive',
  bse_cash: 'true / false',
  bse_currency: 'true / false',
  bse_fo: 'true / false',
  bse_slbm: 'true / false',
  mcx: 'true / false',
  nse_cash: 'true / false',
  nse_currency: 'true / false',
  nse_fo: 'true / false',
  nse_slbm: 'true / false',
  nominee_check: 'yes / no',
};

function schemaExcludedColumns(tableName) {
  return String(tableName ?? '').toLowerCase() === 'userdetails'
    ? USERDETAILS_SCHEMA_EXCLUDED_COLUMNS
    : DEFAULT_SCHEMA_EXCLUDED_COLUMNS;
}

function userDetailsAllowedValue(field) {
  const fieldName = String(field.name).toLowerCase();
  if (/^nominee[123]_/.test(fieldName)) {
    return 'Required when nominee_check = yes';
  }
  return USERDETAILS_CONDITIONAL_VALUES[fieldName]
    || field.conditional_parameter
    || '-';
}

export function createSchemaPdf(fields, tableLabel, rowData, tableName) {
  const excludedColumns = schemaExcludedColumns(tableName);
  const isUserDetails = String(tableName ?? '').toLowerCase() === 'userdetails';
  const exportFields = fields.filter(
    field => !excludedColumns.has(String(field.name).toLowerCase()),
  );
  const doc = new jsPDF();
  const isNsdl = String(tableName ?? '').toLowerCase() === 'nsdl';
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const headingColor = [15, 31, 69];
  doc.setFontSize(18);
  doc.setTextColor(...headingColor);
  doc.text(`${tableLabel} Schema`, 14, 20);
  doc.setFontSize(10);
  doc.setTextColor(107, 122, 153);
  doc.text(`${exportFields.length} columns | Generated ${new Date().toLocaleDateString('en-GB')}`, 14, 28);

  autoTable(doc, {
    startY: 42,
    margin: { top: 14, right: 14, bottom: 18, left: 14 },
    head: [['Column', 'Type', 'Requirement', 'Length', isUserDetails ? 'Allowed Values' : isNsdl ? 'Payload path' : 'Conditional']],
    body: exportFields.map(field => [
      isNsdl ? (field.payload_key || field.name) : field.name,
      field.label ?? field.db_type ?? '-',
      field.requirement ?? (field.nullable ? 'optional' : 'mandatory'),
      field.max_length == null ? 'N/A' : String(field.max_length),
      isUserDetails
        ? userDetailsAllowedValue(field)
        : isNsdl
          ? (field.payload_path || '-')
          : field.conditional_parameter || '-',
    ]),
    styles: {
      fontSize: 8.5,
      cellPadding: { top: 3, right: 3, bottom: 3, left: 3 },
      overflow: 'linebreak',
      valign: 'middle',
      lineColor: [226, 232, 240],
      lineWidth: 0.15,
    },
    headStyles: {
      fillColor: headingColor,
      textColor: [255, 255, 255],
      fontStyle: 'bold',
      halign: 'left',
    },
    alternateRowStyles: { fillColor: [248, 250, 252] },
    bodyStyles: { textColor: [30, 41, 59] },
    columnStyles: {
      0: { cellWidth: 62 },
      1: { cellWidth: 22, halign: 'center' },
      2: { cellWidth: 28 },
      3: { cellWidth: 18, halign: 'center' },
      4: { cellWidth: 52 },
    },
    rowPageBreak: 'avoid',
    showHead: 'everyPage',
  });

  let contentAfterSchemaY = doc.lastAutoTable.finalY + 12;
  if (isUserDetails) {
    const noteLines = doc.splitTextToSize(
      'When nominee_check is yes, nominee details must be provided for at least one nominee. When nominee_check is no, nominee details are not required.',
      pageWidth - 42,
    );
    const noteHeight = 17 + noteLines.length * 4;
    if (contentAfterSchemaY + noteHeight > pageHeight - 18) {
      doc.addPage();
      contentAfterSchemaY = 20;
    }
    doc.setFillColor(255, 251, 235);
    doc.setDrawColor(245, 158, 11);
    doc.roundedRect(14, contentAfterSchemaY, pageWidth - 28, noteHeight, 2, 2, 'FD');
    doc.setFontSize(10);
    doc.setTextColor(146, 64, 14);
    doc.setFont('helvetica', 'bold');
    doc.text('Nominee rule', 19, contentAfterSchemaY + 7);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.text(noteLines, 19, contentAfterSchemaY + 14);
    contentAfterSchemaY += noteHeight + 12;
  }

  if (rowData) {
    const columns = rowData.columns.filter(
      column => !excludedColumns.has(String(column.name).toLowerCase()),
    );
    let headingY = contentAfterSchemaY;
    if (headingY > pageHeight - 38) {
      doc.addPage();
      headingY = 20;
    }
    doc.setFontSize(14);
    doc.setTextColor(...headingColor);
    doc.text(`Row Data (${rowData.rows.length} records)`, 14, headingY);
    if (rowData.rows.length === 0) {
      doc.setFontSize(10);
      doc.text('No records found.', 14, headingY + 8);
    } else {
      autoTable(doc, {
        startY: headingY + 5,
        margin: { top: 16, bottom: 18 },
        head: [columns.map(column => column.label)],
        body: rowData.rows.map(row => columns.map(column => String(row[column.name] ?? ''))),
        styles: {
          fontSize: 8,
          cellPadding: 3,
          overflow: 'linebreak',
          valign: 'middle',
          lineColor: [226, 232, 240],
          lineWidth: 0.15,
        },
        headStyles: { fillColor: headingColor, textColor: [255, 255, 255] },
        alternateRowStyles: { fillColor: [248, 250, 252] },
        rowPageBreak: 'avoid',
        showHead: 'everyPage',
      });
    }
  }

  const pages = doc.getNumberOfPages();
  for (let page = 1; page <= pages; page += 1) {
    doc.setPage(page);
    doc.setFontSize(9);
    doc.setTextColor(107, 122, 153);
    doc.text(`Page ${page} of ${pages}`, pageWidth - 14, pageHeight - 10, { align: 'right' });
  }
  return doc;
}
