"use strict";

// OS Book interactive course. Fully static/client-side:
//   docs/os-book/content.json  -- chapters, sections (HTML), keywords, images
//   docs/os-book/quiz.json     -- flat question bank, one "category" per chapter
// Progress (visited steps + quiz scores) is kept in localStorage only.

const el = (id) => document.getElementById(id);
const PROGRESS_KEY = "osbook_progress_v1";

const state = {
  content: null,
  quizByChapter: new Map(),
  chapters: [], // [{...chapter, steps: [...]}]
  flat: [], // [{chapterIdx, stepIdx}] across the whole course
  progress: loadProgress(),
  quizSession: null, // {chapterNum, current, answers, done, result}
};

function loadProgress() {
  try {
    const raw = localStorage.getItem(PROGRESS_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) { /* ignore corrupt storage */ }
  return { visited: {}, quiz: {} };
}

function saveProgress() {
  localStorage.setItem(PROGRESS_KEY, JSON.stringify(state.progress));
}

function stepKey(chapter, step) {
  if (step.type === "intro") return `${chapter.id}/intro`;
  if (step.type === "quiz") return `${chapter.id}/quiz`;
  return `${chapter.id}/sec/${step.section.num}`;
}

function isStepDone(chapter, step) {
  const key = stepKey(chapter, step);
  if (step.type === "quiz") return !!state.progress.quiz[chapter.num];
  return !!state.progress.visited[key];
}

function markVisited(chapter, step) {
  state.progress.visited[stepKey(chapter, step)] = true;
  saveProgress();
}

function chapterProgress(chapter) {
  const total = chapter.steps.length;
  const done = chapter.steps.filter((s) => isStepDone(chapter, s)).length;
  return { done, total, pct: total ? Math.round((done / total) * 100) : 0 };
}

function overallProgress() {
  let done = 0, total = 0;
  for (const ch of state.chapters) {
    const p = chapterProgress(ch);
    done += p.done;
    total += p.total;
  }
  return total ? Math.round((done / total) * 100) : 0;
}

async function boot() {
  const [content, quiz] = await Promise.all([
    fetch("content.json").then((r) => r.json()),
    fetch("quiz.json").then((r) => r.json()),
  ]);
  state.content = content;
  for (const q of quiz) {
    if (!state.quizByChapter.has(q.chapter)) state.quizByChapter.set(q.chapter, []);
    state.quizByChapter.get(q.chapter).push(q);
  }
  state.chapters = content.chapters.map((ch) => ({ ...ch, steps: buildSteps(ch) }));
  buildFlatIndex();
  renderLanding();
  window.addEventListener("hashchange", route);
  route();
}

function buildSteps(chapter) {
  const steps = [{ type: "intro" }];
  for (const s of chapter.sections) steps.push({ type: "section", section: s });
  if (chapter.quizCount > 0) steps.push({ type: "quiz" });
  return steps;
}

function buildFlatIndex() {
  state.flat = [];
  state.chapters.forEach((ch, ci) => {
    ch.steps.forEach((_, si) => state.flat.push({ chapterIdx: ci, stepIdx: si }));
  });
}

// ---------------------------------------------------------------------------
// Routing: #/  -> landing, #/ch<idx>/<stepIdx> -> a step

function route() {
  const hash = location.hash.replace(/^#\/?/, "");
  if (!hash) {
    showLanding();
    return;
  }
  const m = hash.match(/^ch(\d+)\/(\d+)$/);
  if (!m) {
    showLanding();
    return;
  }
  const chapterIdx = parseInt(m[1], 10);
  const stepIdx = parseInt(m[2], 10);
  if (state.chapters[chapterIdx] && state.chapters[chapterIdx].steps[stepIdx]) {
    showStep(chapterIdx, stepIdx);
  } else {
    showLanding();
  }
}

function goToStep(chapterIdx, stepIdx) {
  location.hash = `#/ch${chapterIdx}/${stepIdx}`;
}

// ---------------------------------------------------------------------------
// Landing page

function renderLanding() {
  const pct = overallProgress();
  el("overallBar").style.width = pct + "%";
  el("overallLabel").textContent = pct === 0 ? "Neînceput" : `${pct}% parcurs`;
  el("forewordText").innerHTML = state.content.frontMatter.foreword;

  const list = el("chapterList");
  list.innerHTML = "";
  state.chapters.forEach((ch, idx) => {
    const p = chapterProgress(ch);
    const a = document.createElement("a");
    a.href = `#/ch${idx}/0`;
    a.className = "chapter-card";
    a.innerHTML = `
      <div class="num ${p.pct === 100 ? "done" : ""}">${p.pct === 100 ? "✓" : ch.num}</div>
      <div class="meta">
        <div class="title">${escapeHtml(ch.title)}</div>
        <div class="sub">${ch.sections.length} secțiuni${ch.quizCount ? " · test de " + ch.quizCount + " întrebări" : ""}</div>
      </div>
      <div class="pct">${p.pct}%</div>`;
    list.appendChild(a);
  });
}

el("forewordToggle").addEventListener("click", (e) => {
  e.preventDefault();
  el("forewordBox").classList.toggle("hidden");
});

function showLanding() {
  el("landing").classList.remove("hidden");
  el("courseView").classList.add("hidden");
  renderLanding();
}

// ---------------------------------------------------------------------------
// Sidebar

function renderSidebar(activeChapterIdx, activeStepIdx) {
  const sidebar = el("sidebar");
  sidebar.innerHTML = "";
  state.chapters.forEach((ch, ci) => {
    const group = document.createElement("div");
    group.className = "chapter-group" + (ci === activeChapterIdx ? " open" : "");
    const p = chapterProgress(ch);
    const head = document.createElement("div");
    head.className = "chapter-head";
    head.innerHTML = `<span class="dot ${p.pct === 100 ? "done" : ""}"></span>
      <span>${ch.num}. ${escapeHtml(ch.title)}</span>
      <span class="arrow">▶</span>`;
    head.addEventListener("click", () => group.classList.toggle("open"));
    group.appendChild(head);

    const stepsEl = document.createElement("div");
    stepsEl.className = "steps";
    ch.steps.forEach((step, si) => {
      const link = document.createElement("div");
      const active = ci === activeChapterIdx && si === activeStepIdx;
      link.className = "step-link" + (active ? " active" : "");
      const done = isStepDone(ch, step);
      link.innerHTML = `<span class="check">${done ? "✓" : ""}</span><span>${stepLabel(step)}</span>`;
      link.addEventListener("click", () => goToStep(ci, si));
      stepsEl.appendChild(link);
    });
    group.appendChild(stepsEl);
    sidebar.appendChild(group);
  });
}

function stepLabel(step) {
  if (step.type === "intro") return "Prezentare capitol";
  if (step.type === "quiz") return "Test de verificare";
  return `${step.section.num} ${step.section.title}`;
}

// ---------------------------------------------------------------------------
// Step view

function showStep(chapterIdx, stepIdx) {
  el("landing").classList.add("hidden");
  el("courseView").classList.remove("hidden");
  el("sidebar").classList.remove("open");

  const chapter = state.chapters[chapterIdx];
  const step = chapter.steps[stepIdx];
  const flatPos = state.flat.findIndex((f) => f.chapterIdx === chapterIdx && f.stepIdx === stepIdx);

  el("stepProgressBar").style.width = `${Math.round(((flatPos + 1) / state.flat.length) * 100)}%`;
  el("crumb").textContent = `Capitolul ${chapter.num} · ${chapter.title}`;

  renderSidebar(chapterIdx, stepIdx);

  if (step.type !== "quiz") {
    markVisited(chapter, step);
  } else if (state.quizSession?.chapterNum !== chapter.num) {
    state.quizSession = null; // reset when (re)entering a different chapter's quiz
  }

  const body = el("stepContent");
  if (step.type === "intro") {
    body.innerHTML = renderIntro(chapter);
  } else if (step.type === "section") {
    body.innerHTML = renderSection(step.section);
  } else {
    renderQuizStep(chapter, body);
  }

  const prevBtn = el("prevBtn");
  const nextBtn = el("nextBtn");
  prevBtn.disabled = flatPos <= 0;
  prevBtn.onclick = () => {
    if (flatPos > 0) {
      const p = state.flat[flatPos - 1];
      goToStep(p.chapterIdx, p.stepIdx);
    }
  };
  const isLast = flatPos >= state.flat.length - 1;
  nextBtn.textContent = isLast ? "Ai terminat cursul 🎉" : "Continuă →";
  nextBtn.disabled = isLast;
  nextBtn.onclick = () => {
    if (flatPos < state.flat.length - 1) {
      const n = state.flat[flatPos + 1];
      goToStep(n.chapterIdx, n.stepIdx);
    }
  };
  el("homeBtn").onclick = () => { location.hash = "#/"; };
  el("contentPane").scrollTop = 0;
}

function renderIntro(chapter) {
  const learn = chapter.learnIntro.length
    ? `<div class="learn-box"><h3>Ce se învață în acest capitol?</h3><ul>${chapter.learnIntro
        .map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul></div>`
    : "";
  const kws = chapter.keywords.length
    ? `<div class="keyword-tags">${chapter.keywords.map((k) => `<span class="tag">${escapeHtml(k)}</span>`).join("")}</div>`
    : "";
  return `<h1 class="step-title">${chapter.num}. ${escapeHtml(chapter.title)}</h1>${learn}${kws}
    <p>Folosește <strong>Continuă →</strong> pentru a parcurge secțiunile acestui capitol${
      chapter.quizCount ? ", încheiate cu un test de verificare." : "."}</p>`;
}

function renderSection(section) {
  const imgs = (section.images || [])
    .map((src) => `<img src="${src}" loading="lazy" alt="Figură din carte" />`).join("");
  return `<h1 class="step-title">${section.num} ${escapeHtml(section.title)}</h1>
    <div class="step-body">${section.html}${imgs}</div>`;
}

// ---------------------------------------------------------------------------
// Quiz step (same interaction model as the DevOps quiz: one question at a
// time, then a scored review), graded client-side against quiz.json.

function renderQuizStep(chapter, body) {
  const questions = state.quizByChapter.get(chapter.num) || [];
  const stored = state.progress.quiz[chapter.num];

  if (!state.quizSession) {
    state.quizSession = { chapterNum: chapter.num, current: 0, answers: {}, done: !!stored, result: stored || null };
  }
  const sess = state.quizSession;

  if (sess.done) {
    renderQuizResult(body, questions, sess.result, chapter);
    return;
  }

  const q = questions[sess.current];
  const total = questions.length;
  body.innerHTML = `
    <h1 class="step-title">Test de verificare — Capitolul ${chapter.num}</h1>
    <p class="quiz-meta">Întrebarea ${sess.current + 1} din ${total}</p>
    <h2>${escapeHtml(q.question)}</h2>
    <ul class="quiz-options" id="quizOptions"></ul>
    <div style="display:flex;justify-content:flex-end;">
      <button class="btn primary" id="quizNextBtn" disabled>${sess.current === total - 1 ? "Finalizează" : "Următoarea"}</button>
    </div>`;

  const list = el("quizOptions");
  q.options.forEach((opt, i) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "opt" + (sess.answers[q.id] === i ? " selected" : "");
    btn.textContent = opt;
    btn.onclick = () => {
      sess.answers[q.id] = i;
      renderQuizStep(chapter, body);
    };
    li.appendChild(btn);
    list.appendChild(li);
  });

  const nextBtn = el("quizNextBtn");
  nextBtn.disabled = sess.answers[q.id] === undefined;
  nextBtn.onclick = () => {
    if (sess.current < total - 1) {
      sess.current++;
      renderQuizStep(chapter, body);
    } else {
      finishQuiz(chapter, questions, body);
    }
  };
}

function finishQuiz(chapter, questions, body) {
  const sess = state.quizSession;
  let correct = 0;
  const feedback = questions.map((q) => {
    const selected = sess.answers[q.id] ?? -1;
    const ok = selected === q.answer;
    if (ok) correct++;
    return { id: q.id, question: q.question, selected, correct: ok, correctIndex: q.answer, explanation: q.explanation, options: q.options };
  });
  const result = { total: questions.length, correct, score: Math.round((correct / questions.length) * 100), feedback };
  sess.done = true;
  sess.result = result;
  state.progress.quiz[chapter.num] = result;
  saveProgress();
  renderSidebar(state.chapters.findIndex((c) => c.num === chapter.num), chapter.steps.length - 1);
  renderQuizResult(body, questions, result, chapter);
}

function renderQuizResult(body, questions, result, chapter) {
  const verdict = result.score >= 90 ? "Excelent! 🏆" : result.score >= 70 ? "Foarte bine 💪" : result.score >= 50 ? "În progres 📈" : "Mai exersează 📚";
  body.innerHTML = `
    <h1 class="step-title">Rezultat — Capitolul ${chapter.num}</h1>
    <div class="score-ring" style="--pct:${result.score}%"><span>${result.score}%</span></div>
    <p class="score-line">${result.correct} din ${result.total} corecte — ${verdict}</p>
    <div id="quizReview"></div>
    <button class="btn" id="retakeBtn">🔁 Reia testul</button>`;
  const review = el("quizReview");
  result.feedback.forEach((f) => {
    const div = document.createElement("div");
    div.className = "review-item " + (f.correct ? "ok" : "bad");
    const chosen = f.selected >= 0 ? f.options[f.selected] : "(fără răspuns)";
    div.innerHTML = `<div class="q">${f.correct ? "✅" : "❌"} ${escapeHtml(f.question)}</div>` +
      (f.correct ? "" : `<div class="exp">Răspunsul tău: ${escapeHtml(chosen)} · Corect: ${escapeHtml(f.options[f.correctIndex])}</div>`) +
      `<div class="exp">${escapeHtml(f.explanation)}</div>`;
    review.appendChild(div);
  });
  el("retakeBtn").onclick = () => {
    state.quizSession = { chapterNum: chapter.num, current: 0, answers: {}, done: false, result: null };
    delete state.progress.quiz[chapter.num];
    saveProgress();
    renderQuizStep(chapter, body);
    renderSidebar(state.chapters.findIndex((c) => c.num === chapter.num), chapter.steps.length - 1);
  };
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

el("menuBtn").addEventListener("click", () => el("sidebar").classList.toggle("open"));

boot().catch((e) => {
  document.body.innerHTML = `<div class="wrap"><p style="color:#ff5d6c">Eroare la încărcarea cursului: ${e}</p></div>`;
  console.error(e);
});
