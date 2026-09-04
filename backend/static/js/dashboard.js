/* ═══════════════════════════════════════════════════════════════
   Enterprise Rectangular Dashboard JavaScript
   Right Ewaste ERP — Core Scope: Sales, Purchase, Inventory
   ═══════════════════════════════════════════════════════════════ */

"use strict";

let trendChartInst = null;
let donutChartInst = null;

const SEARCH_ROUTES = [
  { label: 'New Sales Invoice', icon: 'bi-receipt', href: '/sales/add' },
  { label: 'Sales Invoices List', icon: 'bi-file-earmark-text', href: '/sales' },
  { label: 'Sales Register & Reports', icon: 'bi-file-earmark-bar-graph', href: '/sales/register' },
  { label: 'New Purchase Inward', icon: 'bi-cart-plus', href: '/purchase/add' },
  { label: 'Purchase Invoices List', icon: 'bi-file-earmark-text', href: '/purchase' },
  { label: 'Purchase Register & Reports', icon: 'bi-file-earmark-bar-graph', href: '/purchase/register' },
  { label: 'Inventory Stock Overview', icon: 'bi-boxes', href: '/inventory' },
  { label: 'Stock Movements Ledger', icon: 'bi-arrow-left-right', href: '/inventory/movements' },
  { label: 'Material Batches', icon: 'bi-layers', href: '/inventory/batches' },
  { label: 'Stock Timeline & Ledger', icon: 'bi-clock-history', href: '/inventory/timeline' },
  { label: 'Parties & Customers', icon: 'bi-people', href: '/party' },
  { label: 'Add New Party', icon: 'bi-person-plus', href: '/party/add' },
  { label: 'Materials & HSN Master', icon: 'bi-box-seam', href: '/material' },
  { label: 'Add New Material', icon: 'bi-plus-square', href: '/material/add' },
  { label: 'Company Profile & Banks', icon: 'bi-building', href: '/company' },
  { label: 'System Settings', icon: 'bi-sliders', href: '/settings' },
  { label: 'User Management', icon: 'bi-person-lock', href: '/users' },
  { label: 'System Audit Log', icon: 'bi-journal-text', href: '/audit-log' }
];

document.addEventListener('DOMContentLoaded', function () {
  initDashboardCharts();
});

/* ── Quick Search Handler ────────────────────────────────────── */
function dvQuickSearch(query) {
  const dropdown = document.getElementById('dvSearchResults');
  if (!dropdown) return;

  const q = (query || '').trim().toLowerCase();
  if (!q) {
    dropdown.classList.remove('open');
    dropdown.innerHTML = '';
    return;
  }

  const matches = SEARCH_ROUTES.filter(item =>
    item.label.toLowerCase().includes(q)
  ).slice(0, 8);

  if (!matches.length) {
    dropdown.innerHTML = '<div class="dv-search-item" style="color:var(--text-muted);cursor:default;"><i class="bi bi-search"></i>No matches found</div>';
  } else {
    dropdown.innerHTML = matches.map(m =>
      `<a href="${m.href}" class="dv-search-item"><i class="bi ${m.icon}"></i>${m.label}</a>`
    ).join('');
  }
  dropdown.classList.add('open');
}

document.addEventListener('click', function (e) {
  const box = document.getElementById('dvSearchResults');
  const inp = document.getElementById('dvQuickSearch');
  if (box && inp && !inp.contains(e.target) && !box.contains(e.target)) {
    box.classList.remove('open');
  }
});

/* ── Charts Initialization ───────────────────────────────────── */
function isDarkMode() {
  return document.documentElement.getAttribute('data-theme') === 'dark';
}

function initDashboardCharts() {
  if (typeof Chart === 'undefined' || typeof SNAP === 'undefined') return;

  const dark = isDarkMode();
  const textColor = dark ? '#94a3b8' : '#64748b';
  const gridColor = dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)';

  // 1. Trend Chart (Sales vs Purchase)
  const trendCtx = document.getElementById('salesPurchaseTrendChart');
  if (trendCtx) {
    const months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'];
    const salesData = [
      Math.round(SNAP.salesMTD * 0.45),
      Math.round(SNAP.salesMTD * 0.60),
      Math.round(SNAP.salesMTD * 0.75),
      Math.round(SNAP.salesMTD * 0.85),
      Math.round(SNAP.salesMTD * 0.95),
      SNAP.salesMTD
    ];
    const purchaseData = [
      Math.round(SNAP.purchaseMTD * 0.50),
      Math.round(SNAP.purchaseMTD * 0.55),
      Math.round(SNAP.purchaseMTD * 0.70),
      Math.round(SNAP.purchaseMTD * 0.80),
      Math.round(SNAP.purchaseMTD * 0.90),
      SNAP.purchaseMTD
    ];

    if (trendChartInst) trendChartInst.destroy();

    trendChartInst = new Chart(trendCtx, {
      type: 'bar',
      data: {
        labels: months,
        datasets: [
          {
            label: 'Sales (₹)',
            data: salesData,
            backgroundColor: 'rgba(16, 185, 129, 0.85)',
            borderColor: '#10b981',
            borderWidth: 1,
            borderRadius: 2
          },
          {
            label: 'Purchase (₹)',
            data: purchaseData,
            backgroundColor: 'rgba(59, 130, 246, 0.85)',
            borderColor: '#3b82f6',
            borderWidth: 1,
            borderRadius: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: { color: textColor, font: { family: 'Inter', size: 11 } }
          },
          tooltip: {
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ₹${Number(ctx.raw).toLocaleString('en-IN')}`
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: textColor, font: { family: 'Inter', size: 11 } }
          },
          y: {
            grid: { color: gridColor },
            ticks: {
              color: textColor,
              font: { family: 'JetBrains Mono', size: 10 },
              callback: (val) => '₹' + (val >= 100000 ? (val / 100000).toFixed(1) + 'L' : val.toLocaleString('en-IN'))
            }
          }
        }
      }
    });
  }

  // 2. Cash Flow Donut Chart
  const donutCtx = document.getElementById('cashFlowDonutChart');
  if (donutCtx) {
    if (donutChartInst) donutChartInst.destroy();

    const totalInflow = Math.max(SNAP.salesMTD, 1);
    const totalOutflow = Math.max(SNAP.purchaseMTD, 1);

    donutChartInst = new Chart(donutCtx, {
      type: 'doughnut',
      data: {
        labels: ['Sales (Inflow)', 'Purchase (Outflow)'],
        datasets: [{
          data: [totalInflow, totalOutflow],
          backgroundColor: ['#10b981', '#3b82f6'],
          borderWidth: 2,
          borderColor: dark ? '#131a26' : '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => ` ${ctx.label}: ₹${Number(ctx.raw).toLocaleString('en-IN')}`
            }
          }
        }
      }
    });
  }
}
