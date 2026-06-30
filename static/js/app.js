/* EAPCET Predictor — frontend logic
   No frameworks: vanilla JS, fetch API, progressive rendering. */

const BRANCH_NAMES = {
  CSE: "Computer Science Engg.", ECE: "Electronics & Comm. Engg.",
  EEE: "Electrical & Electronics Engg.", MEC: "Mechanical Engg.",
  CIV: "Civil Engg.", CSM: "CSE (AI & ML)", CSD: "CSE (Data Science)",
  CSC: "CSE (Cyber Security)", CSB: "CSE (Business Systems)",
  CSO: "CSE (IoT)", AID: "AI & Data Science", AIM: "AI & Machine Learning",
  IT: "Information Technology", INF: "Information Technology",
  CHE: "Chemical Engg.", PHD: "Pharm D", PHM: "Pharmacy",
  AGR: "Agricultural Engg.", BIO: "Bio-Technology", MET: "Metallurgical Engg.",
};

function branchLabel(code) {
  return BRANCH_NAMES[code] ? `${code} · ${BRANCH_NAMES[code]}` : code;
}

const DISTRICT_NAMES = {
  ATP: "Anantapur",
  CTR: "Chittoor",
  EG: "East Godavari",
  GTR: "Guntur",
  KDP: "Kadapa",
  KNL: "Kurnool",
  KRI: "Krishna",
  NLR: "Nellore",
  PKS: "Prakasam",
  SKL: "Srikakulam",
  VSP: "Visakhapatnam",
  VZM: "Vizianagaram",
  WG: "West Godavari",
};

function districtLabel(code) {
  return DISTRICT_NAMES[code] ? `${code} (${DISTRICT_NAMES[code]})` : code;
}

let allColleges = [];

function updateCollegesDropdown() {
  const selectedDistrict = els.district.value || "ALL";
  let filtered = allColleges;
  if (selectedDistrict !== "ALL") {
    filtered = allColleges.filter((c) => c.dist === selectedDistrict);
  }
  fillSelect(els.college, filtered, {
    value: (c) => c.code,
    label: (c) => `${c.code} (${c.name})`,
    placeholderKept: true,
  });
  els.college.value = "ALL";
}



const els = {
  category: document.getElementById("category"),
  district: document.getElementById("district"),
  branch: document.getElementById("branch"),
  year: document.getElementById("year"),
  gender: document.getElementById("gender"),
  genderSegmented: document.getElementById("gender-segmented"),
  form: document.getElementById("predict-form"),
  formError: document.getElementById("form-error"),
  resultsSection: document.getElementById("results"),
  resultsTitle: document.getElementById("results-title"),
  resultsSummary: document.getElementById("results-summary"),
  resultsEmpty: document.getElementById("results-empty"),
  resultsBody: document.getElementById("results-body"),
  tableWrap: document.getElementById("table-wrap"),
  resultsLoading: document.getElementById("results-loading"),
  yearPill: document.getElementById("year-pill"),
  footerYears: document.getElementById("footer-years"),
  college: document.getElementById("college"),
};

function fillSelect(select, items, { value, label, placeholderKept = true } = {}) {
  const existingPlaceholder = placeholderKept ? select.firstElementChild : null;
  select.innerHTML = "";
  if (existingPlaceholder) select.appendChild(existingPlaceholder);
  items.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = value ? value(item) : item;
    opt.textContent = label ? label(item) : item;
    select.appendChild(opt);
  });
}

async function loadMeta() {
  const res = await fetch("/api/meta");
  const meta = await res.json();

  fillSelect(els.category, meta.categories, { placeholderKept: true });

  fillSelect(els.district, meta.districts, {
    value: (d) => d.code,
    label: (d) => districtLabel(d.code),
    placeholderKept: true,
  });

  fillSelect(els.branch, meta.branches, {
    value: (b) => b.code,
    label: (b) => branchLabel(b.code),
    placeholderKept: true,
  });

  allColleges = meta.colleges || [];

  fillSelect(els.college, allColleges, {
    value: (c) => c.code,
    label: (c) => `${c.code} (${c.name})`,
    placeholderKept: true,
  });

  fillSelect(els.year, meta.years, { placeholderKept: false });

  if (meta.years.length) {
    const latest = meta.years[0];
    els.yearPill.textContent = `Rank Year ${latest}`;
    els.footerYears.textContent = meta.years.join(", ");
  }
}

function setGender(value) {
  els.gender.value = value;
  [...els.genderSegmented.children].forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.value === value);
  });
}

