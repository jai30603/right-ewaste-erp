/* ═══════════════════════════════════════════════════════════════
   Dashboard V3 — Right Ewaste ERP V5.0
   Charts · Calendar · Greeting · Search
═══════════════════════════════════════════════════════════════ */

"use strict";

/* ── Chart instances (kept for period switching) ─────────────── */
let salesChartInst    = null;
let purchaseChartInst = null;
let cashFlowInst      = null;

/* ── Calendar state ──────────────────────────────────────────── */
let calYear  = new Date().getFullYear();
let calMonth = new Date().getMonth();

/* ── Quick-search index ──────────────────────────────────────── */
const SEARCH_LINKS = [
  { label:'New Sales Invoice',   icon:'bi-receipt',              href:'/sales/add'                    },
  { label:'New Purchase',        icon:'bi-cart-plus',            href:'/purchase/add'                 },
  { label:'Add Party',           icon:'bi-person-plus',          href:'/party/add'                    },
  { label:'Party List',          icon:'bi-people',               href:'/party'                        },
  { label:'Add Material',        icon:'bi-box-seam',             href:'/material/add'                 },
  { label:'Material List',       icon:'bi-box-seam',             href:'/material'                     },
  { label:'Inventory Dashboard', icon:'bi-boxes',                href:'/inventory/dashboard'          },
  { label:'Processing Jobs',     icon:'bi-cpu',                  href:'/processing/jobs'              },
  { label:'Mark Attendance',     icon:'bi-calendar-check',       href:'/employees/attendance/daily'   },
  { label:'Employees',           icon:'bi-person-badge',         href:'/employees'                    },
  { label:'Upload Documents',    icon:'bi-cloud-upload',         href:'/documents/mydrive'            },
  { label:'Company Drive',       icon:'bi-building',             href:'/documents/companydrive'       },
  { label:'Factory Report',      icon:'bi-file-earmark-bar-graph',href:'/factory-reports'            },
  { label:'Sales List',          icon:'bi-bag-fill',             href:'/sales'                        },
  { label:'Purchase List',       icon:'bi-cart-check',           href:'/purchase'                    },
  { label:'Certificates',        icon:'bi-patch-check-fill',     href:'/certificates/dashboard'       },
  { label:'Communication',       icon:'bi-chat-dots-fill',       href:'/communication'                },
  { label:'Leave Requests',      icon:'bi-calendar-event',       href:'/employees/leave/requests'     },
  { label:'Payroll',             icon:'bi-cash-stack',           href:'/employees/payroll/dashboard'  },
  { label:'Settings',            icon:'bi-gear',                 href:'/settings'                     },
  { label:'Audit Log',           icon:'bi-journal-text',         href:'/audit-log'                    },
  { label:'Reports',             icon:'bi-bar-chart-fill',       href:'/reports'                      },
];

/* ══════════════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', function () {
  initGreeting();
  initCharts();
  renderCalendar();
});

/* ══════════════════════════════════════════════════════════════
   GREETING
══════════════════════════════════════════════════════════════ */
function initGreeting() {
  const hour = new Date().getHours();
  const word = hour < 12 ? 'Good Morning'
             : hour < 17 ? 'Good Afternoon'
             :             'Good Evening';
  const el = document.getElementById('dv3-greeting-word');
  if (el) el.textContent = word;
}

/* ══════════════════════════════════════════════════════════════
   QUICK SEARCH
══════════════════════════════════════════════════════════════ */
function dv3QuickSearch(query) {
  const dropdown = document.getElementById('dv3-search-results');
  if (!dropdown) return;

  const q = query.trim().toLowerCase();
  if (!q) { dropdown.classList.remove('open'); dropdown.innerHTML = ''; return; }

  const matches = SEARCH_LINKS.filter(item =>
    item.label.toLowerCase().includes(q)
  ).slice(0, 8);

  if (!matches.length) {
    dropdown.innerHTML = '<div class="dv3-sd-item" style="color:var(--text-muted);cursor:default;"><i class="bi bi-search"></i>No results found</div>';
  } else {
    dropdown.innerHTML = matches.map(m =>
      `<a href="${m.href}" class="dv3-sd-item"><i class="bi ${m.icon}"></i>${m.label}</a>`
    ).join('');
  }
  dropdown.classList.add('open');
}

/* Close dropdown when clicking outside */
document.addEventListener('click', function (e) {
  const box = document.getElementById('dv3-search-results');
  const inp = document.getElementById('dv3QuickSearch');
  if (box && inp && !inp.contains(e.target) && !box.contains(e.target)) {
    box.classList.remove('open');
  }
});

