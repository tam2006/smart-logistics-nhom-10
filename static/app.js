"use strict";

const $ = (id) => document.getElementById(id);

const PENDING_KEY = "smartlogistics.pendingRequest.v1";
const SELECTED_KEY = "smartlogistics.selectedSession.v1";
const PAGE_SIZE = 10;

const statusNames = {
  success: "Thành công",
  duplicate: "Trùng kiện",
  not_found: "Không tồn tại",
  invalid_code: "Mã không hợp lệ",
  missing_destination: "Thiếu điểm đến",
  unconfigured_destination: "Chưa có cửa",
  qr_unreadable: "Không đọc được QR",
};

let sessions = [];
let busy = false;
let historyRows = [];
let hasMore = false;
let nextBeforeId = null;
let pendingRequest = null;
let qrCode = null;
let lastRefreshOk = true;
let batch = newBatch([]);

function newBatch(files) {
  return {
    id: crypto.randomUUID(),
    sessionId: null,
    sessionName: "",
    index: 0,
    running: false,
    pauseRequested: false,
    status: "Chưa chạy",
    message: "",
    entries: files.map((file) => ({
      file,
      code: null,
      readMs: null,
      motionMs: null,
      result: null,
      phase: "Chờ",
      error: "",
    })),
  };
}

function batchHasWork() {
  return Boolean(batch.sessionId) &&
    batch.index < batch.entries.length;
}

function readStored(key) {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function saveSelected(id) {
  try {
    sessionStorage.setItem(SELECTED_KEY, id);
  } catch {
    // Lựa chọn vẫn dùng trong trang hiện tại.
  }
}

function restorePending() {
  try {
    const saved = JSON.parse(readStored(PENDING_KEY) || "null");

    if (
      saved &&
      typeof saved.session_id === "string" &&
      typeof saved.request_id === "string" &&
      typeof saved.code === "string" &&
      ["manual", "qr", "auto", "api"].includes(saved.source)
    ) {
      return saved;
    }
  } catch {
    // Bỏ dữ liệu lưu không đọc được.
  }

  return null;
}

function clearPending() {
  pendingRequest = null;

  try {
    sessionStorage.removeItem(PENDING_KEY);
  } catch {
    // Backend vẫn kiểm tra trùng theo request_id.
  }
}

function notice(text, type = "info") {
  $("notice").textContent = text;
  $("notice").dataset.type = type;
}

function connection(text, state) {
  $("connectionStatus").textContent = text;
  $("connectionStatus").dataset.state = state;
}

function currentSession() {
  return sessions.find(
    (item) => item.id === $("sessionSelect").value
  );
}

function clearGates() {
  document.querySelectorAll(".gate").forEach((gate) => {
    gate.classList.remove("active");
    gate.querySelector(".gate-state").textContent = "Chờ kết quả";
  });
}

function resetLatest() {
  clearGates();
  resetMotion();

  $("latestResult").textContent =
    "Chưa có kết quả mới trên màn hình.";

  $("latestResult").dataset.type = "info";
}

function updateControls() {
  const session = currentSession();
  const active = session?.status === "active";
  const pending = Boolean(pendingRequest);
  const selected = $("sessionSelect").value;
  const locked = batchHasWork();

  $("createButton").disabled = busy || pending || locked;
  $("sessionName").disabled = busy || pending || locked;
  $("sessionSelect").disabled = busy || pending || locked;
  $("refreshButton").disabled = busy;

  $("closeButton").disabled =
    busy || pending || locked || !active ||
    Boolean(session?.pending);

  $("parcelCode").disabled = busy || pending || locked;

  $("processButton").disabled =
    busy || pending || locked || !active;

  $("qrFile").disabled = busy || pending || locked;

  $("readQrButton").disabled =
    busy || pending || locked || !$("qrFile").files.length;

  $("processQrButton").disabled =
    busy || pending || locked || !active || qrCode === null;

  $("processQrButton").textContent = qrCode === ""
    ? "Ghi nhận QR không đọc được"
    : "Xử lý mã QR";

  $("retryButton").hidden = !pending;
  $("retryButton").disabled = busy || !pending;
  $("moreButton").disabled = busy || !selected || !hasMore;

  $("total").textContent =
    session?.total ?? (selected ? "—" : 0);

  $("successes").textContent =
    session?.successes ?? (selected ? "—" : 0);

  $("unsuccessful").textContent =
    session?.unsuccessful ?? (selected ? "—" : 0);

  $("sessionInfo").textContent = session
    ? `${active ? "Đang mở" : "Đã đóng"} · ${session.name} · ` +
      `${session.pending || 0} lượt đang xử lý`
    : pending
      ? "Đang giữ phiên của lượt chưa xác nhận."
      : "Chưa chọn phiên.";

  $("batchFiles").disabled = busy || pending || locked;
  $("batchDelay").disabled = busy || locked;
  $("motionSpeed").disabled = busy || locked;

  $("batchStart").disabled =
    busy || pending || !active ||
    !batch.entries.length ||
    batch.index >= batch.entries.length;

  $("batchStart").textContent =
    batch.entries.length &&
    batch.index === batch.entries.length
      ? "Đã hoàn tất lô"
      : batch.sessionId
        ? "Tiếp tục lô"
        : "Bắt đầu lô";

  $("batchPause").disabled =
    !batch.running || batch.pauseRequested;

  $("batchClear").disabled =
    busy || pending || !batch.entries.length;
}

async function api(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        ...(options.body
          ? { "Content-Type": "application/json" }
          : {}),
        ...options.headers,
      },
    });

    let data;

    try {
      data = await response.json();
    } catch {
      const error = new Error(
        "Không đọc được phản hồi backend."
      );

      error.uncertain = true;
      connection("Phản hồi bất thường", "error");
      throw error;
    }

    if (!response.ok) {
      connection(
        response.status >= 500
          ? "Backend đang lỗi"
          : "Backend đã phản hồi",
        response.status >= 500 ? "error" : "ok"
      );

      const error = new Error(
        data.message || data.reason ||
        `Lỗi HTTP ${response.status}`
      );

      error.uncertain = response.status >= 500;
      throw error;
    }

    connection("Backend đã kết nối", "ok");
    return data;

  } catch (error) {
    if (typeof error.uncertain === "boolean") {
      throw error;
    }

    connection("Chưa nhận được phản hồi", "error");

    const networkError = new Error(
      "Không nhận được phản hồi. Kiểm tra Terminal 1."
    );

    networkError.uncertain = true;
    throw networkError;

  } finally {
    clearTimeout(timer);
  }
}

