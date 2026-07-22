const batchForm = document.querySelector("#batch-form");
const reportForm = document.querySelector("#report-form");
const modeTabs = document.querySelectorAll(".mode-tab");
const modePanels = document.querySelectorAll("[data-mode-panel]");
const referenceInput = document.querySelector("#reference");
const templatesInput = document.querySelector("#templates");
const templateFolderInput = document.querySelector("#template-folder");
const folderTokenInput = document.querySelector("#folder-token");
const nativeFolderButton = document.querySelector("#native-folder-button");
const reviewModeInputs = document.querySelectorAll('input[name="review_mode"]');
const reportSourceInput = document.querySelector("#report-source");
const processingReportInput = document.querySelector("#processing-report");
const referenceList = document.querySelector("#reference-list");
const templatesList = document.querySelector("#templates-list");
const templateFolderList = document.querySelector("#template-folder-list");
const reportSourceList = document.querySelector("#report-source-list");
const processingReportList = document.querySelector("#processing-report-list");
const badge = document.querySelector("#status-badge");
const meterFill = document.querySelector("#meter-fill");
const metricALabel = document.querySelector("#metric-a-label");
const metricBLabel = document.querySelector("#metric-b-label");
const metricCLabel = document.querySelector("#metric-c-label");
const metricDLabel = document.querySelector("#metric-d-label");
const metricELabel = document.querySelector("#metric-e-label");
const metricA = document.querySelector("#metric-a");
const metricB = document.querySelector("#metric-b");
const metricC = document.querySelector("#metric-c");
const metricD = document.querySelector("#metric-d");
const metricE = document.querySelector("#metric-e");
const emptyState = document.querySelector("#empty-state");
const results = document.querySelector("#results");
const resultsHead = document.querySelector("#results-head");
const resultsBody = document.querySelector("#results-body");
const errorsBox = document.querySelector("#errors");
const warningsBox = document.querySelector("#warnings");
const warningsTitle = document.querySelector("#warnings-title");
const warningsList = document.querySelector("#warnings-list");
const fixReprocessButton = document.querySelector("#fix-reprocess");
const correctionsBox = document.querySelector("#corrections");
const correctionsList = document.querySelector("#corrections-list");
const correctionsTitle = document.querySelector("#corrections-title");
const reviewHelp = document.querySelector("#review-help");
const reviewCount = document.querySelector("#review-count");
const newBatchButton = document.querySelector("#new-batch");
const startOverButton = document.querySelector("#start-over");
const reviewToolbar = document.querySelector("#review-toolbar");
const reviewSearch = document.querySelector("#review-search");
const reviewFileFilter = document.querySelector("#review-file-filter");
const reviewStatusFilter = document.querySelector("#review-status-filter");
const reviewPageSize = document.querySelector("#review-page-size");
const reviewPagination = document.querySelector("#review-pagination");
const reviewPrev = document.querySelector("#review-prev");
const reviewNext = document.querySelector("#review-next");
const reviewPageInfo = document.querySelector("#review-page-info");
const reviewSubmit = document.querySelector("#review-submit");
const downloadLink = document.querySelector("#download-link");
const exportCenter = document.querySelector("#export-center");
const exportFileList = document.querySelector("#export-file-list");
const exportSelectAll = document.querySelector("#export-select-all");
const exportClear = document.querySelector("#export-clear");
const exportIncludeReports = document.querySelector("#export-include-reports");
const exportSelectionCount = document.querySelector("#export-selection-count");
const exportSelected = document.querySelector("#export-selected");
const exportStatus = document.querySelector("#export-status");
const batchSubmitButton = document.querySelector("#batch-submit");
const reportSubmitButton = document.querySelector("#report-submit");
const aiSettingsButton = document.querySelector("#ai-settings-button");
const aiSettingsModal = document.querySelector("#ai-settings-modal");
const aiSettingsClose = document.querySelector("#ai-settings-close");
const aiSettingsCancel = document.querySelector("#ai-settings-cancel");
const aiSettingsSave = document.querySelector("#ai-settings-save");
const aiApiKey = document.querySelector("#ai-api-key");
const aiModel = document.querySelector("#ai-model");
const aiSettingsStatus = document.querySelector("#ai-settings-status");

let activeMode = "batch";
let activeJobId = null;
let reviewCorrections = [];
let reviewSkuContexts = {};
let reviewChoices = [];
let reviewIsEditable = false;
let reviewPage = 1;
let selectedReviewRows = new Set();
let aiConfigured = false;
let activeProcessedFiles = [];

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function formatFiles(input) {
  const files = Array.from(input.files || []);
  if (!files.length) {
    return "No file selected";
  }
  if (files.length === 1) {
    return files[0].name;
  }
  return `${files.length} files selected`;
}

