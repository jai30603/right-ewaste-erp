// Material Processing Javascript

document.addEventListener("DOMContentLoaded", function () {
  // Global arrays to keep track of rows
  window.processingInputs = window.processingInputs || [];
  window.processingOutputs = window.processingOutputs || [];
  window.processingLosses = window.processingLosses || [];

  updateWeightBalance();

  // Bind forms if present
  const jobForm = document.getElementById("jobForm");
  if (jobForm) {
    jobForm.addEventListener("submit", function (e) {
      // Serialize arrays to hidden inputs
      document.getElementById("inputs_json").value = JSON.stringify(window.processingInputs);
      if (document.getElementById("outputs_json")) {
        document.getElementById("outputs_json").value = JSON.stringify(window.processingOutputs);
      }
      if (document.getElementById("losses_json")) {
        document.getElementById("losses_json").value = JSON.stringify(window.processingLosses);
      }
    });
  }
});

// Update Weight Balance calculation banner
function updateWeightBalance() {
  const totalInputWtEl = document.getElementById("totalInputWeight");
  const totalOutputWtEl = document.getElementById("totalOutputWeight");
  const totalLossWtEl = document.getElementById("totalLossWeight");
  const wtDiffEl = document.getElementById("weightDifference");
  const balanceStatusEl = document.getElementById("balanceStatus");

  if (!totalInputWtEl) return; // Not on the form page

  let inputWeight = 0;
  window.processingInputs.forEach(function (item) {
    inputWeight += parseFloat(item.weight || 0);
  });

  let outputWeight = 0;
  window.processingOutputs.forEach(function (item) {
    outputWeight += parseFloat(item.weight || 0);
  });

  let lossWeight = 0;
  window.processingLosses.forEach(function (item) {
    lossWeight += parseFloat(item.loss_weight || 0);
  });

  const diff = inputWeight - (outputWeight + lossWeight);
  const tolerance = parseFloat(document.getElementById("weightToleranceVal")?.value || 0.5);

  totalInputWtEl.textContent = inputWeight.toFixed(2) + " KG";
  totalOutputWtEl.textContent = outputWeight.toFixed(2) + " KG";
  totalLossWtEl.textContent = lossWeight.toFixed(2) + " KG";
  wtDiffEl.textContent = Math.abs(diff).toFixed(2) + " KG";

  const completeBtn = document.getElementById("completeJobBtn");

  if (Math.abs(diff) <= tolerance + 0.0001) {
    balanceStatusEl.innerHTML = '<span class="badge bg-success"><i class="bi bi-check-circle-fill me-1"></i> Balanced</span>';
    balanceStatusEl.className = "text-success fw-bold";
    if (completeBtn) completeBtn.disabled = false;
  } else {
    balanceStatusEl.innerHTML = '<span class="badge bg-danger"><i class="bi bi-exclamation-triangle-fill me-1"></i> Unbalanced</span>';
    balanceStatusEl.className = "text-danger fw-bold";
    if (completeBtn) completeBtn.disabled = true;
  }
}

// Add/Remove Inputs
function addInputRow(materialId, name, code, maxQty, maxWt, unit) {
  // Check if already exists
  const exists = window.processingInputs.some(function (item) {
    return item.material_id == materialId;
  });
  if (exists) {
    alert("Material is already added as an input.");
    return;
  }

  const row = {
    material_id: materialId,
    name: name,
    code: code,
    quantity: maxQty,
    weight: maxWt,
    unit: unit,
    processing_type: "DISMANTLING"
  };

  window.processingInputs.push(row);
  renderInputsTable();
  updateWeightBalance();
}

function removeInputRow(index) {
  window.processingInputs.splice(index, 1);
  renderInputsTable();
  updateWeightBalance();
}

function updateInputVal(index, field, val) {
  if (field === "quantity" || field === "weight") {
    window.processingInputs[index][field] = parseFloat(val || 0);
  } else {
    window.processingInputs[index][field] = val;
  }
  updateWeightBalance();
}