async function runTask(task) {
  if (busy) return;

  busy = true;
  updateControls();

  try {
    await task();
  } catch (error) {
    notice(error.message, "error");
  } finally {
    busy = false;
    updateControls();
  }
}

function renderSessions(preferredId) {
  const select = $("sessionSelect");
  select.replaceChildren();

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Chọn phiên làm việc";
  select.append(placeholder);

  sessions.forEach((session) => {
    const option = document.createElement("option");

    option.value = session.id;
    option.textContent =
      `${session.name} · ` +
      (session.status === "active" ? "Đang mở" : "Đã đóng");

    select.append(option);
  });

  if (
    pendingRequest &&
    !sessions.some(
      (session) => session.id === pendingRequest.session_id
    )
  ) {
    const option = document.createElement("option");
    option.value = pendingRequest.session_id;
    option.textContent = "Phiên có lượt chưa xác nhận";
    select.append(option);
  }

  if (
    Array.from(select.options).some(
      (option) => option.value === preferredId
    )
  ) {
    select.value = preferredId;
  }

  saveSelected(select.value);
  updateControls();
}

function addCell(row, value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value ?? "—";
  cell.className = className;
  row.append(cell);
}

function renderHistory() {
  const body = $("historyBody");
  body.replaceChildren();

  $("historyCount").textContent =
    `${historyRows.length} lượt hiển thị`;

  if (!historyRows.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.colSpan = 9;
    cell.className = "empty";
    cell.textContent = $("sessionSelect").value
      ? "Chưa có lượt được tải."
      : "Chưa chọn phiên.";

    row.append(cell);
    body.append(row);
    return;
  }

  historyRows.forEach((item) => {
    const row = document.createElement("tr");

    addCell(row, item.id);
    addCell(row, item.code || "(trống)");
    addCell(row, item.destination);
    addCell(row, item.gate);

    addCell(
      row,
      statusNames[item.status] || item.status,
      item.success ? "text-success" : "text-error"
    );

    addCell(row, item.reason, "reason");

    const sourceNames = {
      manual: "Nhập tay",
      qr: "Ảnh QR",
      auto: "Tự động",
      api: "API",
    };

    addCell(row, sourceNames[item.source] || item.source);
    addCell(row, Number(item.decision_ms).toFixed(3));

    const date = new Date(item.created_at);

    addCell(
      row,
      Number.isNaN(date.getTime())
        ? "—"
        : date.toLocaleString("vi-VN")
    );

    body.append(row);
  });
}

function clearHistory() {
  historyRows = [];
  hasMore = false;
  nextBeforeId = null;
  renderHistory();
}

async function loadHistory(append = false) {
  const sessionId = $("sessionSelect").value;

  if (!sessionId) {
    clearHistory();
    return;
  }

  const params = new URLSearchParams({
    session_id: sessionId,
    limit: String(PAGE_SIZE),
  });

  if (append) {
    if (!hasMore || nextBeforeId === null) return;
    params.set("before_id", String(nextBeforeId));
  }

  const data = await api(`/api/history?${params}`);

  if (append) {
    const seen = new Set(historyRows.map((item) => item.id));

    historyRows.push(
      ...data.history.filter((item) => !seen.has(item.id))
    );
  } else {
    historyRows = data.history;
  }

  hasMore = data.has_more;
  nextBeforeId = data.next_before_id;

  renderHistory();
  updateControls();
}

async function refreshDashboard(
  preferredId = $("sessionSelect").value
) {
  const data = await api("/api/sessions");

  sessions = data.sessions;
  renderSessions(preferredId);

  await loadHistory();

  const sid = $("sessionSelect").value;

  if (!pendingRequest && sid) {
    const data = await api(
      `/api/sessions/${encodeURIComponent(sid)}/pending`
    );

    if (data.pending) {
      pendingRequest = data.pending;

      sessionStorage.setItem(
        PENDING_KEY,
        JSON.stringify(pendingRequest)
      );

      notice(
        "Phiên còn lượt dở. " +
        "Bấm Gửi lại lượt chưa xác nhận để tiếp tục."
      );
    }
  }

  updateControls();
}

function displayResult(result) {
  clearGates();

  const type = result.success ? "success" : "error";

  const text =
    `${result.code || "(trống)"}` +
    `${result.destination ? " · " + result.destination : ""}` +
    ` — ${result.reason}`;

  $("latestResult").textContent = text;
  $("latestResult").dataset.type = type;

  if (result.success && [1, 2, 3].includes(result.gate)) {
    const gate = document.querySelector(
      `.gate[data-gate="${result.gate}"]`
    );

    gate.classList.add("active");
    gate.querySelector(".gate-state").textContent =
      `Đã nhận ${result.code}`;
  }

  notice(text, type);
}

let lastMotionMs = null;
let finishMotion = null;

