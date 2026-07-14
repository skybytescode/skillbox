"use strict";

// SkillBox DevOps quiz front-end. Talks to the Go API:
//   GET  /api/categories
//   GET  /api/quiz?category=&count=
//   POST /api/submit  { answers: [{questionId, selected}] }

const el = (id) => document.getElementById(id);

const state = {
  questions: [],
  answers: {}, // questionId -> selected index
  current: 0,
};

async function loadCategories() {
  const res = await fetch("/api/categories");
  const data = await res.json();
  const select = el("category");
  select.innerHTML = "";
  const all = document.createElement("option");
  all.value = "All";
  all.textContent = "All categories";
  select.appendChild(all);
  for (const c of data.categories) {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = c;
    select.appendChild(o);
  }
  el("startMeta").textContent = `${data.total} questions available across ${data.categories.length} categories.`;
}

async function startQuiz() {
  const category = el("category").value;
  const count = el("count").value;
  const res = await fetch(`/api/quiz?category=${encodeURIComponent(category)}&count=${count}`);
  const data = await res.json();
  state.questions = data.questions || [];
  state.answers = {};
  state.current = 0;

  if (state.questions.length === 0) {
    el("startMeta").textContent = "No questions found for that selection.";
    return;
  }
  show("quiz");
  renderQuestion();
}

function renderQuestion() {
  const q = state.questions[state.current];
  const total = state.questions.length;

  el("progressBar").style.width = `${(state.current / total) * 100}%`;
  el("qMeta").innerHTML = `<span class="tag">${q.category}</span> <span class="tag">${q.difficulty}</span>`;
  el("qText").textContent = q.question;
  el("qCounter").textContent = `Question ${state.current + 1} of ${total}`;

  const list = el("options");
  list.innerHTML = "";
  q.options.forEach((opt, i) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "opt";
    btn.textContent = opt;
    if (state.answers[q.id] === i) btn.classList.add("selected");
    btn.onclick = () => selectOption(q.id, i);
    li.appendChild(btn);
    list.appendChild(li);
  });

  const nextBtn = el("nextBtn");
  nextBtn.disabled = state.answers[q.id] === undefined;
  nextBtn.textContent = state.current === total - 1 ? "Finish" : "Next";
}

function selectOption(qid, idx) {
  state.answers[qid] = idx;
  renderQuestion();
}

function next() {
  if (state.current < state.questions.length - 1) {
    state.current++;
    renderQuestion();
  } else {
    submitQuiz();
  }
}

async function submitQuiz() {
  const answers = state.questions.map((q) => ({
    questionId: q.id,
    selected: state.answers[q.id] ?? -1,
  }));
  const res = await fetch("/api/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  const result = await res.json();
  renderResult(result);
}

function renderResult(result) {
  show("result");
  el("progressBar").style.width = "100%";

  const ring = el("scoreRing");
  ring.style.setProperty("--pct", `${result.score}%`);
  el("scorePct").textContent = `${result.score}%`;
  el("scoreLine").textContent = `${result.correct} of ${result.total} correct — ${verdict(result.score)}`;

  const byId = new Map(state.questions.map((q) => [q.id, q]));
  const review = el("review");
  review.innerHTML = "";
  for (const f of result.feedback) {
    const q = byId.get(f.questionId);
    const item = document.createElement("div");
    item.className = `review-item ${f.correct ? "ok" : "bad"}`;
    const chosen = f.selected >= 0 && q ? q.options[f.selected] : "(no answer)";
    const correct = q ? q.options[f.correctIndex] : "";
    item.innerHTML =
      `<div class="q">${f.correct ? "✅" : "❌"} ${escapeHtml(f.question)}</div>` +
      (f.correct
        ? ""
        : `<div class="exp">Your answer: ${escapeHtml(chosen)} · Correct: ${escapeHtml(correct)}</div>`) +
      `<div class="exp">${escapeHtml(f.explanation)}</div>`;
    review.appendChild(item);
  }
}

function verdict(score) {
  if (score >= 90) return "DevOps pro! 🏆";
  if (score >= 70) return "Solid knowledge 💪";
  if (score >= 50) return "Getting there 📈";
  return "Keep studying 📚";
}

function show(screen) {
  for (const s of ["start", "quiz", "result"]) {
    el(s).classList.toggle("hidden", s !== screen);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

el("startBtn").onclick = startQuiz;
el("nextBtn").onclick = next;
el("restartBtn").onclick = () => show("start");

loadCategories().catch((e) => {
  el("startMeta").textContent = "Failed to load quiz data.";
  console.error(e);
});
