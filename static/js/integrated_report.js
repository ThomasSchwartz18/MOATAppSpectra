document.addEventListener('DOMContentLoaded', () => {
  const runBtn = document.getElementById('run-report');
  const downloadControls = document.getElementById('download-controls');
  const downloadBtn = document.getElementById('download-report');
  const formatSelect = document.getElementById('file-format');
  let reportData = null;

  runBtn?.addEventListener('click', () => {
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    if (!start || !end) {
      alert('Please select a date range.');
      return;
    }

    // --- Sample Yield Data ---
    const yieldData = {
      dates: ['2024-01-01', '2024-01-02', '2024-01-03'],
      yields: [95, 90, 97],
      assemblyYields: { ASM1: 95, ASM2: 88, ASM3: 92 },
    };

    // --- Operator Reject Rate ---
    const operators = [
      { name: 'Alice', inspected: 100, rejected: 5 },
      { name: 'Bob', inspected: 120, rejected: 2 },
      { name: 'Cara', inspected: 110, rejected: 10 },
    ];

    // --- False Calls by Model ---
    const models = [
      { name: 'ModelA', falseCalls: 15 },
      { name: 'ModelB', falseCalls: 25 },
      { name: 'ModelC', falseCalls: 5 },
      { name: 'ModelD', falseCalls: 30 },
    ];

    reportData = { start, end, yieldData, operators, models };
    downloadControls.style.display = 'flex';
  });

  downloadBtn?.addEventListener('click', () => {
    if (!reportData) {
      alert('Run the report first.');
      return;
    }

    const format = formatSelect.value;
    if (format === 'pdf') {
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF();
      doc.text('Integrated Report', 10, 10);
      doc.save('integrated-report.pdf');
    } else if (format === 'xlsx') {
      const wb = XLSX.utils.book_new();
      const ws = XLSX.utils.aoa_to_sheet([['Integrated Report']]);
      XLSX.utils.book_append_sheet(wb, ws, 'Report');
      XLSX.writeFile(wb, 'integrated-report.xlsx');
    }
  });

  document.getElementById('email-report')?.addEventListener('click', () => {
    alert('Email sent (placeholder).');
  });
});