function resetMotion() {
  if (finishMotion) finishMotion();

  $("motionParcel").setAttribute("visibility", "hidden");

  document.querySelectorAll(".route-lines path").forEach((path) => {
    path.classList.remove("route-success", "route-error");
  });

  $("conveyor").dataset.state = "idle";
  $("motionState").textContent = "Sẵn sàng";
  $("motionInfo").textContent =
    "Chưa có kiện mới. Lịch sử chỉ ghi sau khi mô phỏng hoàn tất.";
}

function motionPoint(points, progress) {
  const lengths = points.slice(1).map((point, index) =>
    Math.hypot(
      point[0] - points[index][0],
      point[1] - points[index][1]
    )
  );

  let distance =
    Math.max(0, Math.min(1, progress)) *
    lengths.reduce((sum, length) => sum + length, 0);

  for (let index = 0; index < lengths.length; index += 1) {
    if (
      distance <= lengths[index] ||
      index === lengths.length - 1
    ) {
      const ratio = lengths[index]
        ? distance / lengths[index]
        : 1;

      return points[index].map((value, axis) =>
        value + (points[index + 1][axis] - value) * ratio
      );
    }

    distance -= lengths[index];
  }

  return points[points.length - 1];
}

async function animateResult(result) {
  resetMotion();

  const validGate =
    (result.status === "ready" || result.success === true) &&
    [1, 2, 3].includes(result.gate);

  const routes = {
    1: [[60, 160], [300, 160], [410, 65], [515, 65]],
    2: [[60, 160], [300, 160], [515, 160]],
    3: [[60, 160], [300, 160], [410, 255], [515, 255]],
    check: [[60, 160], [300, 160], [300, 310], [430, 310]],
  };

  const points = routes[validGate ? result.gate : "check"];
  const route = $(validGate ? `route${result.gate}` : "routeCheck");

  route.classList.add(
    validGate ? "route-success" : "route-error"
  );

  const parcel = $("motionParcel");

  $("motionCode").textContent =
    (result.code || "QR lỗi").slice(0, 8);

  parcel.setAttribute("visibility", "visible");
  parcel.setAttribute("transform", "translate(60 160)");

  $("conveyor").dataset.state =
    validGate ? "success" : "error";

  const preferred = Number($("motionSpeed").value);

  const reduced = window.matchMedia?.(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  const duration = reduced
    ? 0
    : [0, 900, 1800].includes(preferred)
      ? preferred
      : 1800;

  const destination = validGate
    ? `cửa ${result.gate}`
    : "vùng kiểm tra";

  $("motionState").textContent =
    duration ? "Đang minh họa" : "Hiện kết quả";

  $("motionInfo").textContent =
    `Đã xác định hướng đi. Đang chuyển đến ${destination}; ` +
    "chưa ghi hoàn tất.";

  const start = performance.now();

  if (duration) {
    await new Promise((resolve) => {
      let frame = null;
      let timer = null;
      let ended = false;

      const finish = () => {
        if (ended) return;

        ended = true;
        cancelAnimationFrame(frame);
        clearTimeout(timer);
        finishMotion = null;
        resolve();
      };

      const tick = (now) => {
        const progress = Math.min(1, (now - start) / duration);
        const [x, y] = motionPoint(points, progress);

        parcel.setAttribute(
          "transform",
          `translate(${x} ${y})`
        );

        if (progress >= 1) {
          finish();
        } else {
          frame = requestAnimationFrame(tick);
        }
      };

      finishMotion = finish;

      timer = setTimeout(finish, duration + 100);
      frame = requestAnimationFrame(tick);
    });
  }

  const [x, y] = points[points.length - 1];

  parcel.setAttribute("transform", `translate(${x} ${y})`);

  const elapsed = duration ? performance.now() - start : 0;

  $("motionState").textContent = validGate
    ? `Đến cửa ${result.gate}`
    : "Cần kiểm tra";

  $("motionInfo").textContent =
    `${result.code || "(mã trống)"} · ` +
    (
      validGate
        ? `Đã minh họa đến cửa ${result.gate}. `
        : `${result.reason} Đi vào vùng kiểm tra. `
    ) +
    (
      duration
        ? `Minh họa: ${elapsed.toFixed(1)} ms trên trang.`
        : reduced
          ? "Đã giảm chuyển động theo cài đặt máy."
          : "Đã tắt chuyển động."
    );

  return elapsed;
}

async function processParcel(code, source, fromBatch = false) {
  if (!pendingRequest) {
    const session = currentSession();

    if (!session || session.status !== "active") {
      throw new Error("Cần chọn một phiên đang mở.");
    }

    const payload = {
      session_id: session.id,
      request_id: crypto.randomUUID(),
      code,
      source,
    };

    if (fromBatch) {
      payload._batchId = batch.id;
      payload._batchIndex = batch.index;
    }

    try {
      sessionStorage.setItem(
        PENDING_KEY,
        JSON.stringify(payload)
      );
    } catch {
      throw new Error(
        "Không lưu được lượt chờ. " +
        "Cho phép trình duyệt lưu dữ liệu trang."
      );
    }

    pendingRequest = payload;
  }

  const waiting = pendingRequest;

  updateControls();
  clearGates();
  resetMotion();

  lastMotionMs = waiting._motionMs ?? null;

  $("latestResult").textContent = "Đang kiểm tra lượt xử lý…";
  $("latestResult").dataset.type = "info";
  $("motionState").textContent = "Chờ backend";

  let prepared;

  try {
    prepared = await api("/api/history/prepare", {
      method: "POST",
      body: JSON.stringify({
        session_id: waiting.session_id,
        request_id: waiting.request_id,
        code: waiting.code,
        source: waiting.source,
      }),
    });

  } catch (error) {
    if (!error.uncertain) clearPending();

    $("motionState").textContent = "Chưa hoàn tất";
    $("latestResult").textContent = error.message;
    $("latestResult").dataset.type = "error";

    throw error;
  }

  let result;

  if (prepared.phase === "completed") {
    result = prepared.result;

    $("motionState").textContent = "Đã xác nhận lượt đã lưu";

    $("motionInfo").textContent =
      `Lượt #${result.id} đã có trong lịch sử. ` +
      "Không tạo thêm lượt.";

  } else {
    try {
      if (!waiting._motionDone) {
        lastMotionMs = await animateResult(prepared.result);

        waiting._motionDone = true;
        waiting._motionMs = lastMotionMs;

        sessionStorage.setItem(
          PENDING_KEY,
          JSON.stringify(waiting)
        );
      }

      $("motionState").textContent = "Đang lưu hoàn tất";

      result = await api(
        `/api/history/${encodeURIComponent(waiting.request_id)}/complete`,
        { method: "POST" }
      );

    } catch (error) {
      $("motionState").textContent = "Chờ xác nhận hoàn tất";

      $("motionInfo").textContent =
        "Lượt được giữ lại. " +
        "Bấm Gửi lại lượt chưa xác nhận để tiếp tục.";

      $("latestResult").textContent = error.message;
      $("latestResult").dataset.type = "error";

      throw error;
    }
  }

  clearPending();
  $("parcelCode").value = "";

  if (result.source === "qr") {
    qrCode = null;

    $("qrInfo").textContent =
      "Đã hoàn tất lượt QR. Đọc ảnh lại để xử lý lượt khác.";
  }

  displayResult(result);

  $("motionState").textContent = result.success
    ? `Đã hoàn tất cửa ${result.gate}`
    : "Đã ghi nhận lượt lỗi";

  lastRefreshOk = true;

  try {
    await refreshDashboard(waiting.session_id);
  } catch {
    lastRefreshOk = false;

    notice(
      `${result.reason} Đã lưu nhưng chưa tải lại thống kê. ` +
      "Bấm Làm mới.",
      result.success ? "success" : "error"
    );
  }

  return result;
}

$("sessionForm").addEventListener("submit", (event) => {
  event.preventDefault();

  runTask(async () => {
    if (batchHasWork()) {
      throw new Error("Hoàn tất hoặc bỏ hàng đợi trước.");
    }

    if (pendingRequest) {
      throw new Error("Cần xác nhận lượt đang chờ trước.");
    }

    const name = $("sessionName").value.trim();

    if (!name) {
      throw new Error("Cậu nhập tên phiên trước nhé.");
    }

    let session;

    try {
      session = await api("/api/sessions", {
        method: "POST",
        body: JSON.stringify({ name }),
      });

    } catch (error) {
      if (error.uncertain) {
        error.message +=
          " Bấm Làm mới để xem phiên đã được tạo chưa " +
          "trước khi tạo lại.";
      }

      throw error;
    }

    $("sessionName").value = "";

    clearHistory();
    resetLatest();

    sessions.unshift({
      ...session,
      total: 0,
      successes: 0,
      unsuccessful: 0,
    });

    renderSessions(session.id);
    notice(`Đã tạo phiên ${session.name}.`, "success");

    try {
      await refreshDashboard(session.id);
    } catch {
      notice(
        "Đã tạo phiên. Bấm Làm mới để tải lại đầy đủ dữ liệu.",
        "error"
      );
    }
  });
});

$("sessionSelect").addEventListener("change", () => {
  saveSelected($("sessionSelect").value);
  clearHistory();
  resetLatest();

  runTask(async () => {
    await refreshDashboard($("sessionSelect").value);

    notice(
      pendingRequest
        ? "Phiên còn lượt dở. Bấm Gửi lại lượt chưa xác nhận."
        : "Đã cập nhật phiên đang chọn."
    );
  });
});

$("refreshButton").addEventListener("click", () => {
  runTask(async () => {
    await api("/api/health");

    await refreshDashboard(
      pendingRequest?.session_id || $("sessionSelect").value
    );

    notice(
      pendingRequest
        ? "Đã làm mới. Cần gửi lại lượt chưa xác nhận."
        : "Đã cập nhật dữ liệu."
    );
  });
});

$("moreButton").addEventListener("click", () => {
  runTask(async () => {
    await loadHistory(true);
    notice(`Đã tải ${historyRows.length} lượt lịch sử.`);
  });
});

$("closeButton").addEventListener("click", () => {
  const session = currentSession();

  if (
    !session ||
    session.status !== "active" ||
    session.pending ||
    batchHasWork() ||
    pendingRequest
  ) {
    return;
  }

  if (
    !window.confirm(
      `Đóng phiên ${session.name}? Lịch sử được giữ lại.`
    )
  ) {
    return;
  }

  runTask(async () => {
    await api(
      `/api/sessions/${encodeURIComponent(session.id)}/close`,
      { method: "POST" }
    );

    session.status = "closed";
    updateControls();

    notice("Đã đóng phiên.", "success");

    try {
      await refreshDashboard(session.id);
    } catch {
      notice(
        "Đã đóng phiên. Bấm Làm mới để tải lại dữ liệu.",
        "error"
      );
    }
  });
});

$("parcelForm").addEventListener("submit", (event) => {
  event.preventDefault();

  runTask(async () => {
    if (pendingRequest) {
      throw new Error("Bấm nút Gửi lại lượt chưa xác nhận.");
    }

    if (batchHasWork()) {
      throw new Error("Hoàn tất hoặc bỏ hàng đợi trước.");
    }

    const code = $("parcelCode").value.trim();

    if (!code) {
      throw new Error("Cậu nhập mã kiện trước nhé.");
    }

    await processParcel(code, "manual");
  });
});

$("retryButton").addEventListener("click", () => {
  runTask(async () => {
    if (!pendingRequest) return;

    const waiting = pendingRequest;

    const result = await processParcel(
      waiting.code,
      waiting.source
    );

    if (
      waiting._batchId === batch.id &&
      waiting._batchIndex === batch.index
    ) {
      finishBatchEntry(result);

      batch.status = batch.index === batch.entries.length
        ? "Hoàn tất"
        : "Tạm dừng";

      batch.message =
        "Đã xác nhận lượt chờ. " +
        "Có thể tiếp tục các ảnh còn lại.";

      renderBatch();

    } else if (waiting._batchId) {
      notice(
        "Đã xác nhận lượt cũ. " +
        "Hàng đợi ảnh không còn sau khi tải lại trang; " +
        "chọn các ảnh còn lại để chạy tiếp."
      );
    }
  });
});

$("qrFile").addEventListener("change", () => {
  qrCode = null;
  $("qrPreview").hidden = true;
  $("qrInfo").textContent = "Ảnh đã chọn chưa được đọc.";
  updateControls();
});

async function decodeImage(file, canvas) {
  if (typeof window.jsQR !== "function") {
    throw new Error("Chưa tải được thư viện jsQR.");
  }

  if (
    !file ||
    !["image/png", "image/jpeg"].includes(file.type)
  ) {
    throw new Error("Chỉ nhận ảnh PNG hoặc JPEG.");
  }

  if (file.size > 5 * 1024 * 1024) {
    throw new Error("Ảnh vượt 5 MB.");
  }

  const start = performance.now();
  let bitmap;

  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error("Không mở được file ảnh.");
  }

  try {
    if (bitmap.width * bitmap.height > 20000000) {
      throw new Error("Ảnh vượt 20 triệu điểm ảnh.");
    }

    const scale = Math.min(
      1,
      1600 / Math.max(bitmap.width, bitmap.height)
    );

    canvas.width = Math.max(
      1,
      Math.round(bitmap.width * scale)
    );

    canvas.height = Math.max(
      1,
      Math.round(bitmap.height * scale)
    );

    const ctx = canvas.getContext(
      "2d",
      { willReadFrequently: true }
    );

    if (!ctx) {
      throw new Error("Không tạo được khung đọc ảnh.");
    }

    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.drawImage(
      bitmap,
      0,
      0,
      canvas.width,
      canvas.height
    );

    const pixels = ctx.getImageData(
      0,
      0,
      canvas.width,
      canvas.height
    );

    const decoded = window.jsQR(
      pixels.data,
      pixels.width,
      pixels.height,
      { inversionAttempts: "attemptBoth" }
    );

    return {
      code: decoded ? decoded.data : "",
      found: Boolean(decoded),
      readMs: performance.now() - start,
    };

  } finally {
    bitmap.close();
  }
}

