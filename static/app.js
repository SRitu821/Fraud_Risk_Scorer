/**
 * SentinelRisk Dashboard Frontend Logic
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const tabs = document.querySelectorAll(".nav-tab");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const scoringForm = document.getElementById("scoring-form");
  const resetBtn = document.getElementById("btn-reset-form");
  const reseedBtn = document.getElementById("btn-reseed");
  const filterBtns = document.querySelectorAll(".filter-btn");
  const searchInput = document.getElementById("filter-search");
  const presetBtns = document.querySelectorAll(".preset-btn");
  
  // Results Elements
  const gaugeArc = document.getElementById("gauge-arc");
  const scoreVal = document.getElementById("score-val");
  const badgeRiskLevel = document.getElementById("badge-risk-level");
  const recAction = document.getElementById("rec-action");
  const recDesc = document.getElementById("rec-desc");
  const triggeredList = document.getElementById("triggered-list");
  const rawJsonOutput = document.getElementById("raw-json-output");
  
  // Modal Elements
  const modal = document.getElementById("audit-modal");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const modalDismissBtn = document.getElementById("modal-dismiss-btn");
  const modalApproveBtn = document.getElementById("modal-approve-btn");
  const modalRejectBtn = document.getElementById("modal-reject-btn");
  const modalTitle = document.getElementById("modal-title");
  const modalSub = document.getElementById("modal-sub");
  const modalContent = document.getElementById("modal-content");

  let currentActiveReturnId = null;
  let currentFilter = "all";
  let searchDebounceTimer = null;

  // Preset Data dictionary matching retail scenarios
  const PRESETS = {
    genuine: {
      customer_id: "CUST_1008",
      order_value: 1250,
      total_orders: 12,
      total_returns: 1,
      delivery_address: "88 Brigade Road, Bengaluru",
      return_address: "88 Brigade Road, Bengaluru",
      return_reason: "wrong_size",
      days_since_delivery: 6,
      damaged_returns_count: 0,
      returns_last_7_days: 0,
      is_sale: false
    },
    serial: {
      customer_id: "CUST_1042",
      order_value: 2499,
      total_orders: 14,
      total_returns: 11,
      delivery_address: "12 MG Road, Pune",
      return_address: "12 MG Road, Pune",
      return_reason: "changed_mind",
      days_since_delivery: 8,
      damaged_returns_count: 1,
      returns_last_7_days: 1,
      is_sale: false
    },
    address: {
      customer_id: "CUST_1042",
      order_value: 2499,
      total_orders: 14,
      total_returns: 11,
      delivery_address: "12 MG Road, Pune",
      return_address: "45 Park Street, Kolkata",
      return_reason: "item_damaged",
      days_since_delivery: 2,
      damaged_returns_count: 3,
      returns_last_7_days: 0,
      is_sale: false
    },
    damage: {
      customer_id: "CUST_1077",
      order_value: 1890,
      total_orders: 6,
      total_returns: 4,
      delivery_address: "14 Marine Drive, Mumbai",
      return_address: "14 Marine Drive, Mumbai",
      return_reason: "item_damaged",
      days_since_delivery: 4,
      damaged_returns_count: 3,
      returns_last_7_days: 0,
      is_sale: false
    },
    wardrobing: {
      customer_id: "CUST_1093",
      order_value: 4850,
      total_orders: 3,
      total_returns: 2,
      delivery_address: "102 Connaught Place, New Delhi",
      return_address: "102 Connaught Place, New Delhi",
      return_reason: "changed_mind",
      days_since_delivery: 2,
      damaged_returns_count: 0,
      returns_last_7_days: 0,
      is_sale: true
    },
    newbie: {
      customer_id: "CUST_1105",
      order_value: 3600,
      total_orders: 1,
      total_returns: 1,
      delivery_address: "56 Anna Salai, Chennai",
      return_address: "56 Anna Salai, Chennai",
      return_reason: "wrong_size",
      days_since_delivery: 5,
      damaged_returns_count: 0,
      returns_last_7_days: 0,
      is_sale: false
    }
  };

  // =========================================================================
  // Tab Navigation
  // =========================================================================
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      tab.classList.add("active");
      const targetPane = document.getElementById(tab.dataset.tab);
      if (targetPane) targetPane.classList.add("active");

      if (tab.dataset.tab === "queue-tab") {
        loadReturnsTable();
      } else if (tab.dataset.tab === "rules-tab") {
        loadRulesMatrix();
      }
    });
  });

  // =========================================================================
  // Toast Helper
  // =========================================================================
  function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    setTimeout(() => {
      toast.className = "toast";
    }, 3500);
  }

  // =========================================================================
  // Load Stats Banner
  // =========================================================================
  async function loadStats() {
    try {
      const res = await fetch("/api/stats");
      if (!res.ok) return;
      const data = await res.json();

      document.getElementById("stat-total-returns").textContent = data.total_returns.toLocaleString();
      document.getElementById("stat-total-customers").textContent = `Across ${data.total_customers} customers`;
      
      const lowPct = data.total_returns > 0 ? Math.round((data.low_risk_count / data.total_returns) * 100) : 0;
      document.getElementById("stat-low-returns").textContent = data.low_risk_count.toLocaleString();
      document.getElementById("stat-low-pct").textContent = `${lowPct}% auto-approved`;

      document.getElementById("stat-medium-returns").textContent = data.medium_risk_count.toLocaleString();
      
      document.getElementById("stat-high-returns").textContent = data.high_risk_count.toLocaleString();
      document.getElementById("stat-high-value").textContent = `₹${data.high_risk_value_protected.toLocaleString()} protected`;

      // Update badge in review queue tab
      const pendingBadge = document.getElementById("pending-badge");
      if (pendingBadge) {
        pendingBadge.textContent = data.pending_high_reviews || data.high_risk_count;
      }
    } catch (err) {
      console.error("Error loading stats:", err);
    }
  }

  // =========================================================================
  // Update Gauge & Results Display
  // =========================================================================
  function renderScoringResult(data) {
    const score = data.risk_score;
    const level = data.risk_level;
    const recommendation = data.recommendation;

    // Update gauge
    // Circumference = 2 * PI * 72 = ~452.39
    const circumference = 2 * Math.PI * 72;
    const offset = circumference - (score / 100) * circumference;
    gaugeArc.style.strokeDashoffset = offset;

    // Gauge color
    let color = "var(--low-color)";
    if (level === "medium") color = "var(--medium-color)";
    if (level === "high") color = "var(--high-color)";
    gaugeArc.style.stroke = color;

    // Number
    scoreVal.textContent = score;

    // Badge
    badgeRiskLevel.textContent = `${level.toUpperCase()} RISK`;
    badgeRiskLevel.className = `badge-status ${level}`;

    // Recommendation
    const actionMap = {
      auto_approve: "Auto-Approve Return",
      light_review: "Secondary Verification Required",
      route_to_manual_review: "Flag for Manual Review"
    };
    const descMap = {
      auto_approve: "Customer exhibits normal return behavior. Generate instant prepaid return label and authorize immediate refund.",
      light_review: "Moderate risk detected. Require customer to submit item condition photos before shipping authorization.",
      route_to_manual_review: "Suspicious abuse detected. Route to fraud team before authorizing refund. Inspect merchandise under CCTV upon receipt."
    };

    recAction.textContent = actionMap[recommendation] || recommendation;
    recAction.className = `rec-action ${level}`;
    recDesc.textContent = descMap[recommendation] || "Review triggered conditions.";

    // Triggered List
    triggeredList.innerHTML = "";
    if (!data.breakdown || data.breakdown.length === 0) {
      triggeredList.innerHTML = `<div class="empty-trigger-msg">No suspicious red flags triggered. Low risk genuine profile.</div>`;
    } else {
      data.breakdown.forEach(item => {
        const isMed = item.points < 20;
        const card = document.createElement("div");
        card.className = `trigger-card ${isMed ? "medium-rule" : ""}`;
        card.innerHTML = `
          <div class="trigger-card-header">
            <span class="trigger-name">${item.name}</span>
            <span class="trigger-pts">+${item.points} pts</span>
          </div>
          <div class="trigger-reason">${item.reason}</div>
        `;
        triggeredList.appendChild(card);
      });
    }

    // JSON Raw Output
    rawJsonOutput.textContent = JSON.stringify(data, null, 2);
  }

  // =========================================================================
  // Submit Scoring Form
  // =========================================================================
  scoringForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      customer_id: document.getElementById("inp-customer-id").value.trim(),
      order_value: parseFloat(document.getElementById("inp-order-value").value),
      total_orders: parseInt(document.getElementById("inp-total-orders").value, 10),
      total_returns: parseInt(document.getElementById("inp-total-returns").value, 10),
      delivery_address: document.getElementById("inp-delivery-address").value.trim(),
      return_address: document.getElementById("inp-return-address").value.trim(),
      return_reason: document.getElementById("inp-return-reason").value,
      days_since_delivery: parseInt(document.getElementById("inp-days-delivery").value, 10),
      damaged_returns_count: parseInt(document.getElementById("inp-damaged-count").value, 10),
      returns_last_7_days: parseInt(document.getElementById("inp-recent-returns").value, 10),
      is_sale_period: document.getElementById("inp-is-sale").checked,
      save_record: true
    };

    const submitBtn = document.getElementById("btn-submit-score");
    submitBtn.disabled = true;
    submitBtn.innerHTML = `Scoring...`;

    try {
      const res = await fetch("/api/score-return", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(`Scoring failed: ${res.statusText}`);
      }

      const result = await res.json();
      renderScoringResult(result);
      showToast(`Scored ${payload.customer_id}: ${result.risk_level.toUpperCase()} (${result.risk_score} pts)`, result.risk_level === "high" ? "error" : "success");
      loadStats();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        Calculate Risk Score
      `;
    }
  });

  // =========================================================================
  // Load Presets
  // =========================================================================
  function applyPreset(presetKey) {
    const p = PRESETS[presetKey];
    if (!p) return;

    document.getElementById("inp-customer-id").value = p.customer_id;
    document.getElementById("inp-order-value").value = p.order_value;
    document.getElementById("inp-total-orders").value = p.total_orders;
    document.getElementById("inp-total-returns").value = p.total_returns;
    document.getElementById("inp-delivery-address").value = p.delivery_address;
    document.getElementById("inp-return-address").value = p.return_address;
    document.getElementById("inp-return-reason").value = p.return_reason;
    document.getElementById("inp-days-delivery").value = p.days_since_delivery;
    document.getElementById("inp-damaged-count").value = p.damaged_returns_count;
    document.getElementById("inp-recent-returns").value = p.returns_last_7_days;
    document.getElementById("inp-is-sale").checked = p.is_sale;

    // Trigger immediate score
    scoringForm.dispatchEvent(new Event("submit"));
  }

  presetBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      applyPreset(btn.dataset.preset);
    });
  });

  resetBtn.addEventListener("click", () => {
    scoringForm.reset();
  });

  // =========================================================================
  // Returns Review Queue Table
  // =========================================================================
  async function loadReturnsTable() {
    const tbody = document.getElementById("returns-table-body");
    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4">Loading queue records...</td></tr>`;

    const searchQuery = searchInput.value.trim();
    let url = `/api/returns?risk_level=${currentFilter}&limit=100`;
    if (searchQuery) url += `&search=${encodeURIComponent(searchQuery)}`;

    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to load returns");
      const data = await res.json();

      if (!data.returns || data.returns.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4">No returns match the selected filter.</td></tr>`;
        return;
      }

      tbody.innerHTML = "";
      data.returns.forEach(r => {
        const tr = document.createElement("tr");

        // Format reasons tags
        const reasonsList = r.reasons && r.reasons.length > 0
          ? r.reasons.map(reason => `<span class="reason-tag">${reason.replace(/_/g, ' ')}</span>`).join("")
          : `<span class="text-dim">None</span>`;

        tr.innerHTML = `
          <td><span class="id-badge">${r.return_id}</span></td>
          <td>
            <div style="font-weight:600; color:white;">${r.customer_id}</div>
            <div class="text-dim" style="font-size:0.75rem;">${r.order_id}</div>
          </td>
          <td>₹${Number(r.order_value).toLocaleString()}</td>
          <td><span class="score-badge ${r.risk_level}">${r.risk_score}</span></td>
          <td><span class="badge-status ${r.risk_level}">${r.risk_level}</span></td>
          <td><div class="reasons-tags">${reasonsList}</div></td>
          <td><span class="status-pill ${r.review_status || 'pending'}" id="status-pill-${r.return_id}">${r.review_status || 'pending'}</span></td>
          <td>
            <button class="btn btn-secondary btn-sm inspect-btn" data-return='${JSON.stringify(r).replace(/'/g, "&apos;")}'>
              Inspect
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      // Bind inspect buttons
      document.querySelectorAll(".inspect-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          const item = JSON.parse(btn.dataset.return);
          openAuditModal(item);
        });
      });
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4" style="color:var(--high-color);">Error: ${err.message}</td></tr>`;
    }
  }

  // Filter Buttons
  filterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      filterBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.dataset.filter;
      loadReturnsTable();
    });
  });

  // Search input debounce
  searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      loadReturnsTable();
    }, 350);
  });

  // =========================================================================
  // Audit Modal
  // =========================================================================
  function openAuditModal(item) {
    currentActiveReturnId = item.return_id;
    modalTitle.textContent = `Return Dossier: ${item.return_id}`;
    modalSub.textContent = `Associated Order: ${item.order_id} • Customer: ${item.customer_id}`;

    let breakdownHtml = "";
    if (item.breakdown && item.breakdown.length > 0) {
      breakdownHtml = item.breakdown.map(b => `
        <div class="trigger-card ${b.points < 20 ? 'medium-rule' : ''}" style="margin-bottom:8px;">
          <div class="trigger-card-header">
            <span class="trigger-name">${b.name}</span>
            <span class="trigger-pts">+${b.points} pts</span>
          </div>
          <div class="trigger-reason">${b.reason}</div>
          <div style="font-size:0.75rem; color:var(--text-dim); margin-top:4px;">${b.explanation}</div>
        </div>
      `).join("");
    } else {
      breakdownHtml = `<div class="empty-trigger-msg">No fraud flags triggered. Standard return procedure.</div>`;
    }

    modalContent.innerHTML = `
      <div class="dossier-grid">
        <div class="dossier-item">
          <span class="dossier-k">Risk Score & Level</span>
          <span class="dossier-v" style="color:var(--${item.risk_level}-color); font-weight:700;">
            ${item.risk_score} / 100 (${item.risk_level.toUpperCase()})
          </span>
        </div>
        <div class="dossier-item">
          <span class="dossier-k">Order Value</span>
          <span class="dossier-v">₹${Number(item.order_value).toLocaleString()}</span>
        </div>
        <div class="dossier-item">
          <span class="dossier-k">Return Reason</span>
          <span class="dossier-v" style="font-family:var(--font-mono);">${item.return_reason}</span>
        </div>
        <div class="dossier-item">
          <span class="dossier-k">Current Audit Status</span>
          <span class="dossier-v status-pill ${item.review_status || 'pending'}">${item.review_status || 'pending'}</span>
        </div>
        <div class="dossier-item" style="grid-column: span 2;">
          <span class="dossier-k">Original Delivery Address</span>
          <span class="dossier-v">${item.delivery_address || 'N/A'}</span>
        </div>
        <div class="dossier-item" style="grid-column: span 2;">
          <span class="dossier-k">Requested Return / Refund Address</span>
          <span class="dossier-v">${item.return_address || 'N/A'}</span>
        </div>
      </div>

      <div>
        <h4 style="font-size:0.85rem; text-transform:uppercase; color:var(--text-dim); margin-bottom:10px;">
          Engine Evaluation & Flag Analysis
        </h4>
        ${breakdownHtml}
      </div>
    `;

    modal.classList.add("open");
  }

  function closeModal() {
    modal.classList.remove("open");
    currentActiveReturnId = null;
  }

  modalCloseBtn.addEventListener("click", closeModal);
  modalDismissBtn.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  // Modal Review Actions
  async function submitReviewDecision(status) {
    if (!currentActiveReturnId) return;
    try {
      const res = await fetch(`/api/returns/${currentActiveReturnId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status })
      });
      if (!res.ok) throw new Error("Failed to record decision");
      showToast(`Return ${currentActiveReturnId} marked as ${status}`, status === "approved" ? "success" : "error");

      // Update in table if visible
      const pill = document.getElementById(`status-pill-${currentActiveReturnId}`);
      if (pill) {
        pill.textContent = status;
        pill.className = `status-pill ${status}`;
      }
      closeModal();
      loadStats();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  modalApproveBtn.addEventListener("click", () => submitReviewDecision("approved"));
  modalRejectBtn.addEventListener("click", () => submitReviewDecision("rejected"));

  // =========================================================================
  // Rules Matrix Tab
  // =========================================================================
  async function loadRulesMatrix() {
    const grid = document.getElementById("rules-grid");
    grid.innerHTML = `<div class="text-center py-4" style="grid-column:1/-1;">Loading active rules...</div>`;

    try {
      const res = await fetch("/api/rules");
      if (!res.ok) throw new Error("Failed to load rules");
      const rules = await res.json();

      grid.innerHTML = "";
      rules.forEach(rule => {
        const card = document.createElement("div");
        card.className = "card glass rule-card";
        card.innerHTML = `
          <div class="rule-card-top">
            <div>
              <span class="rule-card-cat">${rule.category.replace(/_/g, ' ')}</span>
              <div class="rule-card-title">${rule.name}</div>
            </div>
            <span class="rule-card-points">+${rule.points} pts</span>
          </div>
          <div class="rule-card-desc">${rule.explanation}</div>
        `;
        grid.appendChild(card);
      });
    } catch (err) {
      grid.innerHTML = `<div style="color:var(--high-color); grid-column:1/-1;">Failed to load rules: ${err.message}</div>`;
    }
  }

  // =========================================================================
  // Reseed Dataset Button
  // =========================================================================
  reseedBtn.addEventListener("click", async () => {
    if (!confirm("Regenerate synthetic dataset? This will generate fresh customers, orders, and returns.")) {
      return;
    }

    reseedBtn.disabled = true;
    reseedBtn.querySelector("span").textContent = "Generating...";

    try {
      const res = await fetch("/api/generate-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ num_customers: 600 })
      });

      if (!res.ok) throw new Error("Dataset generation failed");
      const data = await res.json();

      showToast(`Generated ${data.summary.customers_created} customers and ${data.summary.returns_created} returns!`, "success");
      loadStats();
      if (document.getElementById("queue-tab").classList.contains("active")) {
        loadReturnsTable();
      }
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      reseedBtn.disabled = false;
      reseedBtn.querySelector("span").textContent = "Regenerate Data";
    }
  });

  // Initial Load
  loadStats();
  applyPreset("address"); // Pre-populate with realistic suspicious case
});
