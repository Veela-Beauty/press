// ===== CONFIG =====
var API_BASE = "https://autodeploypanel.mvpstorm.com";
var currentEmail = "";
var currentSite = "";

// ===== LANDING PAGE NAVIGATION =====
function hideAll() {
    var ids = ["landing-choice","invite-form","request-form","request-submitted","recover-form","demo-creating","demo-ready"];
    ids.forEach(function(id) {
        var el = document.getElementById(id);
        if (el) { el.style.display = "none"; el.classList.remove("active"); }
    });
    updateProgress(0);
}
function showSection(id, progress) {
    hideAll();
    var el = document.getElementById(id);
    el.style.display = "block";
    el.classList.add("active");
    updateProgress(progress || 0);
}
function updateProgress(pct) {
    document.getElementById("progressBar").style.width = pct + "%";
}
function showLanding() { showSection("landing-choice", 0); }
function showInviteForm() { showSection("invite-form", 25); }
function showRequestForm() { showSection("request-form", 25); }
function showRecoverForm() { showSection("recover-form", 10); }

// ===== DEMO CREATION (PATH A) =====
function createDemo() {
    var company = document.getElementById("company").value.trim();
    var email = document.getElementById("email").value.trim();
    var phone = document.getElementById("phone").value.trim();
    var invite_code = document.getElementById("invite_code").value.trim();
    if (!company || company.length < 2) { showError("error-msg", "Please enter your company name"); return; }
    if (!email || !email.includes("@")) { showError("error-msg", "Please enter a valid email"); return; }
    if (!invite_code) { showError("error-msg", "Please enter your invite code"); return; }
    currentEmail = email;
    showSection("demo-creating", 50);
    fetch(API_BASE + "/api/method/press.api.demo.create", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company: company, email: email, phone: phone, invite_code: invite_code })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.exc) {
            showSection("invite-form", 25);
            var msg = "Something went wrong. Please try again.";
            try { msg = JSON.parse(data.exc)[0].split(":").pop().trim(); } catch(e) {}
            showError("error-msg", msg); return;
        }
        var result = data.message;
        if (result.ready || result.status === "exists") { showReady(result.url, result.site); return; }
        pollSiteStatus(result.site);
    })
    .catch(function(err) { showSection("invite-form", 25); showError("error-msg", "Network error: " + err.message); });
}

// ===== DEMO REQUEST (PATH B) =====
function requestDemo() {
    var company = document.getElementById("req-company").value.trim();
    var email = document.getElementById("req-email").value.trim();
    var phone = document.getElementById("req-phone").value.trim();
    var industry = document.getElementById("req-industry-field").value;
    var message = document.getElementById("req-message").value.trim();
    if (!company || company.length < 2) { showError("request-error", "Please enter your company name"); return; }
    if (!email || !email.includes("@")) { showError("request-error", "Please enter a valid email"); return; }
    var btn = document.getElementById("request-btn");
    btn.disabled = true; btn.textContent = "Submitting...";
    fetch(API_BASE + "/api/method/press.api.demo.request_demo", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company: company, email: email, phone: phone, industry: industry, message: message })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        btn.disabled = false; btn.textContent = "Submit Request";
        if (data.exc) { var msg = "Something went wrong."; try { msg = JSON.parse(data.exc)[0].split(":").pop().trim(); } catch(e) {} showError("request-error", msg); return; }
        hideAll();
        document.getElementById("submitted-email").textContent = email;
        document.getElementById("request-submitted").style.display = "block";
        updateProgress(100);
    })
    .catch(function(err) { btn.disabled = false; btn.textContent = "Submit Request"; showError("request-error", "Network error: " + err.message); });
}

// ===== POLLING =====
function pollSiteStatus(site) {
    var attempts = 0;
    var interval = setInterval(function() {
        attempts++;
        updateProgress(50 + Math.min(attempts, 40));
        if (attempts > 60) { clearInterval(interval); showReady("https://" + site, site); return; }
        fetch(API_BASE + "/api/method/press.api.demo.check_status", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ site: site })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) { if (data.message && data.message.ready) { clearInterval(interval); showReady(data.message.url, site); } })
        .catch(function() {});
    }, 5000);
}