$("qrForm").addEventListener("submit", (event) => {
  event.preventDefault();

  runTask(async () => {
    if (batchHasWork()) {
      throw new Error("Hoàn tất hoặc bỏ hàng đợi trước.");
    }

    qrCode = null;
    $("qrPreview").hidden = true;
    $("qrInfo").textContent = "Đang đọc ảnh…";

    const decoded = await decodeImage(
      $("qrFile").files[0],
      $("qrPreview")
    );

    qrCode = decoded.code;
    $("qrPreview").hidden = false;

    $("qrInfo").textContent = decoded.found
      ? `Nội dung QR: ${qrCode || "(rỗng)"} · ` +
        `Đọc ảnh: ${decoded.readMs.toFixed(1)} ms.`
      : "Không đọc được QR · " +
        `Đọc ảnh: ${decoded.readMs.toFixed(1)} ms.`;

    notice(
      decoded.found
        ? "Đã đọc ảnh. Bấm Xử lý mã QR để ghi lượt."
        : "Không đọc được QR. Có thể ghi nhận lượt lỗi " +
          "hoặc chọn ảnh khác."
    );
  });
});

$("processQrButton").addEventListener("click", () => {
  runTask(async () => {
    if (pendingRequest) {
      throw new Error("Cần xác nhận lượt đang chờ trước.");
    }

    if (batchHasWork()) {
      throw new Error("Hoàn tất hoặc bỏ hàng đợi trước.");
    }

    if (qrCode === null) {
      throw new Error("Cần đọc ảnh trước khi xử lý.");
    }

    await processParcel(qrCode, "qr");
  });
});

