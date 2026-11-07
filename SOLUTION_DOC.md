# Cliffhanger Auditor (Problem 3)

**App:** https://cliffhanger-auditor-mmvbkdwqqpei5lx7fj2xga.streamlit.app/ (synthetic demo, baseline only) ·
**Code:** https://github.com/SibaDakshana-12/cliffhanger-auditor ·
**Raw outputs:** _(Drive link: add it in the PDF only; not in the public repo)_ · **Video:** _(link)_

**One user, one step, one checkable output:** a story editor reviewing episode endings gets each ending (and the next episode's opening) scored, weak ones flagged with evidence line IDs and timestamps, and an optional earlier cut point using existing lines. They accept or reject each one.

## Why this problem (and not 1 or 2)
In the short videos I've watched, people really wait for the next part when a video ends on a cliffhanger; otherwise they just make fun of it. On Instagram channels posting short AI videos, most comments ask for the next part. The two Kuku episodes I watched ended on cliffhangers and made me want the next one; one Instagram reel just continued, and I found it boring.

Problem 1 picks promo moments from finished episodes; my tool finds weak endings while they can still be fixed. Problem 2 (AI lawyer) has nothing to do with Kuku's business, while this problem is tied directly to Kuku's own product: episodes that make people want the next one. The two overlap: a good promo also has to end on a cliffhanger.

**Limits of the evidence:** 2 episodes, 2 reels, 3-4 friends, and Instagram comments I didn't screenshot. Endings are one factor among several; friends also named animation, audio and story variety.

## Assumptions
- **Not verified:** editors check endings by hand today; re-cutting existing material is possible in their workflow.
- **Script only:** script time is not the same as the final video length. The ending window (last ~25s) and opening window (next ~10s) are judgment calls, set in config.yaml.
- **Flag rule:** an episode is weak if its weighted score is 3.0 or below, or pull_to_next is 2 or below. I set this after seeing my own 10 scores, so agreement on those 10 is optimistic.

## How it works
1. **Code:** a regex parser gives every line an ID and its own timestamp, and cuts the ending and opening windows.
2. **LLM** (Gemini, one call per episode): sees only the numbered window lines, with writer labels like "cliffhanger" masked. It returns JSON: ending type, five 1-5 scores, confidence, reason, evidence IDs, and a cut point or "no_valid_alternative".
3. **Code:** validators reject invented line IDs, cuts outside the episode and broken rubric rules, then retry once. Timestamps come only from the parser. The weighted score and flag are plain Python.
4. **Human:** a Streamlit app shows the weakest endings first: Accept, Reject or Needs review, with a live acceptance rate.

A keyword baseline runs alongside it, to check the LLM is worth its cost.

## How I know it's good (real runs; n=10 is tiny)
I scored 10 episodes (from 1-40) myself before seeing any AI output. Main model: gemini-3.5-flash-lite.

| vs my scores | LLM | Keyword baseline |
|---|---|---|
| Weak/strong flag agrees | **8/10** (0 false flags; missed 2) | 6/10 (falsely flags all 4 strong endings) |
| Overall within 1 point | **10/10** | 6/10 |
| Ending type, exact match | 5/10 | 2/10 |

- **Episodes 1-40:** 40/40 valid outputs; validators caught 3 invalid outputs, all fixed on retry; 10 flagged.
- **Held-out 41-50** (never used to tune the prompt): 10/10 valid, 0 flagged. There are no manual scores for these, so this shows it runs on unseen input, not that it's accurate there.
- **Model swap** (a one-line config change; 3.5-flash vs flash-lite on episodes 1-11): same flag on 10/11, final score within 1 point on 11/11. Flash-lite used about 6x fewer output tokens.
- **Editor review of the 10 flags (in the app):** 6 accepted, 2 rejected (16, 17), 2 needs review, so the **acceptance rate is 6/8 = 75%**. Episode 17 is a deliberate, tender ending: my rule-based flag and the model both caught it, but on reading it I rejected the flag. The 3.0 threshold also catches quiet endings that are fine.
- **Success in a real team:** the same acceptance rate over many shows. Improved retention would need audience data, and I don't claim it.

## Where it fails
- **Squeezes scores to the top:** pull was 5 on 23 of 40 episodes; episode 24 got 5 where I gave 2. It acts more like a hook / no-hook switch than a 1-5 scale.
- **Never recognised a flat ending** (see below), and on flash-lite **never suggested a cut**. 3.5-flash did, so that feature depends on the model.
- **Confidence was always 0.90-1.00,** even on the misses, so it's labelled uncalibrated everywhere.
- **Trope risk:** humiliation and withheld-reveal endings all got pull 5, but so did threat endings. With one manual example, I can't confirm trope-specific over-scoring.
- **Reads scripts only:** it can't judge animation, audio, acting or originality. Validators check that cited lines exist, not that they support the reason.

## Scale, cost, languages
- **Real tokens per episode:** about 2,600 input; output about 280 (flash-lite) or 1,500 (3.5-flash).
- **Cost:** nothing was spent; every run used the free tier. At flash-lite's paid price ($0.30 / $2.50 per 1M input/output tokens, checked 2026-11-08), that's about **$0.0015 per episode, $0.09 per show, ~$9 per 100 shows**.
- **Throughput:** the free tier allows about 20 requests per day per model, and it ran out several times. Production needs the paid tier, which also stops Google using the inputs to improve its products.
- **Any show in this format:** `python run.py --input <folder>`. Other formats fail with a clear error. **Other languages are untested:** the prompt and baseline keywords are English.

## What a stronger paid model would add
In the swap, 3.5-flash suggested cut points where flash-lite never did. A stronger model might also tell flat endings from deliberate ones. That's untested, and my 10 manual scores are how I'd check it, at the same token counts times that model's price.

## Tools used, and one place AI got it wrong
- **Tools:** Claude Code (build), Gemini 2.5-flash / 3.5-flash / 3.5-flash-lite (scoring), Python, Pydantic, Pandas, Streamlit.
- **Where AI got it wrong:** I scored episode 20 as a flat ending: the story just continues with no new hook (pull 2). gemini-3.5-flash-lite called it a "threat" (pull 3, 0.90 confidence), so it wasn't flagged. Across 40 episodes it never labelled an ending "flat", even though that was an explicit rubric rule. That's why every flag goes to a human.
