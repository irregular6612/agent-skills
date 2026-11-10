// One file per talk: what the deck is, how long each part may take, and the question ledger.
// Fill this in at the storyline step (SKILL.md Phase 2) before writing any section file.
module.exports = {
  title: "Talk title",
  author: "Presenter(s)",
  scriptLang: "ko",                        // language of build/script/<lang>/*.md (speaker notes)
  sessions: { A: 30 },                     // minutes per presenter block; Q&A/discussion not included
  // section files in order: build/<name>.js. min = target minutes (script + clicks) from the storyline.
  sections: {
    s1_background: { session: "A", min: 5 },
    s2_q1: { session: "A", min: 12 },
    s3_synthesis: { session: "A", min: 4 },
  },
  questions: [
    { id: "Q1", short: "≤ 22 chars", full: "The full research question, one sentence?", session: "Session A", papers: "Author 2024 · Author 2025" },
  ],
};
