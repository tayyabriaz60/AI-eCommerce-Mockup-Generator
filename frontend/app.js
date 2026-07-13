// AI eCommerce Mockup Generator — frontend logic (vanilla JS, no build step)

const API_BASE = ""; // same-origin: backend serves this frontend directly

// Keep option lists here so they're easy to tweak without touching backend.
// (Mirrors backend/config.py — MVP duplication is fine; could be fetched from
// an /api/options endpoint later.)
const PLATFORMS = ["Etsy", "Shopify", "Amazon", "TikTok Shop", "Custom"];
const STYLES = ["White Background", "Studio Lighting", "Lifestyle Scene", "Flat Lay", "Minimalist"];
const PRODUCT_TYPES = ["T-shirt", "Mug", "Poster/Wall Art", "Phone Case", "Tote Bag", "Sticker", "Other"];

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
  historyGrid: document.getElementById("historyGrid"),
  historyEmpty: document.getElementById("historyEmpty"),
};

let selectedFile = null;

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

  loadHistory();
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
    loadHistory();
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

async function loadHistory() {
  try {
    const res = await fetch(`${API_BASE}/api/history`);
    if (!res.ok) return;
    const data = await res.json();
    renderHistory(data.items || []);
  } catch (err) {
    console.error("Failed to load history", err);
  }
}

function renderHistory(items) {
  if (!items.length) {
    el.historyGrid.innerHTML = "";
    el.historyEmpty.classList.remove("hidden");
    return;
  }

  el.historyEmpty.classList.add("hidden");
  el.historyGrid.innerHTML = items
    .map((item) => {
      const date = new Date(item.created_at);
      const dateStr = isNaN(date) ? "" : date.toLocaleString();
      return `
        <div class="history-card">
          <img src="${item.image_url}" alt="${item.product_type} mockup" loading="lazy" />
          <div class="history-meta">
            <strong>${item.product_type}</strong>
            <span>${item.platform} · ${item.style}</span><br />
            <span>${dateStr}</span>
          </div>
        </div>
      `;
    })
    .join("");
}

init();