function formatFolderFiles(input) {
  const files = Array.from(input.files || []);
  if (!files.length) {
    return "No folder selected";
  }
  const firstPath = files[0].webkitRelativePath || files[0].name;
  const folderName = firstPath.split("/")[0] || "Folder";
  return `${folderName} - ${files.length} files selected`;
}

function setBadge(text, state) {
  badge.textContent = text;
  badge.classList.remove("is-busy", "is-done", "is-error", "is-warning");
  if (state) {
    badge.classList.add(state);
  }
}

function setMeter(percent) {
  meterFill.style.width = `${percent}%`;
}

function setMetricLabels(labels) {
  [metricALabel, metricBLabel, metricCLabel, metricDLabel, metricELabel].forEach(
    (label, index) => {
      label.textContent = labels[index];
    },
  );
}

function setMetricValues(values) {
  [metricA, metricB, metricC, metricD, metricE].forEach((metric, index) => {
    metric.textContent = formatNumber(values[index]);
  });
}

function resetResults(mode = activeMode) {
  reviewSkuContexts = {};
  activeProcessedFiles = [];
  document.body.classList.remove("review-mode-active");
  document.body.classList.remove("automatic-results");
  document.querySelector(".workspace").classList.remove("is-reviewing");
  newBatchButton.hidden = true;
  startOverButton.hidden = true;
  if (mode === "report") {
    setMetricLabels([
      "Source SKUs",
      "Retry SKUs",
      "Removed Clean",
      "Manual Review",
      "Corrections",
    ]);
  } else {
    setMetricLabels([
      "Reference SKUs",
      "Templates",
      "Removed Rows",
      "Text Fixes",
      "Alerts",
    ]);
  }
  setMetricValues([0, 0, 0, 0, 0]);
  resultsHead.textContent = "";
  resultsBody.textContent = "";
  errorsBox.textContent = "";
  errorsBox.hidden = true;
  warningsList.textContent = "";
  warningsBox.hidden = true;
  fixReprocessButton.hidden = true;
  correctionsList.textContent = "";
  correctionsBox.hidden = true;
  reviewToolbar.hidden = true;
  reviewPagination.hidden = true;
  reviewSubmit.hidden = true;
  downloadLink.hidden = true;
  downloadLink.href = "#";
  exportCenter.hidden = true;
  exportFileList.textContent = "";
  exportStatus.textContent = "";
  results.hidden = true;
  emptyState.hidden = false;
}

function renderTable(headers, rows) {
  resultsHead.textContent = "";
  headers.forEach((header) => {
    const cell = document.createElement("th");
    cell.textContent = header;
    resultsHead.appendChild(cell);
  });

  resultsBody.textContent = "";
  rows.forEach((values) => {
    const row = document.createElement("tr");
    values.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    });
    resultsBody.appendChild(row);
  });
}

function showResults() {
  emptyState.hidden = true;
  results.hidden = false;
  newBatchButton.hidden = false;
  startOverButton.hidden = false;
}

function encodedFilePath(filename) {
  return String(filename).split("/").map(encodeURIComponent).join("/");
}

function updateExportSelection() {
  const checked = exportFileList.querySelectorAll('input[type="checkbox"]:checked').length;
  exportSelectionCount.textContent = `${formatNumber(checked)} selected`;
  exportSelected.disabled = checked === 0;
}

function renderExportFiles() {
  exportFileList.textContent = "";
  activeProcessedFiles.forEach((file) => {
    const item = document.createElement("div");
    item.className = "export-file";
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = file.filename;
    checkbox.checked = true;
    checkbox.addEventListener("change", updateExportSelection);
    const copy = document.createElement("span");
    const name = document.createElement("strong");
    name.textContent = file.filename;
    name.title = file.filename;
    const detail = document.createElement("small");
    detail.textContent = `${formatNumber(file.updated)} SKUs processed`;
    copy.append(name, detail);
    label.append(checkbox, copy);
    const individual = document.createElement("a");
    individual.href = `/download-file/${activeJobId}/${encodedFilePath(file.filename)}`;
    individual.textContent = "Download";
    individual.setAttribute("download", "");
    item.append(label, individual);
    exportFileList.appendChild(item);
  });
  updateExportSelection();
}

function showDownload(downloadUrl) {
  downloadLink.href = downloadUrl;
  downloadLink.hidden = false;
  exportCenter.hidden = false;
  const hasIndividualFiles = activeMode === "batch" && activeProcessedFiles.length > 0;
  exportFileList.hidden = !hasIndividualFiles;
  document.querySelector(".export-toolbar").hidden = !hasIndividualFiles;
  if (hasIndividualFiles) renderExportFiles();
}

