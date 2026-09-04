/* ═══════════════════════════════════════════════════════════════════════════
   Right Ewaste ERP v5.0 – Inventory Workspace JS
   Shared across all Inventory module pages
   ═══════════════════════════════════════════════════════════════════════════ */

'use strict';

/* ── View toggle (grid / list / card / table) ─────────────────────────────── */
function invSetView(viewId) {
  document.querySelectorAll('[data-inv-view]').forEach(el => {
    el.style.display = el.dataset.invView === viewId ? '' : 'none';
  });
  document.querySelectorAll('.inv-view-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewId);
  });
  localStorage.setItem('inv_view_' + (window.INV_PAGE || 'default'), viewId);
}

function invInitViewToggle(defaultView) {
  const saved = localStorage.getItem('inv_view_' + (window.INV_PAGE || 'default'));
  invSetView(saved || defaultView || 'table');
}

/* ── Sort table columns ───────────────────────────────────────────────────── */
function invInitTableSort() {
  document.querySelectorAll('.inv-table thead th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const table = th.closest('table');
      const col = Array.from(th.parentElement.children).indexOf(th);
      const asc = th.classList.contains('sorted-asc');
      // Clear all
      table.querySelectorAll('thead th').forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
      th.classList.add(asc ? 'sorted-desc' : 'sorted-asc');
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort((a, b) => {
        const av = a.cells[col]?.textContent.trim() || '';
        const bv = b.cells[col]?.textContent.trim() || '';
        const an = parseFloat(av.replace(/[^0-9.-]/g, ''));
        const bn = parseFloat(bv.replace(/[^0-9.-]/g, ''));
        if (!isNaN(an) && !isNaN(bn)) return asc ? bn - an : an - bn;
        return asc ? bv.localeCompare(av) : av.localeCompare(bv);
      });
      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

/* ── Bulk checkbox select all ─────────────────────────────────────────────── */
function invInitBulkSelect() {
  const master = document.getElementById('inv-select-all');
  if (!master) return;
  master.addEventListener('change', () => {
    document.querySelectorAll('.inv-row-check').forEach(cb => {
      cb.checked = master.checked;
    });
    invUpdateBulkBar();
  });
  document.querySelectorAll('.inv-row-check').forEach(cb => {
    cb.addEventListener('change', invUpdateBulkBar);
  });
}

function invUpdateBulkBar() {
  const checked = document.querySelectorAll('.inv-row-check:checked').length;
  const bar = document.getElementById('inv-bulk-bar');
  if (bar) {
    bar.style.display = checked > 0 ? 'flex' : 'none';
    const cnt = bar.querySelector('.bulk-count');
    if (cnt) cnt.textContent = checked + ' selected';
  }
}

/* ── Instant client-side search ───────────────────────────────────────────── */
function invInitClientSearch(inputId, rowSelector) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase().trim();
    document.querySelectorAll(rowSelector).forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = (!q || text.includes(q)) ? '' : 'none';
    });
  });
}

/* ── Filter drawer (mobile) ───────────────────────────────────────────────── */
function invOpenFilterDrawer() {
  document.getElementById('invFilterOverlay')?.classList.add('open');
  document.getElementById('invFilterDrawer')?.classList.add('open');
}
function invCloseFilterDrawer() {
  document.getElementById('invFilterOverlay')?.classList.remove('open');
  document.getElementById('invFilterDrawer')?.classList.remove('open');
}

/* ── Date range toggle ────────────────────────────────────────────────────── */
function invToggleDateRange(selectEl, rangeId) {
  const show = selectEl.value === 'custom';
  const el = document.getElementById(rangeId);
  if (el) el.style.display = show ? 'flex' : 'none';
}

/* ── Auto-submit filter forms on select change ────────────────────────────── */
function invInitAutoSubmit() {
  document.querySelectorAll('[data-inv-autosubmit]').forEach(el => {
    el.addEventListener('change', () => el.closest('form')?.submit());
  });
}

/* ── Export helpers ───────────────────────────────────────────────────────── */
function invExport(fmt) {
  const url = new URL(window.location.href);
  url.searchParams.set('format', fmt);
  window.location.href = url.toString();
}

/* ── Flow diagram node click ──────────────────────────────────────────────── */
function invNodeClick(node, detailId) {
  document.querySelectorAll('.inv-flow-node').forEach(n => n.classList.remove('node-selected'));
  node.classList.add('node-selected');
  const detail = document.getElementById(detailId);
  if (detail) {
    const title = node.querySelector('.inv-flow-node-label')?.textContent || 'Node Details';
    const contentHtml = detail.innerHTML;
    
    let overlay = document.getElementById('inv-drawer-overlay');
    let drawer = document.getElementById('inv-drawer');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'inv-drawer-overlay';
      overlay.className = 'inv-drawer-overlay';
      overlay.onclick = invCloseDrawer;
      document.body.appendChild(overlay);
    }
    if (!drawer) {
      drawer = document.createElement('div');
      drawer.id = 'inv-drawer';
      drawer.className = 'inv-drawer';
      drawer.innerHTML = `
        <div class="inv-drawer-header">
          <h3 class="inv-drawer-title" id="inv-drawer-title">Details</h3>
          <button class="inv-btn inv-btn-ghost" onclick="invCloseDrawer()" style="padding: 4px 8px;">
            <i class="bi bi-x-lg" style="font-size: 14px;"></i>
          </button>
        </div>
        <div class="inv-drawer-body" id="inv-drawer-body"></div>
      `;
      document.body.appendChild(drawer);
    }
    document.getElementById('inv-drawer-title').textContent = title;
    document.getElementById('inv-drawer-body').innerHTML = contentHtml;
    overlay.classList.add('open');
    drawer.classList.add('open');
  }
}