function renderBatch() {
  const confirmed = batch.entries.filter(
    (entry) => entry.result
  ).length;

  const fileErrors = batch.entries.filter(
    (entry) => entry.phase === "Lỗi tệp"
  ).length;

  $("batchProgress").max = Math.max(
    1,
    batch.entries.length
  );

  $("batchProgress").value = batch.index;

  $("batchInfo").textContent =
    `${batch.status} · ` +
    `Đã kết thúc ${batch.index}/${batch.entries.length} ảnh` +
    ` · Đã ghi ${confirmed} lượt` +
    ` · Lỗi tệp ${fileErrors}` +
    (batch.sessionName ? ` · Phiên: ${batch.sessionName}` : "") +
    (batch.message ? ` · ${batch.message}` : "");

  const body = $("batchBody");
  body.replaceChildren();

  batch.entries.forEach((entry, index) => {
    const row = document.createElement("tr");

    addCell(row, index + 1);
    addCell(row, entry.file.name);

    addCell(
      row,
      entry.code === null ? "—" : entry.code || "(trống)"
    );

    addCell(
      row,
      entry.result
        ? statusNames[entry.result.status] || entry.result.status
        : entry.phase,
      entry.result
        ? entry.result.success
          ? "text-success"
          : "text-error"
        : ""
    );

    addCell(row, entry.result?.gate);

    addCell(
      row,
      entry.readMs === null ? "—" : entry.readMs.toFixed(1)
    );

    addCell(
      row,
      entry.result
        ? Number(entry.result.decision_ms).toFixed(3)
        : "—"
    );

    addCell(
      row,
      entry.motionMs === null ? "—" : entry.motionMs.toFixed(1)
    );

    addCell(
      row,
      entry.result?.reason || entry.error || "—",
      "reason"
    );

    body.append(row);
  });
}

