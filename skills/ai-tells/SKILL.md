---
name: ai-tells
description: Check a page or text for common AI-writing tells with TypeSafe's Jev decision model, and calibrate new tells before trusting them. The check step splits any HTML, Markdown or plain text into sentences, sends one request per sentence pinned to jev-1.14.0, and lists flagged sentences with probabilities, yes and unsure bands, and rates per 100 sentences and per 1,000 words against human and AI baselines. Only tells that passed calibration are reported as tells; the rest are shown as leads. The calibrate step tests a candidate tell definition on human and AI corpus sentences (HAP-E-2) and keeps it only if the AI-to-human ratio is 2x or more and held-out precision is 0.8 or more. Use when asked whether a document reads like AI wrote it, to audit an explainer or doc before publishing, or to add or re-test a tell.
---

# ai-tells

A checker for AI-writing tells that has been measured, not guessed.
A tell here is a sentence-level construction (a participial clause tacked on with a comma, a tricolon, and so on) that Jev can spot and that appears much more often in AI text than in human text.
Every tell in `tells.json` has a record of how it was tested, and only tells that passed are reported as tells.

Read `jev-field-practice` first if you change any question wording; it explains how Jev reads questions.
This skill does not cover Jev's API.

## Safety limits

- **Key.**
  The key goes only in the request header, read from `TYPESAFE_API_KEY`, a named `.env` file (`--env-file`, only that one variable is read) or a private key file (`--key-file`, mode 600).
  Never put it on a command line, in a log, in output or in a file.
  Use a key the user has said this task may use; ask first if you were not given one.
- **Spend cap.**
  Both steps estimate the cost first, refuse to start if the estimate passes `--cap-usd`, and enforce the cap again in code from the token usage each response reports.
  Jev input costs about $0.042 per million tokens.
  A checker pass over a 400-sentence page with two tells costs about 2 cents.
- **Private text.**
  Every sentence you check is sent to TypeSafe (or to the provider you choose with `--provider`).
  Redact or get the owner's approval before sending text that is not meant to leave their machine.
- **Pinned model.**
  Requests name `jev-1.14.0`, and a response from any other model is an error.
  A baseline measured on one model version does not carry to another, so recalibrate when you change the pin.

## Check a document

```sh
python3 scripts/check.py PAGE.html            # kept tells only
python3 scripts/check.py notes.md --leads     # also list unvalidated leads
python3 scripts/check.py - --format plain < draft.txt
python3 scripts/check.py PAGE.html --dry-run  # sentence count and cost estimate, nothing sent
```

Options: `--cap-usd` (default 0.25), `--json OUT` for the full report, `--tells a,b`, `--provider typesafe|vercel`, `--env-file`, `--key-file`.

It prints:

- the sentence and word counts (headings are set apart and not sent);
- per tell, the **flagged** sentences (probability at or above the tell's yes cutoff) and the **unsure** ones (between its no and yes cutoffs), each with its probability;
- rates per 100 sentences and per 1,000 words, beside the human and AI baselines from each calibration.

How to read it:

- Compare **per 1,000 words** first. Calibration sentences average about 24 words, so a page of short sentences looks high per 100 sentences.
- A rate near or under the human baseline means the page does not overuse that tell. A rate above the AI baseline is worth a look sentence by sentence.
- A flagged sentence is a candidate to rewrite, not proof that a model wrote it. People use these constructions too, and a good human sentence can be flagged.
- **Leads** are tells that have not passed calibration: their cutoffs are unvalidated or their precision fell short. List them if they help a human read, but never count them as tells or report their rates as findings.
- Rejected tells are never asked.

## Calibrate a tell

A candidate is a question for Jev (a Noul in `tells.json`, with a question, what counts, a NOT clause and one yes and one no example) plus a status of `lead` until it earns `kept`.
Calibrate with `scripts/calibrate.py`, which needs `pandas` and `pyarrow` for the corpus steps only.
Get the HAP-E-2 files (`hape2-text_chunk_1`, `hape2-text_chunk_2` and one AI model's file) from https://huggingface.co/datasets/browndw/human-ai-parallel-corpus-2.

1. **Define.** Write the question using the rules in `jev-field-practice`: narrow, one construction, a NOT clause naming the ordinary use. Put it in a copy of `tells.json`.
2. **Sample.** `calibrate.py sample RUN --corpus DIR --ai-parquet NAME` (or `--ai-jsonl FILE` with `{base, text}` rows from a model you generated with). It draws 150 academic and 150 news openings (seed 194) and takes one eligible sentence from each pair's human text and AI text: 300 and 300.
3. **Run.** `calibrate.py run RUN --tells a,b --defs FILE` sends one request per sentence (resumable). `calibrate.py rank RUN` shows each tell's ratio at 0.5.
4. **Register.** `calibrate.py register RUN --tells a,b --defs FILE` freezes the question hashes, the sample hash and the rule (ratio at least 2.0, held-out precision at least 0.8) **before any label exists**. It refuses once labels exist, and `label-sheet` refuses without it.
5. **Label.** `calibrate.py label-sheet RUN` picks 40 sentences per tell (up to 20 above 0.5, the rest below), splits each stratum into dev and held-out halves, and writes a blind sheet with only the tell and the sentence. A labeller who has not seen Jev's probability or whether the text is human or AI writes `labels.jsonl` (`{"item": n, "label": true|false}`) against the written definition.
6. **Decide.** `calibrate.py decide RUN` sets the yes cutoff from the dev half (the smallest of 0.5 to 0.9 with precision 0.8 or more) and the no cutoff, then measures ratio at that cutoff and held-out precision. A tell with fewer than 5 yes answers is too rare to keep.
7. **Replay.** `calibrate.py replay-ids RUN` lists answers within 0.1 of a cutoff; run them again with `--tag replay1 --ids FILE` and `decide` again. Answers near a cutoff flip between replays.
8. **Promote.** `calibrate.py promote RUN --into tells.json --id ID --ai-source NAME` writes status, cutoffs, the calibration record and a baseline (rates per 100 sentences and per 1,000 words for the human and AI samples).

Cost: about 600 requests at 1,800 to 2,900 tokens each, roughly 5 to 15 cents for a handful of tells.

What a calibration does not show:

- It is only as good as its labels. If a model labelled, say so; a person's labels are better.
- The AI control is one model. A tell measured against Claude Haiku 4.5 text may not hold for another model, which is why a calibration against the model that writes your text is the useful one.
- Ratios and precision are for corpus genres (academic and news), not every genre. Check a tell on a page of your own kind before trusting it there.

## Where the current tells stand

As of the Opus 5.5 rerun, one tell is validated: **tricolon** (a series of exactly three parallel items).
The participial clause passed against Claude Haiku 4.5 text but not against Opus 5.5, so it is a lead.
Corrective framing, the importance flag, the stock signpost opener and the clause-subject passive are rejected as tells.
They may still be useful as a reader's lint (an explainer's own "X, not Y" habit), but they do not separate AI text from human text in these samples.

`tells.json` holds each tell's `status` (`kept`, `lead` or `rejected`), cutoffs, calibration record and baselines.
`CALIBRATIONS.md` has the numbers and what each calibration found.
