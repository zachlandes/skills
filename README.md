# skills

Agent skills by Zachary Landes.
A skill is a folder of instructions an AI coding agent loads when a task calls for it.
These work in Claude Code and in other agents that load skills from a `SKILL.md` file.

## design-craft

AI-made interfaces tend to look alike.
At every design decision a model picks the most likely option, so its screens converge on the same gradients, cards, labels and fonts.
`design-craft` is a process that pushes back against that, in three stages:

1. **Discover.** The agent builds four to six quick, deliberately different versions of your screen and shows them side by side. The variety comes from outside the model: a random seed string, research into fields that solved a similar problem, or your own reactions to a list of wild ideas. You pick a direction.
2. **Define.** The agent refines your pick in a loop. Each round, a critic that sees only screenshots - never the code, the history or the goal - scores the design and says what a top studio would do differently. The loop stops when the critic is satisfied, when the score stops improving, or when you say so. You accept the design or send it back.
3. **Deliver.** The agent proposes cuts, walks you through four overused patterns one at a time, and hands you every line of copy to rewrite yourself. You sign it off.

The agent stops and asks you at the end of every stage.
Nothing moves on without your answer.

### What you need

- A brief for the screen: what the product is, who uses it and when, what must be on screen, the device, and anything that cannot change. If you are redesigning a screen, the current one covers the layout, and the agent also asks what is wrong with it. The agent asks for anything that is missing.
- A way for your agent to run the critic in a fresh context: a subagent, or a non-interactive call to a model from the command line. Use the strongest model you have for the critic. It can be the same model that builds; what makes it independent is that it sees nothing but the screenshots.
- A way to take screenshots of the design, such as a browser your agent can drive.

### Install

With the [skills CLI](https://github.com/vercel-labs/skills):

```sh
npx skills add zachlandes/skills --skill design-craft
```

Or copy the `skills/design-craft` folder into your agent's skills folder, for example `~/.claude/skills/` for Claude Code.

### Use

Ask your agent for it by name, or describe the job:

> Use design-craft on the checkout page.

> This dashboard looks like every other AI-made dashboard. Can you give it a real design?

The agent keeps a run log, the requirements, and the copy table under `design/craft/` in your project.

### Credit

The method is adapted from Anshu Chimala's article ["How to turn your AI into a world-class designer"](https://www.lennysnewsletter.com/p/how-to-turn-your-ai-into-a-world) in [Lenny's Newsletter](https://www.lennysnewsletter.com/).
The core techniques come from the article: random-seed variants, human-steered ideation, a blind critic loop, generated imagery and motion, cutting what adds nothing, reviewing overused patterns, and a human rewrite of the copy.
The skill quotes the article only in a few short, credited lines and puts everything else in its own words; read the article for the full reasoning and examples.
The random-seed technique builds on String Seed of Thought from Sakana AI.

The stage gates, the research-derived variants, the optional check critic, the calibrated target for screens where a 9 is out of reach, and the file layout that keeps later stages hidden from earlier ones are additions in this adaptation.

## jev-field-practice

[Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) is TypeSafe's decision model: instead of writing text, it picks among options and says how sure it is.
It's fast and cheap enough to put inside an app's control flow, but how well it decides depends heavily on how you ask.
`jev-field-practice` is what I learned building with it: a message tagger, a router, and agents that fill in web forms.

It covers how to word questions and options, what state to send and how to prepare it in code, when to offer a "none" option, many questions in one request against one at a time, confidence floors in multi-step workflows, testing on held-out data, and using Jev as a gate on a decision.
Each heuristic says when it matters.
My own measurements aren't published, so the skill gives their direction without numbers, and every number it does give comes from a public study listed in `sources.md`.

### What you need

- Access to Jev: a TypeSafe API key, or an [OpenRouter](https://openrouter.ai/typesafe/jev-1.13) or [Vercel AI Gateway](https://vercel.com/ai-gateway/models/jev) account. The skill has a dated note on both.
- TypeSafe's docs at [docs.typesafe.ai](https://docs.typesafe.ai) or their [`typesafe-ai` skill](https://github.com/typesafe-ai/skills) for the API itself. This skill doesn't cover how to call Jev.

### Install

With the [skills CLI](https://github.com/vercel-labs/skills):

```sh
npx skills add zachlandes/skills --skill jev-field-practice
```

Or copy the `skills/jev-field-practice` folder into your agent's skills folder, for example `~/.claude/skills/` for Claude Code.

### Use

Your agent loads it when a task involves Jev, or you can ask for it by name:

> Use jev-field-practice to review how this classifier asks Jev.

> Our Jev router keeps picking the wrong rule for refactor tasks. What should we change?

### Background

The code and raw answers are in [trolley-bench](https://github.com/zachlandes/trolley-bench).
The heuristics were written against `jev-1.13`, so check TypeSafe's model notes for anything a later version changed.

## ai-tells

Some sentence constructions show up far more often in AI text than in human text: a participial clause tacked on after a comma, a series of three, and so on.
`ai-tells` checks a page or text for them with Jev, and only reports a construction as a tell if it passed a measured test.

The check step splits any HTML, Markdown or plain text into sentences, asks Jev about each one, and lists the flagged sentences with their probabilities.
It gives rates per 100 sentences and per 1,000 words beside the rates in human and AI text from calibration.
The calibrate step tests a new candidate on 300 human and 300 AI corpus sentences and keeps it only if the AI-to-human ratio is 2x or more and precision on held-out hand labels is 0.8 or more, with the rule set before any label is written.
Constructions that have not passed show up only as leads.

### What you need

- Python 3 and a way to call Jev: a TypeSafe key, or a Vercel AI Gateway key. Both steps cap spend in code; a check of a 400-sentence page costs about 2 cents.
- For the calibrate step only: `pandas`, `pyarrow` and the [HAP-E-2 corpus](https://huggingface.co/datasets/browndw/human-ai-parallel-corpus-2).
- The `jev-field-practice` skill is worth reading before you change a tell's wording.

### Install

```sh
npx skills add zachlandes/skills --skill ai-tells
```

Or copy the `skills/ai-tells` folder into your agent's skills folder.

### Use

> Use ai-tells to check docs/overview.html.

> Add "performed hedging" as a candidate tell and calibrate it.

Every sentence you check is sent to TypeSafe, so check text you are free to share.

## License

MIT. See [LICENSE](LICENSE).