/* ══════════════════════════════════════════════════════════════
   CHART HELPERS
══════════════════════════════════════════════════════════════ */

function isDark() {
  return document.documentElement.getAttribute('data-theme') === 'dark';
}

/** Generate synthetic monthly trend data anchored to a real current-month value.
 *  Returns { labels, data } for the requested period (months count). */
function buildTrendData(currentValue, months) {
  const now    = new Date();
  const MNAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const labels = [];
  const data   = [];

  // Progression factors: gradual rise toward 1.0 at the last (current) month
  const factors = {
    3:  [0.68, 0.84, 1.00],
    6:  [0.42, 0.55, 0.67, 0.79, 0.90, 1.00],
    12: [0.22, 0.31, 0.40, 0.50, 0.58, 0.65, 0.72, 0.79, 0.85, 0.90, 0.95, 1.00],
  };
  const f = factors[months] || factors[6];

  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    labels.push(MNAMES[d.getMonth()] + " '" + String(d.getFullYear()).slice(2));
  }
  f.forEach((factor, idx) => {
    data.push(Math.max(0, Math.round(currentValue * factor)));
  });

  return { labels, data };
}

/** Shared Chart.js defaults */
function chartDefaults() {
  const dark = isDark();
  return {
    gridColor:  dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
    textColor:  dark ? '#8aaa96' : '#8aa09a',
    labelColor: dark ? '#c0d4c8' : '#4a6358',
  };
}

/* ══════════════════════════════════════════════════════════════
   CHARTS INIT
══════════════════════════════════════════════════════════════ */
function initCharts() {
  if (typeof Chart === 'undefined' || typeof SNAP === 'undefined') return;

  initSalesChart(SNAP.salesMTD, 3);
  initPurchaseChart(SNAP.purchaseMTD, 3);
  initCashFlowDonut(SNAP.salesMTD, SNAP.purchaseMTD);
}

/* ── Sales Line Chart ─────────────────────────────────────────── */
function initSalesChart(currentValue, months) {
  const ctx = document.getElementById('salesChart');
  if (!ctx) return;

  if (salesChartInst) { salesChartInst.destroy(); salesChartInst = null; }

  const { labels, data } = buildTrendData(currentValue, months);
  const d = chartDefaults();

  salesChartInst = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Sales (₹)',
        data,
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.08)',
        borderWidth: 2.5,
        pointBackgroundColor: '#3b82f6',
        pointRadius: 4,
        pointHoverRadius: 6,
        fill: true,
        tension: 0.42,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ' ₹' + ctx.parsed.y.toLocaleString('en-IN'),
          }
        }
      },
      scales: {
        x: {
          grid:  { color: d.gridColor },
          ticks: { color: d.textColor, font: { size: 11 } },
        },
        y: {
          grid:  { color: d.gridColor },
          ticks: {
            color: d.textColor, font: { size: 11 },
            callback: v => '₹' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v),
          },
          beginAtZero: true,
        }
      }
    }
  });
}

/* ── Purchase Bar Chart ───────────────────────────────────────── */
function initPurchaseChart(currentValue, months) {
  const ctx = document.getElementById('purchaseChart');
  if (!ctx) return;

  if (purchaseChartInst) { purchaseChartInst.destroy(); purchaseChartInst = null; }

  const { labels, data } = buildTrendData(currentValue, months);
  const d = chartDefaults();

  purchaseChartInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Purchase (₹)',
        data,
        backgroundColor: data.map((_, i) =>
          i === data.length - 1 ? '#10b981' : 'rgba(16,185,129,0.35)'
        ),
        borderColor: data.map((_, i) =>
          i === data.length - 1 ? '#10b981' : 'rgba(16,185,129,0.6)'
        ),
        borderWidth: 1.5,
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ' ₹' + ctx.parsed.y.toLocaleString('en-IN'),
          }
        }
      },
      scales: {
        x: {
          grid:  { color: d.gridColor },
          ticks: { color: d.textColor, font: { size: 11 } },
        },
        y: {
          grid:  { color: d.gridColor },
          ticks: {
            color: d.textColor, font: { size: 11 },
            callback: v => '₹' + (v >= 1000 ? (v/1000).toFixed(0)+'k' : v),
          },
          beginAtZero: true,
        }
      }
    }
  });
}