function finishBatchEntry(result) {
  const entry = batch.entries[batch.index];

  entry.result = result;
  entry.motionMs = lastMotionMs;
  entry.phase = "Đã xác nhận";
  entry.error = "";

  batch.index += 1;
  renderBatch();
}

async function runBatch() {
  if (pendingRequest) {
    throw new Error(
      "Gửi lại lượt chưa xác nhận trước khi tiếp tục lô."
    );
  }

  if (typeof window.jsQR !== "function") {
    throw new Error("Chưa tải được thư viện jsQR.");
  }

  if (
    !batch.entries.length ||
    batch.index >= batch.entries.length
  ) {
    return;
  }

  if (
    batch.sessionId &&
    batch.sessionId !== $("sessionSelect").value
  ) {
    throw new Error("Cần chọn lại đúng phiên của lô.");
  }

  await refreshDashboard(
    batch.sessionId || $("sessionSelect").value
  );

  if (pendingRequest) {
    throw new Error(
      "Cần xác nhận lượt dở trước khi chạy lô."
    );
  }

  const session = currentSession();

  if (!session || session.status !== "active") {
    throw new Error("Cần một phiên đang mở.");
  }

  if (!batch.sessionId) {
    batch.sessionId = session.id;
    batch.sessionName = session.name;
  }

  batch.running = true;
  batch.pauseRequested = false;
  batch.status = "Đang chạy";
  batch.message = "";
  qrCode = null;

  updateControls();
  renderBatch();

  try {
    while (
      batch.index < batch.entries.length &&
      !batch.pauseRequested
    ) {
      const entry = batch.entries[batch.index];

      if (entry.code === null) {
        entry.phase = "Đang đọc";
        renderBatch();

        try {
          const decoded = await decodeImage(
            entry.file,
            $("qrPreview")
          );

          entry.code = decoded.code;
          entry.readMs = decoded.readMs;
          entry.phase = "Đã đọc";

          $("qrPreview").hidden = false;

          $("qrInfo").textContent =
            `Ảnh trong lô: ${entry.file.name} · ` +
            "Nội dung: " +
            (entry.code || "(không đọc được)");

        } catch (error) {
          entry.phase = "Lỗi tệp";
          entry.error = error.message;
          batch.index += 1;

          renderBatch();

          await new Promise((resolve) =>
            setTimeout(resolve, Number($("batchDelay").value))
          );

          continue;
        }
      }

      if (batch.pauseRequested) break;

      entry.phase = "Đang gửi";
      renderBatch();

      try {
        const result = await processParcel(
          entry.code,
          "qr",
          true
        );

        finishBatchEntry(result);

        if (!lastRefreshOk) {
          batch.pauseRequested = true;
          batch.message =
            "Lượt đã lưu nhưng chưa tải lại thống kê. " +
            "Làm mới trước khi tiếp tục.";
        }

      } catch (error) {
        entry.phase = pendingRequest
          ? "Chờ xác nhận"
          : "Bị từ chối";

        entry.error = error.message;
        batch.status = "Tạm dừng";
        batch.message = error.message;

        renderBatch();
        throw error;
      }

      await new Promise((resolve) =>
        setTimeout(resolve, Number($("batchDelay").value))
      );
    }

    batch.status = batch.index === batch.entries.length
      ? "Hoàn tất"
      : "Tạm dừng";

    if (!batch.message) {
      batch.message = batch.status === "Hoàn tất"
        ? "Xem kết quả từng ảnh ở bảng bên dưới."
        : "Bấm Tiếp tục lô để chạy các ảnh còn lại.";
    }

    notice(batch.message);

  } finally {
    batch.running = false;
    renderBatch();
    updateControls();
  }
}

$("batchFiles").addEventListener("change", () => {
  // Tên chỉ dùng sắp thứ tự. Mã luôn đọc từ nội dung ảnh.
  const files = Array.from($("batchFiles").files).sort(
    (a, b) => a.name.localeCompare(
      b.name,
      "en",
      { numeric: true }
    )
  );

  if (
    files.length > 30 ||
    files.some((file) =>
      !["image/png", "image/jpeg"].includes(file.type) ||
      file.size > 5 * 1024 * 1024
    )
  ) {
    $("batchFiles").value = "";
    batch = newBatch([]);

    notice(
      "Chọn tối đa 30 ảnh PNG/JPEG, mỗi ảnh không quá 5 MB.",
      "error"
    );

  } else {
    batch = newBatch(files);

    notice(
      `Đã xếp ${files.length} ảnh. ` +
      "Tên file chỉ dùng sắp thứ tự; mã được đọc từ ảnh."
    );
  }

  renderBatch();
  updateControls();
});

$("batchStart").addEventListener("click", () => {
  runTask(runBatch);
});

$("batchPause").addEventListener("click", () => {
  if (!batch.running) return;

  batch.pauseRequested = true;

  batch.message =
    "Sẽ dừng sau thao tác đang thực hiện; " +
    "không hủy yêu cầu đang gửi.";

  renderBatch();
  updateControls();
});

$("batchClear").addEventListener("click", () => {
  if (busy || pendingRequest) return;

  batch = newBatch([]);
  $("batchFiles").value = "";

  renderBatch();
  updateControls();

  notice(
    "Đã bỏ hàng đợi. Lịch sử đã lưu được giữ nguyên."
  );
});

const motionNote = $("motionInfo")
  .closest(".card")
  ?.querySelector("p.muted.small");

