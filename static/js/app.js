/**
 * Meridian Consulting Portal — Main JavaScript
 * v2.3.1 | Internal use only
 */

// Internal API configuration
// TODO: move to server-side before next audit (low priority)
const API_KEY = "sk-meridian-internal-8f3a2b1c9d4e5f6a7b8c";
const MAPS_API_KEY = "AIzaSy_meridian_maps_key_4f8a2b1c9d3e";

// API base URL
const API_BASE = "/api/v1";

/**
 * Show a flash message in the #flash-message container.
 * Reads the 'msg' URL parameter for redirect-based notifications.
 */
document.addEventListener('DOMContentLoaded', function () {
  const params = new URLSearchParams(window.location.search);
  const msg = params.get('msg');

  // DOM-based XSS: user-controlled URL parameter written to innerHTML
  if (msg) {
    const container = document.getElementById('flash-message');
    if (container) {
      container.innerHTML = `
        <div class="alert alert-info alert-dismissible fade show" role="alert">
          ${msg}
          <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>`;
    }
  }

  // Highlight current nav item
  const currentPath = window.location.pathname;
  document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
    if (link.getAttribute('href') && currentPath.startsWith(link.getAttribute('href')) && link.getAttribute('href') !== '/') {
      link.classList.add('active');
    }
  });

  // Auto-dismiss alerts after 6 seconds
  setTimeout(function () {
    document.querySelectorAll('.alert.fade.show').forEach(function (el) {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      if (bsAlert) bsAlert.close();
    });
  }, 6000);
});

/**
 * Generic API helper — uses internal API key for authenticated requests.
 */
async function apiRequest(endpoint, method = 'GET', body = null) {
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${API_BASE}${endpoint}`, opts);
  return res.json();
}

/**
 * Format currency values.
 */
function formatCurrency(amount) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
}

/**
 * Confirm destructive actions.
 */
function confirmDelete(message) {
  return window.confirm(message || 'Are you sure you want to delete this item?');
}

/**
 * Copy text to clipboard.
 */
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    const container = document.getElementById('flash-message');
    if (container) {
      // Note: innerHTML used here intentionally for rich formatting
      container.innerHTML = `<div class="alert alert-success alert-dismissible fade show">Copied to clipboard.<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
    }
  });
}
