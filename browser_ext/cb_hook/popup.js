/* CipherBridge Hook popup — 总开关写入 chrome.storage */
(function () {
  "use strict";

  var DEFAULTS = {
    functionHook: true,
    evalHook: true,
    timerHook: true,
    timerNuke: false,
    consoleClear: true,
    sizeSpoof: true,
    rewriteResponse: false,
  };

  var enabledEl = document.getElementById("cbEnabled");
  var msgEl = document.getElementById("msg");

  function showMsg(t) {
    msgEl.textContent = t || "";
  }

  async function load() {
    try {
      var stored = await chrome.storage.local.get(["cbEnabled", "cbInjectOpts"]);
      enabledEl.checked = stored.cbEnabled !== false;
      return;
    } catch (e) {}
    enabledEl.checked = true;
  }

  async function save() {
    var opts = Object.assign({}, DEFAULTS);
    try {
      var prev = await chrome.storage.local.get(["cbInjectOpts"]);
      if (prev.cbInjectOpts && typeof prev.cbInjectOpts === "object") {
        opts = Object.assign(opts, prev.cbInjectOpts);
      }
    } catch (e) {}
    await chrome.storage.local.set({
      cbEnabled: !!enabledEl.checked,
      cbInjectOpts: opts,
    });
    showMsg("已保存 · 请刷新页面");
    setTimeout(function () {
      showMsg("");
    }, 2500);
  }

  async function reset() {
    enabledEl.checked = true;
    await chrome.storage.local.set({
      cbEnabled: true,
      cbInjectOpts: Object.assign({}, DEFAULTS),
    });
    showMsg("已恢复默认");
    setTimeout(function () {
      showMsg("");
    }, 2000);
  }

  document.getElementById("btnSave").addEventListener("click", save);
  document.getElementById("btnReset").addEventListener("click", reset);
  enabledEl.addEventListener("change", save);

  load();
})();
