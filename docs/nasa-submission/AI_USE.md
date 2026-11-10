# Use of Artificial Intelligence

Draft for the team to confirm before submission. The 2026 participant rules ask each submission to describe how AI tools were used during development; check the exact wording and any labelling requirement in the Project Submission Guide before copying this into the project page.

## In the development of the project

- **Code, tests and documentation.** The team worked with two AI coding assistants, Claude Code (Anthropic) and Codex (OpenAI), under the direction and review of the team lead. They wrote and reviewed backend and frontend code, automated tests, the decision log and the documents in this folder. Every merge into the main branch passed the automated test suite, the frontend build and a browser check.
- **Design assets.** The application icon is an SVG written with AI assistance. The project contains no AI-generated photographs, video or audio.
- **Verification.** Statistical code is checked against frozen reference values from an independent implementation (`pymannkendall`), financial formulas against independent calculations, and the wind and hydro models against real production reported by the grid operator COES.

## In the product

- **No AI generates or alters data.** Every figure comes from a cited provider, from a declared calculation, or from an assumption entered by the user, and is labelled with one of six provenance classes.
- **Trend detection is classical statistics.** Mann–Kendall with the Hamed–Rao correction, Theil–Sen and Benjamini–Hochberg. No machine learning model is trained or applied by the platform.
- **The answers to the challenge questions and the discoveries are built by deterministic rules** from the computed results. No language model is involved.
- **The assistant answers by rules by default,** using only the texts and figures of the current analysis. A language model (Google Gemini) is called only when the user presses a separate button, and its answer is restricted to the figures of the analysis.
- **One data source is itself a machine-learning product:** NASA's LHASA 2 landslide nowcast. The platform reports its value as published and does not classify it as an alert.
