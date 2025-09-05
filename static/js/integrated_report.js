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
      // Track current position and column for two-column layout
      let y = 20;
      let col = 0;
      let rowBottom = 20;
      const chartWidth = (pageWidth - 30) / 2;

      const addChart = (canvasId, title, lines, color, fullWidth = false) => {
        const defaultSize = doc.getFontSize();
        const lineHeight = 5;
        const padding = 1;
        const width = fullWidth ? pageWidth - 20 : chartWidth;
        const height = width / 3;

        if (fullWidth && col === 1) {
          y = Math.max(rowBottom, y) + 10;
          col = 0;
          rowBottom = y;
        }

        doc.setFontSize(10);
        const processed = lines.map((line) => {
          const textLines = doc.splitTextToSize(line, width - 4);
          return {
            textLines,
            height: textLines.length * lineHeight + padding * 2,
          };
        });
        doc.setFontSize(defaultSize);
        const descHeight = 6 + processed.reduce((a, l) => a + l.height, 0);
        const blockHeight = 10 + height + 5 + descHeight + 10;
        if (y + blockHeight > pageHeight) {
          doc.addPage();
          y = 20;
          col = 0;
          rowBottom = 20;
        }
        const x = fullWidth ? 10 : 10 + col * (chartWidth + 10);
        const blockBottom = y + blockHeight;

        // header
        doc.setFillColor(...color);
        doc.rect(x, y, width, 8, 'F');
        doc.setTextColor(255, 255, 255);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(defaultSize);
        doc.text(title, x + 4, y + 5);
        let innerY = y + 10;

        // chart box
        doc.setTextColor(0, 0, 0);
        doc.setDrawColor(0);
        doc.rect(x, innerY, width, height);
        const canvas = document.getElementById(canvasId);
        const img = canvas.toDataURL('image/png');
        doc.addImage(img, 'PNG', x + 2, innerY + 2, width - 4, height - 4);
        innerY += height + 5;

        // description header
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(defaultSize);
        doc.text(title, x + 2, innerY);
        innerY += 6;

        // description lines with alternating bands
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(10);
        processed.forEach((line, i) => {
          doc.setFillColor(i % 2 === 0 ? 240 : 255);
          doc.rect(x, innerY, width, line.height, 'F');
          doc.text(line.textLines, x + 2, innerY + lineHeight + padding);
          innerY += line.height;
        });
        doc.setFontSize(defaultSize);

        // Surround block with border
        doc.setDrawColor(0);
        doc.rect(x, y, width, blockHeight);

        if (fullWidth) {
          col = 0;
          y = blockBottom + 10;
          rowBottom = y;
        } else if (col === 0) {
          col = 1;
          rowBottom = blockBottom;
        } else {
          col = 0;
          y = Math.max(rowBottom, blockBottom) + 10;
          rowBottom = y;
        }
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
        [0, 200, 0],
        true
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
        [255, 165, 0],
        true
      );

      doc.save('integrated-report.pdf');
    } else if (format === 'xlsx') {
      const wb = XLSX.utils.book_new();
      const ws = XLSX.utils.aoa_to_sheet([]);
      let row = 1;

      XLSX.utils.sheet_add_aoa(ws, [['Integrated Report']], { origin: `A${row}` });
      row += 2;

      // Yield chart, description, and table
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
        { origin: `A${row}` }
      );
      XLSX.utils.sheet_add_aoa(ws, [['Date', 'Yield %']], { origin: `A${row + 2}` });
      XLSX.utils.sheet_add_aoa(
        ws,
        reportData.yieldData.dates.map((d, i) => [d, reportData.yieldData.yields[i]]),
        { origin: `A${row + 3}` }
      );
      row += reportData.yieldData.dates.length + 6;

      // Operator chart, description, and table
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
        { origin: `A${row}` }
      );
      XLSX.utils.sheet_add_aoa(
        ws,
        [['Operator', 'Inspected', 'Rejected']],
        { origin: `A${row + 2}` }
      );
      XLSX.utils.sheet_add_aoa(
        ws,
        reportData.operators.map((o) => [o.name, o.inspected, o.rejected]),
        { origin: `A${row + 3}` }
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
    // Sort operators by inspected count so charts and exports share the order
    ops.sort((a, b) => b.inspected - a.inspected);
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

    const yTable = document.getElementById('yieldTrendTable');
    const yTbody = yTable.querySelector('tbody');
    yTbody.innerHTML = '';
    (yieldData.dates || []).forEach((d, i) => {
      const tr = document.createElement('tr');
      const dateTd = document.createElement('td');
      dateTd.textContent = d;
      const yieldTd = document.createElement('td');
      yieldTd.textContent = (yieldData.yields[i] ?? 0).toFixed(1);
      tr.appendChild(dateTd);
      tr.appendChild(yieldTd);
      yTbody.appendChild(tr);
    });
    yTable.style.display = (yieldData.dates || []).length ? 'table' : 'none';

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

    const oTable = document.getElementById('operatorRejectTable');
    const oTbody = oTable.querySelector('tbody');
    oTbody.innerHTML = '';
    (operators || []).forEach((op) => {
      const tr = document.createElement('tr');
      const nameTd = document.createElement('td');
      nameTd.textContent = op.name;
      const inspTd = document.createElement('td');
      inspTd.textContent = op.inspected;
      const rejTd = document.createElement('td');
      rejTd.textContent = op.rejected;
      tr.appendChild(nameTd);
      tr.appendChild(inspTd);
      tr.appendChild(rejTd);
      oTbody.appendChild(tr);
    });
    oTable.style.display = (operators || []).length ? 'table' : 'none';

    const modelCanvas = document.getElementById('modelFalseCallsChart');
    modelCanvas.width = 800;
    modelCanvas.height = 400;
    const modelCtx = modelCanvas.getContext('2d');

    // Calculate control limits for false calls by model
    const falseCalls = models.map((m) => m.falseCalls);
    const mean =
      falseCalls.reduce((sum, v) => sum + v, 0) / (falseCalls.length || 1);
    const stdDev = Math.sqrt(
      falseCalls.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) /
        (falseCalls.length || 1)
    );
    const upperCL = mean + 3 * stdDev;
    const lowerCL = Math.max(mean - 3 * stdDev, 0);

    modelChart = new Chart(modelCtx, {
      type: 'line',
      data: {
        labels: models.map((m) => m.name),
        datasets: [
          {
            label: 'False Calls',
            data: falseCalls,
            borderColor: 'orange',
            backgroundColor: 'orange',
            tension: 0,
            fill: false,
          },
          {
            label: 'Mean',
            data: Array(falseCalls.length).fill(mean),
            borderColor: 'blue',
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
          },
          {
            label: '+3σ',
            data: Array(falseCalls.length).fill(upperCL),
            borderColor: 'green',
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
          },
          {
            label: '-3σ',
            data: Array(falseCalls.length).fill(lowerCL),
            borderColor: 'red',
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
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
      `Line chart shows mean and ±3σ control limits; models outside may need review.\n` +
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