exportSelectAll.addEventListener("click", () => {
  exportFileList.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = true; });
  updateExportSelection();
});
exportClear.addEventListener("click", () => {
  exportFileList.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = false; });
  updateExportSelection();
});
exportSelected.addEventListener("click", async () => {
  const filenames = Array.from(exportFileList.querySelectorAll('input[type="checkbox"]:checked')).map((input) => input.value);
  if (!filenames.length || !activeJobId) return;
  exportSelected.disabled = true;
  exportStatus.textContent = "Preparing selected files…";
  try {
    const response = await fetch(`/api/export/${activeJobId}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({filenames, include_reports:exportIncludeReports.checked})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The selected export could not be created.");
    exportStatus.textContent = `${formatNumber(filenames.length)} files ready`;
    const link = document.createElement("a");
    link.href = data.download_url;
    link.download = "focus_amazon_selected.zip";
    document.body.appendChild(link);
    link.click();
    link.remove();
  } catch (error) {
    exportStatus.textContent = error.message;
  } finally {
    updateExportSelection();
  }
});

function renderErrors(errors) {
  if (!errors.length) {
    return;
  }
  errorsBox.hidden = false;
  errorsBox.textContent = errors
    .map((item) => `${item.filename || "File"}: ${item.error || item}`)
    .join("\n");
}

function renderBatchResults(data) {
  const warnings = data.warnings || [];
  const corrections = data.corrections || [];
  activeJobId = data.job_id;
  activeProcessedFiles = (data.processed || []).map((file) => ({filename:file.filename, updated:file.updated}));
  document.body.classList.toggle("automatic-results", data.review_mode === "automatic");

  setMetricLabels([
    "Reference SKUs",
    "Templates",
    "Removed Rows",
    data.review_mode === "review" ? "Fields To Review" : "Text Fixes",
    "Alerts",
  ]);
  const totals = data.totals || {};
  setMetricValues([
    data.reference_count,
    data.processed.length,
    totals.removed || 0,
    data.review_mode === "review" ? corrections.length : (totals.text_fields_cleaned || corrections.length),
    warnings.length + (data.errors || []).length,
  ]);

  renderTable(
    ["File", "Updated", "Removed", data.review_mode === "review" ? "Review Fields" : "Text Fixes", "HTML", "Truncated", "Alerts"],
    data.processed.map((item) => [
      item.filename,
      formatNumber(item.updated),
      formatNumber(item.removed),
      formatNumber(item.text_fields_cleaned || item.corrections),
      formatNumber(item.html_cleaned),
      formatNumber(item.field_truncated),
      formatNumber(item.warnings),
    ]),
  );

  if (warnings.length) {
    warningsBox.hidden = false;
    warningsTitle.textContent = data.auto_fix_bullets
      ? "Pending Amazon Text Alerts After Correction"
      : "Amazon Text Alerts";
    warningsList.textContent = "";
    warnings.slice(0, 200).forEach((warning) => {
      const item = document.createElement("div");
      item.className = "warning-item";

      const title = document.createElement("strong");
      title.textContent = `${warning.filename} | SKU ${warning.sku} | row ${warning.row}, column ${warning.column}`;

      const issue = document.createElement("span");
      issue.textContent = warning.issues.join("; ");

      const preview = document.createElement("small");
      preview.textContent = warning.preview;

      item.append(title, issue, preview);
      warningsList.appendChild(item);
    });

    if (warnings.length > 200) {
      const more = document.createElement("div");
      more.className = "warning-more";
      more.textContent = `${formatNumber(warnings.length - 200)} additional alerts are included in amazon_text_alerts.csv inside the ZIP.`;
      warningsList.appendChild(more);
    }

    fixReprocessButton.hidden = Boolean(data.auto_fix_bullets);
  }

  if (corrections.length) {
    correctionsBox.hidden = false;
    correctionsList.textContent = "";
    const isReview = data.review_mode === "review";
    document.body.classList.toggle("review-mode-active", isReview);
    document.querySelector(".workspace").classList.toggle("is-reviewing", isReview);
    correctionsTitle.textContent = isReview ? "Review proposed changes" : "Corrections applied";
    reviewHelp.textContent = isReview ? "Edit final values directly. Hover a field to view its original value." : "Safe corrections were applied automatically.";
    reviewCount.textContent = `${formatNumber(corrections.length)} changes`;
    reviewToolbar.hidden = !isReview;
    reviewSubmit.hidden = !isReview;
    reviewCorrections = corrections;
    reviewSkuContexts = data.sku_contexts || {};
    activeJobId = data.job_id;
    reviewChoices = corrections.map((correction) => ({ choice: "fixed", value: correction.fixed }));
    reviewIsEditable = isReview;
    reviewPage = 1;
    selectedReviewRows = new Set(corrections.map((item) => `${item.filename}\u0000${item.sku}`));
    reviewSearch.value = "";
    reviewFileFilter.textContent = "";
    const allFilesOption = document.createElement("option");
    allFilesOption.value = "";
    allFilesOption.textContent = "All files";
    reviewFileFilter.appendChild(allFilesOption);
    Array.from(new Set(corrections.map((item) => item.filename))).sort().forEach((filename) => {
      const option = document.createElement("option");
      option.value = filename;
      option.textContent = filename;
      reviewFileFilter.appendChild(option);
    });
    renderCorrectionGroups();
    updateReviewCount();
  }

  renderErrors(data.errors || []);
  if (data.review_mode !== "review" || !corrections.length) showDownload(data.download_url);
  showResults();
}

function renderReportFixResults(data) {
  setMetricLabels([
    "Source SKUs",
    "Retry SKUs",
    "Removed Clean",
    "Manual Review",
    "Corrections",
  ]);
  setMetricValues([
    data.source_skus,
    data.kept_retry_skus,
    data.removed_clean_success_skus,
    data.manual_review_items,
    data.corrections_applied,
  ]);

  renderTable(
    [
      "Output",
      "Source SKUs",
      "Report SKUs",
      "Retry SKUs",
      "Removed Clean SKUs",
      "Not In Report Kept",
      "Corrections",
      "Manual Review",
    ],
    [
      [
        "Retry workbook",
        formatNumber(data.source_skus),
        formatNumber(data.report_skus),
        formatNumber(data.kept_retry_skus),
        formatNumber(data.removed_clean_success_skus),
        formatNumber(data.not_processed_in_report_kept),
        formatNumber(data.corrections_applied),
        formatNumber(data.manual_review_items),
      ],
    ],
  );

  correctionsBox.hidden = false;
  correctionsList.textContent = "";
  const summary = document.createElement("div");
  summary.className = "correction-item";
  const title = document.createElement("strong");
  title.textContent = "Retry file created";
  const detail = document.createElement("span");
  detail.textContent = `${formatNumber(data.removed_clean_success_skus)} clean success SKUs were removed. ${formatNumber(data.kept_retry_skus)} SKUs remain in the retry workbook.`;
  const included = document.createElement("small");
  included.textContent = "The ZIP includes the corrected .xlsm, correction CSV, manual-review CSV, and summary CSV.";
  summary.append(title, detail, included);
  correctionsList.appendChild(summary);

  if (data.manual_review_items) {
    warningsBox.hidden = false;
    warningsTitle.textContent = "Manual Review Needed";
    warningsList.textContent = "";
    const item = document.createElement("div");
    item.className = "warning-item";
    const warningTitle = document.createElement("strong");
    warningTitle.textContent = `${formatNumber(data.manual_review_items)} items need Seller Central review`;
    const warningCopy = document.createElement("span");
    warningCopy.textContent = "Open the manual-review CSV in the ZIP for fields that require external data or a manual decision.";
    item.append(warningTitle, warningCopy);
    warningsList.appendChild(item);
  }

  showDownload(data.download_url);
  showResults();
}

function updateFileLabels() {
  referenceList.textContent = formatFiles(referenceInput);
  templatesList.textContent = formatFiles(templatesInput);
  templateFolderList.textContent = formatFolderFiles(templateFolderInput);
  reportSourceList.textContent = formatFiles(reportSourceInput);
  processingReportList.textContent = formatFiles(processingReportInput);
}

function setMode(mode) {
  activeMode = mode;
  modeTabs.forEach((tab) => {
    const selected = tab.dataset.mode === mode;
    tab.classList.toggle("is-active", selected);
    tab.setAttribute("aria-selected", selected ? "true" : "false");
  });
  modePanels.forEach((panel) => {
    const selected = panel.dataset.modePanel === mode;
    panel.hidden = !selected;
    panel.classList.toggle("is-active", selected);
  });
  resetResults(mode);
  setBadge("Ready");
  setMeter(0);
}

function startProgress(button) {
  button.disabled = true;
  setBadge("Processing", "is-busy");
  setMeter(18);
  return window.setInterval(() => {
    const current = Number.parseFloat(meterFill.style.width) || 18;
    if (current < 82) {
      setMeter(current + 8);
    }
  }, 450);
}

function finishProgress(timer, button) {
  window.clearInterval(timer);
  button.disabled = false;
}

[referenceInput, templatesInput, templateFolderInput, reportSourceInput, processingReportInput].forEach(
  (input) => {
    input.addEventListener("change", updateFileLabels);
  },
);

modeTabs.forEach((tab) => {
  tab.addEventListener("click", () => setMode(tab.dataset.mode));
});

document.querySelectorAll(".drop-zone").forEach((zone) => {
  zone.addEventListener("dragover", (event) => event.preventDefault());
  zone.addEventListener("dragenter", () => zone.classList.add("is-dragging"));
  zone.addEventListener("dragleave", () => zone.classList.remove("is-dragging"));
  zone.addEventListener("drop", () => {
    zone.classList.remove("is-dragging");
    window.setTimeout(updateFileLabels, 0);
  });
});

batchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetResults("batch");

  const uploadedTemplates = [
    ...Array.from(templatesInput.files || []),
    ...Array.from(templateFolderInput.files || []),
  ];
  if (!uploadedTemplates.length && !folderTokenInput.value) {
    setBadge("Missing Template", "is-error");
    return;
  }

  const payload = new FormData();
  if (referenceInput.files[0]) {
    payload.append("reference", referenceInput.files[0]);
  }
  const reviewMode = Array.from(reviewModeInputs).find((input) => input.checked)?.value || "manual";
  payload.append("review_mode", reviewMode);
  uploadedTemplates.forEach((file) => {
    payload.append("templates", file, file.webkitRelativePath || file.name);
  });
  if (folderTokenInput.value) payload.append("folder_token", folderTokenInput.value);

  const progressTimer = startProgress(batchSubmitButton);

  try {
    const response = await fetch("/api/process", {
      method: "POST",
      body: payload,
    });
    const data = await response
      .json()
      .catch(() => ({ error: "The server did not return a valid response." }));
    if (!response.ok) {
      throw new Error(data.error || "The batch could not be processed.");
    }

    renderBatchResults(data);
    setMeter(100);
    if ((data.warnings || []).length) {
      setBadge("Needs Review", "is-warning");
    } else if (data.review_mode === "review" && (data.corrections || []).length) {
      setBadge("Needs Review", "is-warning");
    } else if ((data.corrections || []).length) {
      setBadge("Fixed", "is-done");
    } else {
      setBadge("Complete", "is-done");
    }
  } catch (error) {
    errorsBox.hidden = false;
    errorsBox.textContent = error.message;
    showResults();
    setMeter(100);
    setBadge("Error", "is-error");
  } finally {
    finishProgress(progressTimer, batchSubmitButton);
  }
});

reportForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetResults("report");

  if (!reportSourceInput.files.length) {
    setBadge("Missing Source", "is-error");
    return;
  }
  if (!processingReportInput.files.length) {
    setBadge("Missing Report", "is-error");
    return;
  }

  const payload = new FormData();
  payload.append("source", reportSourceInput.files[0]);
  payload.append("processing_report", processingReportInput.files[0]);

  const progressTimer = startProgress(reportSubmitButton);

  try {
    const response = await fetch("/api/fix-report", {
      method: "POST",
      body: payload,
    });
    const data = await response
      .json()
      .catch(() => ({ error: "The server did not return a valid response." }));
    if (!response.ok) {
      throw new Error(data.error || "The retry workbook could not be created.");
    }

    renderReportFixResults(data);
    setMeter(100);
    if (data.manual_review_items) {
      setBadge("Needs Review", "is-warning");
    } else {
      setBadge("Fixed", "is-done");
    }
  } catch (error) {
    errorsBox.hidden = false;
    errorsBox.textContent = error.message;
    showResults();
    setMeter(100);
    setBadge("Error", "is-error");
  } finally {
    finishProgress(progressTimer, reportSubmitButton);
  }
});

fixReprocessButton.addEventListener("click", () => {
  const automatic = Array.from(reviewModeInputs).find((input) => input.value === "automatic");
  automatic.checked = true;
  if (batchForm.requestSubmit) {
    batchForm.requestSubmit();
  } else {
    batchForm.dispatchEvent(new Event("submit", { cancelable: true }));
  }
});

updateFileLabels();
resetResults();

window.addEventListener("pywebviewready", () => {
  nativeFolderButton.hidden = false;
});

nativeFolderButton.addEventListener("click", async (event) => {
  event.preventDefault();
  event.stopPropagation();
  const selected = await window.pywebview?.api?.choose_template_folder();
  if (!selected) return;
  folderTokenInput.value = selected.token;
  templateFolderList.textContent = `${selected.name} · ${formatNumber(selected.count)} .xlsm files`;
});

function getReviewGroups() {
  const groups = new Map();
  reviewCorrections.forEach((correction, index) => {
    const key = `${correction.filename}\u0000${correction.sku}`;
    const contextKey = `${correction.filename}\u0000${correction.sku}\u0000${correction.row}`;
    if (!groups.has(key)) groups.set(key, { key, filename: correction.filename, sku: correction.sku, context: reviewSkuContexts[contextKey] || {}, items: [] });
    groups.get(key).items.push({ correction, index });
  });
  return Array.from(groups.values());
}

function renderCorrectionGroups() {
  correctionsList.textContent = "";
  const normalizedQuery = reviewSearch.value.trim().toLowerCase();
  const fileFilter = reviewFileFilter.value;
  const statusFilter = reviewStatusFilter.value;
  const matchingGroups = getReviewGroups().filter((group) => {
    const matchesText = !normalizedQuery || `${group.filename} ${group.sku} ${group.items.map(({correction}) => correction.fixed).join(" ")}`.toLowerCase().includes(normalizedQuery);
    const matchesFile = !fileFilter || group.filename === fileFilter;
    const matchesStatus = !statusFilter || group.items.some(({index}) => reviewChoices[index].choice === statusFilter);
    return matchesText && matchesFile && matchesStatus;
  });
  const pageSize = Number(reviewPageSize.value || 25);
  const pageCount = Math.max(1, Math.ceil(matchingGroups.length / pageSize));
  reviewPage = Math.min(reviewPage, pageCount);
  const pageGroups = matchingGroups.slice((reviewPage - 1) * pageSize, reviewPage * pageSize);

  const wrap = document.createElement("div");
  wrap.className = "review-grid-wrap";
  const table = document.createElement("table");
  table.className = "review-grid";
  table.innerHTML = `<thead><tr><th><input type="checkbox" id="select-page" aria-label="Select page"></th><th>#</th><th>SKU</th><th>Title <small>(uploaded file)</small></th><th>Amazon title <small>(Item Name)</small></th><th>Item highlight</th><th>Other</th><th>Status</th><th>File</th></tr></thead>`;
  const body = document.createElement("tbody");
  pageGroups.forEach((group, pageIndex) => {
    const row = document.createElement("tr");
    row.dataset.key = group.key;
    const absoluteIndex = (reviewPage - 1) * pageSize + pageIndex + 1;
    row.innerHTML = `<td><input class="row-select" type="checkbox" aria-label="Select SKU ${escapeHtml(group.sku)}" ${selectedReviewRows.has(group.key) ? "checked" : ""}></td><td class="row-number">${absoluteIndex}</td><td class="sku-cell"><strong>${escapeHtml(group.sku)}</strong></td>`;
    ["Title", "Item Name", "Item Highlight"].forEach((field) => row.appendChild(buildReviewFieldCell(group, field)));
    const otherItems = group.items.filter(({correction}) => !["Title", "Item Name", "Item Highlight"].includes(correction.field));
    const otherCell = document.createElement("td");
    otherCell.className = "other-cell";
    otherCell.textContent = otherItems.length ? `${otherItems.length} more` : "—";
    if (otherItems.length) otherCell.title = otherItems.map(({correction}) => correction.field).join(", ");
    row.appendChild(otherCell);
    const choices = group.items.map(({index}) => reviewChoices[index].choice);
    const status = choices.includes("edited") ? "Edited" : choices.includes("original") ? "Original" : "Ready";
    const statusCell = document.createElement("td");
    const statusChip = document.createElement("span");
    statusChip.className = `row-status is-${status.toLowerCase()}`;
    statusChip.textContent = status;
    statusCell.appendChild(statusChip);
    const fileCell = document.createElement("td");
    fileCell.className = "file-cell";
    fileCell.title = group.filename;
    fileCell.textContent = group.filename;
    row.append(statusCell, fileCell);
    row.querySelector(".row-select").addEventListener("change", (event) => {
      if (event.target.checked) selectedReviewRows.add(group.key); else selectedReviewRows.delete(group.key);
    });
    body.appendChild(row);
  });
  table.appendChild(body);
  wrap.appendChild(table);
  correctionsList.appendChild(wrap);
  const selectPage = table.querySelector("#select-page");
  selectPage.checked = pageGroups.length > 0 && pageGroups.every((group) => selectedReviewRows.has(group.key));
  selectPage.addEventListener("change", (event) => {
    pageGroups.forEach((group) => event.target.checked ? selectedReviewRows.add(group.key) : selectedReviewRows.delete(group.key));
    renderCorrectionGroups();
  });

  reviewPagination.hidden = false;
  reviewPrev.disabled = reviewPage <= 1;
  reviewNext.disabled = reviewPage >= pageCount;
  const firstRow = matchingGroups.length ? (reviewPage - 1) * pageSize + 1 : 0;
  const lastRow = Math.min(reviewPage * pageSize, matchingGroups.length);
  reviewPageInfo.textContent = `${formatNumber(firstRow)}–${formatNumber(lastRow)} of ${formatNumber(matchingGroups.length)} SKUs`;
}

function buildReviewFieldCell(group, field) {
  const cell = document.createElement("td");
  cell.className = "editable-cell";
  const matches = group.items.filter(({correction}) => correction.field === field);
  if (!matches.length) {
    const sourceKey = {
      "Title": "Source Uploaded Title",
      "Item Name": "Source Amazon Title (Item Name)",
      "Item Highlight": "Source Item Highlight",
    }[field];
    const sourceValue = String(group.context?.[sourceKey] || "");
    if (!sourceValue) {
      cell.textContent = "—";
      cell.classList.add("is-empty");
      return cell;
    }
    const sourceEditor = document.createElement("textarea");
    sourceEditor.value = sourceValue;
    sourceEditor.readOnly = true;
    sourceEditor.rows = Math.max(2, Math.min(4, Math.ceil(sourceValue.length / (field === "Item Highlight" ? 42 : 48))));
    sourceEditor.setAttribute("aria-label", `${field} source value for SKU ${group.sku}`);
    const sourceMeta = document.createElement("div");
    sourceMeta.className = "cell-meta";
    const limit = {"Title": 200, "Item Name": 75, "Item Highlight": 125}[field];
    sourceMeta.textContent = `${sourceValue.length}/${limit} · From uploaded file · Read only`;
    cell.append(sourceEditor, sourceMeta);
    return cell;
  }
  const { correction, index } = matches[0];
  const editor = document.createElement("textarea");
  editor.value = reviewChoices[index].choice === "original" ? correction.original : reviewChoices[index].value;
  editor.readOnly = !reviewIsEditable;
  editor.setAttribute("aria-label", `${field} for SKU ${group.sku}`);
  editor.title = `Original: ${correction.original || "Empty"}`;
  const meta = document.createElement("div");
  meta.className = "cell-meta";
  const limit = {"Title": 200, "Item Name": 75, "Item Highlight": 125}[field];
  const count = document.createElement("span");
  count.textContent = limit ? `${editor.value.length}/${limit}` : `${editor.value.length}`;
  const restore = document.createElement("button");
  restore.type = "button";
  restore.textContent = "↶";
  restore.setAttribute("aria-label", "Restore original value");
  restore.title = "Use original value";
  restore.hidden = !reviewIsEditable;
  restore.addEventListener("click", () => {
    reviewChoices[index] = {choice:"original", value:correction.original};
    editor.value = correction.original;
    renderCorrectionGroups();
  });
  const aiButton = document.createElement("button");
  aiButton.type = "button";
  aiButton.className = "ai-optimize-button";
  aiButton.textContent = "✦";
  aiButton.setAttribute("aria-label", `Optimize ${field} with OpenAI`);
  aiButton.title = "Optimize with OpenAI";
  aiButton.hidden = !reviewIsEditable;
  const aiCellStatus = document.createElement("span");
  aiCellStatus.className = "ai-cell-status";
  aiButton.addEventListener("click", () => optimizeWithAI({button:aiButton, group, correction, index, editor, count, limit, status:aiCellStatus}));
  editor.addEventListener("input", () => {
    reviewChoices[index] = {choice:"edited", value:editor.value};
    count.textContent = limit ? `${editor.value.length}/${limit}` : `${editor.value.length}`;
    const row = editor.closest("tr");
    row.querySelector(".row-status").textContent = "Edited";
    row.querySelector(".row-status").className = "row-status is-edited";
  });
  const estimatedLines = Math.max(2, Math.min(4, Math.ceil(editor.value.length / (field === "Item Highlight" ? 42 : 48))));
  editor.rows = estimatedLines;
  const cellActions = document.createElement("span");
  cellActions.className = "cell-actions";
  cellActions.append(aiButton, restore);
  meta.append(count, aiCellStatus, cellActions);
  cell.append(editor, meta);
  if (matches.length > 1) {
    const more = document.createElement("small");
    more.textContent = `+${matches.length - 1} linked field`;
    cell.appendChild(more);
  }
  return cell;
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

function updateReviewCount() {
  if (!reviewCorrections.length) return;
  const skuCount = new Set(reviewCorrections.map((item) => `${item.filename}\u0000${item.sku}`)).size;
  reviewCount.textContent = `${formatNumber(reviewCorrections.length)} changes · ${formatNumber(skuCount)} SKUs`;
}

reviewToolbar.addEventListener("click", (event) => {
  const value = event.target.dataset.reviewAll;
  if (!value) return;
  reviewCorrections.forEach((correction, index) => {
    const key = `${correction.filename}\u0000${correction.sku}`;
    if (selectedReviewRows.has(key)) reviewChoices[index] = { choice: value, value: value === "original" ? correction.original : correction.fixed };
  });
  renderCorrectionGroups();
  updateReviewCount();
});

reviewSearch.addEventListener("input", () => {
  reviewPage = 1;
  renderCorrectionGroups();
});
reviewFileFilter.addEventListener("change", () => { reviewPage = 1; renderCorrectionGroups(); });
reviewStatusFilter.addEventListener("change", () => { reviewPage = 1; renderCorrectionGroups(); });
reviewPageSize.addEventListener("change", () => { reviewPage = 1; renderCorrectionGroups(); });
reviewPrev.addEventListener("click", () => { if (reviewPage > 1) { reviewPage -= 1; renderCorrectionGroups(); } });
reviewNext.addEventListener("click", () => { reviewPage += 1; renderCorrectionGroups(); });
function confirmDiscardReview() {
  if (!reviewIsEditable || reviewSubmit.hidden || !reviewCorrections.length) return true;
  return window.confirm("You have reviewed changes that have not been applied. Discard them and continue?");
}

function clearBatchSources({keepReference = false} = {}) {
  if (!keepReference) referenceInput.value = "";
  templatesInput.value = "";
  templateFolderInput.value = "";
  folderTokenInput.value = "";
  reportSourceInput.value = "";
  processingReportInput.value = "";
  templateFolderList.textContent = "No folder selected";
  updateFileLabels();
}

newBatchButton.addEventListener("click", () => {
  if (!confirmDiscardReview()) return;
  clearBatchSources({keepReference:true});
  resetResults(activeMode);
  setBadge("Ready");
  setMeter(0);
  window.scrollTo({top: 0, behavior: "smooth"});
});

startOverButton.addEventListener("click", () => {
  if (!confirmDiscardReview()) return;
  batchForm.reset();
  reportForm.reset();
  clearBatchSources();
  setMode("batch");
  window.scrollTo({top: 0, behavior: "smooth"});
});

function openAISettings(message = "") {
  aiSettingsModal.hidden = false;
  if (message) aiSettingsStatus.textContent = message;
  window.setTimeout(() => aiApiKey.focus(), 0);
}

function closeAISettings() {
  aiSettingsModal.hidden = true;
  aiApiKey.value = "";
}

aiSettingsButton.addEventListener("click", () => openAISettings());
aiSettingsClose.addEventListener("click", closeAISettings);
aiSettingsCancel.addEventListener("click", closeAISettings);
aiSettingsModal.addEventListener("click", (event) => { if (event.target === aiSettingsModal) closeAISettings(); });
aiSettingsSave.addEventListener("click", async () => {
  aiSettingsSave.disabled = true;
  aiSettingsStatus.textContent = "Saving…";
  try {
    const response = await fetch("/api/ai/config", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({api_key:aiApiKey.value, model:aiModel.value})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Settings could not be saved.");
    aiConfigured = Boolean(data.configured);
    aiSettingsStatus.textContent = aiConfigured ? "Ready for this session" : "Enter an API key to enable optimization";
    if (aiConfigured) window.setTimeout(closeAISettings, 450);
  } catch (error) {
    aiSettingsStatus.textContent = error.message;
  } finally {
    aiSettingsSave.disabled = false;
  }
});

async function optimizeWithAI({button, group, correction, index, editor, count, limit, status}) {
  if (!aiConfigured) {
    openAISettings("Add an API key before optimizing a field.");
    return;
  }
  // Start with every populated source column from this SKU, then overlay the
  // latest reviewed values so the model sees both complete evidence and edits.
  const context = {...(group.context || {})};
  group.items.forEach(({correction:item, index:itemIndex}) => {
    const choice = reviewChoices[itemIndex];
    context[`Reviewed ${item.field}`] = choice.choice === "original" ? item.original : choice.value;
  });
  button.disabled = true;
  button.textContent = "…";
  status.textContent = "Optimizing";
  try {
    const response = await fetch("/api/ai/optimize", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({field:correction.field, current:editor.value, context})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "AI optimization failed.");
    reviewChoices[index] = {choice:"edited", value:data.value};
    editor.value = data.value;
    count.textContent = `${data.length}/${data.limit || limit}`;
    editor.rows = Math.max(2, Math.min(4, Math.ceil(editor.value.length / (correction.field === "Item Highlight" ? 42 : 48))));
    const row = editor.closest("tr");
    row.querySelector(".row-status").textContent = "AI edited";
    row.querySelector(".row-status").className = "row-status is-edited";
    status.textContent = "AI";
  } catch (error) {
    status.textContent = error.message;
    status.title = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "✦";
  }
}

fetch("/api/ai/status").then((response) => response.json()).then((data) => {
  aiConfigured = Boolean(data.configured);
  aiModel.value = data.model || "gpt-5.6-terra";
  aiSettingsStatus.textContent = aiConfigured ? "Ready for this session" : "Not configured";
}).catch(() => {});

reviewSubmit.addEventListener("click", async () => {
  reviewSubmit.disabled = true;
  reviewSubmit.textContent = "Applying changes...";
  const decisions = reviewCorrections.map((correction, index) => {
    const decision = reviewChoices[index];
    return { filename: correction.filename, row: correction.row, column: correction.column, value: decision.choice === "original" ? correction.original : decision.choice === "edited" ? decision.value : correction.fixed };
  });
  try {
    const response = await fetch(`/api/review/${activeJobId}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decisions }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The reviewed changes could not be applied.");
    showDownload(data.download_url);
    reviewToolbar.hidden = true;
    reviewSubmit.hidden = true;
    reviewHelp.textContent = "Your reviewed workbook is ready to download.";
    setBadge("Reviewed", "is-done");
  } catch (error) {
    errorsBox.hidden = false;
    errorsBox.textContent = error.message;
  } finally {
    reviewSubmit.disabled = false;
    reviewSubmit.textContent = "Apply reviewed changes";
  }
});
