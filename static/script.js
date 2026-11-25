const dz = document.getElementById("dropzone");
const picker = document.getElementById("picker");

if (dz && picker) {
  ["dragenter", "dragover"].forEach(type => dz.addEventListener(type, event => {
    event.preventDefault();
    dz.classList.add("drag");
  }));
  ["dragleave", "drop"].forEach(type => dz.addEventListener(type, event => {
    event.preventDefault();
    dz.classList.remove("drag");
  }));
  dz.addEventListener("drop", event => upload(event.dataTransfer.files));
  picker.addEventListener("change", () => upload(picker.files));
}

function formatSize(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let index = 0;
  while (bytes >= 1024 && index < units.length - 1) {
    bytes /= 1024;
    index++;
  }
  return `${bytes.toFixed(index ? 1 : 0)} ${units[index]}`;
}

function upload(files) {
  if (!files || !files.length) return;
  const form = new FormData();
  [...files].forEach(file => form.append("files", file));
  const progress = document.getElementById("prog");
  const bar = document.getElementById("bar");
  const text = document.getElementById("pt");
  progress.classList.remove("hidden");

  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/room/${encodeURIComponent(ROOM)}/upload`);
  xhr.upload.onprogress = event => {
    if (!event.lengthComputable) return;
    const percent = Math.round(event.loaded / event.total * 100);
    bar.style.width = `${percent}%`;
    text.textContent = `Uploading ${percent}%`;
  };
  xhr.onload = () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      text.textContent = "Upload complete ✓";
      loadFiles();
    } else {
      text.textContent = xhr.status === 403 ? "Access denied. Re-enter the room password." : "Upload failed. Please try again.";
    }
    setTimeout(() => progress.classList.add("hidden"), 2200);
    picker.value = "";
  };
  xhr.onerror = () => { text.textContent = "Network error. Please try again."; };
  xhr.send(form);
}

async function loadFiles() {
  const box = document.getElementById("files");
  try {
    const response = await fetch(`/api/room/${encodeURIComponent(ROOM)}/files`);
    if (!response.ok) throw new Error("Could not load files");
    const files = await response.json();
    box.innerHTML = files.length ? files.map(file => `
      <div class="file">
        <span aria-hidden="true">📄</span>
        <span class="name" title="${escapeHTML(file.original_name)}">${escapeHTML(file.original_name)}</span>
        <span class="size">${formatSize(file.size)}</span>
        <a class="download" href="/download/${file.id}" aria-label="Download ${escapeHTML(file.original_name)}">↓</a>
        <button class="del" type="button" onclick="deleteFile(${file.id})" aria-label="Delete ${escapeHTML(file.original_name)}">×</button>
      </div>`).join("") : '<p class="empty">No files yet. Upload the first file to get started.</p>';
  } catch (error) {
    box.innerHTML = '<p class="empty">Unable to load files. Refresh the page and try again.</p>';
  }
}

async function deleteFile(id) {
  if (!confirm("Delete this file?")) return;
  const response = await fetch(`/api/file/${id}`, { method: "DELETE" });
  if (response.ok) loadFiles();
  else alert("Could not delete this file. Please refresh and try again.");
}

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

async function copyText(elementId, button, isText = false) {
  const element = document.getElementById(elementId);
  const value = isText ? element.textContent.trim() : element.value;
  try {
    await navigator.clipboard.writeText(value);
    const oldText = button.textContent;
    button.textContent = "Copied ✓";
    setTimeout(() => button.textContent = oldText, 1400);
  } catch {
    const feedback = document.getElementById("share-feedback");
    feedback.textContent = "Copy was blocked by your browser. Select and copy the text manually.";
  }
}

async function shareRoom() {
  const payload = { title: "QuickDrop room", text: `Join my QuickDrop room. Room ID: ${ROOM}`, url: SHARE_URL };
  if (navigator.share) {
    try { await navigator.share(payload); }
    catch (error) { if (error.name !== "AbortError") document.getElementById("share-feedback").textContent = "Sharing was unavailable. You can copy the link or Room ID instead."; }
  } else {
    await navigator.clipboard.writeText(SHARE_URL);
    document.getElementById("share-feedback").textContent = "Your room link has been copied.";
  }
}

if (typeof ROOM !== "undefined") loadFiles();
