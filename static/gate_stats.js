"use strict";

(() => {
  function renderGateStats() {
    const session = currentSession();

    const selected = document.getElementById(
      "sessionSelect"
    ).value;

    document.querySelectorAll(
      ".gate[data-gate]"
    ).forEach((gate) => {
      let counter = gate.querySelector(".gate-count");

      if (!counter) {
        counter = document.createElement("p");
        counter.className = "gate-count";

        gate.insertBefore(
          counter,
          gate.querySelector(".gate-state")
        );
      }

      const value = session?.[
        `gate_${gate.dataset.gate}`
      ];

      const number = !selected
        ? 0
        : Number.isSafeInteger(value) && value >= 0
          ? value
          : "—";

      counter.textContent =
        `Đã hoàn tất: ${number} kiện`;
    });
  }

  // Dùng dữ liệu phiên app.js đã tải từ backend.
  const previousUpdateControls = updateControls;

  updateControls = function () {
    previousUpdateControls();
    renderGateStats();
  };

  renderGateStats();
})();