---
name: jev-field-practice
description: Field-tested heuristics for building with TypeSafe's Jev decision model - how to word questions and options so Jev does well, what state to send and how to prepare it in code, when to offer a none or abstain option, many questions in one request versus one at a time, confidence floors and code-owned control flow in multi-step workflows, offline testing with held-out data, and using Jev as a gate. Each heuristic says when it matters, and numbers appear only where a public source backs them. Use when designing, prompting, testing, tuning, debugging or evaluating anything built on Jev, including classifiers and taggers, routers, browser or form agents, voice or chat pipelines that fill structured data, and judgment gates. TypeSafe's own docs and typesafe-ai skill cover the API itself.
---

# jev-field-practice

Heuristics for getting good decisions out of Jev, TypeSafe's decision model.
Read them as judgment, not a checklist: each one says what tended to work and when it matters.
The only hard rules are the safety limits in the next section.

The heuristics come from our own experiments with Jev: a multi-label message tagger, a router that matches a task description to one of several handling rules, an allocator that picks between resource pools, and agents that fill multi-step web forms.
Those measurements are not published, so this file states what they showed without their numbers.
Where a number appears, a public source backs it, and the source is cited by an ID such as **[E3]** that resolves in `sources.md` beside this file.
Our experiments and most of the cited studies ran on `jev-1.13`; check the current model's notes before relying on any of it.