els.genderSegmented.addEventListener("click", (e) => {
  const btn = e.target.closest(".segmented-btn");
  if (!btn) return;
  setGender(btn.dataset.value);
});

function showError(message) {
  els.formError.textContent = message;
  els.formError.hidden = false;
}

function clearError() {
  els.formError.hidden = true;
  els.formError.textContent = "";
}

function fmtNumber(n) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString("en-IN");
}

function renderResults(data) {
  els.resultsSection.hidden = false;
  els.resultsLoading.hidden = true;

  const { results, rank, category, gender, district, branch, college, year } = data;

  const genderLabel = gender === "boys" ? "Boy" : "Girl";
  const scopeBits = [];
  if (district !== "ALL") scopeBits.push(district);
  if (branch !== "ALL") scopeBits.push(branch);
  if (college !== "ALL") scopeBits.push(college);
  const scopeText = scopeBits.length ? ` · ${scopeBits.join(" · ")}` : "";

  els.resultsTitle.textContent = `Colleges within reach for rank ${fmtNumber(rank)}`;
  els.resultsSummary.textContent =
    `${category} · ${genderLabel}${scopeText} · ${year} closing ranks · ${results.length} match${results.length === 1 ? "" : "es"}`;

  if (!results.length) {
    els.tableWrap.hidden = true;
    els.resultsEmpty.hidden = false;
    return;
  }

  els.resultsEmpty.hidden = true;
  els.tableWrap.hidden = false;

  els.resultsBody.innerHTML = results
    .map((row) => `
      <tr>
        <td data-label="College">
          <div class="college-info">
            <span class="college-name">${escapeHtml(row.name_of_institution)}</span>
            <span class="college-code">${escapeHtml(row.instcode)} · ${escapeHtml(row.affl || "")}</span>
            <span class="college-place">${escapeHtml(row.place || "")}${row.estd ? ` · est. ${row.estd}` : ""}</span>
          </div>
        </td>
        <td data-label="Branch"><span class="branch-badge">${escapeHtml(row.branch_code)}</span></td>
        <td data-label="District">${escapeHtml(row.dist || "—")}</td>
        <td data-label="Type"><span class="type-badge">${escapeHtml(row.type || "—")}</span></td>
        <td data-label="Closing rank" class="num"><span class="rank-value">${fmtNumber(row.closing_rank)}</span></td>
        <td data-label="Annual fee" class="num"><span class="fee-value">${row.college_fee ? "₹" + fmtNumber(row.college_fee) : "—"}</span></td>
      </tr>
    `)
    .join("");
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();

  let rank = document.getElementById("rank").value.trim();
  if (rank === "") {
    rank = "1";
  }
  const category = els.category.value;
  const gender = els.gender.value;
  const district = els.district.value || "ALL";
  const branch = els.branch.value || "ALL";
  const college = els.college.value || "ALL";
  const year = els.year.value;

  if (Number(rank) <= 0) {
    showError("Please enter your EAPCET rank as a positive number.");
    return;
  }
  if (!category) {
    showError("Please select your category.");
    return;
  }
  if (!gender) {
    showError("Please select your gender.");
    return;
  }

  els.resultsSection.hidden = false;
  els.tableWrap.hidden = true;
  els.resultsEmpty.hidden = true;
  els.resultsLoading.hidden = false;
  els.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });

  const params = new URLSearchParams({ rank, category, gender, district, branch, college, year });

  try {
    const res = await fetch(`/api/predict?${params.toString()}`);
    const data = await res.json();
    if (!res.ok) {
      els.resultsLoading.hidden = true;
      showError(data.error || "Something went wrong. Please try again.");
      els.resultsSection.hidden = true;
      return;
    }
    renderResults(data);
  } catch (err) {
    els.resultsLoading.hidden = true;
    showError("Could not reach the server. Please check your connection and try again.");
    els.resultsSection.hidden = true;
  }
});

function animateCount(el) {
  const target = Number(el.dataset.count);
  const duration = 900;
  const start = performance.now();
  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(target * eased).toLocaleString("en-IN");
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function initCountUp() {
  const nums = document.querySelectorAll(".hero-stat-num");
  if (!nums.length) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) {
    nums.forEach((el) => (el.textContent = Number(el.dataset.count).toLocaleString("en-IN")));
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          animateCount(entry.target);
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.4 }
  );
  nums.forEach((el) => observer.observe(el));
}

(async function init() {
  initCountUp();
  setGender("boys");
  try {
    await loadMeta();
    els.district.addEventListener("change", updateCollegesDropdown);
  } catch (err) {
    showError("Could not load filter options from the server.");
  }
})();
