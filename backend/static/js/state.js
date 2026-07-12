function updateStateCode() {
    const state = document.getElementById("state").value;
    document.getElementById("state_code").value = window.STATE_CODES[state] || "";
}

document.getElementById("state").addEventListener("change", updateStateCode);
updateStateCode();