function showReady(url, site) {
    currentSite = site; showSection("demo-ready", 100);
    document.getElementById("site-link").href = url;
    document.getElementById("site-link").textContent = site;
    document.getElementById("site-url-text").textContent = url;
}

// ===== CREDENTIAL RECOVERY =====
function resendCredentials() {
    var email = document.getElementById("recover-email").value.trim();
    if (!email || !email.includes("@")) { showError("recover-error", "Please enter a valid email"); return; }
    currentEmail = email;
    var btn = document.getElementById("recover-btn"); btn.disabled = true; btn.textContent = "Sending...";
    fetch(API_BASE + "/api/method/press.api.demo.resend_credentials", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        btn.disabled = false; btn.textContent = "Send My Credentials";
        if (data.exc) { var msg = "Something went wrong."; try { msg = JSON.parse(data.exc)[0].split(":").pop().trim(); } catch(e) {} showError("recover-error", msg); return; }
        showSuccess("recover-success", "Credentials sent! Check your email.");
    })
    .catch(function(err) { btn.disabled = false; btn.textContent = "Send My Credentials"; showError("recover-error", "Network error: " + err.message); });
}

function resendFromReady() {
    var email = currentEmail || document.getElementById("email").value.trim();
    if (!email) return;
    var btn = document.getElementById("resend-ready-btn"); btn.disabled = true; btn.textContent = "Sending...";
    fetch(API_BASE + "/api/method/press.api.demo.resend_credentials", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        btn.disabled = false; btn.textContent = "Resend Credentials to My Email";
        if (data.exc) { btn.textContent = "Failed - Try Again"; return; }
        btn.textContent = "Sent! Check your email";
        setTimeout(function() { btn.textContent = "Resend Credentials to My Email"; }, 3000);
    })
    .catch(function() { btn.disabled = false; btn.textContent = "Failed - Try Again"; });
}

// ===== FEEDBACK HELPERS =====
function showError(id, msg) {
    var el = document.getElementById(id); el.textContent = msg; el.style.display = "block";
    setTimeout(function() { el.style.display = "none"; }, 5000);
}
function showSuccess(id, msg) {
    var el = document.getElementById(id); el.textContent = msg; el.style.display = "block";
    setTimeout(function() { el.style.display = "none"; }, 5000);
}

// ===== XSS ESCAPE HELPER =====
function esc(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}

// ===== REQUIREMENTS WIZARD (21 steps) =====
var reqStep = 1;
var reqTotal = 21;
var navigating = false; // debounce flag

function showRequirementsForm() {
    document.getElementById("start-req-btn").style.display = "none";
    document.getElementById("req-wizard").style.display = "block";
    updateProgress(100);
    updateReqProgress();
}
function skipRequirements() {
    document.getElementById("req-wizard").style.display = "none";
    document.getElementById("start-req-btn").style.display = "none";
}

// Navigate by data-step attribute (resilient to HTML reordering)
function reqNext() {
    if (navigating || reqStep >= reqTotal) return;
    navigating = true;
    setTimeout(function() { navigating = false; }, 500);

    if (reqStep === 20) generateSummary();

    var current = document.querySelector('#req-wizard [data-step="' + reqStep + '"]');
    if (!current) return;
    current.classList.remove("active");
    current.style.display = "none";
    reqStep++;
    var next = document.querySelector('#req-wizard [data-step="' + reqStep + '"]');
    if (!next) return;
    next.style.display = "block";
    next.classList.add("active");
    updateReqProgress();
    document.querySelector(".container").scrollIntoView({ behavior: "smooth" });
}
function reqPrev() {
    if (navigating || reqStep <= 1) return;
    navigating = true;
    setTimeout(function() { navigating = false; }, 500);

    var current = document.querySelector('#req-wizard [data-step="' + reqStep + '"]');
    if (!current) return;
    current.classList.remove("active");
    current.style.display = "none";
    reqStep--;
    var prev = document.querySelector('#req-wizard [data-step="' + reqStep + '"]');
    if (!prev) return;
    prev.style.display = "block";
    prev.classList.add("active");
    updateReqProgress();
    document.querySelector(".container").scrollIntoView({ behavior: "smooth" });
}
function updateReqProgress() {
    updateProgress(Math.round((reqStep / reqTotal) * 100));
}

