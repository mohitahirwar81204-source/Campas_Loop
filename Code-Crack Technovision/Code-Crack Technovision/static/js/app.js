const state = {
  products: [],
  categories: [],
  priority: "balanced",
  recommendations: null,
  shortlist: new Set(JSON.parse(localStorage.getItem("campusloop-shortlist") || "[]")),
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const categoryGlyphs = {
  laptop: "LP",
  bicycle: "BI",
  book: "BK",
  gadget: "GD",
  furniture: "FR",
};

const searchCategoryAliases = {
  book: "book",
  books: "book",
  textbook: "book",
  textbooks: "book",
  bicycle: "bicycle",
  bicycles: "bicycle",
  cycle: "bicycle",
  cycles: "bicycle",
  bike: "bicycle",
  bikes: "bicycle",
  laptop: "laptop",
  laptops: "laptop",
  computer: "laptop",
  computers: "laptop",
  notebook: "laptop",
  notebooks: "laptop",
  gadget: "gadget",
  gadgets: "gadget",
  electronics: "gadget",
  tech: "gadget",
  furniture: "furniture",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
      else if (Array.isArray(body.detail)) message = body.detail[0]?.msg || message;
    } catch (_) {
      // Keep the status-based message for non-JSON errors.
    }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function showToast(message, isError = false) {
  const toast = $("#toast");
  $("#toastMessage").textContent = message;
  $("#toastIcon").textContent = isError ? "!" : "✓";
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 3200);
}

function currentBudget() {
  return Math.max(1, Number($("#budgetInput").value) || 23000);
}

function glyphFor(category) {
  const key = String(category || "").toLowerCase();
  return categoryGlyphs[key] || key.slice(0, 2).toUpperCase() || "IT";
}

