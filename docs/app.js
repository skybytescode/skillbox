"use strict";

// Static (GitHub Pages) build of the SkillBox DevOps quiz.
// There is no backend here: questions are loaded from questions.json and
// graded entirely in the browser. Identical UX to the Go-served version.

const el = (id) => document.getElementById(id);

const state = {
  bank: [], // full question objects (with answers)
  quiz: [], // current run's questions
  answers: {}, // questionId -> selected index
  current: 0,
};

async function loadBank() {
  const res = await fetch("questions.json");
  if (!res.ok) throw new Error("failed to load questions.json");
  state.bank = await res.json();

  const cats = [...new Set(state.bank.map((q) => q.category))].sort();
  const select = el("category");
  select.innerHTML = "";
  const all = document.createElement("option");
  all.value = "All";
  all.textContent = "All categories";
  select.appendChild(all);
  for (const c of cats) {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = c;
    select.appendChild(o);
  }
  el("startMeta").textContent = `${state.bank.length} questions available across ${cats.length} categories.`;
}

function startQuiz() {
  const category = el("category").value;
  const count = parseInt(el("count").value, 10);

  let pool = state.bank.filter((q) => category === "All" || q.category === category);
  if (count > 0) pool = pool.slice(0, count);

  state.quiz = pool;
  state.answers = {};
  state.current = 0;

  if (state.quiz.length === 0) {
    el("startMeta").textContent = "No questions found for that selection.";
    return;
  }
  show("quiz");
  renderQuestion();
}

function renderQuestion() {
  const q = state.quiz[state.current];
  const total = state.quiz.length;

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
  if (state.current < state.quiz.length - 1) {
    state.current++;
    renderQuestion();
  } else {
    finish();
  }
}

function finish() {
  let correct = 0;
  const feedback = state.quiz.map((q) => {
    const selected = state.answers[q.id] ?? -1;
    const ok = selected === q.answer;
    if (ok) correct++;
    return { q, selected, ok };
  });
  const total = state.quiz.length;
  const score = total > 0 ? Math.round((correct / total) * 100) : 0;
  renderResult({ total, correct, score, feedback });
}

function renderResult(result) {
  show("result");
  el("progressBar").style.width = "100%";

  const ring = el("scoreRing");
  ring.style.setProperty("--pct", `${result.score}%`);
  el("scorePct").textContent = `${result.score}%`;
  el("scoreLine").textContent = `${result.correct} of ${result.total} correct — ${verdict(result.score)}`;

  const review = el("review");
  review.innerHTML = "";
  for (const f of result.feedback) {
    const q = f.q;
    const item = document.createElement("div");
    item.className = `review-item ${f.ok ? "ok" : "bad"}`;
    const chosen = f.selected >= 0 ? q.options[f.selected] : "(no answer)";
    const correct = q.options[q.answer];
    item.innerHTML =
      `<div class="q">${f.ok ? "✅" : "❌"} ${escapeHtml(q.question)}</div>` +
      (f.ok
        ? ""
        : `<div class="exp">Your answer: ${escapeHtml(chosen)} · Correct: ${escapeHtml(correct)}</div>`) +
      `<div class="exp">${escapeHtml(q.explanation)}</div>`;
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

loadBank().catch((e) => {
  el("startMeta").textContent = "Failed to load quiz data.";
  console.error(e);
});
