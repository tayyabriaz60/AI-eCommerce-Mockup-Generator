// AI eCommerce Mockup Generator — frontend logic (vanilla JS, no build step)

const API_BASE = ""; // same-origin: backend serves this frontend directly
const HISTORY_PAGE_SIZE = 12;

const PLATFORMS = ["Etsy", "Shopify", "Amazon", "TikTok Shop", "Custom"];
const STYLES = ["White Background", "Studio Lighting", "Lifestyle Scene", "Flat Lay", "Minimalist"];
const PRODUCT_TYPES = ["T-shirt", "Mug", "Poster/Wall Art", "Phone Case", "Tote Bag", "Sticker", "Other"];

const TRASH_ICON_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`;

const el = {
  dropzone: document.getElementById("dropzone"),
  fileInput: document.getElementById("fileInput"),
  dropzoneEmpty: document.getElementById("dropzoneEmpty"),
  dropzonePreview: document.getElementById("dropzonePreview"),
  previewImg: document.getElementById("previewImg"),
  removeImageBtn: document.getElementById("removeImageBtn"),
  platformSelect: document.getElementById("platformSelect"),
  styleSelect: document.getElementById("styleSelect"),
  productTypeSelect: document.getElementById("productTypeSelect"),
  generateBtn: document.getElementById("generateBtn"),
  generateBtnText: document.getElementById("generateBtnText"),
  generateSpinner: document.getElementById("generateSpinner"),
  errorMessage: document.getElementById("errorMessage"),
  resultEmpty: document.getElementById("resultEmpty"),
  resultContent: document.getElementById("resultContent"),
  resultImg: document.getElementById("resultImg"),
  downloadBtn: document.getElementById("downloadBtn"),
  historyCount: document.getElementById("historyCount"),
  historySkeleton: document.getElementById("historySkeleton"),
  historyGrid: document.getElementById("historyGrid"),
  historyEmpty: document.getElementById("historyEmpty"),
  loadMoreBtn: document.getElementById("loadMoreBtn"),
  lightbox: document.getElementById("lightbox"),
  lightboxBackdrop: document.getElementById("lightboxBackdrop"),
  lightboxClose: document.getElementById("lightboxClose"),
  lightboxImg: document.getElementById("lightboxImg"),
  lightboxDownload: document.getElementById("lightboxDownload"),
  toast: document.getElementById("toast"),
};

let selectedFile = null;
let historyOffset = 0;
let historyTotal = 0;
let historyLoadedCount = 0;
let historyInitialLoadDone = false;
let pendingDelete = { id: null, timeoutId: null };
let toastTimeoutId = null;

function populateSelect(selectEl, options) {
  selectEl.innerHTML = options.map((opt) => `<option value="${opt}">${opt}</option>`).join("");
}

function init() {
  populateSelect(el.platformSelect, PLATFORMS);
  populateSelect(el.styleSelect, STYLES);
  populateSelect(el.productTypeSelect, PRODUCT_TYPES);

  el.dropzone.addEventListener("click", () => el.fileInput.click());
  el.fileInput.addEventListener("change", (e) => handleFileSelected(e.target.files[0]));

  ["dragenter", "dragover"].forEach((evt) =>
    el.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      el.dropzone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    el.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      el.dropzone.classList.remove("dragover");
    })
  );
  el.dropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) handleFileSelected(file);
  });

  el.removeImageBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    clearSelectedFile();
  });

  el.generateBtn.addEventListener("click", generateMockup);
  el.loadMoreBtn.addEventListener("click", loadMoreHistory);

  el.lightboxClose.addEventListener("click", closeLightbox);
  el.lightboxBackdrop.addEventListener("click", closeLightbox);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !el.lightbox.classList.contains("hidden")) {
      closeLightbox();
    }
  });

  renderHistorySkeleton();
  loadHistory({ reset: true });
}

function handleFileSelected(file) {
  if (!file) return;

  const validTypes = ["image/png", "image/jpeg", "image/jpg"];
  if (!validTypes.includes(file.type)) {
    showError("Only PNG and JPG images are supported.");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showError("Image is too large (max 10MB).");
    return;
  }

  selectedFile = file;
  hideError();

  const reader = new FileReader();
  reader.onload = (e) => {
    el.previewImg.src = e.target.result;
    el.dropzoneEmpty.classList.add("hidden");
    el.dropzonePreview.classList.remove("hidden");
  };
  reader.readAsDataURL(file);

  updateGenerateButtonState();
}

function clearSelectedFile() {
  selectedFile = null;
  el.fileInput.value = "";
  el.previewImg.src = "";
  el.dropzoneEmpty.classList.remove("hidden");
  el.dropzonePreview.classList.add("hidden");
  updateGenerateButtonState();
}

function updateGenerateButtonState() {
  el.generateBtn.disabled = !selectedFile;
}

function showError(message) {
  el.errorMessage.textContent = message;
  el.errorMessage.classList.remove("hidden");
}

function hideError() {
  el.errorMessage.classList.add("hidden");
}

function setLoading(isLoading) {
  el.generateBtn.disabled = isLoading || !selectedFile;
  el.generateBtnText.textContent = isLoading ? "Generating..." : "Generate Mockup";
  el.generateSpinner.classList.toggle("hidden", !isLoading);
}

async function generateMockup() {
  if (!selectedFile) {
    showError("Please upload an image before generating a mockup.");
    return;
  }

  hideError();
  setLoading(true);

  const formData = new FormData();
  formData.append("image", selectedFile);
  formData.append("platform", el.platformSelect.value);
  formData.append("style", el.styleSelect.value);
  formData.append("product_type", el.productTypeSelect.value);

  try {
    const res = await fetch(`${API_BASE}/api/generate`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const errBody = await safeJson(res);
      throw new Error(errBody?.detail || `Generation failed (status ${res.status}).`);
    }

    const data = await res.json();
    renderResult(data.image_url);
    loadHistory({ reset: true });
  } catch (err) {
    console.error(err);
    showError(err.message || "Something went wrong while generating your mockup. Please try again.");
  } finally {
    setLoading(false);
  }
}

async function safeJson(res) {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function renderResult(imageUrl) {
  el.resultImg.src = imageUrl;
  el.downloadBtn.href = imageUrl;
  el.resultEmpty.classList.add("hidden");
  el.resultContent.classList.remove("hidden");
}

function formatRelativeTime(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";

  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 45) return "just now";

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;

  return date.toLocaleDateString();
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderHistorySkeleton(count = 4) {
  el.historySkeleton.innerHTML = Array.from({ length: count }, () => `
    <div class="skeleton-card">
      <div class="skeleton-image"></div>
      <div class="skeleton-lines">
        <div class="skeleton-line"></div>
        <div class="skeleton-line short"></div>
        <div class="skeleton-line shorter"></div>
      </div>
    </div>
  `).join("");
  el.historySkeleton.classList.remove("hidden");
  el.historyGrid.classList.add("hidden");
  el.historyEmpty.classList.add("hidden");
  el.loadMoreBtn.classList.add("hidden");
}

function updateHistoryCount() {
  if (historyTotal === 0) {
    el.historyCount.classList.add("hidden");
    el.historyCount.textContent = "";
    return;
  }

  el.historyCount.textContent = `Showing ${historyLoadedCount} of ${historyTotal}`;
  el.historyCount.classList.remove("hidden");
}

function updateLoadMoreButton() {
  const hasMore = historyLoadedCount < historyTotal;
  el.loadMoreBtn.classList.toggle("hidden", !hasMore || historyTotal === 0);
  el.loadMoreBtn.disabled = false;
  el.loadMoreBtn.textContent = "Load More";
}

function buildHistoryCard(item) {
  const card = document.createElement("article");
  card.className = "history-card";
  card.dataset.id = String(item.id);

  card.innerHTML = `
    <div class="history-card-image-wrap" tabindex="0" role="button" aria-label="View full-size mockup">
      <img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.product_type)} mockup" loading="lazy" />
      <button type="button" class="history-delete-btn" aria-label="Delete generation">${TRASH_ICON_SVG}</button>
    </div>
    <div class="history-meta">
      <span class="history-meta-title">${escapeHtml(item.product_type)}</span>
      <span class="history-meta-tags">${escapeHtml(item.platform)} · ${escapeHtml(item.style)}</span>
      <span class="history-meta-time">${escapeHtml(formatRelativeTime(item.created_at))}</span>
    </div>
  `;

  const imageWrap = card.querySelector(".history-card-image-wrap");
  const deleteBtn = card.querySelector(".history-delete-btn");

  imageWrap.addEventListener("click", (e) => {
    if (e.target.closest(".history-delete-btn")) return;
    openLightbox(item.image_url);
  });

  imageWrap.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openLightbox(item.image_url);
    }
  });

  deleteBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    handleDeleteClick(item.id, deleteBtn, card);
  });

  return card;
}

function appendHistoryItems(items) {
  const fragment = document.createDocumentFragment();
  items.forEach((item) => fragment.appendChild(buildHistoryCard(item)));
  el.historyGrid.appendChild(fragment);
}

async function loadHistory({ reset = false } = {}) {
  if (reset) {
    historyOffset = 0;
    historyLoadedCount = 0;
    historyTotal = 0;
    el.historyGrid.innerHTML = "";
    renderHistorySkeleton();
  }

  try {
    const res = await fetch(
      `${API_BASE}/api/history?limit=${HISTORY_PAGE_SIZE}&offset=${historyOffset}`
    );

    if (!res.ok) {
      const errBody = await safeJson(res);
      throw new Error(errBody?.detail || `Failed to load history (${res.status}).`);
    }

    const data = await res.json();
    const items = data.items || [];
    historyTotal = data.total ?? items.length;

    el.historySkeleton.classList.add("hidden");

    if (reset) {
      el.historyGrid.innerHTML = "";
    }

    if (historyTotal === 0) {
      el.historyGrid.classList.add("hidden");
      el.historyEmpty.classList.remove("hidden");
      el.loadMoreBtn.classList.add("hidden");
      el.historyCount.classList.add("hidden");
      historyInitialLoadDone = true;
      return;
    }

    el.historyEmpty.classList.add("hidden");
    el.historyGrid.classList.remove("hidden");
    appendHistoryItems(items);

    historyLoadedCount += items.length;
    historyOffset += items.length;
    updateHistoryCount();
    updateLoadMoreButton();
    historyInitialLoadDone = true;
  } catch (err) {
    console.error("Failed to load history", err);
    el.historySkeleton.classList.add("hidden");

    if (!historyInitialLoadDone) {
      el.historyGrid.classList.add("hidden");
      el.historyEmpty.classList.remove("hidden");
      el.historyEmpty.querySelector("h3").textContent = "Couldn't load history";
      el.historyEmpty.querySelector("p").textContent =
        "Please refresh the page and try again.";
    }
  }
}

async function loadMoreHistory() {
  el.loadMoreBtn.disabled = true;
  el.loadMoreBtn.textContent = "Loading…";
  await loadHistory({ reset: false });
}

function resetDeleteConfirm(deleteBtn) {
  if (pendingDelete.timeoutId) {
    clearTimeout(pendingDelete.timeoutId);
  }
  pendingDelete = { id: null, timeoutId: null };
  if (deleteBtn) {
    deleteBtn.classList.remove("confirming");
    deleteBtn.removeAttribute("data-confirming");
    deleteBtn.removeAttribute("data-action");
    deleteBtn.innerHTML = TRASH_ICON_SVG;
    deleteBtn.setAttribute("aria-label", "Delete generation");
  }
}

function handleDeleteClick(id, deleteBtn, card) {
  if (deleteBtn.dataset.confirming === "true") {
    if (deleteBtn.dataset.action === "confirm") {
      resetDeleteConfirm(deleteBtn);
      deleteGeneration(id, card);
    } else if (deleteBtn.dataset.action === "cancel") {
      resetDeleteConfirm(deleteBtn);
    }
    return;
  }

  document.querySelectorAll(".history-delete-btn.confirming").forEach((btn) => {
    resetDeleteConfirm(btn);
  });

  deleteBtn.classList.add("confirming");
  deleteBtn.dataset.confirming = "true";
  deleteBtn.innerHTML = `
    <span class="delete-confirm-actions">
      <span class="delete-action" data-action="confirm" role="button" tabindex="0">Confirm?</span>
      <span class="delete-action delete-cancel" data-action="cancel" role="button" tabindex="0">Cancel</span>
    </span>
  `;
  deleteBtn.setAttribute("aria-label", "Confirm or cancel delete");

  deleteBtn.querySelectorAll(".delete-action").forEach((actionEl) => {
    actionEl.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteBtn.dataset.action = actionEl.dataset.action;
      handleDeleteClick(id, deleteBtn, card);
    });
  });

  pendingDelete.id = id;
  pendingDelete.timeoutId = setTimeout(() => {
    resetDeleteConfirm(deleteBtn);
  }, 3000);
}

async function deleteGeneration(id, card) {
  resetDeleteConfirm(card.querySelector(".history-delete-btn"));

  try {
    const res = await fetch(`${API_BASE}/api/history/${id}`, { method: "DELETE" });

    if (!res.ok) {
      const errBody = await safeJson(res);
      throw new Error(errBody?.detail || `Delete failed (${res.status}).`);
    }

    card.classList.add("removing");
    setTimeout(() => {
      card.remove();
      historyLoadedCount = Math.max(0, historyLoadedCount - 1);
      historyTotal = Math.max(0, historyTotal - 1);
      historyOffset = Math.max(0, historyOffset - 1);

      if (historyTotal === 0) {
        el.historyGrid.classList.add("hidden");
        el.historyEmpty.classList.remove("hidden");
        el.historyEmpty.querySelector("h3").textContent = "No mockups yet";
        el.historyEmpty.querySelector("p").textContent =
          "Generate your first one above — it will show up here in your gallery.";
        el.historyCount.classList.add("hidden");
        el.loadMoreBtn.classList.add("hidden");
      } else {
        updateHistoryCount();
        updateLoadMoreButton();
      }
    }, 280);

    showToast("Generation deleted");
  } catch (err) {
    console.error(err);
    showToast(err.message || "Could not delete generation");
  }
}

function openLightbox(imageUrl) {
  el.lightboxImg.src = imageUrl;
  el.lightboxDownload.href = imageUrl;
  el.lightbox.classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closeLightbox() {
  el.lightbox.classList.add("hidden");
  el.lightboxImg.src = "";
  document.body.style.overflow = "";
}

function showToast(message) {
  if (toastTimeoutId) clearTimeout(toastTimeoutId);

  el.toast.textContent = message;
  el.toast.classList.remove("hidden");
  requestAnimationFrame(() => el.toast.classList.add("visible"));

  toastTimeoutId = setTimeout(() => {
    el.toast.classList.remove("visible");
    setTimeout(() => el.toast.classList.add("hidden"), 250);
  }, 2800);
}

init();
