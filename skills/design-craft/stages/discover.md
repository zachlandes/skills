# Discover: go broad before deep

Read this when Discover starts, not before.
Do not open `define.md` or `deliver.md` until the user has passed this stage's gate.

The goal is several honest, genuinely different directions the user can compare side by side.
Asking a model for "something unique" still gets its defaults in a new costume.
The article's author tried telling a model to make every design decision at random, and it still returned the same colours, structure and metaphor every time.
So the variety has to come from outside the model: a random string, real research, or the user's own taste.

## 1. Write the hard requirements

Before any variant, write `design/craft/requirements.md` from the brief.
It holds structure only: the device and viewport, what must be visible at rest, the information on each screen and its real names, the states the moment of use passes through, and every constraint the brief says cannot change.
It says nothing about colour, type, mood or style; those are what the variants explore.

The split is the point.
**Hard requirements fix the structure; the seed, the research or the user's steer shapes the look.**
A variant that breaks a requirement is not a bolder variant, it is a wrong one.

## 2. Choose the variant mix

Aim for four to six variants, drawn from the sources below.
Use at least two sources, so one method's blind spot does not become the whole set.

### Seed-string variants

Each one is built by its own fresh builder, all in parallel, so no variant sees another.
The randomness comes from String Seed of Thought, a technique from Sakana AI that the article adapts for design.
In outline, each builder:

1. generates a long random alphanumeric string with a shell command;
2. reads a creative direction out of that string - colour scheme, layout, typography and so on - looking past its surface for patterns, numbers or anything else that sparks an idea;
3. uses its own judgment to turn that direction into a design that looks great.

The string never appears in the design; in the article's words, "It's only for your inspiration."
For a work tool, "layout" in step 2 means arrangement within the hard requirements, never a different structure.

### Research-derived variants (especially for work tools)

For a tool someone uses under pressure, a random look is not enough on its own: the best ideas often come from other fields that already solved the same reading problem.
Name two or three fields whose users face the brief's moment of use - glanceable under time pressure, dense but scannable, one-handed, someone waiting on the other end - such as air traffic control, trading terminals, broadcast control rooms, cockpit displays, newsroom tools or clinical monitors.
Research how each one actually presents its information, and pull out two or three concrete visual patterns per field, with where you found them.
Each research variant is built around one field's patterns, still inside the hard requirements.

Patterns are looked-up facts, so cite them; never present a pattern you imagined as one you found.

### Human-steered variants

Offer this; the user may decline.
A wild, concrete starting image - a still from a pixel-art game, an isometric city full of life, a layout that deliberately breaks the usual rules - gives the builder a vision to make decisions from instead of falling back on defaults.
Feeding a model's ideas straight back into a model gets the result anyone would get; the user's own reactions are what make the result theirs.

Run it with the ideation partner, a blind context continued for the whole conversation, called as `critics.md` describes:

1. Send `prompts/ideation/1-go-broad.md`, with `{{PRODUCT}}` replaced by one plain phrase naming the product and who uses it - nothing about this process.
2. Show the user the list. Ask which ideas they can picture, and what they like and dislike about them.
3. Send `prompts/ideation/2-sharpen.md` with `{{CHOSEN_IDEA}}` set to the idea's name and `{{REACTIONS}}` set to the user's own words, verbatim. Repeat steps 2 and 3 until the user is happy with it.
4. Send `prompts/ideation/3-write-build-prompt.md`. The prompt it returns, plus the hard requirements, is that variant's build brief.

Encourage ideas that sound terrible; the article reports that the results often surprise you.
Keep every steered prompt that did not work in `design/craft/prompts-to-retry.md`, to try again on a newer model.

## 3. Build the variants

Brief every variant builder - a fresh subagent per variant, started in parallel - with exactly the list below.
Without a subagent tool you build them yourself, as `SKILL.md` says; the same list is then each variant's whole brief, written down before you build any:

- the product in a sentence, and the hard requirements file;
- its direction: the seed procedure above, or its research patterns with their sources, or its steered build prompt;
- where to build it, so variants never overwrite each other (separate files or routes the project can show side by side);
- "Build it quickly and honestly: real content from the requirements, realistic values, no lorem ipsum, no placeholder boxes, nothing on screen the real product would not show. Do not polish beyond a first good version."

The builders get nothing else: not this file, not the other variants, and no list of patterns to avoid.

There is no critic in this stage.
Each variant gets one pass; a variant that came out broken gets one fix, then is shown as it is.

Screenshot every variant at the requirements' device and viewport, in each state the moment of use passes through.
Record in the run log each variant's letter, its source (seed with its string, research with its fields, or steered with its prompt) and where it was built.

## 4. Show them side by side

Put every variant on one page, at the same scale, labelled by letter with a one-line description of its direction.
Use whatever review surface your environment offers for showing images to the user, with the screenshots inline; never hand over bare file paths.

**Optional blind ranking.**
While the user looks, the critic may score each variant blind: `prompts/critic.md` with that variant's screenshot as the only image, called as `critics.md` describes.
Keep the scores out of the page and out of the conversation until the user has picked.
Their value is as a second opinion on a choice already made; shown first, they would make the choice for the user.

## 5. Choose the reference designs for Define

Define's critic measures against reference designs when there are some, and ranking against real work is a steadier bar than a bare score.
Gather three to five screenshots of professional work in a similar space at the quality you are aiming for: what the user names, the product the brief says this will be compared with, and strong examples from the research.
They set the bar, like a moodboard; they are never something to copy.

Some tasks never score 9, however good the design gets, so propose one screen as the calibration screen that sets Define's target from real work.
If the design will live inside a host with its own UI - a game, a host app, an operating system - include the host's own screens in the set and propose the host's best comparable screen (for a game, its Settings screen is a good default).
Otherwise, propose the reference closest to this screen's job, or none if the user would rather hold the design to the full bar.

## The gate

Present the side-by-side page and the proposed reference set, then ask, as one message:

> Which direction goes forward into Define - one variant, or a combination you describe? Are these the right reference designs to measure it against, and is this the right screen to calibrate the target against? And if you want generated imagery or motion in Define, give me a dedicated API key with a tight spending cap; without one, Define stays code-only.

End your turn and wait.
Once the user has picked, show the blind ranking if you ran one, and record the pick, the references, the calibration screen if any, and the key decision (never the key itself) in the log.
A combination is built as Define's starting point, before the first critic round.
