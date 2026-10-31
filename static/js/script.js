/**
 * Digital Library & Research Management System
 * Frontend Client-Side Controller & Dynamic Interactivity
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Auto-dismiss flash alerts after 5 seconds
  const flashAlerts = document.querySelectorAll('.alert-dismissible');
  flashAlerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) {
        bsAlert.close();
      }
    }, 5000);
  });

  // 2. Initialize Bootstrap tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // 3. Highlight current active nav item based on URL path
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll('.nav-link-custom, .admin-sidebar-nav .nav-link');
  navLinks.forEach(function (link) {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });
});

/**
 * Toast / In-page dynamic notification utility
 */
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) {
    const newContainer = document.createElement('div');
    newContainer.id = 'toast-container';
    newContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    newContainer.style.zIndex = '1090';
    document.body.appendChild(newContainer);
  }

  const toastId = 'toast-' + Date.now();
  const bgClass = type === 'success' ? 'bg-success' : type === 'danger' ? 'bg-danger' : type === 'warning' ? 'bg-warning' : 'bg-primary';
  const toastHtml = `
    <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">
          ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;

  document.getElementById('toast-container').insertAdjacentHTML('beforeend', toastHtml);
  const toastElem = document.getElementById(toastId);
  const bsToast = new bootstrap.Toast(toastElem, { delay: 4000 });
  bsToast.show();

  toastElem.addEventListener('hidden.bs.toast', function () {
    toastElem.remove();
  });
}

/**
 * Client-Side API Helper: Submit Borrow Request
 */
async function requestBookBorrow(bookId, bookTitle) {
  if (!confirm(`Are you sure you want to request to borrow "${bookTitle}"?`)) {
    return;
  }

  try {
    const response = await fetch('/api/borrow/request', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ book_id: bookId }),
    });

    const data = await response.json();
    if (response.ok) {
      showToast(data.message || 'Borrow request submitted successfully!', 'success');
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } else {
      showToast(data.error || 'Failed to submit borrow request.', 'danger');
    }
  } catch (err) {
    console.error('Request error:', err);
    showToast('A network error occurred. Please try again.', 'danger');
  }
}

/**
 * Client-Side API Helper: Approve Borrow Request (Admin)
 */
async function approveBorrowRequest(recordId) {
  if (!confirm('Approve this book issue request for the student?')) {
    return;
  }

  try {
    const response = await fetch(`/api/borrow/approve/${recordId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    if (response.ok) {
      showToast(data.message || 'Book issued successfully!', 'success');
      setTimeout(() => window.location.reload(), 1200);
    } else {
      showToast(data.error || 'Failed to approve request.', 'danger');
    }
  } catch (err) {
    showToast('Network error processing approval.', 'danger');
  }
}

/**
 * Client-Side API Helper: Reject Borrow Request (Admin)
 */
async function rejectBorrowRequest(recordId) {
  const reason = prompt('Please enter the reason for rejection (optional):', 'Book currently reserved for library reference');
  if (reason === null) return;

  try {
    const response = await fetch(`/api/borrow/reject/${recordId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ remarks: reason }),
    });
    const data = await response.json();
    if (response.ok) {
      showToast(data.message || 'Request rejected.', 'info');
      setTimeout(() => window.location.reload(), 1200);
    } else {
      showToast(data.error || 'Failed to reject request.', 'danger');
    }
  } catch (err) {
    showToast('Network error processing rejection.', 'danger');
  }
}

/**
 * Client-Side API Helper: Return Issued Book (Admin)
 */
async function returnIssuedBook(recordId) {
  if (!confirm('Confirm return of this book? Available inventory will be incremented.')) {
    return;
  }

  try {
    const response = await fetch(`/api/borrow/return/${recordId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    if (response.ok) {
      showToast(data.message || 'Book return recorded successfully!', 'success');
      setTimeout(() => window.location.reload(), 1200);
    } else {
      showToast(data.error || 'Failed to record return.', 'danger');
    }
  } catch (err) {
    showToast('Network error processing return.', 'danger');
  }
}

/**
 * Client-Side API Helper: Toggle Member Account Status (Admin)
 */
async function toggleMemberStatus(userId, currentStatus) {
  const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
  const actionText = newStatus === 'active' ? 'activate' : 'deactivate';

  if (!confirm(`Are you sure you want to ${actionText} this member account?`)) {
    return;
  }

  try {
    const response = await fetch(`/api/members/${userId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    });
    const data = await response.json();
    if (response.ok) {
      showToast(`Member account marked as ${newStatus}!`, 'success');
      setTimeout(() => window.location.reload(), 1200);
    } else {
      showToast(data.error || 'Failed to update member status.', 'danger');
    }
  } catch (err) {
    showToast('Network error updating status.', 'danger');
  }
}
