# Calling a blind role

Read this the first time you call the critic, the polish reviewer or the ideation partner.
It is mechanics only: how to fill a template, how to keep the call blind, and how to reach a fresh context.
When to call and what to do with the answer belong to the stage files.

## Prepare a blind directory

Make a fresh temporary directory (`mktemp -d`), outside the project: one per call, except in a Define loop, which reuses one directory for all its rounds so its frozen prompt never changes.
Copy into it, under neutral names, only the images the role should see: `subject.png` for the design under review (or `screen-1.png`, `screen-2.png` for several states of one design) and `ref-1.png`, `ref-2.png` for reference designs.
A name must never reveal a round, a variant letter, a score or the project.

Copy the template from `prompts/` to `prompt.md` in that directory and replace its slots:

- `{{IMAGES}}` - one line per image, the design under review first, each as a label and its absolute path, for example `- Design under review: /tmp/tmp.X/subject.png` then `- Reference 1: /tmp/tmp.X/ref-1.png`. Several states of one design are each labelled `Design under review`.

Change nothing else in the template, not a word.
Within one Define loop the filled prompt is frozen: the same text and the same reference images every round, for every critic.
Note its checksum (`shasum prompt.md`) in the log the first time and check it before each round.

## Reaching a fresh, blind context

Every call is a new context that has never seen this run.
Never continue a critic or the polish reviewer from an earlier call; it would see its own earlier critiques.
Use the strongest model available to you, as `SKILL.md` says.

Pick the first route your environment supports, and record which in the run log.

### A subagent

If your agent can start a subagent, start a new one for each call, on the strongest model it can use.
Give it a neutral description such as "review a screen design" and, as its whole task, the contents of `prompt.md`, verbatim.
Add nothing: no context about the project, the run or why you are asking.

A subagent may still see your environment's standing instructions or its list of installed skills.
That is acceptable; what must never reach it is anything you add yourself.

### A headless command-line call

If you cannot start a subagent, call a model from the shell in non-interactive mode: the command-line tool for the user's own agent or model provider, run once per call.
Configure it so the call stays blind:

- no tools, or only what it needs to read the attached images, so it cannot go looking through the project;
- no project instruction files, skills, plugins or memory loaded;
- no saved session, so the next call starts fresh;
- run from inside the blind directory, with the images attached in the order `{{IMAGES}}` lists them.

Check the tool's own help for the flags that do each of these, and write the exact command into the run log the first time it works.
If the tool reads standard input in non-interactive mode, redirect it from `/dev/null`; from an agent's shell, standard input may never close, and the call then hangs with no output.

If the call fails, retry once.
If it still fails, treat that route as unavailable for the run, log why, and try the next.

### The ideation partner

The ideation partner is one blind context continued across turns, because it needs the conversation so far.
With a subagent, continue the same one for the whole conversation.
With a command-line call, use the tool's option for a session file kept inside the blind directory, and send each turn as its own call with that turn's filled template; the session carries the conversation, so later turns need nothing else.

### No route at all

If you can reach neither a subagent nor a headless call, there is no blind role.
Stop and ask the user how they want to proceed; never play the role yourself.

## A second, optional check critic

`stages/define.md` can use a check critic that scores every round beside the critic.
It is a second blind call per round with the same frozen prompt: the same strongest model in another fresh context, or, if the user happens to have one, a strong model from another provider.
It is optional.
Without it the critic's score stands on its own, and that is the normal case.

## Reading the answer

The critic templates end in fixed lines: `SCORE: n` and, for the ranked template, `RANK: a > b > c`.
Parse those; never infer a score from the prose.
A reply without them is a failed call: call again once with the same prompt, then log the score as missing.