This skill does not cover how to call Jev.
For the API, the SDKs, the primitives (Noul, Choice and the rest), limits and prices, read TypeSafe's docs at https://docs.typesafe.ai and their `typesafe-ai` agent skill (https://github.com/typesafe-ai/skills).
Their model notes for `jev-1.13` (https://docs.typesafe.ai/model-jaggedness/jev-1.13.md) list the known weak spots, and several heuristics below are the practical side of that page.

**Access (checked 2026-10-14).**
A TypeSafe key isn't required: Jev is also served through two other providers, billed to your account there.
Provider lists, model ids and retention terms change, so check these pages before relying on them.

- **OpenRouter** serves Jev 1.13 (https://openrouter.ai/typesafe/jev-1.13) through its System One API, and the TypeSafe SDKs work against it with a changed base URL and an OpenRouter key (https://openrouter.ai/docs/guides/community/typesafe-sdk).
  Its endpoint is on OpenRouter's zero-data-retention list, and you can enforce ZDR per request or account-wide (https://openrouter.ai/docs/features/zdr).
- **Vercel AI Gateway** serves it as `typesafe-ai/jev` (https://vercel.com/ai-gateway/models/jev), called through the AI SDK's `experimental_decide` (https://ai-sdk.dev/docs/ai-sdk-core/decisions).
  Both providers it routes to are marked no-training, but only TypeSafe's own endpoint has zero data retention (https://ai-gateway.vercel.sh/v1/models/typesafe-ai/jev/endpoints), so pin that provider if you need it (https://vercel.com/docs/ai-gateway/models-and-providers/provider-filtering-and-ordering).

## Safety limits

- **Private data.**
  Redact real people's messages, records and personal details before they reach Jev, and get the owner's approval before sending a batch of real history.
  Keep raw text and raw answers in a private folder and let only aggregate scores leave it.
- **Keys and spend.**
  Pass the API key in the request header from the environment or a file descriptor, never on a command line, in a log or in a committed file.
  A batch run enforces its spend cap in code, from the token usage each response reports, and reserves each request's cost before sending it.
- **Untrusted text in a gate.**
  Text Jev is judging (a worker's report, a page you did not write) is never the source that supports a claim, and a Jev verdict that gates something may demote, never authorise.
  See "Using Jev as a gate".
- **Automating third-party sites.**
  Drive them from a dedicated automation browser with its own profile, never someone's everyday browser and its saved sign-ins.
  Never automate a step that commits a person: buying, paying, signing, or submitting an application.

## 1. What makes Jev perform well

### Wording is the lever that moves scores most

In every application we tried, rewriting what the question, options and definitions say moved results more than adding context, moving thresholds or changing settings.
*Third-party* evidence agrees: criteria rewrites moved paired accuracy from 70% to 96%, and a narrow question scored 0.99 where the same check inside a broad question scored 0.30 **[E9]**.
A trolley-problem benchmark of Jev and other decision models found that rewording the same dilemma changed what the models chose **[E16]**.

- **For a router, say the shape of each rule, name its signals, and end with what it is NOT.**
  A NOT clause naming the neighbouring rule each rule must not absorb was the change that removed confident wrong answers in our router.
  When one rule kept winning cases it should not, tightening its wording fixed it where trimming the context had not.
- **For a category definition, add a boundary note and one or two worked examples.**
  A boundary note that says which neighbouring category owns a case was the one change in our tagger that held up on fresh data.
- **Say what counts, not just what is central.**
  Most of our tagger's misses were real secondary topics scored just under the threshold.
  Saying that a topic need not be the message's main subject, and that a message can have several, recovered most of them.
- **Ask the narrow question.**
  "Should a button be pressed yet?" invites `none`; "The form is filled in. Which button submits it?" gets the right button.
- **Make the question's premise true wherever it is asked.**
  A question that assumes a filled form ("which control submits these fields?") is correctly answered `none` on a landing page that has no form.
  If code chooses which question to ask (an entry question on a landing page, a submit question on a form step), that choice is part of the wording and needs its own test.
- **Make every option self-contained and unique**, such as `question ▸ option` rather than a bare "Yes".
  A page with several identical Yes/No buttons is ambiguous to Jev until each option names its question.
  *Third-party* **[E10]**: a whole move as one option beat splitting it into action, target and value.

Prompting habits that came out of this:

- Keep the prompt as a versioned data file and record its revision with every answer.
- Take worked examples from the tuning data, not from the set you will judge on.
- When a question tells Jev how to use context, test that sentence on its own (section 2 has the case where one restrictive sentence cost most of the short replies the context was added for).
- Instruction text repeats per question, so it is usually most of a request's tokens (section 4).

### Thresholds are rarely the lever

When precision or coverage is short, moving the threshold tends to trade one for the other without reaching both.
In our tagger no threshold reached the precision target until the wording changed.
So try the wording before tuning the threshold, and tune the threshold on development data only.

### Let code do the arithmetic, and hand Jev a verdict or a plain-language state

When we asked Jev to choose between resource pools from their quota state, the same policy text did better the more of the work code had done first: raw numbers, then numbers computed in code, then plain-language buckets, then code-stated verdicts ("eligible", "over budget").
Only the verdicts gave reliable, confident picks, and once code states the verdict the decision is code's, so we made that choice deterministic.

The heuristic: a comparison of quantities, dates or thresholds belongs in code, and Jev is good at reading language into categories.
TypeSafe's model notes say the same for counting, arithmetic and date comparison.
*Third-party* results on counting and dates disagree with each other, from near-perfect on simple comparisons to poor on exact counting **[E13]**; the heuristic stands either way because code is exact.

### Gains on development data often shrink on fresh data

Several of our changes that looked clearly better on the data they were tuned on gave a smaller gain, or none, on data collected after tuning finished.
Each fresh sample also brought a boundary nobody had written down, such as a new feature whose name reused a word that had meant another category.

A held-out set is worth building when a result will be relied on, gated on, or tuned hard over several rounds, because that is when in-sample gains mislead.
It is overkill for a one-off or a proposal a human reviews anyway: a router tuned on one set runs safely if a confidence floor hands borderline cases back.
For a vocabulary that keeps moving, such as topics that change with the product, a live loop of small regular samples and logged corrections fits better than another fixed round.

**A held-out set has to sample what the claim is about.**
Pages from modern consumer sign-up flows say nothing about older enterprise portals built from tables, frames and server postbacks.

- **Derive strata from how runs fail, not from proxies.**
  "Site age" stands in for mechanisms that change behaviour (widget implementation, page transitions, frames, table layout, repeating rows, overlays), so stratify on those.
- **The unit is the site or flow, never the page.**
  Pages within one flow share widgets, so a hundred pages from twenty flows carry much less independent evidence than a hundred flows.
- **Size it by power.**
  6 successes out of 8 has a 95% interval of 0.35 to 0.97, so 8 flows cannot tell 50% success from 80%.
  Zero failures in N trials bounds the true failure rate below about 3/N (the rule of three).
- **Freeze and hash it before any tuning run**: a seeded stratified draw, a second labeller on every key decision, the manifest hash recorded first.
  Report aggregates only; once anyone reads per-item outcomes or designs around a specific item, the set is spent and becomes development data.
- **Key equivalent answers and harmful ones**: list every acceptable answer, and separately the answers that must never be chosen, and score both apart from confidence.

Two more things that shape how far to trust a score:

- **Replays are stable except near the threshold.**
  Identical requests return nearly identical probabilities, but answers close to a threshold flip between replays **[E12]**.
  Replay once more when a result sits near a threshold, and pin a model version rather than a "latest" alias for any comparison.
- **Labels are part of the uncertainty.**
  When we adjudicated the cases where Jev and the labeller disagreed confidently, the labeller was wrong in a meaningful share of them.
  Check the criterion as well: the wording you gave Jev may be wider or narrower than what the labels actually applied.
  A key that names one right answer also manufactures confident wrong answers when two different controls lead to the same place, so check where an answer goes before calling it wrong, and say so when you re-score after the fact.

## 2. What state to include

### Include what resolves the reference, and say how to use it

- **The message a reply answers.**
  Short replies ("yes", "go ahead", a lone option letter) cannot be classified without it, and adding just that one earlier message was our tagger's largest gain on them.
- **One more turn usually helped.**
  The turn before the message being replied to helped a little more in every round, and context rarely leaked a tag that belonged only to the context.
- **Context cannot fix a message Jev already misreads.**
  Most misses on messages that name their own topic were wording problems, not missing context.
- **The instruction about context matters as much as the context.**
  "Use it only to work out what the message refers to; judge the message itself" undid most of what the context was added for, on exactly the short replies it was meant to help.
  Letting the context say what the message is about, when the message does not say it fully, fixed that.
- **Context can also pull a message away from its own words.**
  A short question that named its topic scored high on its own and low once the previous turn, about another topic, was added.
  Check short, self-naming messages with and without context before adopting a context window.

### Prepare state in code

Jev's input tokens are cheap (see the models page for the current price), so adding state costs little; preparing it with an LLM does not, in money or latency.
State built deterministically from records you already have (the linked ticket, the owner, the earlier message a reply continues) takes milliseconds.
In our tagger it helped on development data and did not help on fresh data, so build it because it is cheap, and keep it out of the request until a fresh sample shows a gain.
Be wary of feeding Jev's own earlier answers back to it as state: one early misfiling then carries forward through a run of related messages.

### Give evidence as data; state a derived relation only when it is exactly true

For picking which control moves a form on, adding each candidate's facts as plain data (tag, type, where its name comes from, image alt text, page region, which form it submits, position against the fields) plus page facts (step, percent complete, amounts shown, validation messages) was our largest gain, for a modest increase in tokens.
The same facts written as derived sentences ("this button does not submit the form", "this link sits in the header") gained nothing.
Most relations code can state about a candidate are negative, and a negative statement spreads probability around instead of moving it: a correct "does not submit the form" on a script-driven button took a right answer from confident to unsure.
Positive relations (step 3 of 4, prices shown, the only submit button) were harmless but added nothing on top of the evidence.
**A wrong positive statement moves the answer the wrong way.**
A rule that called a sidebar button "the form's only submit button" when it submitted a different small form made Jev pick that button confidently.
So code states a relation only when it is true of the whole page, and never states what a control is not.

Richer evidence also makes Jev readier to press something, so score pages where the right answer is "press nothing" separately, and keep the safety check independent of it (section 9).
Send the evidence every time, rather than only when a plain request comes back unsure: asking twice cost more tokens overall, and it cannot catch a confident wrong answer.
*Third-party* **[E14]** found that derived beliefs beat raw evidence in its scenarios, and that statements which only rule something out stay weak even when stated; on our form pages the second part held and the first reversed, likely because our evidence was already per-candidate data.

### Send the parts that carry the task, not the whole document

Sending only a task description's relevant sections instead of the whole document left our router's answers unchanged and cut input tokens several-fold.
It did not fix a mis-routed case, and it pushed one borderline case under the floor, so trimming is a cost and noise lever, not an accuracy fix.
Facts code already knows (what kind of task this is, whether a written spec exists) are candidates to pass as explicit state rather than leave Jev to infer.
*Third-party* **[E3]**: many independent items packed into one long state interfere with each other.

### State for page and form judgments

- **Show state, not just controls**: checked state and current dropdown values.
  Without them an agent will pick the same placeholder option ("-Select one-") over and over.
- **Put the filled form in state** when asking which button submits it.
- **Prune what is not the task**: header, navigation, progress bar, footer, feedback and chat widgets.
  Navigation links cause detours, and a feedback tab can absorb an agent's clicks indefinitely.
  Cap labels at about 100 characters, since some dropdowns carry paragraphs of help text in their names.
- **Keep a short slice of page text**, about 2,000 characters: dropping it hides validation messages.
- **Keep off-screen controls, marked as such, and scroll when acting**; otherwise submit buttons below the fold are never chosen.
- **Give the goal as structured data, not prose.**
- **Values Jev cannot see make number-keyed options abstain.**
  If personal values reach Jev only as placeholders, options keyed by a number (counts, days a week) come back as "ask a human"; route those to a person or map the number to its option in code.
- **Shadow DOM**: treat a custom element whose shadow root holds a button as a button, and name an unlabelled input from the nearest text above it.

## 3. A none or negative option, or positive-only

This covers an option among the choices and the negatives inside the wording, and they work differently.

**A no-op or abstain option among the choices** tends to turn a confident wrong answer into a visible abstention.
Without one, a form agent will type something plausible into a field that should stay empty; with `leave_as_is` and an ask-a-human option on every field, our form fallback had no confident wrong field answers.
A router's `default` rule plus a confidence floor handed back genuine boundary cases without letting wrong answers through above the floor.
The option is only as good as its description: a `none` worded for a filled form is the right answer on every page without one (section 1).
*Third-party* **[E1]**: removing the abstain option took accuracy on unanswerable items from 0.950 to 0.000, at 0.79 confidence.
**[E8]** adds that extra options shift an ambiguous pick's probability, so keep the option set stable once floors are tuned.

**Negative criteria in the wording** (what does NOT count) did most of the precision work.
The router's NOT clauses removed its confident wrong answers, and two exclusions in the tagger's criteria (a closing line that only mentions a topic; work that was only handed off) raised precision at almost no cost in coverage, though part of that was fitted to the development errors.
Negatives help inside a definition, not as facts about candidates in state (section 2).

**Multi-label yes/no questions carry the negative inside each question**, and two thresholds give an uncertain middle band you can show for a person to confirm or reject.

Worth testing on your own data: an explicit "none of these" option for a multi-label tagger against per-label yes/no alone, and shuffled option order (TypeSafe's model notes and **[E8]** both say order can move ambiguous picks).

## 4. Many judgments at once, or one at a time

"Parallel" covers different shapes here, and they behave differently.

**Many questions over one shared state, in one request: this worked well.**
One request per form page, with one Choice per field plus one for the submit button, answered every field correctly and cost a small fraction of the tokens of a one-action-per-step agent loop, whose live failures were silently skipped questions.
A long dropdown (dozens of years) as one Choice picked right with full confidence, so there is no need to shortlist below the per-Choice option limit (check the docs for the current limit).
*Third-party* **[E2]** agrees: 16 questions against 1 over the same state shifted confidence by 0.008, and latency stayed flat from 1 to 30 questions.
TypeSafe's fan-out pattern (https://docs.typesafe.ai/patterns/fan-out.md) describes the same shape.

**Many independent items packed into one state: avoid.**
*Third-party* **[E3]**: 40 rows in one long state flipped 77 of 360 decisions, while one row per request passed.
So send one item per request, with every label as its own question.

**One Choice across options, or an independent yes/no per option.**
Use one Choice when exactly one answer is right (a routing rule, a button, a field value).
Use separate yes/no questions when several can be true, as with a message that belongs to two topics.
*Third-party* **[E10]**: independent signals combined in code beat one question, 62.6% against 95.0%.
That holds when code combines the parts any-of (a match on any one counts).
Under all-of (every part must pass) each extra question is another chance to veto, so keep a compound criterion as one question, or tune each part's threshold for the conjunction rather than one at a time.
*Third-party* **[E7]**: a Noul and a Choice give different numbers for the same judgment, so tune each threshold for its primitive.

For picking the one control that moves a flow on, one yes/no per candidate in a shared request, with a floor on the top probability, did better than one Choice over the candidates on our development pages and pressed nothing on pages where nothing should be pressed.
A tournament (groups of ten, the top two of each, then a final Choice) doubled the requests for no gain, because most pages had only a handful of candidates.

**The cost of many questions is the repeated instruction text.**
Each question carries its full wording, and in our tagger the wording took far more tokens than the context.
At Jev's price that rarely matters; sending shared instructions once instead of per question is a lever we have not measured for accuracy.

**Concurrent requests** caused no trouble at our scale (a few workers, thousands of requests, no failures or retries), and nothing suggested concurrency changes answers.

## 5. Multi-step workflows

### Code owns the flow; Jev answers the judgments code cannot make

1. **Code decides when, Jev decides which.**
   Code owns every field answered, the page settled, no loop; Jev picks which option, which value, which button.
   Code, or a stricter button floor, also owns pages that need an in-page save before moving on: Jev tends to prefer a generic "Continue" over a "Save address" style button, and those were the only wrong answers our form fallback gave.
2. **Re-ask only what changed.**
   After applying answers, take a fresh snapshot and ask again only about fields that are new or whose options changed (dependent dropdowns).
3. **Choose values, do not generate them.**
   A Choice over the caller's own value keys filled every text field correctly, with no second LLM.
4. **Deterministic first, Jev as the fallback, for anything live.**
   A per-site script runs with zero Jev calls; when a selector breaks, one Jev request finds the field.
   A stock agent loop driven only by Jev failed the same form every time.
5. **Jev classifies, code allocates.**
   In a router, Jev picks the rule and code picks what runs it.
6. **Cheap deterministic layers around Jev.**
   Rules such as "a short reply inherits its target's single topic" are right most of the time and almost never when the target had several topics; use layers like these beside Jev, not instead of it.

### Floors between steps

- **Floor on confidence and hand back below it.**
  The unstable decisions are the low-confidence ones: in our runs, both the answers that flipped between replays and the live failure spirals sat at low confidence, as in **[E5]**.
- **Per-rule floors in a router.**
  A high floor on a rule that keeps winning wrongly hands the case back as ambiguous, and a low floor on the runner-up lets it fall back to that rule instead.
- **Know which number a floor reads.**
  A Choice's confidence is (N·p_max − 1)/(N − 1) over N options, so one confidence floor is stricter on a yes/no than on a long list (TypeSafe's confidence page, https://docs.typesafe.ai/confidence.md, and **[E4]**).
  If one place in your code reads an option's probability and another reads confidence, the same floor value means different things, and a floor meant to tighten a rule can loosen it.
- **Read the floor on an equivalence class's total, not one copy's.**
  When the right control appears N times, each copy holds about 1/N of the probability, and a floor refuses all of them.
  Collapse candidates that go to the same place, keyed on label plus exact destination (form action, method and submitter, because one form can have both a "get price" and a "buy" button), never on label alone; or add up the probability over the class.
- **Calibrate a floor per kind of question on labelled cases.**
  Our form fallback's wrong answers were all on the submit button, never on fields, so the button gets a higher floor than the fields.
  *Third-party* **[E6]**: a stated probability is not a hit rate until it is checked against labels.
- **A below-floor answer on a big task is a signal.**
  A task description that splits its probability across three rules may really be three tasks; split it.
- *Third-party* **[E5]**: in an agent loop, wrong answers sit at low probability but so do some right ones, so a floor is a brake and the loop guards do the protecting.

### Chaining Jev into Jev

Keep what passes between Jev steps deterministic where you can, and score each step on its own.
Feeding a step's earlier answers back in carried one mistake forward (section 2).
To compare a two-step design against one step, run both on the same labelled set and compare confident-wrong counts, not only accuracy.

### Waits and loops in live automation

- **Wait on page signals, not the clock or class names.**
  Hold while the page has fewer than three controls (server interstitials can take seconds), trust only `aria-busy`, and after a submit wait until no fetch or XHR is in flight.
  A class-name spinner detector can match a permanent loading class and add seconds to every step.
  Waiting after every click, not just submits, adds up quickly.
- **Stop loops in code**: withdraw a target after it has been acted on three times on one URL, and stop when one page is submitted twice.
- **Keep typing mechanics in code**: some validators accept key-by-key typing and reject a single text insert.

## 6. Cost and latency

- **Tokens are repetition.**
  In a per-action agent loop, dropdown options can appear twice per request and the goal plus rules once per question; in a tagger the repeated question text outweighs the context.
  Count tokens per request before optimising anything else.
- **Price moves.**
  Re-read it from https://docs.typesafe.ai/models.md before quoting a cost.
- **Measure latency yourself and keep the connection warm.**
  *Third-party* **[E15]** reports about 150 ms warm against 290 ms after an idle gap.
- **Measure a demo claim before comparing to it.**
  A headline browser-agent time can exclude navigation, cover one page, and run in a browser that is already signed in; on a real multi-page form most of the wall clock is the site's own servers.
- **Judge adoption on measured benefit.**
  A small, low-volume classification that an LLM you already pay for handles well gains little from a separate metered bill.

## 7. Test offline before tuning live

A community linter, jevlint (https://github.com/Fox-Islam/jevlint), checks request shape; treat its findings as suggestions, and run any probe mode that calls the API only on fixture or already-redacted data.

- **Capture once, replay many.**
  Capture the real page or record at each decision point, replay configurations against it, and score against a known-good run.
  It costs cents, sends no traffic to third parties, and finds bugs in your own state builder.
- **Change one thing per arm.**
  An ablation that adds one change at a time (the label list, then definitions, then hints, then the context window) is what shows which change did the work.
- **Write the decision rule before the answers exist** when the result decides adoption.
  Then a missed target is a result, not an invitation to re-tune.
- **Score a fallback in shadow mode before it acts.**
  Ask Jev the fixed request shapes at every step the script already handles, never act on the answer, and score each as agree, abstain or wrong.
  Only a confident wrong answer can do harm, so that is what a floor is set from.

## 8. Live conversation to a structured form (voice or chat)

Design guidance from the public Pipecat + Jev demo and pull requests **[E15]**, not built or measured by us:

- The form's current state is the answer space: one Choice per enumerable field over its canonical options plus `not_mentioned`, all fields in one request per user turn.
- Context per turn is the current state plus the latest utterance (and the last bot message), not the whole transcript.
- Per field, ask "was it mentioned?" and "which value?"; use the answer only above threshold, and otherwise ask the caller, since asking beats guessing.
  Use a higher threshold for high-impact fields, and read back low-confidence ones.
- Code extracts free text (names, addresses, dates, IDs); Jev chooses among the extracted candidates.
  Add phonetic matching for names that speech-to-text mangles, and accept a correction only when Jev is at least 60% sure the recognizer was wrong.
- Tune the "mentioned?" Noul and the "which value?" Choice thresholds separately **[E7]**, and test in the caller's language: accuracy drops with the state's language **[E13]**.
- On garbled speech, the demo reports an LLM returning nothing 39% of the time against Jev's 6%.

## 9. Using Jev as a gate on a decision

- Keep dates, counts, arithmetic and staleness in code (section 1).
- Do not show Jev untrusted text as the source that supports a claim: state is data, and adversarial content can move it.
  *Third-party* **[E11]**: a planted fact ("already approved") moves verdicts where a planted command mostly does not, and page text in a form agent's state is just as untrusted.
- Make a Jev verdict demotion-only when it gates something: it may flag, not upgrade or authorise.
- Call it from fixed points in the code, not whenever a model feels unsure, and print a distinct "off" or "unreachable" line on outage so an absence of flags never reads as a pass.
- **Put a code never-press rule in front of any safety question.**
  A separate yes/no per control ("would activating this buy, sign, pay or submit an application?") caught most unsafe controls in our tests, but missed a button whose visible text was "Next" and whose only cue was an image alt or a form action.
  A plain code rule that reads what a person sees and what the submit would do (visible name and text, image alt and title, the submitter's name and value, the form action) caught every unsafe control on our development pages, so the code rule goes first and the Jev question is the backstop for controls with no such word.
  A commit control with no cue anywhere is caught by neither, so keep commit steps out of automation entirely.
- **Richer context makes Jev readier to press, so evidence needs the code guard in front of it.**
  On a page whose submit button was a plain "Buy now", a sparse request chose `none`, while every richer-context request chose the button; only the independent safety question stopped it.
  Ask the safety question independently of the forward context, and never send richer evidence in a live request without the code guard ahead of Jev.

## 10. Worth testing on your own data

| Question | Test |
|---|---|
| Does an explicit "none of these" option help a multi-label tagger? | Rerun a frozen labelled set with the option added |
| Does option order move your ambiguous picks? | Replay a frozen set with options shuffled |
| One Choice across labels, or a yes/no per label, for items that truly have one label? | Both shapes on the same set, single-label items scored |
| Does sending shared instructions once, not per question, keep accuracy? | Both shapes on the same set |
| Split or compound criteria when code combines them all-of? | Both shapes on labels before building the gate |
| Does a two-step Jev design beat one step? | Each against its one-step version on labels, comparing confident-wrong counts |
| Fan-out on states longer than about 10k tokens | A replay set with long pages **[E3]** |
| A floor on top probability instead of confidence | A replay set, both floors **[E4]** |
| Does a gating floor mean what it says? | Labelled cases before it gates anything **[E6]** |
