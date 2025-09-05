document.addEventListener('DOMContentLoaded', () => {
  const runBtn = document.getElementById('run-report');
  const downloadControls = document.getElementById('download-controls');
  const downloadBtn = document.getElementById('download-report');
  const formatSelect = document.getElementById('file-format');
  let reportData = null;
  let yieldChart, operatorChart, modelChart, fcVsNgChart, fcNgRatioChart;

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
      if (window.jspdfAutoTable) {
        window.jspdfAutoTable(jsPDF);
      }
      const doc = new jsPDF();
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      doc.text('Integrated Report', 10, 10);
      // Track current position and column for two-column layout
      let y = 20;
      let col = 0;
      let rowBottom = 20;
      const chartWidth = (pageWidth - 30) / 2;

      const addChart = (
        canvasId,
        title,
        lines,
        color,
        table,
        fullWidth = false
      ) => {
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
        const blockHeightEstimate = 10 + height + 5 + descHeight + 10;
        if (y + blockHeightEstimate > pageHeight) {
          doc.addPage();
          y = 20;
          col = 0;
          rowBottom = 20;
        }
        const x = fullWidth ? 10 : 10 + col * (chartWidth + 10);

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

        // table if provided
        let blockBottom = innerY;
        if (table) {
          doc.autoTable({
            startY: innerY,
            head: table.head,
            body: table.body,
            margin: { left: x, right: pageWidth - x - width },
            tableWidth: width,
            headStyles: { fillColor: color },
          });
          blockBottom = doc.lastAutoTable.finalY;
        }

        // Surround block with border
        doc.setDrawColor(0);
        doc.rect(x, y, width, blockBottom - y);

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
        [0, 123, 255],
        {
          head: [['Date', 'Yield %']],
          body: (reportData.yieldData.dates || []).map((d, i) => [
            d,
            (reportData.yieldData.yields[i] ?? 0).toFixed(1),
          ]),
        },
        true
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
        {
          head: [['Operator', 'Inspected', 'Rejected', 'Reject %']],
          body: (reportData.operators || []).map((o) => [
            o.name,
            o.inspected,
            o.rejected,
            o.rate?.toFixed(2),
          ]),
        },
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
        {
          head: [['Model Name', 'Avg False Calls']],
          body: (reportData.problemAssemblies || []).map((m) => [
            m.name,
            m.falseCalls,
          ]),
        },
        true
      );

      const fr = reportData.fcVsNgSummary || {};
      addChart(
        'fcVsNgRateChart',
        'False Call vs NG Rate',
        [
          `Date range: ${reportData.start} - ${reportData.end}`,
          `Correlation: ${fr.correlation?.toFixed(2) ?? '0'}`,
          `False call rate has ${fr.fcTrend} over period`,
        ],
        [128, 0, 128],
        {
          head: [['Date', 'NG PPM', 'FalseCall PPM']],
          body: (reportData.fcVsNgRate?.dates || []).map((d, i) => [
            d,
            reportData.fcVsNgRate?.ngPpm[i]?.toFixed(1) ?? 0,
            reportData.fcVsNgRate?.fcPpm[i]?.toFixed(1) ?? 0,
          ]),
        },
        true
      );

      const nr = reportData.fcNgRatioSummary || {};
      addChart(
        'fcNgRatioChart',
        'False Call/NG Ratio',
        [
          `Date range: ${reportData.start} - ${reportData.end}`,
          `Top ratios: ${(nr.top || [])
            .map((m) => `${m.name} (${m.ratio.toFixed(2)})`)
            .join(', ') || 'None'}`,
        ],
        [0, 128, 128],
        {
          head: [['Model', 'FC Parts', 'NG Parts', 'FC/NG']],
          body: (reportData.fcNgRatio?.models || []).map((m, i) => [
            m,
            reportData.fcNgRatio?.fcParts?.[i]?.toFixed(1) ?? 0,
            reportData.fcNgRatio?.ngParts?.[i]?.toFixed(1) ?? 0,
            reportData.fcNgRatio?.ratios?.[i]?.toFixed(2) ?? 0,
          ]),
        },
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
        [['Operator', 'Inspected', 'Rejected', 'Reject %']],
        { origin: `A${row + 2}` }
      );
      XLSX.utils.sheet_add_aoa(
        ws,
        reportData.operators.map((o) => [
          o.name,
          o.inspected,
          o.rejected,
          o.rate?.toFixed(2),
        ]),
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

    const fc = data.fcVsNgRate || {};
    const ngVals = fc.ngPpm || [];
    const fcVals = fc.fcPpm || [];
    const n = Math.min(ngVals.length, fcVals.length);
    let corr = 0;
    if (n > 1) {
      const avgNg = ngVals.reduce((a, b) => a + b, 0) / n;
      const avgFc = fcVals.reduce((a, b) => a + b, 0) / n;
      let num = 0;
      let denNg = 0;
      let denFc = 0;
      for (let i = 0; i < n; i += 1) {
        const x = ngVals[i] - avgNg;
        const y = fcVals[i] - avgFc;
        num += x * y;
        denNg += x * x;
        denFc += y * y;
      }
      const den = Math.sqrt(denNg * denFc);
      corr = den ? num / den : 0;
    }
    const fcTrend =
      fcVals.length > 1
        ? fcVals[0] < fcVals[fcVals.length - 1]
          ? 'increased'
          : 'decreased'
        : 'stable';
    data.fcVsNgSummary = { correlation: corr, fcTrend };

    const ratioData = data.fcNgRatio || {};
    const rModels = ratioData.models || [];
    const rRatios =
      ratioData.ratios ||
      rModels.map((_, i) => {
        const fcPart = ratioData.fcParts?.[i] || 0;
        const ngPart = ratioData.ngParts?.[i] || 0;
        return ngPart ? fcPart / ngPart : 0;
      });
    const pairs = rModels.map((m, i) => ({ name: m, ratio: rRatios[i] }));
    pairs.sort((a, b) => b.ratio - a.ratio);
    data.fcNgRatioSummary = { top: pairs.slice(0, 3) };
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
      fcVsNgRate,
      fcVsNgSummary,
      fcNgRatio,
      fcNgRatioSummary,
      start,
      end,
    } = data;

    yieldChart?.destroy();
    operatorChart?.destroy();
    modelChart?.destroy();
    fcVsNgChart?.destroy();
    fcNgRatioChart?.destroy();

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
      const rateTd = document.createElement('td');
      rateTd.textContent = `${op.rate?.toFixed(2) ?? '0.00'}%`;
      tr.appendChild(nameTd);
      tr.appendChild(inspTd);
      tr.appendChild(rejTd);
      tr.appendChild(rateTd);
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
      options: {
        scales: {
          x: {
            ticks: { display: false },
            grid: { display: false },
          },
        },
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

    const fcCanvas = document.getElementById('fcVsNgRateChart');
    fcCanvas.width = 800;
    fcCanvas.height = 400;
    const fcCtx = fcCanvas.getContext('2d');
    fcVsNgChart = new Chart(fcCtx, {
      type: 'line',
      data: {
        labels: fcVsNgRate?.dates || [],
        datasets: [
          {
            label: 'NG PPM',
            data: fcVsNgRate?.ngPpm || [],
            borderColor: 'red',
            fill: false,
          },
          {
            label: 'FalseCall PPM',
            data: fcVsNgRate?.fcPpm || [],
            borderColor: 'blue',
            fill: false,
          },
        ],
      },
    });
    const fr = fcVsNgSummary || {};
    const fcDesc = document.getElementById('fcVsNgDesc');
    fcDesc.style.whiteSpace = 'pre-line';
    fcDesc.textContent =
      `Date range: ${start} - ${end}\n` +
      `Correlation (FC vs NG): ${fr.correlation?.toFixed(2) ?? '0'}\n` +
      `False call rate has ${fr.fcTrend} over period`;

    const fcTable = document.getElementById('fcVsNgRateTable');
    const fcTbody = fcTable.querySelector('tbody');
    fcTbody.innerHTML = '';
    (fcVsNgRate?.dates || []).forEach((d, i) => {
      const tr = document.createElement('tr');
      const dateTd = document.createElement('td');
      dateTd.textContent = d;
      const ngTd = document.createElement('td');
      ngTd.textContent = (fcVsNgRate?.ngPpm[i] ?? 0).toFixed(1);
      const fcTd = document.createElement('td');
      fcTd.textContent = (fcVsNgRate?.fcPpm[i] ?? 0).toFixed(1);
      tr.appendChild(dateTd);
      tr.appendChild(ngTd);
      tr.appendChild(fcTd);
      fcTbody.appendChild(tr);
    });
    fcTable.style.display = (fcVsNgRate?.dates || []).length ? 'table' : 'none';

    const ratioCanvas = document.getElementById('fcNgRatioChart');
    ratioCanvas.width = 800;
    ratioCanvas.height = 400;
    const ratioCtx = ratioCanvas.getContext('2d');
    fcNgRatioChart = new Chart(ratioCtx, {
      type: 'bar',
      data: {
        labels: fcNgRatio?.models || [],
        datasets: [
          {
            label: 'FC/NG Ratio',
            data: fcNgRatio?.ratios || [],
            backgroundColor: 'teal',
          },
        ],
      },
    });
    const nr = fcNgRatioSummary || {};
    const ratioDesc = document.getElementById('fcNgRatioDesc');
    ratioDesc.style.whiteSpace = 'pre-line';
    ratioDesc.textContent =
      `Date range: ${start} - ${end}\n` +
      `Top ratios: ${(nr.top || [])
        .map((m) => `${m.name} (${m.ratio.toFixed(2)})`)
        .join(', ') || 'None'}`;

    const ratioTable = document.getElementById('fcNgRatioTable');
    const ratioTbody = ratioTable.querySelector('tbody');
    ratioTbody.innerHTML = '';
    (fcNgRatio?.models || []).forEach((m, i) => {
      const tr = document.createElement('tr');
      const modelTd = document.createElement('td');
      modelTd.textContent = m;
      const fcTd = document.createElement('td');
      fcTd.textContent = (fcNgRatio.fcParts?.[i] ?? 0).toFixed(1);
      const ngTd = document.createElement('td');
      ngTd.textContent = (fcNgRatio.ngParts?.[i] ?? 0).toFixed(1);
      const ratioTd = document.createElement('td');
      ratioTd.textContent = (fcNgRatio.ratios?.[i] ?? 0).toFixed(2);
      tr.append(modelTd, fcTd, ngTd, ratioTd);
      ratioTbody.appendChild(tr);
    });
    ratioTable.style.display = (fcNgRatio?.models || []).length ? 'table' : 'none';
  }
});

