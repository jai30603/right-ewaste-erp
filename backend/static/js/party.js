// Party Module JavaScript

// states dict is injected by the template before this script loads
function updateStateCode() {
    const stateEl = document.getElementById("state");
    const stateCodeEl = document.getElementById("state_code");
    if (stateEl && stateCodeEl && typeof states !== 'undefined') {
        const state = stateEl.value;
        stateCodeEl.value = states[state] || "";
    }
}