function populateCategoryControls() {
  const options = state.categories
    .map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`)
    .join("");
  const recommendationValue = $("#recommendationCategory").value;
  const filterValue = $("#categoryFilter").value;
  $("#recommendationCategory").innerHTML = options;
  $("#categoryFilter").innerHTML = `<option value="">All categories</option>${options}`;
  $("#categoryOptions").innerHTML = options;
  const defaultCategory = state.categories.find((category) => category.toLowerCase() === "laptop") || state.categories[0] || "";
  $("#recommendationCategory").value = state.categories.includes(recommendationValue) ? recommendationValue : defaultCategory;
  $("#categoryFilter").value = filterValue;
}

function renderMetrics() {
  const budget = currentBudget();
  $("#listingCount").textContent = state.products.length;
  $("#categoryCount").textContent = new Set(state.products.map((p) => p.category.toLowerCase())).size;
  $("#withinBudgetCount").textContent = state.products.filter((p) => p.price <= budget).length;
  $("#unusualCount").textContent = state.products.filter((p) => p.is_unusual).length;
  $("#budgetLabel").textContent = new Intl.NumberFormat("en-IN").format(budget);
}

function filteredProducts() {
  const search = $("#searchInput").value.trim().toLowerCase();
  const searchTokens = search.split(/\s+/).filter(Boolean);
  const category = $("#categoryFilter").value.toLowerCase();
  const budgetOnly = $("#budgetOnly").checked;
  const budget = currentBudget();
  const products = state.products.filter((product) => {
    const searchableText = `${product.title} ${product.category} ${product.condition || ""}`.toLowerCase();
    const matchesName = searchTokens.every((token) => {
      const categoryAlias = searchCategoryAliases[token];
      if (token.length === 1) {
        return product.title.toLowerCase().split(/\W+/).includes(token);
      }
      return categoryAlias
        ? product.category.toLowerCase() === categoryAlias
        : searchableText.includes(token);
    });
    const matchesCategory = !category || product.category.toLowerCase() === category;
    const matchesBudget = !budgetOnly || product.price <= budget;
    return matchesName && matchesCategory && matchesBudget;
  });
  const sort = $("#sortFilter").value;
  const sorters = {
    "price-low": (a, b) => a.price - b.price,
    "price-high": (a, b) => b.price - a.price,
    discount: (a, b) => (a.price_ratio ?? 1) - (b.price_ratio ?? 1),
    newest: (a, b) => (a.age ?? 999) - (b.age ?? 999),
  };
  return sorters[sort] ? products.sort(sorters[sort]) : products;
}

function scrollToMarketplace() {
  const marketplace = $("#marketplace");
  const headerHeight = $(".commerce-header").offsetHeight;
  const targetTop = marketplace.getBoundingClientRect().top + window.scrollY - headerHeight - 14;
  window.scrollTo({ top: Math.max(0, targetTop), behavior: "smooth" });
}

function priceIndicator(product) {
  if (product.price_ratio == null) return `<span title="Original price is missing">Not available</span>`;
  const percent = Math.round(product.price_ratio * 100);
  return `<strong>${percent}%</strong> <span>of original</span>`;
}

function priceStatus(product) {
  if (product.comparable_count < 3) {
    return `<span class="status-chip insufficient" title="${escapeHtml(product.anomaly_reason)}">Limited data</span>`;
  }
  if (product.is_unusual) {
    return `<span class="status-chip review" title="${escapeHtml(product.anomaly_reason)}">! Review price</span>`;
  }
  return `<span class="status-chip ok">✓ Near median</span>`;
}

function renderProducts() {
  const products = filteredProducts();
  $("#resultCount").textContent = `${products.length} of ${state.products.length} listings`;
  $("#emptyState").hidden = products.length !== 0;
  $("#productGrid").innerHTML = products.map((product) => {
    const conditionClass = product.condition ? product.condition.toLowerCase() : "missing";
    const discount = product.price_ratio == null ? null : Math.max(0, Math.round((1 - product.price_ratio) * 100));
    const shortListed = state.shortlist.has(product.id);
    return `
      <article class="product-card" data-product-id="${product.id}" data-price="${product.price}">
        <div class="product-media media-${escapeHtml(product.category.toLowerCase())}">
          ${discount != null ? `<span class="deal-badge">${discount}% off</span>` : `<span class="deal-badge neutral">Smart deal</span>`}
          <button class="heart-button ${shortListed ? "active" : ""}" type="button" data-shortlist-id="${product.id}" aria-label="${shortListed ? "Remove from" : "Add to"} shortlist">♥</button>
          ${productVisual(product.category)}
          <span class="media-category">${escapeHtml(product.category)}</span>
        </div>
        <div class="product-content">
          <div class="product-meta"><span>Listing #${product.id}</span><span>${product.age == null ? "Age not shared" : `${product.age} yr old`}</span></div>
          <h3 title="${escapeHtml(product.title)}">${escapeHtml(product.title)}</h3>
          <div class="card-condition"><span class="condition-chip ${escapeHtml(conditionClass)}">${escapeHtml(product.condition || "Not provided")}</span>${priceStatus(product)}</div>
          <div class="card-price"><strong>${money.format(product.price)}</strong>${product.original_price == null ? "" : `<del>${money.format(product.original_price)}</del>`}${discount ? `<span>${discount}% saved</span>` : ""}</div>
          <div class="price-evidence"><span>Price ratio</span><b>${product.price_ratio == null ? "Unavailable" : `${Math.round(product.price_ratio * 100)}% of original`}</b></div>
          <div class="product-actions"><button class="analyse-button" type="button" data-edit-id="${product.id}">Edit listing</button><button class="shortlist-text" type="button" data-shortlist-id="${product.id}">${shortListed ? "Shortlisted" : "+ Shortlist"}</button></div>
        </div>
      </article>`;
  }).join("");
}

function productVisual(category) {
  const type = String(category || "").toLowerCase();
  const visuals = {
    laptop: `<svg viewBox="0 0 180 120" aria-hidden="true"><rect x="35" y="16" width="110" height="72" rx="7"/><rect class="screen" x="43" y="24" width="94" height="56" rx="2"/><path d="M23 94h134l-12 12H35z"/></svg>`,
    bicycle: `<svg viewBox="0 0 180 120" aria-hidden="true"><circle cx="48" cy="83" r="26"/><circle cx="134" cy="83" r="26"/><path d="M48 83l31-43 27 43H48l23-31h50l13 31M77 40H62M105 34h21"/></svg>`,
    book: `<svg viewBox="0 0 180 120" aria-hidden="true"><path d="M28 24c23-7 42-2 62 12v70c-20-14-39-19-62-12z"/><path d="M152 24c-23-7-42-2-62 12v70c20-14 39-19 62-12z"/><path class="detail" d="M42 43c14-2 24 1 36 7M42 56c14-2 24 1 36 7M138 43c-14-2-24 1-36 7M138 56c-14-2-24 1-36 7"/></svg>`,
    gadget: `<svg viewBox="0 0 180 120" aria-hidden="true"><rect x="57" y="11" width="66" height="98" rx="12"/><rect class="screen" x="64" y="23" width="52" height="68" rx="4"/><circle cx="90" cy="100" r="3"/><path class="detail" d="M75 43h30M75 53h21"/></svg>`,
    furniture: `<svg viewBox="0 0 180 120" aria-hidden="true"><path d="M48 54h84v31H48zM55 84v25M125 84v25M60 54V25h60v29M70 34h40"/></svg>`,
  };
  return `<div class="product-illustration">${visuals[type] || `<span>${glyphFor(category)}</span>`}</div>`;
}

function renderRecommendations(data) {
  state.recommendations = data;
  const grid = $("#recommendationGrid");
  const weights = data.weights;
  const profileName = data.priority.charAt(0).toUpperCase() + data.priority.slice(1);
  $("#formulaStrip").innerHTML = `
    <span class="pulse-dot"></span>
    <p><strong>${profileName} formula:</strong> ${weights.price}% affordability + ${weights.age}% age + ${weights.condition}% condition.</p>
    <span class="formula-note">${data.eligible_count} eligible · every factor is visible</span>`;

  if (!data.recommendations.length) {
    $("#heroTopScore").textContent = "—";
    grid.innerHTML = `<div class="no-recommendations"><span>₹</span><h3>No eligible products</h3><p>Increase the budget or select another category to see recommendations.</p></div>`;
    return;
  }

  $("#heroTopScore").textContent = Math.round(data.recommendations[0].score);
  grid.innerHTML = data.recommendations.map((product, index) => {
    const components = product.component_scores;
    const unusual = product.is_unusual
      ? `<div class="warning-chip" title="${escapeHtml(product.anomaly_reason)}">! Price differs significantly from its category median</div>`
      : "";
    return `
      <article class="recommendation-card">
        <div class="recommendation-top">
          <span class="rank-tag">#${index + 1} ${index === 0 ? "BEST MATCH" : "RECOMMENDED"}</span>
          <span class="product-glyph">${glyphFor(product.category)}</span>
          <div class="score-ring" style="--score:${Math.max(0, Math.min(100, product.score))}%"><span>${Math.round(product.score)}<small>score</small></span></div>
        </div>
        <div class="recommendation-body">
          <p class="category-label">${escapeHtml(product.category)}</p>
          <h3 title="${escapeHtml(product.title)}">${escapeHtml(product.title)}</h3>
          <p class="rec-price">${money.format(product.price)} <small>${product.price_ratio == null ? "original price missing" : `${Math.round(product.price_ratio * 100)}% of original`}</small></p>
          <div class="score-bars">
            ${scoreRow("Price", components.price)}
            ${scoreRow("Age", components.age)}
            ${scoreRow("Condition", components.condition)}
          </div>
          <p class="rec-explanation">${escapeHtml(product.explanation)}</p>
          ${unusual}
        </div>
      </article>`;
  }).join("");
}

function renderPriorityComparison(affordabilityData, conditionData) {
  const affordable = affordabilityData.recommendations[0];
  const quality = conditionData.recommendations[0];
  const category = affordabilityData.category || $("#recommendationCategory").value;
  $("#comparisonScope").textContent = `Comparing ${category} listings only`;

  if (!affordable || !quality) {
    $("#decisionNarrative").textContent = "There are not enough eligible products at this budget to compare both priority profiles.";
    $("#priorityComparison").innerHTML = `<div class="no-recommendations"><h3>No comparison yet</h3><p>Increase the budget to bring this category into range.</p></div>`;
    return;
  }

  const changed = affordable.id !== quality.id;
  $("#decisionNarrative").textContent = changed
    ? `Changing only the weights moves the top pick from ${affordable.title} to ${quality.title}. The products and budget stay exactly the same.`
    : `${affordable.title} stays on top in both modes. That stability is useful evidence too: it performs strongly on both price and condition.`;

  $("#priorityComparison").innerHTML = `
    ${labCard("affordability", "Affordability first", "65% price weight", affordable)}
    <div class="lab-arrow" aria-hidden="true">${changed ? "→" : "="}</div>
    ${labCard("condition", "Condition first", "60% condition weight", quality)}`;
}

function labCard(kind, label, weight, product) {
  const strongest = kind === "affordability"
    ? `${Math.round(product.component_scores.price)} affordability points`
    : `${Math.round(product.component_scores.condition)} condition points`;
  return `
    <article class="lab-card ${kind}">
      <div class="lab-label">${label}<span>${weight}</span></div>
      <div class="lab-product">
        <span class="product-glyph">${glyphFor(product.category)}</span>
        <div><strong title="${escapeHtml(product.title)}">${escapeHtml(product.title)}</strong><small>${money.format(product.price)} · ${Math.round(product.score)}/100 overall</small></div>
      </div>
      <p class="lab-reason"><b>Why it wins:</b> ${strongest}; ${product.age == null ? "age not provided" : `${product.age} year(s) old`}; ${product.condition ? `${product.condition.toLowerCase()} condition` : "condition not provided"}.</p>
    </article>`;
}

function scoreRow(label, score) {
  return `<div class="score-row"><span>${label}</span><div class="bar"><i style="width:${score}%"></i></div><b>${Math.round(score)}</b></div>`;
}

async function loadRecommendations() {
  const button = $("#updateRecommendations");
  button.disabled = true;
  button.textContent = "Scoring…";
  const category = $("#recommendationCategory").value;
  const recommendationUrl = (priority) => {
    const params = new URLSearchParams({
      budget: String(currentBudget()),
      priority,
      category,
    });
    return `/api/recommendations?${params}`;
  };
  try {
    const [data, affordabilityData, conditionData] = await Promise.all([
      api(recommendationUrl(state.priority)),
      api(recommendationUrl("affordability")),
      api(recommendationUrl("condition")),
    ]);
    renderRecommendations(data);
    renderPriorityComparison(affordabilityData, conditionData);
    renderMetrics();
    renderProducts();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Update picks";
  }
}

async function loadMarketplace() {
  try {
    const [products, categoryData] = await Promise.all([
      api("/api/products"),
      api("/api/categories"),
    ]);
    state.products = products;
    state.categories = categoryData.categories;
    populateCategoryControls();
    renderMetrics();
    renderProducts();
  } catch (error) {
    showToast(`Could not load marketplace: ${error.message}`, true);
  }
}

function openListingDialog(product = null) {
  $("#listingForm").reset();
  $("#listingId").value = product?.id || "";
  $("#listingDialogTitle").textContent = product ? "Edit this listing" : "Add a new listing";
  $("#saveListingButton").textContent = product ? "Update listing" : "Save listing";
  if (product) {
    $("#titleField").value = product.title;
    $("#categoryField").value = product.category;
    $("#conditionField").value = product.condition || "";
    $("#priceField").value = product.price;
    $("#originalPriceField").value = product.original_price ?? "";
    $("#ageField").value = product.age ?? "";
  }
  $("#listingDialog").showModal();
  setTimeout(() => $("#titleField").focus(), 50);
}

async function saveListing(event) {
  event.preventDefault();
  const id = $("#listingId").value;
  const nullableNumber = (selector) => {
    const value = $(selector).value.trim();
    return value === "" ? null : Number(value);
  };
  const payload = {
    title: $("#titleField").value.trim(),
    category: $("#categoryField").value.trim(),
    condition: $("#conditionField").value || null,
    price: Number($("#priceField").value),
    original_price: nullableNumber("#originalPriceField"),
    age: nullableNumber("#ageField"),
  };
  const button = $("#saveListingButton");
  button.disabled = true;
  try {
    await api(id ? `/api/products/${id}` : "/api/products", {
      method: id ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("#listingDialog").close();
    showToast(id ? "Listing updated" : "Listing added");
    await loadMarketplace();
    await loadRecommendations();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function importFile(file) {
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  try {
    showToast(`Importing ${file.name}…`);
    const result = await api("/api/import", { method: "POST", body: formData });
    const details = [];
    if (result.duplicates) details.push(`${result.duplicates} duplicate row(s) skipped`);
    if (result.invalid) details.push(`${result.invalid} invalid row(s) skipped`);
    const suffix = details.length ? ` ${details.join("; ")}.` : "";
    if (result.imported > 0) {
      showToast(`${result.imported} new listing(s) imported.${suffix}`);
    } else {
      showToast(`No new listings added. ${result.duplicates || 0} row(s) already exist.`);
    }
    await loadMarketplace();
    await loadRecommendations();
  } catch (error) {
    showToast(`Import failed: ${error.message}`, true);
  } finally {
    $("#importInput").value = "";
  }
}

function bindEvents() {
  ["#headerAddButton", "#heroAddButton", "#marketAddButton"].forEach((selector) => {
    $(selector).addEventListener("click", () => openListingDialog());
  });
  $("#importButton").addEventListener("click", () => $("#importInput").click());
  $("#importInput").addEventListener("change", (event) => importFile(event.target.files[0]));
  $("#formulaButton").addEventListener("click", () => $("#formulaDialog").showModal());
  $("#listingForm").addEventListener("submit", saveListing);
  $("#updateRecommendations").addEventListener("click", loadRecommendations);
  $("#budgetInput").addEventListener("input", () => {
    $("#marketBudgetInput").value = currentBudget();
    renderMetrics();
    renderProducts();
  });
  $("#budgetInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadRecommendations();
  });
  ["#searchInput", "#categoryFilter", "#budgetOnly", "#sortFilter"].forEach((selector) => {
    $(selector).addEventListener(selector === "#searchInput" ? "input" : "change", renderProducts);
  });
  $("#marketBudgetInput").addEventListener("input", () => {
    const budget = Number($("#marketBudgetInput").value);
    if (budget > 0) {
      $("#budgetInput").value = budget;
      $("#budgetOnly").checked = true;
      renderMetrics();
      renderProducts();
    }
  });
  $$('[data-budget]').forEach((button) => {
    button.addEventListener("click", () => {
      const budget = Number(button.dataset.budget);
      $("#marketBudgetInput").value = budget;
      $("#budgetInput").value = budget;
      $("#budgetOnly").checked = true;
      renderMetrics();
      renderProducts();
    });
  });
  $("#searchInput").addEventListener("input", () => { $("#headerSearch").value = $("#searchInput").value; });
  $("#headerSearch").addEventListener("input", () => {
    $("#searchInput").value = $("#headerSearch").value;
    renderProducts();
  });
  $("#headerSearch").addEventListener("keydown", (event) => {
    if (event.key === "Enter") scrollToMarketplace();
  });
  $("#headerSearchButton").addEventListener("click", scrollToMarketplace);
  $$('[data-shop-category]').forEach((button) => {
    button.addEventListener("click", () => {
      $("#categoryFilter").value = button.dataset.shopCategory;
      $$('[data-shop-category]').forEach((item) => item.classList.toggle("active", item.dataset.shopCategory === button.dataset.shopCategory));
      renderProducts();
      scrollToMarketplace();
    });
  });
  $("#clearFilters").addEventListener("click", () => {
    $("#searchInput").value = "";
    $("#headerSearch").value = "";
    $("#categoryFilter").value = "";
    $("#budgetOnly").checked = false;
    $("#budgetInput").value = 23000;
    $("#marketBudgetInput").value = 23000;
    $("#sortFilter").value = "default";
    $$('[data-shop-category]').forEach((item) => item.classList.toggle("active", item.dataset.shopCategory === ""));
    renderProducts();
    renderMetrics();
  });
  $("#priorityTabs").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-priority]");
    if (!button) return;
    state.priority = button.dataset.priority;
    $$("#priorityTabs button").forEach((tab) => tab.classList.toggle("active", tab === button));
    loadRecommendations();
  });
  $("#recommendationCategory").addEventListener("change", loadRecommendations);
  $("#productGrid").addEventListener("click", (event) => {
    const shortlistButton = event.target.closest("[data-shortlist-id]");
    if (shortlistButton) {
      const id = Number(shortlistButton.dataset.shortlistId);
      if (state.shortlist.has(id)) state.shortlist.delete(id);
      else state.shortlist.add(id);
      localStorage.setItem("campusloop-shortlist", JSON.stringify([...state.shortlist]));
      showToast(state.shortlist.has(id) ? "Added to shortlist" : "Removed from shortlist");
      renderProducts();
      return;
    }
    const button = event.target.closest("[data-edit-id]");
    if (!button) return;
    const product = state.products.find((item) => item.id === Number(button.dataset.editId));
    if (product) openListingDialog(product);
  });
  $$('[data-close]').forEach((button) => {
    button.addEventListener("click", () => $(`#${button.dataset.close}`).close());
  });
  $$("dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      const rect = dialog.getBoundingClientRect();
      const inside = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
      if (!inside) dialog.close();
    });
  });
}

async function init() {
  bindEvents();
  await loadMarketplace();
  await loadRecommendations();
}

document.addEventListener("DOMContentLoaded", init);