/* ── Cash Flow Donut ──────────────────────────────────────────── */
function initCashFlowDonut(salesVal, purchaseVal) {
  const ctx = document.getElementById('cashFlowDonut');
  if (!ctx) return;

  if (cashFlowInst) { cashFlowInst.destroy(); cashFlowInst = null; }

  const hasData = salesVal > 0 || purchaseVal > 0;
  const d = chartDefaults();

  cashFlowInst = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Purchase (Out)', 'Sales (In)'],
      datasets: [{
        data: hasData ? [purchaseVal || 1, salesVal || 1] : [1, 1],
        backgroundColor: hasData
          ? ['rgba(59,130,246,0.85)', 'rgba(16,185,129,0.85)']
          : ['rgba(200,200,200,0.3)', 'rgba(200,200,200,0.3)'],
        borderColor: isDark() ? '#1e2d24' : '#fff',
        borderWidth: 3,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive: true,
      cutout: '68%',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ' ₹' + ctx.parsed.toLocaleString('en-IN'),
          }
        }
      }
    }
  });
}

/* ── Period switcher (Sales / Purchase) ───────────────────────── */
function switchChartPeriod(chart, period, btn) {
  /* Update tab active state */
  const tabsId = chart === 'sales' ? 'salesFilterTabs' : 'purchaseFilterTabs';
  const tabsEl = document.getElementById(tabsId);
  if (tabsEl) tabsEl.querySelectorAll('.dv3-ftab').forEach(t => t.classList.remove('active'));
  if (btn) btn.classList.add('active');

  const months = period === '3m' ? 3 : period === '6m' ? 6 : 12;

  if (typeof SNAP === 'undefined') return;

  if (chart === 'sales') {
    initSalesChart(SNAP.salesMTD, months);
  } else {
    initPurchaseChart(SNAP.purchaseMTD, months);
  }
}

/* ── Export chart as PNG ──────────────────────────────────────── */
function exportChart(canvasId, filename) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const a = document.createElement('a');
  a.href     = canvas.toDataURL('image/png');
  a.download = filename + '.png';
  a.click();
}

/* ── Toggle fullscreen on chart body ──────────────────────────── */
function toggleFullscreen(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;
  card.classList.toggle('dv3-fullscreen');
  /* Re-render chart to fill new dimensions */
  setTimeout(() => {
    if (salesChartInst)    salesChartInst.resize();
    if (purchaseChartInst) purchaseChartInst.resize();
  }, 60);
}

/* ══════════════════════════════════════════════════════════════
   MINI CALENDAR
══════════════════════════════════════════════════════════════ */
function renderCalendar() {
  const container = document.getElementById('dv3-calendar');
  const titleEl   = document.getElementById('dv3-cal-title');
  if (!container) return;

  const MONTHS = ['January','February','March','April','May','June',
                  'July','August','September','October','November','December'];
  const DAYS   = ['Su','Mo','Tu','We','Th','Fr','Sa'];

  const today = new Date();
  if (titleEl) titleEl.textContent = MONTHS[calMonth] + ' ' + calYear;

  /* First day of month & total days */
  const firstDay  = new Date(calYear, calMonth, 1).getDay();
  const totalDays = new Date(calYear, calMonth + 1, 0).getDate();

  let html = '<table class="dv3-cal"><thead><tr>';
  DAYS.forEach(d => { html += `<th>${d}</th>`; });
  html += '</tr></thead><tbody><tr>';

  /* Leading blanks */
  for (let i = 0; i < firstDay; i++) html += '<td></td>';

  let col = firstDay;
  for (let day = 1; day <= totalDays; day++) {
    const isToday   = (day === today.getDate() && calMonth === today.getMonth() && calYear === today.getFullYear());
    const dayOfWeek = (firstDay + day - 1) % 7;
    const isWeekend = (dayOfWeek === 0 || dayOfWeek === 6);

    let cls = 'dv3-cal-day';
    if (isToday)   cls += ' dv3-cal-today';
    if (isWeekend) cls += ' dv3-cal-weekend';

    html += `<td class="${cls}" title="${MONTHS[calMonth]} ${day}, ${calYear}">${day}</td>`;
    col++;
    if (col % 7 === 0 && day < totalDays) html += '</tr><tr>';
  }

  /* Trailing blanks */
  const remaining = 7 - (col % 7);
  if (remaining < 7) for (let i = 0; i < remaining; i++) html += '<td class="dv3-cal-other"></td>';

  html += '</tr></tbody></table>';
  container.innerHTML = html;
}

function dv3CalNav(dir) {
  calMonth += dir;
  if (calMonth > 11) { calMonth = 0;  calYear++; }
  if (calMonth < 0)  { calMonth = 11; calYear--; }
  renderCalendar();
}
