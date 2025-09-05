document.addEventListener('DOMContentLoaded', () => {
  const runBtn = document.getElementById('run-report');
  const downloadControls = document.getElementById('download-controls');
  const downloadBtn = document.getElementById('download-report');
  const formatSelect = document.getElementById('file-format');
  let reportData = null;
  let yieldChart, operatorChart, modelChart;

  if (downloadControls) downloadControls.style.display = 'none';

  runBtn?.addEventListener('click', () => {
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    if (!start || !end) {
      alert('Please select a date range.');
      return;
    }

    fetch(`/api/reports/integrated?start_date=${start}&end_date=${end}`)
      .then((res) => res.json())
      .then((data) => {
        reportData = { ...data, start, end };
        computeSummary(reportData);
        renderCharts(reportData);
        downloadControls.style.display = 'flex';
      })
      .catch(() => alert('Failed to run report.'));
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
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      doc.text('Integrated Report', 10, 10);
      let y = 20;

      const addChart = (canvasId, title, lines, color) => {
        const chartWidth = pageWidth - 20;
        const chartHeight = chartWidth / 2;
        const blockHeight = 10 + chartHeight + 6 + lines.length * 6 + 10;
        if (y + blockHeight > pageHeight) {
          doc.addPage();
          y = 20;
        }

        // header
        doc.setFillColor(...color);
        doc.rect(10, y, chartWidth, 8, 'F');
        doc.setTextColor(255, 255, 255);
        doc.setFont('helvetica', 'bold');
        doc.text(title, 14, y + 5);
        y += 10;

        // chart box
        doc.setTextColor(0, 0, 0);
        doc.setDrawColor(0);
        doc.rect(10, y, chartWidth, chartHeight);
        const canvas = document.getElementById(canvasId);
        const img = canvas.toDataURL('image/png');
        doc.addImage(img, 'PNG', 12, y + 2, chartWidth - 4, chartHeight - 4);
        y += chartHeight + 5;

        // description
        doc.setFont('helvetica', 'bold');
        doc.text(title, 12, y);
        doc.setFont('helvetica', 'normal');
        const text = doc.splitTextToSize(lines.join('\n'), chartWidth - 2);
        doc.text(text, 12, y + 6);
        y += text.length * 6 + 10;
      };

      const yd = reportData.yieldSummary || {};
      addChart(
        'yieldTrendChart',
        'Yield Trend',
        [
          `Date range: ${reportData.start} - ${reportData.end}`,
          `Average: ${yd.avg?.toFixed(1) ?? '0'}%`,
          `Worst day: ${yd.worstDay?.date || 'N/A'} (${yd.worstDay?.yield?.toFixed(1) ?? '0'}%)`,
          `Worst assembly: ${
            yd.worstAssembly?.assembly || 'N/A'
          } (${yd.worstAssembly?.yield?.toFixed(1) ?? '0'}%)`,
        ],
        [0, 123, 255]
      );

      const os = reportData.operatorSummary || {};
      addChart(
        'operatorRejectChart',
        'Operator Reject Rate',
        [
          `Date range: ${reportData.start} - ${reportData.end}`,
          `Total boards: ${os.totalBoards ?? 0}`,
          `Avg reject rate: ${os.avgRate?.toFixed(2) ?? '0'}%`,
          `Best: ${os.min?.name || 'N/A'} (${os.min?.rate?.toFixed(2) ?? '0'}%)`,
          `Worst: ${os.max?.name || 'N/A'} (${os.max?.rate?.toFixed(2) ?? '0'}%)`,
        ],
        [0, 200, 0]
      );

      const ms = reportData.modelSummary || {};
      addChart(
        'modelFalseCallsChart',
        'Model False Calls',
        [
          `Date range: ${reportData.start} - ${reportData.end}`,
          `Avg false calls/board: ${ms.avgFalseCalls?.toFixed(2) ?? '0'}`,
          `Models >20 false calls: ${ms.over20?.join(', ') || 'None'}`,
        ],
        [255, 165, 0]
      );

      doc.save('integrated-report.pdf');
    } else if (format === 'xlsx') {
      const wb = XLSX.utils.book_new();
      const ws = XLSX.utils.aoa_to_sheet([]);
      let row = 1;

      XLSX.utils.sheet_add_aoa(ws, [['Integrated Report']], { origin: `A${row}` });
      row += 2;

      // Yield data table and chart
      XLSX.utils.sheet_add_aoa(ws, [['Date', 'Yield %']], { origin: `A${row}` });
      XLSX.utils.sheet_add_aoa(
        ws,
        reportData.yieldData.dates.map((d, i) => [d, reportData.yieldData.yields[i]]),
        { origin: `A${row + 1}` }
      );
      const yieldImg = document
        .getElementById('yieldTrendChart')
        .toDataURL('image/png');
      XLSX.utils.sheet_add_image(ws, yieldImg, {
        tl: { col: 3, row: row - 1 },
        ext: { width: 400, height: 200 },
      });
      XLSX.utils.sheet_add_aoa(
        ws,
        [[document.getElementById('yieldTrendDesc').textContent]],
        { origin: `A${row + reportData.yieldData.dates.length + 2}` }
      );
      row += reportData.yieldData.dates.length + 6;

      // Operator reject rate table and chart
      XLSX.utils.sheet_add_aoa(ws, [['Operator', 'Inspected', 'Rejected']], {
        origin: `A${row}`,
      });
      XLSX.utils.sheet_add_aoa(
        ws,
        reportData.operators.map((o) => [o.name, o.inspected, o.rejected]),
        { origin: `A${row + 1}` }
      );
      const opImg = document
        .getElementById('operatorRejectChart')
        .toDataURL('image/png');
      XLSX.utils.sheet_add_image(ws, opImg, {
        tl: { col: 4, row: row - 1 },
        ext: { width: 400, height: 200 },
      });
      XLSX.utils.sheet_add_aoa(
        ws,
        [[document.getElementById('operatorRejectDesc').textContent]],
        { origin: `A${row + reportData.operators.length + 2}` }
      );
      row += reportData.operators.length + 6;

      // False calls by model table and chart
      XLSX.utils.sheet_add_aoa(ws, [['Model', 'False Calls']], {
        origin: `A${row}`,
      });
      XLSX.utils.sheet_add_aoa(
        ws,
        reportData.models.map((m) => [m.name, m.falseCalls]),
        { origin: `A${row + 1}` }
      );
      const modelImg = document
        .getElementById('modelFalseCallsChart')
        .toDataURL('image/png');
      XLSX.utils.sheet_add_image(ws, modelImg, {
        tl: { col: 3, row: row - 1 },
        ext: { width: 400, height: 200 },
      });
      XLSX.utils.sheet_add_aoa(
        ws,
        [[document.getElementById('modelFalseCallsDesc').textContent]],
        { origin: `A${row + reportData.models.length + 2}` }
      );

      XLSX.utils.book_append_sheet(wb, ws, 'Report');
      XLSX.writeFile(wb, 'integrated-report.xlsx');
    }
  });

  document.getElementById('email-report')?.addEventListener('click', () => {
    alert('Email sent (placeholder).');
  });

  function computeSummary(data) {
    const yields = data.yieldData.yields || [];
    const dates = data.yieldData.dates || [];
    const avgYield =
      yields.reduce((a, b) => a + b, 0) / (yields.length || 1);
    let worstIdx = 0;
    yields.forEach((v, i) => {
      if (v < yields[worstIdx]) worstIdx = i;
    });
    const worstDay = {
      date: dates[worstIdx] || null,
      yield: yields[worstIdx] || 0,
    };
    let worstAsm = { assembly: null, yield: Infinity };
    Object.entries(data.yieldData.assemblyYields || {}).forEach(([k, v]) => {
      if (v < worstAsm.yield) worstAsm = { assembly: k, yield: v };
    });
    data.yieldSummary = { avg: avgYield, worstDay, worstAssembly: worstAsm };

    const ops = (data.operators || []).map((o) => ({
      ...o,
      rate: o.inspected ? (o.rejected / o.inspected) * 100 : 0,
    }));
    data.operators = ops;
    const totalBoards = ops.reduce((a, o) => a + o.inspected, 0);
    const avgRate =
      ops.reduce((a, o) => a + o.rate, 0) / (ops.length || 1);
    let minOp = ops[0] || { name: '', rate: 0 };
    let maxOp = ops[0] || { name: '', rate: 0 };
    ops.forEach((o) => {
      if (o.rate < minOp.rate) minOp = o;
      if (o.rate > maxOp.rate) maxOp = o;
    });
    data.operatorSummary = { totalBoards, avgRate, min: minOp, max: maxOp };

    const avgFc =
      (data.models || []).reduce((a, m) => a + m.falseCalls, 0) /
      ((data.models || []).length || 1);
    const problemAssemblies = (data.models || []).filter(
      (m) => m.falseCalls > 20
    );
    const over20 = problemAssemblies.map((m) => m.name);
    data.modelSummary = { avgFalseCalls: avgFc, over20 };
    data.problemAssemblies = problemAssemblies;
  }

  function renderCharts(data) {
    const {
      yieldData,
      operators,
      models,
      yieldSummary,
      operatorSummary,
      modelSummary,
      problemAssemblies,
      start,
      end,
    } = data;

    yieldChart?.destroy();
    operatorChart?.destroy();
    modelChart?.destroy();

    const yieldCanvas = document.getElementById('yieldTrendChart');
    yieldCanvas.width = 800;
    yieldCanvas.height = 400;
    const yieldCtx = yieldCanvas.getContext('2d');
    yieldChart = new Chart(yieldCtx, {
      type: 'line',
      data: {
        labels: yieldData.dates,
        datasets: [
          {
            label: 'Yield %',
            data: yieldData.yields,
            borderColor: 'blue',
            fill: false,
          },
        ],
      },
    });
    const yd = yieldSummary || {};
    const yDesc = document.getElementById('yieldTrendDesc');
    yDesc.style.whiteSpace = 'pre-line';
    yDesc.textContent =
      `Date range: ${start} - ${end}\n` +
      `Average yield: ${yd.avg?.toFixed(1) ?? '0'}%\n` +
      `Lowest yield date: ${yd.worstDay?.date || 'N/A'} (${yd.worstDay?.yield?.toFixed(1) ?? '0'}%)\n` +
      `Worst assembly: ${yd.worstAssembly?.assembly || 'N/A'} (${yd.worstAssembly?.yield?.toFixed(1) ?? '0'}%)`;

    const operatorCanvas = document.getElementById('operatorRejectChart');
    operatorCanvas.width = 800;
    operatorCanvas.height = 400;
    const operatorCtx = operatorCanvas.getContext('2d');
    const accepted = operators.map((o) => o.inspected - o.rejected);
    const rejected = operators.map((o) => o.rejected);
    operatorChart = new Chart(operatorCtx, {
      type: 'bar',
      data: {
        labels: operators.map((o) => o.name),
        datasets: [
          { label: 'Accepted', data: accepted, backgroundColor: 'green' },
          { label: 'Rejected', data: rejected, backgroundColor: 'red' },
        ],
      },
      options: {
        scales: {
          x: { stacked: true },
          y: { stacked: true },
        },
      },
    });
    const os = operatorSummary || {};
    const oDesc = document.getElementById('operatorRejectDesc');
    oDesc.style.whiteSpace = 'pre-line';
    oDesc.textContent =
      `Date range: ${start} - ${end}\n` +
      `Total boards: ${os.totalBoards ?? 0}\n` +
      `Average reject rate: ${os.avgRate?.toFixed(2) ?? '0'}%\n` +
      `Min reject rate: ${os.min?.name || 'N/A'} (${os.min?.rate?.toFixed(2) ?? '0'}%)\n` +
      `Max reject rate: ${os.max?.name || 'N/A'} (${os.max?.rate?.toFixed(2) ?? '0'}%)`;

    const modelCanvas = document.getElementById('modelFalseCallsChart');
    modelCanvas.width = 800;
    modelCanvas.height = 400;
    const modelCtx = modelCanvas.getContext('2d');
    modelChart = new Chart(modelCtx, {
      type: 'bar',
      data: {
        labels: models.map((m) => m.name),
        datasets: [
          {
            label: 'False Calls',
            data: models.map((m) => m.falseCalls),
            backgroundColor: 'orange',
          },
        ],
      },
    });
    const ms = modelSummary || {};
    const mDesc = document.getElementById('modelFalseCallsDesc');
    mDesc.style.whiteSpace = 'pre-line';
    mDesc.textContent =
      `Date range: ${start} - ${end}\n` +
      `Average false calls/board: ${ms.avgFalseCalls?.toFixed(2) ?? '0'}\n` +
      `Problem assemblies (>20 false calls/board): ${ms.over20?.join(', ') || 'None'}`;

    const table = document.getElementById('problem-assemblies');
    const tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
    (problemAssemblies || []).forEach((m) => {
      const tr = document.createElement('tr');
      const nameTd = document.createElement('td');
      nameTd.textContent = m.name;
      const fcTd = document.createElement('td');
      fcTd.textContent = m.falseCalls;
      tr.appendChild(nameTd);
      tr.appendChild(fcTd);
      tbody.appendChild(tr);
    });
    table.style.display = (problemAssemblies || []).length ? 'table' : 'none';
  }
});

