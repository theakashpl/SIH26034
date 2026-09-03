/**
 * Packaged Commodity Compliance Scanner - Frontend Logic
 * SIH26034 - Legal Metrology Rules, 2011
 */

(function () {
  'use strict';

  // --- Configuration ---
  // Connects to local FastAPI backend or current origin if served directly
  const API_BASE_URL = (
    window.location.origin.includes('5500') ||
    window.location.origin.includes('3000') ||
    window.location.origin.includes('5173') ||
    window.location.protocol === 'file:'
  ) ? 'http://127.0.0.1:8000' : window.location.origin;

  const MAX_IMAGES = 4;
  const ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff'];

  // --- State ---
  let selectedFiles = []; // Array of File objects (1 to 4)
  let thumbnailUrls = [];  // Object URLs for memory cleanup

  // --- DOM Elements ---
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const previewArea = document.getElementById('previewArea');
  const previewGrid = document.getElementById('previewGrid');
  const imageCounter = document.getElementById('imageCounter');
  const scanBtn = document.getElementById('scanBtn');
  const clearBtn = document.getElementById('clearBtn');
  const alertBanner = document.getElementById('alertBanner');
  const alertMessage = document.getElementById('alertMessage');
  const alertCloseBtn = document.getElementById('alertCloseBtn');
  const loadingOverlay = document.getElementById('loadingOverlay');
  const loadingStatusText = document.getElementById('loadingStatusText');
  const loadingSubtext = document.getElementById('loadingSubtext');

  // Results elements
  const scanSection = document.getElementById('scanSection');
  const resultSection = document.getElementById('resultSection');
  const complianceOverviewCard = document.getElementById('complianceOverviewCard');
  const reportProductName = document.getElementById('reportProductName');
  const scoreValue = document.getElementById('scoreValue');
  const statusTag = document.getElementById('statusTag');
  const statusIcon = document.getElementById('statusIcon');
  const statusText = document.getElementById('statusText');
  const summaryText = document.getElementById('summaryText');
  const metaImageCount = document.getElementById('metaImageCount');
  const metaOcrConfidence = document.getElementById('metaOcrConfidence');
  const conflictAlertBox = document.getElementById('conflictAlertBox');
  const conflictDetailsList = document.getElementById('conflictDetailsList');
  const rulesGrid = document.getElementById('rulesGrid');
  const techOcrContent = document.getElementById('techOcrContent');
  const scanAnotherBtn = document.getElementById('scanAnotherBtn');

  // --- Utility: Alerts ---
  function showAlert(message, isInfo = false) {
    alertMessage.textContent = message;
    alertBanner.className = isInfo ? 'alert-banner info' : 'alert-banner';
    alertBanner.classList.remove('hidden');
    // Auto scroll to top of card if needed
    alertBanner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideAlert() {
    alertBanner.classList.add('hidden');
  }

  alertCloseBtn.addEventListener('click', hideAlert);

  // --- Utility: File Validation ---
  function isValidFileType(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    return ALLOWED_EXTENSIONS.includes(ext);
  }

  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  // --- Image Selection & Drag-and-Drop ---
  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleNewFiles(Array.from(e.dataTransfer.files));
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleNewFiles(Array.from(e.target.files));
      fileInput.value = ''; // Reset input to allow re-selection
    }
  });

  function handleNewFiles(files) {
    hideAlert();
    let rejectedFormatCount = 0;
    let addedCount = 0;

    for (const file of files) {
      if (!isValidFileType(file)) {
        rejectedFormatCount++;
        continue;
      }

      if (selectedFiles.length >= MAX_IMAGES) {
        showAlert(`Maximum ${MAX_IMAGES} images per product. Extra images were not added.`);
        break;
      }

      // Check if already in list (same name and size)
      const isDuplicate = selectedFiles.some(f => f.name === file.name && f.size === file.size);
      if (!isDuplicate) {
        selectedFiles.push(file);
        addedCount++;
      }
    }

    if (rejectedFormatCount > 0) {
      showAlert(`Skipped ${rejectedFormatCount} unsupported file(s). Allowed: JPG, PNG, WEBP, BMP, TIFF.`);
    }

    updatePreviewUI();
  }

  function removeImage(index) {
    hideAlert();
    if (index >= 0 && index < selectedFiles.length) {
      selectedFiles.splice(index, 1);
      updatePreviewUI();
    }
  }

  function clearAllImages() {
    hideAlert();
    // Revoke old thumbnail URLs
    thumbnailUrls.forEach(url => URL.revokeObjectURL(url));
    thumbnailUrls = [];
    selectedFiles = [];
    updatePreviewUI();
  }

  clearBtn.addEventListener('click', clearAllImages);

  // --- Preview Grid Rendering ---
  function updatePreviewUI() {
    // Revoke previous URLs
    thumbnailUrls.forEach(url => URL.revokeObjectURL(url));
    thumbnailUrls = [];

    previewGrid.innerHTML = '';

    if (selectedFiles.length === 0) {
      previewArea.classList.add('hidden');
      clearBtn.classList.add('hidden');
      scanBtn.disabled = true;
      imageCounter.textContent = `0 of ${MAX_IMAGES} images`;
      return;
    }

    previewArea.classList.remove('hidden');
    clearBtn.classList.remove('hidden');
    scanBtn.disabled = false;
    imageCounter.textContent = `${selectedFiles.length} of ${MAX_IMAGES} images`;

    selectedFiles.forEach((file, idx) => {
      const thumbUrl = URL.createObjectURL(file);
      thumbnailUrls.push(thumbUrl);

      const card = document.createElement('div');
      card.className = 'preview-card';
      card.innerHTML = `
        <button type="button" class="preview-remove-btn" title="Remove image" aria-label="Remove image">&times;</button>
        <div class="preview-thumb-container">
          <img src="${thumbUrl}" alt="Preview View ${idx + 1}" class="preview-thumb" loading="lazy">
        </div>
        <div class="preview-meta">
          <span class="preview-name" title="${file.name}">${file.name}</span>
          <span class="preview-badge">View ${idx + 1}</span>
        </div>
      `;

      card.querySelector('.preview-remove-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        removeImage(idx);
      });

      previewGrid.appendChild(card);
    });
  }

  // --- Multi-Step Loading Simulation ---
  let loadingInterval = null;
  const loadingSteps = [
    { title: "Analyzing product views...", sub: "Validating 1–4 package scans" },
    { title: "Running OCR on uploaded images...", sub: "Extracting text declarations using Tesseract" },
    { title: "Combining multi-view evidence...", sub: "Aggregating declarations and resolving duplicate values" },
    { title: "Checking Legal Metrology rules...", sub: "Evaluating mandatory declarations and conflict detection" }
  ];

  function startLoadingState() {
    loadingOverlay.classList.remove('hidden');
    scanBtn.disabled = true;
    clearBtn.disabled = true;

    let stepIndex = 0;
    loadingStatusText.textContent = loadingSteps[0].title;
    loadingSubtext.textContent = loadingSteps[0].sub;

    loadingInterval = setInterval(() => {
      stepIndex = (stepIndex + 1) % loadingSteps.length;
      loadingStatusText.textContent = loadingSteps[stepIndex].title;
      loadingSubtext.textContent = loadingSteps[stepIndex].sub;
    }, 2200);
  }

  function stopLoadingState() {
    if (loadingInterval) {
      clearInterval(loadingInterval);
      loadingInterval = null;
    }
    loadingOverlay.classList.add('hidden');
    scanBtn.disabled = selectedFiles.length === 0;
    clearBtn.disabled = false;
  }

  // --- Scan Submission ---
  scanBtn.addEventListener('click', performScan);

  async function performScan() {
    if (selectedFiles.length === 0) {
      showAlert("Please select at least 1 image to scan.");
      return;
    }

    if (selectedFiles.length > MAX_IMAGES) {
      showAlert(`Maximum ${MAX_IMAGES} images allowed. Please remove extra images.`);
      return;
    }

    hideAlert();
    startLoadingState();

    const formData = new FormData();
    selectedFiles.forEach((file) => {
      formData.append('files', file);
    });

    try {
      const response = await fetch(`${API_BASE_URL}/scan`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (!response.ok) {
        // HTTP 400 or 500 error from backend
        const detailMsg = data && data.detail ? data.detail : `Server error (${response.status})`;
        throw new Error(detailMsg);
      }

      // Success -> Render Dashboard
      renderComplianceResults(data);

    } catch (err) {
      console.error("Scan request failed:", err);
      let userMsg = err.message;
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        userMsg = `Unable to connect to the compliance server at ${API_BASE_URL}. Please ensure the FastAPI backend is running.`;
      }
      showAlert(userMsg);
    } finally {
      stopLoadingState();
    }
  }

  // --- Render Results Dashboard ---
  function renderComplianceResults(data) {
    const compliance = data.compliance || {};
    const checks = data.checks || [];
    const fields = data.fields || {};
    const details = data.details || {};
    const conflicts = data.conflicts || {};
    const images = data.images || [];

    // 1. Overview card styling & score
    const isCompliant = compliance.status === 'COMPLIANT';
    complianceOverviewCard.className = isCompliant 
      ? 'compliance-card status-compliant' 
      : 'compliance-card status-non-compliant';

    reportProductName.textContent = fields.product_name || "Product Name Not Detected";
    scoreValue.textContent = `${compliance.score || 0}%`;

    statusIcon.textContent = isCompliant ? "✓" : "✗";
    statusText.textContent = compliance.status || "NON_COMPLIANT";
    summaryText.textContent = compliance.summary || (isCompliant 
      ? "All required declarations checked by this MVP were detected." 
      : "One or more required declarations checked by this MVP are missing or conflicting.");

    metaImageCount.textContent = `${images.length} view(s)`;
    metaOcrConfidence.textContent = `${data.ocr_confidence || 0}%`;

    // 2. Conflict Warning Box
    const conflictKeys = Object.keys(conflicts);
    if (conflictKeys.length > 0) {
      conflictAlertBox.classList.remove('hidden');
      conflictDetailsList.innerHTML = '';

      conflictKeys.forEach(field => {
        const conflictItem = document.createElement('div');
        conflictItem.className = 'conflict-item';
        
        const friendlyName = getFieldFriendlyName(field);
        const entries = conflicts[field] || [];
        const sourcesText = entries.map(e => {
          const valDisplay = e.unit ? `${e.value} ${e.unit}` : (typeof e.value === 'number' ? `₹${e.value}` : (e.name || e.phone || e.value));
          return `<span><strong>Image ${e.source_image_id}:</strong> ${escapeHtml(String(valDisplay))}</span>`;
        }).join('&bull;');

        conflictItem.innerHTML = `
          <div class="conflict-field-title">⚠ ${friendlyName} Conflict</div>
          <div class="conflict-sources-row">${sourcesText}</div>
        `;
        conflictDetailsList.appendChild(conflictItem);
      });
    } else {
      conflictAlertBox.classList.add('hidden');
    }

    // 3. Render the 5 Core Mandatory Check Cards
    rulesGrid.innerHTML = '';
    checks.forEach(check => {
      const card = document.createElement('div');
      const isPass = check.status === 'PASS';
      const isConflict = check.reason && check.reason.toLowerCase().includes('conflict');
      
      let statusClass = isPass ? 'pass' : (isConflict ? 'conflict' : 'fail');
      let statusLabel = isPass ? '✓ DETECTED' : (isConflict ? '⚠ CONFLICT' : '✗ MISSING');

      // Determine source image attribution if available
      const sourceImageId = getSourceImageIdForCheck(check.rule_id, details);
      const sourceFilename = getSourceFilename(sourceImageId, images);
      const sourceBadgeHtml = sourceImageId 
        ? `<div class="rule-source-badge">📷 Detected from Image ${sourceImageId}${sourceFilename ? ` (${escapeHtml(sourceFilename)})` : ''}</div>`
        : '';

      const valueHtml = check.value
        ? `<div class="rule-value-box">${escapeHtml(String(check.value))}</div>`
        : `<div class="rule-value-box rule-value-missing">Declaration Not Detected</div>`;

      card.className = `rule-card ${statusClass}`;
      card.innerHTML = `
        <div class="rule-info">
          <div class="rule-title-row">
            <span class="rule-id-pill">${escapeHtml(check.rule_id)}</span>
            <span class="rule-name">${escapeHtml(check.name)}</span>
          </div>
          ${valueHtml}
          <div class="rule-reason">${escapeHtml(check.reason || '')}</div>
          ${sourceBadgeHtml}
        </div>
        <div class="rule-status-pill ${statusClass}">
          ${statusLabel}
        </div>
      `;
      rulesGrid.appendChild(card);
    });

    // 4. Populate Technical Raw OCR Drawer
    techOcrContent.innerHTML = '';
    if (images.length === 0 && data.ocr_text) {
      techOcrContent.innerHTML = `<pre class="ocr-pre">${escapeHtml(data.ocr_text)}</pre>`;
    } else {
      images.forEach(img => {
        const block = document.createElement('div');
        block.className = 'ocr-image-block';
        block.innerHTML = `
          <div class="ocr-block-header">
            <span>Image ${img.image_id}: ${escapeHtml(img.filename)}</span>
            <span>OCR Confidence: ${img.confidence}%</span>
          </div>
          <pre class="ocr-pre">${escapeHtml(img.cleaned_text || img.ocr_text || '(No text detected)')}</pre>
        `;
        techOcrContent.appendChild(block);
      });
    }

    // 5. Swap Views smoothly
    scanSection.classList.add('hidden');
    resultSection.classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // --- Helper: Field Name Formatter ---
  function getFieldFriendlyName(fieldKey) {
    const map = {
      'product_name': 'Product Name',
      'mrp': 'Maximum Retail Price (MRP)',
      'net_quantity': 'Net Quantity',
      'manufacturer': 'Manufacturer Details',
      'consumer_information': 'Consumer Care Information',
      'consumer_care': 'Consumer Care Information'
    };
    return map[fieldKey] || fieldKey;
  }

  // --- Helper: Source Attribution Lookup ---
  function getSourceImageIdForCheck(ruleId, details) {
    if (!details) return null;
    const ruleFieldMap = {
      'LM-001': 'product_name',
      'LM-002': 'manufacturer',
      'LM-003': 'net_quantity',
      'LM-004': 'mrp',
      'LM-005': 'consumer_information'
    };
    const fieldKey = ruleFieldMap[ruleId];
    if (fieldKey && details[fieldKey]) {
      return details[fieldKey].source_image_id || null;
    }
    return null;
  }

  function getSourceFilename(sourceImageId, images) {
    if (!sourceImageId || !images) return '';
    const found = images.find(img => img.image_id === sourceImageId);
    return found ? found.filename : '';
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --- Scan Another Product ---
  scanAnotherBtn.addEventListener('click', () => {
    clearAllImages();
    resultSection.classList.add('hidden');
    scanSection.classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

})();
