# Phase 3: The Self-Editing Agentic Loop Specification (*The Quarantine Manifest*)

Every chapter is executed as a strict **4-Stage State Machine** to prevent context-window drift, LLM rushing/summarizing, and continuity errors across the 23-chapter manuscript.

## Stage 1: Context Loader
Before generating a single word of prose, the agent MUST read:
1. `01_style_guide.md` (Lexical bans, 100% 1st-person present POV/tense contract, cadence rules)
2. `02_world_and_characters.md` (Fixed physical anchors, Barrow Island `B.I.Q.S.-04` layout, timeline, cast dossiers)
3. `03_chapter_outline.md` (Target chapter's Micro-Goal, Value Shift, Fair-Play Clues, Cliffhanger)
4. `04_current_state.md` (Inventory, character locations, knowledge matrix, last chapter summary)

## Stage 2: The Drafter (Scene-by-Scene Expansion)
To defeat LLM compression, each **1,750–2,200-word** chapter is drafted across **3 discrete ~600–750-word scene beats** (no skipping transitions):
- **Scene Beat A (~600–700 words): Entry & Spatial Friction.** Establish physical setting via 2+ non-visual sensory details, immediate tactical micro-goal, and opening friction.
- **Scene Beat B (~600–750 words): Subtext Confrontation / Investigation.** Characters deflect with logistics or physical tasks; advance conflict without exposition dumps.
- **Scene Beat C (~600–750 words): Value Shift & Early-Cut Hook.** Execute the physical clue/reversal and **cut two beats early** on a concrete object or interrupted motion—never a summary thought.

## Stage 3: The Ruthless Editor (Critic Agent + Deterministic Linter)
Run two passes on the raw draft:
1. **Deterministic Linter (`python3 scripts/style_lint.py chapters/chapter_XX.md`):**
   - Rejects any banned lexicon match (`testament`, `tapestry`, `palpable`, `ozone`, `shiver down`, etc.).
   - Flags participial (`-ing`) opener density > 1 per 500 words.
   - Flags 3+ consecutive medium-length (12–16 word) sentences.
   - Verifies total word count sits within **1,750–2,200 words** (Chapter 1 is locked verbatim from Book 2's back-matter preview).
2. **Qualitative Critic Rubric:**
   - **Pacing & Hook Retention:** Does line 1 establish tension/specificity? Does the final line force a page-turn without summarizing?
   - **Continuity & State Tracking:** Does every object, scar, wound, handedness, date, and character knowledge state match `02_world_and_characters.md`, `04_current_state.md`, `../Master_story`, and `../Master_plot`?
   - **LLM-ism Purge:** Cut emotion-telling (*"I felt scared"*), `"not X, but Y"` crutches, and melodrama.

## Stage 4: The Rewriter & State Updater
1. Apply every deterministic linter fix and Critic redline cleanly into the final polished chapter file (`chapters/chapter_XX.md`).
2. Re-run `python3 scripts/style_lint.py chapters/chapter_XX.md` until **PASS (0 violations)**.
3. Update `04_current_state.md` with:
   - Updated chapter count, cumulative word count, timeline clock, locations, inventory, planted clues, and a tight **≤100-word Last Chapter Summary**.
