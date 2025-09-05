document.addEventListener('DOMContentLoaded', () => {
  const runBtn = document.getElementById('run-report');
  const preview = document.getElementById('report-preview');
  runBtn?.addEventListener('click', () => {
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    if (!start || !end) {
      alert('Please select a date range.');
      return;
    }
    preview.style.display = 'block';

    // --- Sample Yield Data ---
    const yieldData = {
      dates: ['2024-01-01', '2024-01-02', '2024-01-03'],
      yields: [95, 90, 97],
      assemblyYields: { ASM1: 95, ASM2: 88, ASM3: 92 },
    };
    const yieldCtx = document.getElementById('yieldChart').getContext('2d');
    // eslint-disable-next-line no-undef
    new Chart(yieldCtx, {
      type: 'line',
      data: { labels: yieldData.dates, datasets: [{ data: yieldData.yields, borderColor: '#000', backgroundColor: '#000', pointRadius: 3, fill: false, tension: 0 }] },
      options: { responsive: true, maintainAspectRatio: false },
    });
    const avg = yieldData.yields.reduce((a, b) => a + b, 0) / yieldData.yields.length;
    const minIdx = yieldData.yields.indexOf(Math.min(...yieldData.yields));
    const worstDay = yieldData.dates[minIdx];
    const worstAssembly = Object.entries(yieldData.assemblyYields).reduce((a, b) => (a[1] < b[1] ? a : b))[0];
    document.getElementById('yield-info').textContent = `For ${start} to ${end}:\nAverage Daily Yield: ${avg.toFixed(1)}%\nWorst day: ${worstDay}\nWorst Assembly: ${worstAssembly}`;

    // --- Operator Reject Rate ---
    const operators = [
      { name: 'Alice', inspected: 100, rejected: 5 },
      { name: 'Bob', inspected: 120, rejected: 2 },
      { name: 'Cara', inspected: 110, rejected: 10 },
    ];
    const labels = operators.map((o) => o.name);
    const rejectRates = operators.map((o) => ((o.rejected / o.inspected) * 100).toFixed(1));
    const opCtx = document.getElementById('operatorChart').getContext('2d');
    // eslint-disable-next-line no-undef
    new Chart(opCtx, {
      type: 'bar',
      data: { labels, datasets: [{ data: rejectRates, backgroundColor: '#000' }] },
      options: { responsive: true, maintainAspectRatio: false },
    });
    const totalBoards = operators.reduce((sum, o) => sum + o.inspected, 0);
    const avgReject =
      (operators.reduce((sum, o) => sum + o.rejected / o.inspected, 0) / operators.length) * 100;
    const minOp = operators.reduce((a, b) => (a.rejected / a.inspected < b.rejected / b.inspected ? a : b));
    const maxOp = operators.reduce((a, b) => (a.rejected / a.inspected > b.rejected / b.inspected ? a : b));
    document.getElementById('operator-info').textContent = `Total boards ran through AOI for ${start} to ${end}: ${totalBoards}\nAverage Rejection Rate: ${avgReject.toFixed(1)}%\nMin Reject Rate: ${minOp.name} (${((minOp.rejected / minOp.inspected) * 100).toFixed(1)}%)\nMax Reject Rate: ${maxOp.name} (${((maxOp.rejected / maxOp.inspected) * 100).toFixed(1)}%)`;

    // --- False Calls by Model ---
    const models = [
      { name: 'ModelA', falseCalls: 15 },
      { name: 'ModelB', falseCalls: 25 },
      { name: 'ModelC', falseCalls: 5 },
      { name: 'ModelD', falseCalls: 30 },
    ];
    const modelLabels = models.map((m) => m.name);
    const falseVals = models.map((m) => m.falseCalls);
    const falseCtx = document.getElementById('falseChart').getContext('2d');
    // eslint-disable-next-line no-undef
    new Chart(falseCtx, {
      type: 'bar',
      data: { labels: modelLabels, datasets: [{ data: falseVals, backgroundColor: '#000' }] },
      options: { responsive: true, maintainAspectRatio: false },
    });
    const avgFalse = falseVals.reduce((a, b) => a + b, 0) / falseVals.length;
    document.getElementById('false-info').textContent = `Average False Call/Panel: ${avgFalse.toFixed(1)}`;
    const problem = models.filter((m) => m.falseCalls > 20);
    const table = document.getElementById('problem-table');
    const tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
    problem.forEach((p) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${p.name}</td><td>${p.falseCalls}</td>`;
      tbody.appendChild(tr);
    });
    table.style.display = problem.length ? 'table' : 'none';
  });

  document.getElementById('download-pdf')?.addEventListener('click', () => {
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF();
    pdf.text('Integrated Report', 10, 10);
    pdf.save('integrated-report.pdf');
  });

  document.getElementById('download-xls')?.addEventListener('click', () => {
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet([["Integrated Report"]]);
    XLSX.utils.book_append_sheet(wb, ws, 'Report');
    XLSX.writeFile(wb, 'integrated-report.xlsx');
  });

  document.getElementById('email-report')?.addEventListener('click', () => {
    alert('Email sent (placeholder).');
  });
});