if (motionNote) {
  motionNote.textContent =
    "Cửa tô xanh thể hiện lượt đã hoàn tất. " +
    "Lịch sử được ghi sau khi trình duyệt hoàn tất mô phỏng; " +
    "đây là xác nhận phần mềm, không phải tín hiệu thiết bị thật. " +
    "Thời gian quyết định không gồm hoạt ảnh.";
}

resetMotion();
renderBatch();

pendingRequest = restorePending();

if (pendingRequest) {
  renderSessions(pendingRequest.session_id);
}

runTask(async () => {
  await api("/api/health");

  await refreshDashboard(
    pendingRequest?.session_id ||
    readStored(SELECTED_KEY) ||
    ""
  );

  notice(
    pendingRequest
      ? "Có lượt chưa xác nhận. Bấm Gửi lại lượt chưa xác nhận."
      : "Đã kết nối. Tạo hoặc chọn phiên " +
        "rồi nhập mã hoặc chọn ảnh QR."
  );
});

/* QR_METRICS_V1: bổ sung đo thời gian và lưu số đo QR. */
(() => {
  "use strict";

  if (globalThis.__smartLogisticsMetricsV1) return;
  globalThis.__smartLogisticsMetricsV1 = true;

  let lastDecode = null;
  let activeMetric = null;
  let runToken = 0;

  const oldDecode = decodeImage;
  const oldProcess = processParcel;
  const oldApi = api;
  const oldRunBatch = runBatch;
  const oldRenderBatch = renderBatch;
  const oldUpdateControls = updateControls;
  const oldResetLatest = resetLatest;

  const note = document.createElement("p");
  note.id = "qrMeasurementInfo";
  note.className = "note";
  note.setAttribute("aria-live", "polite");
  note.textContent = "Chưa có số đo QR mới được xác nhận.";

  $("latestResult").insertAdjacentElement("afterend", note);

  function invalidate(sample, reason) {
    if (!sample || sample._finished) return;

    sample.valid = false;

    const reasons = (sample.invalid_reason || "")
      .split("; ")
      .filter(Boolean);

    if (!reasons.includes(reason)) {
      reasons.push(reason);
    }

    sample.invalid_reason = reasons.join("; ").slice(0, 500);
  }

  function persist(sample) {
    if (!pendingRequest || pendingRequest.source !== "qr") {
      return;
    }

    pendingRequest._qrMeasurement = sample;

    try {
      sessionStorage.setItem(
        PENDING_KEY,
        JSON.stringify(pendingRequest)
      );
    } catch {
      invalidate(sample, "measurement_storage_failed");
    }
  }

  function isNumber(value) {
    return (
      typeof value === "number" &&
      Number.isFinite(value) &&
      value >= 0
    );
  }

  async function imageHash(file) {
    try {
      const hash = await crypto.subtle.digest(
        "SHA-256",
        await file.arrayBuffer()
      );

      return Array.from(
        new Uint8Array(hash),
        value => value.toString(16).padStart(2, "0")
      ).join("");
    } catch {
      return null;
    }
  }

  function bodyFor(sample) {
    const fields = [
      "read_ms",
      "prepare_ms",
      "pipeline_ms",
      "animation_ms",
    ];

    if (
      sample.valid &&
      fields.some(key => !isNumber(sample[key]))
    ) {
      invalidate(sample, "incomplete_timing");
    }

    if (
      sample.valid &&
      sample.pipeline_ms <
        Math.max(sample.read_ms, sample.prepare_ms)
    ) {
      invalidate(sample, "inconsistent_timing");
    }

    const result = {
      measurement_version: 1,
      mode: sample.mode,
      image_name: sample.image_name,
      image_sha256: sample.image_sha256 || null,
      valid: sample.valid === true,
      invalid_reason: sample.valid
        ? null
        : sample.invalid_reason || "missing_timing",
    };

    fields.forEach(key => {
      result[key] = isNumber(sample[key])
        ? sample[key]
        : null;
    });

    return result;
  }

  decodeImage = async function (file, canvas) {
    if (!file) return oldDecode(file, canvas);

    // Nhận diện tệp trước khoảng thời gian cần đo.
    const hash = await imageHash(file);

    const sample = {
      mode: batch.running ? "batch" : "single",
      image_name: file.name,
      image_sha256: hash,
      read_ms: null,
      prepare_ms: null,
      pipeline_ms: null,
      animation_ms: null,
      valid: true,
      invalid_reason: null,
      _start: performance.now(),
      _origin: performance.timeOrigin,
      _measured: false,
      _finished: false,
    };

    activeMetric = sample;

    if (document.visibilityState !== "visible") {
      invalidate(sample, "page_hidden");
    }

    try {
      const decoded = await oldDecode(file, canvas);

      sample.read_ms = decoded.readMs;

      lastDecode = {
        file,
        code: decoded.code,
        runToken,
        sample,
        used: false,
      };

      return decoded;

    } catch (error) {
      invalidate(sample, "image_decode_failed");
      lastDecode = null;
      activeMetric = null;
      throw error;
    }
  };

  runBatch = async function (...args) {
    runToken += 1;
    return oldRunBatch(...args);
  };

  api = async function (url, options = {}) {
    const preparing = url === "/api/history/prepare";

    const completing =
      /^\/api\/history\/[^/]+\/complete$/.test(url);

    let sample = pendingRequest?.source === "qr"
      ? activeMetric ||
        pendingRequest._qrMeasurement ||
        null
      : null;

    if (
      sample &&
      sample._origin !== performance.timeOrigin
    ) {
      invalidate(sample, "page_reloaded");
      sample.prepare_ms = null;
      sample.pipeline_ms = null;
    }

    if (
      sample &&
      document.visibilityState !== "visible"
    ) {
      invalidate(sample, "page_hidden");
    }

    if (preparing && sample) {
      persist(sample);
    }

    if (completing && sample) {
      sample.animation_ms = isNumber(
        pendingRequest?._motionMs
      )
        ? pendingRequest._motionMs
        : null;

      options = {
        ...options,
        body: JSON.stringify({
          measurement: bodyFor(sample),
        }),
      };

      persist(sample);
    }

    const start = performance.now();

    try {
      const response = await oldApi(url, options);

      if (
        preparing &&
        sample &&
        response.phase === "pending" &&
        !sample._measured
      ) {
        if (
          sample._origin === performance.timeOrigin &&
          isNumber(sample._start)
        ) {
          const end = performance.now();

          sample.prepare_ms = end - start;
          sample.pipeline_ms = end - sample._start;
          sample._measured = true;

        } else {
          invalidate(sample, "missing_clock_context");
        }

        persist(sample);
      }

      if (completing && sample) {
        sample._finished = true;
      }

      return response;

    } catch (error) {
      if ((preparing || completing) && sample) {
        invalidate(sample, "request_interrupted");
        persist(sample);
      }

      throw error;
    }
  };

  processParcel = async function (
    code,
    source,
    fromBatch = false
  ) {
    let sample = null;
    let entry = null;

    if (pendingRequest) {
      if (
        pendingRequest._batchId === batch.id &&
        pendingRequest._batchIndex === batch.index
      ) {
        entry = batch.entries[batch.index];
      }

      sample = pendingRequest.source === "qr"
        ? pendingRequest._qrMeasurement || null
        : null;

    } else if (source === "qr") {
      entry = fromBatch
        ? batch.entries[batch.index]
        : null;

      const file = fromBatch
        ? entry?.file
        : $("qrFile").files[0];

      const reusable =
        fromBatch &&
        lastDecode &&
        !lastDecode.used &&
        lastDecode.file === file &&
        lastDecode.code === code &&
        lastDecode.runToken === runToken;

      if (!reusable) {
        // Ảnh đơn: đọc lại ngay khi bấm xử lý.
        // Lô tiếp tục: đọc lại nếu số đo thuộc lần chạy trước.
        const decoded = await decodeImage(
          file,
          $("qrPreview")
        );

        if (decoded.code !== code) {
          throw new Error(
            "Nội dung ảnh đã thay đổi. " +
            "Đọc lại ảnh trước khi xử lý."
          );
        }

        if (entry) {
          entry.readMs = decoded.readMs;
        }
      }

      sample = lastDecode?.sample || null;

      if (lastDecode) {
        lastDecode.used = true;
      }
    }

    activeMetric = sample;

    if (sample) {
      sample.mode = (
        fromBatch || pendingRequest?._batchId
      )
        ? "batch"
        : sample.mode;

      note.textContent =
        "Đang đo QR → tra cứu → xác định cửa…";

    } else {
      note.textContent =
        "Lượt này chưa có dữ liệu đo QR từ ảnh.";
    }

    try {
      const result = await oldProcess(
        code,
        source,
        fromBatch
      );

      if (result.source === "qr") {
        try {
          const data = await api(
            `/api/history/${
              encodeURIComponent(result.request_id)
            }/measurement`
          );

          const saved = data.measurement;

          if (entry) {
            entry._savedMeasurement = saved;
          }

          if (!saved) {
            note.textContent =
              "Đã lưu lượt xử lý. " +
              "Lượt này không có số đo QR trong database.";

          } else if (!saved.valid) {
            note.textContent =
              `Đã lưu số đo bị gián đoạn: ${
                saved.invalid_reason
              }. Không dùng để so sánh tốc độ.`;

          } else {
            note.textContent =
              "Đã lưu số đo QR · " +
              `Đọc ảnh: ${saved.read_ms.toFixed(1)} ms · ` +
              "Gửi/nhận chuẩn bị: " +
              `${saved.prepare_ms.toFixed(1)} ms · ` +
              "QR → cửa: " +
              `${saved.pipeline_ms.toFixed(1)} ms · ` +
              "Hoạt ảnh riêng: " +
              `${saved.animation_ms.toFixed(1)} ms.`;
          }

        } catch {
          note.textContent =
            "Đã lưu kết quả xử lý, " +
            "nhưng chưa tải lại được số đo. " +
            "Không suy ra số đo từ thông báo thành công.";
        }
      }

      return result;

    } finally {
      activeMetric = null;
    }
  };

  renderBatch = function (...args) {
    oldRenderBatch(...args);

    const table = $("batchBody").closest("table");
    const header = table?.querySelector("thead tr");

    if (
      header &&
      !header.querySelector(".qr-metric-heading")
    ) {
      [
        "QR → cửa (ms)",
        "Số đo trong database",
      ].forEach(title => {
        const cell = document.createElement("th");

        cell.className = "qr-metric-heading";
        cell.textContent = title;
        header.append(cell);
      });
    }

    Array.from(
      $("batchBody").children
    ).forEach((row, index) => {
      const saved =
        batch.entries[index]?._savedMeasurement;

      addCell(
        row,
        saved?.valid
          ? saved.pipeline_ms.toFixed(1)
          : "—"
      );

      addCell(
        row,
        saved
          ? saved.valid
            ? "Hợp lệ"
            : "Bị gián đoạn"
          : "Chưa xác minh"
      );
    });
  };

  updateControls = function (...args) {
    oldUpdateControls(...args);

    if (qrCode !== null && qrCode !== "") {
      $("processQrButton").textContent =
        "Đọc lại và xử lý QR";
    }
  };

  resetLatest = function (...args) {
    oldResetLatest(...args);

    note.textContent =
      "Chưa có số đo QR mới được xác nhận.";
  };

  document.addEventListener(
    "visibilitychange",
    () => {
      if (
        document.visibilityState === "hidden" &&
        activeMetric
      ) {
        invalidate(activeMetric, "page_hidden");
        persist(activeMetric);
      }
    }
  );

  renderBatch();
  updateControls();
})();