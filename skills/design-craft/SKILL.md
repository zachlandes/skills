---
name: design-craft
description: Give a screen, page or app a distinctive, finished visual design in three stages, each ending in a decision by the user - Discover (several divergent variants to pick from), Define (the pick refined in a loop judged by a blind critic) and Deliver (cutting what adds nothing, reviewing overused patterns, and a human rewrite of the copy). Use when asked to design how a UI looks, to make a UI look world-class or distinctive, or to make it look less like AI made it.
---

# design-craft

Turns a brief for a screen into a visual design that does not look like every other model's.
The method is adapted from Anshu Chimala's article "How to turn your AI into a world-class designer" in Lenny's Newsletter (see Source at the end).
Left alone, a model takes the most likely option at every design decision, so its designs all converge on the same look; each stage below pushes against that from a different side.

This file is for you, the agent running the process.
Nothing in it, and nothing else in this skill's directory except the prompt templates, is ever shown to a blind role.

## Before you start: the brief

You need a brief from the user, and you do not invent one.
It covers:

- the product, and who uses it;
- the moment of use: when and where they use it, and what pressure they are under;
- the screens and states in scope, and what must be visible on each;
- the device and viewport;
- the structure, if it is already decided: the layout, the navigation, the information on each screen;
- anything that cannot change: platform, framework, brand rules, a host app the design lives inside.

An existing screen to redesign counts as a brief: its current structure is the structure unless the user says otherwise.
If anything above is missing, ask for it in one message and wait.
If the user has not worked out the journey or the structure yet, say so: a separate discovery step about the job and the layout is a better start than this process.

Do not load any design-rules skill or style guide during a run.
Up-front rules about what to avoid are exactly what this process holds back until Deliver, because the article finds that banning patterns early makes the output worse.

## Context hygiene is the whole design

Three things must not leak, and the file layout enforces them.

- **Stage material opens only at its stage.** Read `stages/discover.md` when Discover starts, `stages/define.md` only after the user passes the Discover gate, and `stages/deliver.md` only after the Define gate. Never open a later stage's file early, even to plan; the specific harm is Deliver's list of overused patterns reaching a builder during Discover or Define.
- **Blind roles get a template and images, nothing else.** The critic, the polish reviewer and the ideation partner run in a fresh context from the fixed templates in `prompts/`, passed verbatim with only their marked slots filled. They never see this skill, its name, its purpose, the round number, the target score, earlier critiques or the code. Open a template only at the stage that uses it.
- **Image paths are neutral.** Copy every image a blind role sees into a fresh temporary directory under names like `subject.png` and `ref-1.png`, so a path never says which round, variant or project it came from.

## Who does what

| Role | Model | How it runs | Sees |
| --- | --- | --- | --- |
| Builder | The model you are running on | You | The brief, the code, the critique it is handed, the target score |
| Variant builders (Discover) | Any capable coding model | One fresh subagent per variant, in parallel, if your environment has subagents; otherwise you | A variant brief from `stages/discover.md` |
| Critic | The strongest model available to you | A fresh, blind context for every call | A template from `prompts/` and images |
| Polish reviewer (Deliver) | The strongest model available to you | A fresh, blind context | `prompts/polish-reviewer.md` and images |
| Ideation partner (Discover, optional) | Any capable model | One blind context, continued for the conversation | `prompts/ideation/` |

Use the strongest model you can reach for the critic and the polish reviewer, even when the builder runs on a cheaper one.
They make the judgment calls, and they are cheap: in the article's runs the expensive critic accounted for under a tenth of the output tokens, because a capable, cheaper model did the building.
If the user's own instructions name a critic model, use it; otherwise pick the strongest one you can call and record which in the run log.

The critic's independence comes from being blind, not from being a different model.
A fresh context that sees only the fixed prompt and the screenshots cannot share the builder's reasons for its choices, which is what lets it see the screen as a stranger does.
The critic can be the same model as the builder; a model from another provider is an optional extra, never a requirement.

`critics.md` is how any blind role is called: the blind directory, the frozen prompt, and the routes to a fresh context.

## Without a subagent tool

Some agents cannot start a subagent.
The method still runs, with these substitutions; record each one in the run log and mention it at the Discover gate.

- **You are every builder**, the variant builders included. Write every variant's direction into the log before building any, then build each from its own direction alone, one at a time, and never revise one after seeing the next. One context carries its defaults into every variant, so lean on sources whose variety comes from outside you: research and the user's own steer.
- **A blind role is a separate call, never you.** Never write a critique, score or polish review yourself: you know the code, the history and the target, which is exactly what a blind role must not. Reach a fresh context another way, as `critics.md` describes.
- **No route to a fresh context at all:** there is no blind critic. Stop and ask the user how to proceed rather than judging your own work.

## The stages

Each stage ends at a gate.
At a gate you present the result, ask the gate's question, and end your turn.
Never move on to the next stage by yourself, and never treat silence, approval of something else, or an earlier approval as passing the gate.

1. **Discover** - `stages/discover.md`. Several quick, honest variants, deliberately divergent, shown side by side. Gate: the user picks a direction and confirms the reference designs for Define.
2. **Define** - `stages/define.md`. The picked direction refined in a blind critic loop until the critic scores it at studio level, or as good as a comparable real screen where studio level is out of reach for the task, with optional generated imagery. Gate: the user accepts the design, or sends it back with notes.
3. **Deliver** - `stages/deliver.md`. Cut what adds nothing, review a list of overused patterns, and have the user rewrite the copy. Gate: the user signs off the finished design.

Keep a run log at `design/craft/log.md`, or wherever the project keeps design documents: the brief, the critic model, the stage, each gate's answer, and Define's score table.
It lets someone pick the run up later, and it is what you hand the user when a loop stalls.

## Source

Anshu Chimala, ["How to turn your AI into a world-class designer"](https://www.lennysnewsletter.com/p/how-to-turn-your-ai-into-a-world), Lenny's Newsletter, 2026-09-01.
The core techniques come from the article: random-seed variants, human-steered ideation, a blind critic loop, generated imagery and motion, cutting what adds nothing, reviewing overused patterns, and a human copy rewrite.
Short quotations are marked where they appear; everything else is paraphrase.
The stage gates, the research-derived variants, the optional check critic, the native ceiling for designs inside a host, and the context-hygiene layout are additions in this adaptation.