// ===== DATA-DRIVEN ANSWER COLLECTION =====
// Collects answers automatically from data-section/data-question/data-type attributes
function collectAnswers() {
    var answers = [];
    var elements = document.querySelectorAll("#req-wizard [data-section][data-question]");

    elements.forEach(function(el) {
        var section = el.getAttribute("data-section");
        var question = el.getAttribute("data-question");
        var type = el.getAttribute("data-type");
        var value = "";

        if (type === "checks") {
            // Checkbox group: collect all checked values
            var vals = [];
            el.querySelectorAll("input[type='checkbox']:checked").forEach(function(cb) { vals.push(cb.value); });
            value = vals.join(", ");
        } else if (type === "radio") {
            // Radio group: find checked radio inside container
            var checked = el.querySelector("input[type='radio']:checked");
            value = checked ? checked.value : "";
        } else if (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA") {
            // Simple form element: get value directly
            value = el.value.trim();
        }

        if (value) {
            answers.push({ section: section, question: question, answer: value });
        }
    });

    console.log("collectAnswers: " + answers.length + " answers collected");
    return answers;
}

// ===== SUMMARY GENERATION (XSS-safe) =====
function generateSummary() {
    var answers = collectAnswers();
    var html = "";
    var currentSection = "";

    answers.forEach(function(a) {
        if (a.section !== currentSection) {
            if (currentSection) html += "</div>";
            currentSection = a.section;
            html += '<div class="summary-section"><h3>' + esc(a.section) + '</h3>';
        }
        html += '<div class="summary-item"><span class="summary-label">' + esc(a.question) + ':</span><span class="summary-value">' + esc(a.answer) + '</span></div>';
    });
    if (currentSection) html += "</div>";

    document.getElementById("summaryContent").innerHTML = html || '<p style="color:#6b7280;">No information provided yet.</p>';
}

// ===== VALIDATION =====
function validateRequired() {
    var companyName = document.getElementById("req-company-name").value.trim();
    var contactEmail = document.getElementById("req-contact-email").value.trim();

    if (!companyName && !contactEmail) {
        return true; // Allow fully empty submission (user may have skipped)
    }

    var errors = [];
    if (companyName && !contactEmail) errors.push("Please provide an email address");
    if (contactEmail && !contactEmail.includes("@")) errors.push("Please enter a valid email address");

    if (errors.length) {
        showError("req-submit-error", errors.join(". "));
        return false;
    }
    return true;
}

// ===== SUBMIT REQUIREMENTS =====
function submitRequirements() {
    if (!validateRequired()) return;

    var answers = collectAnswers();
    if (!answers.length) {
        showError("req-submit-error", "No information to submit. Please fill in at least some fields.");
        return;
    }

    var site = currentSite || document.getElementById("site-link").textContent;
    var btn = document.querySelector("[data-step='21'] .btn-submit");
    btn.disabled = true; btn.textContent = "Submitting...";

    fetch(API_BASE + "/api/method/press.api.demo.submit_requirements", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site: site, answers: JSON.stringify(answers) })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        btn.disabled = false; btn.textContent = "Submit Requirements";
        if (data.exc) {
            var msg = "Submission failed. Please try again.";
            try { msg = JSON.parse(data.exc)[0].split(":").pop().trim(); } catch(e) {}
            showError("req-submit-error", msg);
            return;
        }
        // Hide all wizard steps, show success
        document.querySelectorAll("#req-wizard .section").forEach(function(s) {
            s.style.display = "none";
            s.classList.remove("active");
        });
        document.getElementById("req-done").style.display = "block";
        updateProgress(100);
    })
    .catch(function(err) {
        btn.disabled = false; btn.textContent = "Submit Requirements";
        showError("req-submit-error", "Network error: " + err.message);
    });
}
