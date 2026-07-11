// states dict is injected by the template before this script loads

function updateStateCode() {
    const state = document.getElementById("state").value;
    document.getElementById("state_code").value = states[state] || "";
}
