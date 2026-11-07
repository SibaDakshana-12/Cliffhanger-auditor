# Cliffhanger Auditor (Problem 3)

**Links:**
- App: https://cliffhanger-auditor-mmvbkdwqqpei5lx7fj2xga.streamlit.app/ (synthetic demo, baseline only)
- Code: https://github.com/SibaDakshana-12/cliffhanger-auditor
- Raw outputs: _(Drive link)_
- Video: _(link)_

**One user, one step, one checkable output:** a story editor reviewing episode endings gets each ending (and the next episode's opening) scored, weak ones flagged with evidence line IDs and timestamps, and an optional earlier cut point using existing lines. They accept or reject each one.

## Why this problem (and not 1 or 2)
_(Your words. Draw on research/problem_proof.md: the 2 Kuku episodes that ended on cliffhangers and made you want the next one, the 2 Instagram reels with no cliffhanger (one a hook only, one a flat continuation you found boring), and what friends described. Explain the overlap with Problem 1: a promo also has to end on a cliffhanger, so the same ending judgment serves both. Explain why it matters more than Problems 1 and 2.)_

**Limits of that evidence:** 2 episodes, 2 reels and 3-4 friends. Endings are one factor among several; friends also named animation, audio and story variety.

## Assumptions
- **Not verified:** editors check endings by hand today; re-cutting or reordering existing material is possible in their workflow.
- **Judged from the script only.** Script time is not the same as the final video length.
- **Windows:** the ending is the last ~25s and the opening is the next episode's first ~10s. These are judgment calls, set in config.yaml.
- **Flag rule:** an episode is weak if its weighted score is 3.0 or below, or pull_to_next is 2 or below. I set this after seeing my own 10 scores, so agreement on those 10 is optimistic.

## How it works
1. **Code:** a regex parser gives every script line an ID and its own timestamp, and picks the ending and opening windows.
2. **LLM** (Gemini, one call per episode): sees only the numbered window lines, with writer labels like "cliffhanger" masked. It returns JSON: ending type, five 1-5 scores, confidence, reason, evidence IDs, and a cut point or "no_valid_alternative".
3. **Code:** Pydantic and validators reject invented line IDs, cut points outside the episode, and broken rubric rules, then retry once with the problems listed. Timestamps always come from the parser. The weighted score and flag are plain Python, with weights in config.yaml.
4. **Human:** a Streamlit app ranks the weakest endings first. Each gets Accept, Reject or Needs review, saved to CSV, with a live acceptance rate.

A keyword baseline runs alongside it, to check the LLM is worth its cost.

## How I know it's good (real runs; n=10 is tiny)
I scored 10 episodes (from 1-40) myself before seeing any AI output. Main model: gemini-3.5-flash-lite.

| vs my scores | LLM | Keyword baseline |
|---|---|---|
| Weak/strong flag agrees | **8/10** (0 false flags; missed 2) | 6/10 (falsely flags all 4 strong endings) |
| Overall within 1 point | **10/10** | 6/10 |
| pull_to_next within 1 point | 9/10 | 6/10 |
| Ending type, exact match | 5/10 | 2/10 |

**Full run on 1-40:** 40/40 valid outputs. 3 invalid outputs were caught by the validators and fixed on retry, plus 2 rate-limit retries. 10 episodes were flagged.

**Held-out 41-50** (prompt never tuned on them; run once as an interview dry run): 10/10 valid outputs, 3 invalid outputs caught by validation and fixed on retry, 0 API failures, 0 flagged. Final scores 3.2-5.0, four episodes at 5.0. I have no manual scores for 41-50, so this shows the tool runs cleanly on unseen input. It doesn't measure accuracy there, and the high scores fit the upward squeeze seen on 1-40.

**Model swap** (same prompt, a one-line config change; gemini-3.5-flash vs flash-lite on episodes 1-11): same flag on 10/11, final score within 1 point on 11/11, same ending type on 9/11. Flash-lite scored slightly higher on average and used about 6-8x fewer output tokens.

**Success in a real team:** the editor's acceptance rate, and the share of flagged episodes the editor agrees with. Improved retention would need audience data, and I don't claim it.

## Where it fails
- **Missed the flat ending:** episode 20, which I scored flat (pull 2), was called a "threat" (pull 3). Flash-lite never used "flat" on any of the 40 episodes.
- **Over-scores weak endings:** episode 24 got pull 5 where I gave 2. Pull was 5 on 23 of 40 episodes. It works more like a hook / no-hook switch than a 1-5 scale.
- **Never suggested a cut on flash-lite** (all 40 "no_valid_alternative"). gemini-3.5-flash did suggest cuts, so this feature depends on the model.
- **Confidence was always 0.90-1.00,** including on the misses. It is labelled uncalibrated everywhere.
- **Trope risk:** humiliation and withheld-reveal endings all got pull 5, but so did threat endings. With one manual example, I can't confirm trope-specific over-scoring.
- **Can't judge animation, audio, acting or story originality:** it reads scripts only.
- **The validators check that cited lines exist,** not that they support the reason.

## Scale, cost, languages
- **Real tokens per episode:** about 2,600 input. Output was about 280 (flash-lite) or about 1,500 (3.5-flash, which "thinks" first).
- **Cost:** at the paid list prices in config.yaml (to verify), that's about $0.0015 per episode with flash-lite and $0.005 with 3.5-flash: roughly $7-23 per 100 shows of 50 episodes.
- **Throughput:** the free tier allows about 20 requests per day per model, which ran out several times during this project. Production needs the paid tier, which also stops Google using the content.
- **Any show in this format** runs with `python run.py --input <folder>`. A different format fails with a clear error.
- **Other languages: untested.** The baseline's keyword lists are English-only, the LLM prompt is in English, and the parser assumes this format.

## What a stronger paid model would add
Based on the swap: 3.5-flash, unlike lite, actually suggested cuts and spread its scores more. A stronger model could plausibly separate flat from deliberate endings better. That's untested, and the 10-episode comparison is how I'd check it. The cost is the same token counts at that model's price (to verify).

## Tools used, and one place AI got it wrong
- **Tools:** Claude Code (build), Gemini 2.5-flash / 3.5-flash / 3.5-flash-lite (scoring), Python, Pydantic, Pandas, Streamlit.
- **Where AI got it wrong:** _(pick one from notes/ai_mistakes.md. Suggested: M7, flash-lite gave pull 5 to an ending I scored 2 and never recognised a flat ending, with 0.95 confidence. Or M3, another AI assistant confidently claimed the scripts had no line IDs.)_
