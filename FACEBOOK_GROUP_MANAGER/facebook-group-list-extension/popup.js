const $ = (selector) => document.querySelector(selector);
let groups = [];

function escapeHtml(value) {
  return String(value || "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function filteredGroups() {
  const q = $("#search").value.trim().toLowerCase();
  return groups.filter((g) => !q || `${g.name} ${g.id} ${g.url}`.toLowerCase().includes(q));
}

function render() {
  const visible = filteredGroups();
  $("#counter").textContent = `${groups.length} nhóm`;
  $("#selectAll").checked = visible.length > 0 && visible.every((g) => g.selected);
  $("#selectAll").indeterminate = visible.some((g) => g.selected) && !visible.every((g) => g.selected);
  $("#list").innerHTML = visible.length ? visible.map((g) => `
    <article class="group">
      <input class="pick" type="checkbox" data-url="${escapeHtml(g.url)}" ${g.selected ? "checked" : ""}>
      ${g.image ? `<img src="${escapeHtml(g.image)}" alt="">` : `<div></div>`}
      <div>
        <a class="name" href="${escapeHtml(g.url)}" target="_blank" title="${escapeHtml(g.name)}">${escapeHtml(g.name)}</a>
        <div class="meta">ID: ${escapeHtml(g.id || "Không hiển thị trong URL")}</div>
      </div>
    </article>`).join("") : `<div class="empty">Chưa có nhóm nào trong danh sách.</div>`;
}

async function load() {
  const data = await chrome.storage.local.get({ groups: [], scanStatus: "", apiConfig: {} });
  groups = data.groups;
  $("#apiUrl").value = data.apiConfig.url || "";
  $("#apiKey").value = data.apiConfig.key || "";
  $("#deviceName").value = data.apiConfig.deviceName || "PC-DUC";
  if (data.scanStatus) $("#status").textContent = data.scanStatus;
  render();
}

function apiConfigFromForm() {
  return {
    url: $("#apiUrl").value.trim(),
    key: $("#apiKey").value.trim(),
    deviceName: $("#deviceName").value.trim() || "PC-DUC"
  };
}

async function saveApiConfig() {
  const config = apiConfigFromForm();
  if (!/^https?:\/\//i.test(config.url)) throw new Error("URL API phải bắt đầu bằng http:// hoặc https://");
  const origin = new URL(config.url).origin + "/*";
  const granted = await chrome.permissions.request({ origins: [origin] });
  if (!granted) throw new Error("Bạn chưa cấp quyền kết nối tới tên miền web.");
  await chrome.storage.local.set({ apiConfig: config });
  return config;
}

async function persist() {
  await chrome.storage.local.set({ groups });
  render();
}

function selectedGroups() {
  return groups.filter((g) => g.selected);
}

function csvCell(value) {
  return `"${String(value || "").replace(/"/g, '""')}"`;
}

$("#openPage").addEventListener("click", () => chrome.tabs.create({ url: "https://www.facebook.com/groups/joins/" }));
$("#search").addEventListener("input", render);
$("#list").addEventListener("change", async (event) => {
  if (!event.target.matches(".pick")) return;
  const group = groups.find((g) => g.url === event.target.dataset.url);
  if (group) group.selected = event.target.checked;
  await persist();
});
$("#selectAll").addEventListener("change", async (event) => {
  const urls = new Set(filteredGroups().map((g) => g.url));
  groups.forEach((g) => { if (urls.has(g.url)) g.selected = event.target.checked; });
  await persist();
});
$("#clear").addEventListener("click", async () => {
  groups = [];
  await chrome.storage.local.set({ groups: [], scanStatus: "Đã xóa danh sách." });
  $("#status").textContent = "Đã xóa danh sách.";
  render();
});

$("#scan").addEventListener("click", async () => {
  const button = $("#scan");
  const status = $("#status");
  button.disabled = true;
  status.classList.remove("error");
  status.textContent = "Đang kết nối với trang Facebook…";
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.url || !/^https:\/\/(www|web)\.facebook\.com\//.test(tab.url)) throw new Error("Hãy mở Facebook ở tab hiện tại trước.");
    let response;
    try {
      response = await chrome.tabs.sendMessage(tab.id, { type: "DUC_SCAN_GROUPS" });
    } catch (_) {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
      response = await chrome.tabs.sendMessage(tab.id, { type: "DUC_SCAN_GROUPS" });
    }
    if (!response?.ok) throw new Error(response?.error || "Không thể quét trang.");
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
  } finally {
    button.disabled = false;
    await load();
  }
});

$("#copy").addEventListener("click", async () => {
  const picked = selectedGroups();
  if (!picked.length) return $("#status").textContent = "Bạn chưa tích chọn nhóm nào.";
  const text = picked.map((g) => `${g.name}\t${g.id || ""}\t${g.url}\t${g.image || ""}`).join("\n");
  await navigator.clipboard.writeText(text);
  $("#status").textContent = `Đã sao chép ${picked.length} nhóm.`;
});

$("#csv").addEventListener("click", async () => {
  const picked = selectedGroups();
  if (!picked.length) return $("#status").textContent = "Bạn chưa tích chọn nhóm nào.";
  const rows = [["Tên nhóm", "ID nhóm", "Link nhóm", "Link ảnh"], ...picked.map((g) => [g.name, g.id, g.url, g.image])];
  const csv = "\ufeff" + rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  await chrome.downloads.download({ url, filename: `duc-tool-facebook-groups-${new Date().toISOString().slice(0, 10)}.csv`, saveAs: true });
  setTimeout(() => URL.revokeObjectURL(url), 10000);
});

$("#saveApi").addEventListener("click", async () => {
  try {
    await saveApiConfig();
    $("#status").textContent = "Đã lưu kết nối web.";
  } catch (error) {
    $("#status").textContent = error.message;
    $("#status").classList.add("error");
  }
});

$("#sync").addEventListener("click", async () => {
  const button = $("#sync");
  try {
    button.disabled = true;
    $("#status").classList.remove("error");
    const config = await saveApiConfig();
    const picked = selectedGroups();
    if (!picked.length) throw new Error("Bạn chưa tích chọn nhóm nào.");
    const response = await fetch(config.url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": config.key },
      body: JSON.stringify({ device_name: config.deviceName, groups: picked.map(({ selected, ...g }) => g) })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) throw new Error(result.error || `Máy chủ trả về HTTP ${response.status}`);
    $("#status").textContent = `Đã gửi ${result.received} nhóm lên web.`;
  } catch (error) {
    $("#status").textContent = error.message;
    $("#status").classList.add("error");
  } finally {
    button.disabled = false;
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type !== "DUC_SCAN_PROGRESS") return;
  $("#status").textContent = message.status;
  load();
});

load();
