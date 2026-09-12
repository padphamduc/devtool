(function () {
  if (window.__ducToolGroupScannerLoaded) return;
  window.__ducToolGroupScannerLoaded = true;

  const STOP_AFTER_STABLE_ROUNDS = 7;
  const MAX_ROUNDS = 180;
  const WAIT_MS = 900;
  let scanning = false;

  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function cleanText(value) {
    return (value || "").replace(/\s+/g, " ").trim();
  }

  function parseGroupUrl(rawUrl) {
    try {
      const url = new URL(rawUrl, location.origin);
      const match = url.pathname.match(/^\/groups\/([^/?#]+)/i);
      if (!match) return null;
      const key = decodeURIComponent(match[1]);
      const blocked = new Set(["feed", "discover", "joins", "create", "notifications", "requests", "manage", "your_groups"]);
      if (!key || blocked.has(key.toLowerCase())) return null;
      return {
        key: key.toLowerCase(),
        id: /^\d+$/.test(key) ? key : "",
        url: `${url.origin}/groups/${encodeURIComponent(key)}/`
      };
    } catch (_) {
      return null;
    }
  }

  function bestContainer(anchor) {
    let node = anchor;
    for (let i = 0; node && i < 7; i += 1, node = node.parentElement) {
      if (node.matches?.('[role="listitem"]')) return node;
      const text = cleanText(node.innerText);
      const images = node.querySelectorAll?.("img").length || 0;
      if (text && text.length < 350 && images > 0) return node;
    }
    return anchor.parentElement || anchor;
  }

  function readName(anchor, container, parsed) {
    const options = [
      anchor.getAttribute("aria-label"),
      anchor.innerText,
      anchor.textContent,
      container.querySelector?.("a[aria-label]")?.getAttribute("aria-label")
    ].map(cleanText).filter(Boolean);
    return options.find((x) => x.length >= 2 && x.length <= 160) || parsed.key;
  }

  function readImage(container, name) {
    const images = [...(container.querySelectorAll?.("img") || [])];
    const named = images.find((img) => cleanText(img.alt).toLowerCase().includes(name.toLowerCase()));
    const image = named || images.find((img) => (img.naturalWidth || img.width) >= 32);
    return image?.currentSrc || image?.src || "";
  }

  function collectVisibleGroups() {
    const map = new Map();
    const anchors = document.querySelectorAll('a[href*="/groups/"]');
    for (const anchor of anchors) {
      const parsed = parseGroupUrl(anchor.href);
      if (!parsed) continue;
      const container = bestContainer(anchor);
      const name = readName(anchor, container, parsed);
      if (!name || name.toLowerCase() === "groups") continue;
      const candidate = { name, id: parsed.id, url: parsed.url, image: readImage(container, name) };
      const old = map.get(parsed.key);
      if (!old || (candidate.image && !old.image) || candidate.name.length > old.name.length) map.set(parsed.key, candidate);
    }
    return [...map.values()];
  }

  async function saveAndReport(groups, status, sendResponse) {
    const old = await chrome.storage.local.get({ groups: [] });
    const merged = new Map(old.groups.map((g) => [g.url, g]));
    groups.forEach((g) => merged.set(g.url, { ...merged.get(g.url), ...g, selected: merged.get(g.url)?.selected ?? true }));
    const result = [...merged.values()].sort((a, b) => a.name.localeCompare(b.name, "vi"));
    await chrome.storage.local.set({ groups: result, scanStatus: status });
    chrome.runtime.sendMessage({ type: "DUC_SCAN_PROGRESS", count: result.length, status }).catch(() => {});
    if (sendResponse) sendResponse({ ok: true, count: result.length });
  }

  async function scanAll(sendResponse) {
    if (scanning) return sendResponse({ ok: false, error: "Đang có một lượt quét chạy." });
    scanning = true;
    try {
      let stable = 0;
      let previousCount = 0;
      let all = new Map();
      window.scrollTo({ top: 0, behavior: "instant" });
      await wait(500);

      for (let round = 0; round < MAX_ROUNDS && stable < STOP_AFTER_STABLE_ROUNDS; round += 1) {
        for (const group of collectVisibleGroups()) all.set(group.url, { ...all.get(group.url), ...group });
        stable = all.size === previousCount ? stable + 1 : 0;
        previousCount = all.size;
        await saveAndReport([...all.values()], `Đang quét: ${all.size} nhóm…`);
        window.scrollTo({ top: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight), behavior: "smooth" });
        await wait(WAIT_MS);
      }

      await saveAndReport([...all.values()], `Hoàn tất: tìm thấy ${all.size} nhóm.`, sendResponse);
    } catch (error) {
      sendResponse({ ok: false, error: error.message || String(error) });
    } finally {
      scanning = false;
    }
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "DUC_SCAN_GROUPS") return false;
    scanAll(sendResponse);
    return true;
  });
})();
