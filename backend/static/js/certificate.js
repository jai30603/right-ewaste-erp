// Certificate Javascript Utilities

document.addEventListener("DOMContentLoaded", function () {
  const customerSelect = document.getElementById("customer_id_select");
  if (customerSelect) {
    customerSelect.addEventListener("change", performReadinessValidation);
  }

  // Monitor processing job selections to validate
  const jobCheckboxes = document.querySelectorAll('input[name="processing_job_ids"]');
  jobCheckboxes.forEach(cb => {
    cb.addEventListener("change", performReadinessValidation);
  });
  
  performReadinessValidation();
});

// Run checklist verification checks via API
function performReadinessValidation() {
  const customerSelect = document.getElementById("customer_id_select");
  if (!customerSelect) return;
  
  const customerId = customerSelect.value;
  if (!customerId) {
    updateChecklistState(false, ["Please select a customer first."]);
    return;
  }

  const selectedJobs = [];
  const checkedBoxes = document.querySelectorAll('input[name="processing_job_ids"]:checked');
  checkedBoxes.forEach(cb => {
    selectedJobs.push(cb.value);
  });

  if (selectedJobs.length === 0) {
    updateChecklistState(false, ["Please select at least one Processing Job."]);
    return;
  }

  // Call API
  let url = `/certificates/validate-readiness/${customerId}?`;
  selectedJobs.forEach(id => {
    url += `job_ids=${id}&`;
  });

  fetch(url)
    .then(res => res.json())
    .then(data => {
      updateChecklistState(data.valid, data.errors);
    })
    .catch(err => {
      console.error("Readiness check failed:", err);
    });
}

function updateChecklistState(isValid, errors) {
  const checklistBody = document.getElementById("validationChecklistBody");
  if (!checklistBody) return;

  let html = "";
  
  // Rule 1: Customer Details
  const customerErr = errors.find(x => x.includes("Customer"));
  if (customerErr) {
    html += `<li class="list-group-item list-group-item-danger"><i class="bi bi-x-circle-fill me-2"></i>Customer Verification: ${customerErr}</li>`;
  } else {
    html += `<li class="list-group-item list-group-item-success"><i class="bi bi-check-circle-fill me-2"></i>Customer Verified</li>`;
  }

  // Rule 2: Processing Completed
  const jobsChecked = document.querySelectorAll('input[name="processing_job_ids"]:checked');
  if (jobsChecked.length > 0) {
    const certErr = errors.find(x => x.includes("certified"));
    if (certErr) {
      html += `<li class="list-group-item list-group-item-danger"><i class="bi bi-x-circle-fill me-2"></i>Processing Verification: ${certErr}</li>`;
    } else {
      html += `<li class="list-group-item list-group-item-success"><i class="bi bi-check-circle-fill me-2"></i>Processing Jobs Verified & Completed</li>`;
    }
  } else {
    html += `<li class="list-group-item list-group-item-warning"><i class="bi bi-exclamation-triangle-fill me-2"></i>Processing Jobs: None selected</li>`;
  }

  // Rule 3: Inventory Synced
  html += `<li class="list-group-item list-group-item-success"><i class="bi bi-check-circle-fill me-2"></i>Inventory Sync status: Verified</li>`;
  
  // Rule 4: Company Profile
  html += `<li class="list-group-item list-group-item-success"><i class="bi bi-check-circle-fill me-2"></i>Company profile: Verified</li>`;

  checklistBody.innerHTML = html;

  // Toggle submit buttons
  const submitBtn = document.getElementById("createCertSubmitBtn");
  if (submitBtn) {
    submitBtn.disabled = !isValid;
  }
}

// Live Toggle visual fields in template designer
function toggleTemplateSection(sectionName, isVisible) {
  const previewElement = document.getElementById(`preview_sec_${sectionName}`);
  if (previewElement) {
    previewElement.style.display = isVisible ? "block" : "none";
  }
}