/* ── Copy to clipboard ────────────────────────────────────────────────────── */
function invCopy(text) {
  navigator.clipboard?.writeText(text).then(() => {
    const toast = document.createElement('div');
    toast.className = 'inv-toast';
    toast.textContent = 'Copied!';
    toast.style.cssText = 'position:fixed;bottom:80px;right:24px;background:#0d9488;color:#fff;padding:8px 16px;border-radius:8px;font-size:13px;z-index:9999;animation:fadeIn .2s ease;';
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 1800);
  });
}

/* ── Refresh current page ─────────────────────────────────────────────────── */
/* ── Toggle collapse sections ─────────────────────────────────────────────── */
function invToggleCollapse(collapseId) {
  const el = document.getElementById(collapseId);
  const chevron = document.getElementById(collapseId + 'Chevron');
  if (el) {
    const hidden = el.style.display === 'none';
    el.style.display = hidden ? '' : 'none';
    if (chevron) {
      chevron.className = hidden ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
    }
  }
}

function invRefresh() {
  window.location.reload();
}

/* ── Persist workspace filters in sessionStorage ─────────────────────────── */
function invSaveFilters() {
  const params = new URLSearchParams(window.location.search);
  sessionStorage.setItem('inv_filters', params.toString());
}
function invRestoreFiltersLink(href) {
  const saved = sessionStorage.getItem('inv_filters');
  if (!saved) return href;
  try {
    const base = new URL(href, window.location.origin);
    const saved_params = new URLSearchParams(saved);
    saved_params.forEach((v, k) => {
      if (!['page'].includes(k)) base.searchParams.set(k, v);
    });
    return base.pathname + '?' + base.searchParams.toString();
  } catch { return href; }
}

/* ── Sidebar Details Drawer ───────────────────────────────────────────────── */
function invShowDrawer(url, title = 'Item Details') {
  let overlay = document.getElementById('inv-drawer-overlay');
  let drawer = document.getElementById('inv-drawer');
  
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'inv-drawer-overlay';
    overlay.className = 'inv-drawer-overlay';
    overlay.onclick = invCloseDrawer;
    document.body.appendChild(overlay);
  }
  if (!drawer) {
    drawer = document.createElement('div');
    drawer.id = 'inv-drawer';
    drawer.className = 'inv-drawer';
    drawer.innerHTML = `
      <div class="inv-drawer-header">
        <h3 class="inv-drawer-title" id="inv-drawer-title">Details</h3>
        <button class="inv-btn inv-btn-ghost" onclick="invCloseDrawer()" style="padding: 4px 8px;">
          <i class="bi bi-x-lg" style="font-size: 14px;"></i>
        </button>
      </div>
      <div class="inv-drawer-body" id="inv-drawer-body"></div>
    `;
    document.body.appendChild(drawer);
  }

  document.getElementById('inv-drawer-title').textContent = title;
  const body = document.getElementById('inv-drawer-body');
  
  body.innerHTML = `
    <div class="inv-skeleton-title"></div>
    <div class="inv-skeleton-row" style="width: 90%;"></div>
    <div class="inv-skeleton-row" style="width: 80%;"></div>
    <div class="inv-skeleton-row" style="width: 85%;"></div>
    <div class="inv-skeleton-row" style="width: 60%;"></div>
    <div class="inv-skeleton-row" style="width: 75%;"></div>
  `;
  
  overlay.classList.add('open');
  drawer.classList.add('open');

  const fetchUrl = url + (url.indexOf('?') >= 0 ? '&' : '?') + 'drawer=1';
  fetch(fetchUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then(r => {
      if (!r.ok) throw new Error('Failed to load details');
      return r.text();
    })
    .then(html => {
      body.innerHTML = html;
    })
    .catch(err => {
      body.innerHTML = `
        <div class="text-danger p-3 text-center">
          <i class="bi bi-exclamation-octagon" style="font-size: 24px;"></i>
          <p class="mt-2">${err.message}</p>
        </div>
      `;
    });
}

function invCloseDrawer() {
  document.getElementById('inv-drawer-overlay')?.classList.remove('open');
  document.getElementById('inv-drawer')?.classList.remove('open');
}

/* ── Init all ─────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  invInitTableSort();
  invInitBulkSelect();
  invInitAutoSubmit();
});