function renderInputsTable() {
  const tbody = document.getElementById("inputsTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  window.processingInputs.forEach(function (item, idx) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        <span class="fw-bold">${item.name}</span><br>
        <small class="text-muted">${item.code}</small>
      </td>
      <td>
        <input type="number" class="form-control form-control-sm" step="0.01" value="${item.quantity}" onchange="updateInputVal(${idx}, 'quantity', this.value)">
      </td>
      <td>
        <div class="input-group input-group-sm">
          <input type="number" class="form-control" step="0.01" value="${item.weight}" onchange="updateInputVal(${idx}, 'weight', this.value)">
          <span class="input-group-text">KG</span>
        </div>
      </td>
      <td>
        <select class="form-select form-select-sm" onchange="updateInputVal(${idx}, 'processing_type', this.value)">
          <option value="DISMANTLING" ${item.processing_type === 'DISMANTLING' ? 'selected' : ''}>Dismantling</option>
          <option value="REFURBISHMENT" ${item.processing_type === 'REFURBISHMENT' ? 'selected' : ''}>Refurbishment</option>
          <option value="SORTING" ${item.processing_type === 'SORTING' ? 'selected' : ''}>Sorting</option>
          <option value="INTERNAL_CONSUMPTION" ${item.processing_type === 'INTERNAL_CONSUMPTION' ? 'selected' : ''}>Internal Consumption</option>
          <option value="WEIGHT_ADJUSTMENT" ${item.processing_type === 'WEIGHT_ADJUSTMENT' ? 'selected' : ''}>Weight Adjustment</option>
        </select>
      </td>
      <td>
        <button type="button" class="btn btn-outline-danger btn-sm" onclick="removeInputRow(${idx})">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// Add/Remove Outputs
function addOutputRow(materialId, name, code, unit) {
  const row = {
    material_id: materialId,
    name: name,
    code: code,
    quantity: 0,
    weight: 0,
    unit: unit,
    inventory_state: "RECOVERED",
    recovered_from_material_id: ""
  };

  window.processingOutputs.push(row);
  renderOutputsTable();
  updateWeightBalance();
}

function removeOutputRow(index) {
  window.processingOutputs.splice(index, 1);
  renderOutputsTable();
  updateWeightBalance();
}

function updateOutputVal(index, field, val) {
  if (field === "quantity" || field === "weight") {
    window.processingOutputs[index][field] = parseFloat(val || 0);
  } else {
    window.processingOutputs[index][field] = val;
  }
  updateWeightBalance();
}

function renderOutputsTable() {
  const tbody = document.getElementById("outputsTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  // Generate genealogy options based on current inputs
  let genealogyOptions = '<option value="">-- Unknown/Select Input --</option>';
  window.processingInputs.forEach(function (item) {
    genealogyOptions += `<option value="${item.material_id}">${item.name}</option>`;
  });

  window.processingOutputs.forEach(function (item, idx) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        <span class="fw-bold">${item.name}</span><br>
        <small class="text-muted">${item.code}</small>
      </td>
      <td>
        <input type="number" class="form-control form-control-sm" step="0.01" value="${item.quantity}" onchange="updateOutputVal(${idx}, 'quantity', this.value)">
      </td>
      <td>
        <div class="input-group input-group-sm">
          <input type="number" class="form-control" step="0.01" value="${item.weight}" onchange="updateOutputVal(${idx}, 'weight', this.value)">
          <span class="input-group-text">KG</span>
        </div>
      </td>
      <td>
        <select class="form-select form-select-sm" onchange="updateOutputVal(${idx}, 'inventory_state', this.value)">
          <option value="RECOVERED" ${item.inventory_state === 'RECOVERED' ? 'selected' : ''}>Recovered</option>
          <option value="REFURBISHED" ${item.inventory_state === 'REFURBISHED' ? 'selected' : ''}>Refurbished</option>
          <option value="RAW" ${item.inventory_state === 'RAW' ? 'selected' : ''}>Raw</option>
          <option value="FINISHED" ${item.inventory_state === 'FINISHED' ? 'selected' : ''}>Finished</option>
        </select>
      </td>
      <td>
        <select class="form-select form-select-sm" onchange="updateOutputVal(${idx}, 'recovered_from_material_id', this.value)">
          ${genealogyOptions}
        </select>
      </td>
      <td>
        <button type="button" class="btn btn-outline-danger btn-sm" onclick="removeOutputRow(${idx})">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);

    // Set value for dropdown since it's dynamically populated
    const select = tr.querySelector(`select[onchange*="recovered_from_material_id"]`);
    if (select) {
      select.value = item.recovered_from_material_id || "";
    }
  });
}

// Add/Remove Losses
function addLossRow() {
  const row = {
    loss_weight: 0,
    loss_reason: "WATER",
    remarks: ""
  };
  window.processingLosses.push(row);
  renderLossesTable();
  updateWeightBalance();
}

function removeLossRow(index) {
  window.processingLosses.splice(index, 1);
  renderLossesTable();
  updateWeightBalance();
}

function updateLossVal(index, field, val) {
  if (field === "loss_weight") {
    window.processingLosses[index][field] = parseFloat(val || 0);
  } else {
    window.processingLosses[index][field] = val;
  }
  updateWeightBalance();
}

function renderLossesTable() {
  const tbody = document.getElementById("lossesTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  window.processingLosses.forEach(function (item, idx) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        <div class="input-group input-group-sm">
          <input type="number" class="form-control" step="0.01" value="${item.loss_weight}" onchange="updateLossVal(${idx}, 'loss_weight', this.value)">
          <span class="input-group-text">KG</span>
        </div>
      </td>
      <td>
        <select class="form-select form-select-sm" onchange="updateLossVal(${idx}, 'loss_reason', this.value)">
          <option value="WATER" ${item.loss_reason === 'WATER' ? 'selected' : ''}>Water</option>
          <option value="DUST" ${item.loss_reason === 'DUST' ? 'selected' : ''}>Dust</option>
          <option value="PACKAGING" ${item.loss_reason === 'PACKAGING' ? 'selected' : ''}>Packaging</option>
          <option value="BROKEN_MATERIAL" ${item.loss_reason === 'BROKEN_MATERIAL' ? 'selected' : ''}>Broken Material</option>
          <option value="NON_RECYCLABLE_WASTE" ${item.loss_reason === 'NON_RECYCLABLE_WASTE' ? 'selected' : ''}>Non-Recyclable Waste</option>
          <option value="OTHER" ${item.loss_reason === 'OTHER' ? 'selected' : ''}>Other</option>
          <option value="UNKNOWN" ${item.loss_reason === 'UNKNOWN' ? 'selected' : ''}>Unknown</option>
        </select>
      </td>
      <td>
        <input type="text" class="form-control form-control-sm" value="${item.remarks || ''}" onchange="updateLossVal(${idx}, 'remarks', this.value)">
      </td>
      <td>
        <button type="button" class="btn btn-outline-danger btn-sm" onclick="removeLossRow(${idx})">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}
