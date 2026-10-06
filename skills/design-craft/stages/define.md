# Define: give the direction its own identity

Read this only after the user has passed the Discover gate.
Do not open `deliver.md` until the user has passed this stage's gate.

The picked direction is promising but still leans on stale patterns.
Define refines it in a loop: the builder improves the design, and a critic who cannot see the code, the history or the goal decides when it is good enough.
A builder cannot judge its own work: it reviews its own code and its own reasons, and cannot step back far enough to see the screen the way a stranger does.

## The roles

- **Builder** - you. You own the code, receive the critique, and know the target: **the design is done when the critic, scoring blind, gives it the target score or more.** The target is 9, or the score of a calibration screen, as described below. You may know the target; the critic never does.
- **Critic** - the strongest model available to you, in a fresh blind context every round, as `critics.md` describes. Its critique is what steers you.
- **Check critic** - optional. A second blind call every round with the same frozen prompt and images. Its critique is recorded but not passed on unless the stop rule below needs it. Without one, the critic's score stands on its own.

## Set up once

1. Choose the template: `prompts/critic-ranked.md` if the user confirmed reference designs at the Discover gate, otherwise `prompts/critic.md`. Ranking against real work is the steadier bar, so prefer it. Keep the choice for the whole loop.
2. Read `critics.md` and prepare the blind directory and the frozen prompt as it says.
3. If the user confirmed a calibration screen at the Discover gate, set the target from it as described below.
4. Start the score table in the run log:

   | Round | Score | Rank | Check score | Check rank | Critique sent to builder | Note |
   | --- | --- | --- | --- | --- | --- | --- |

   Leave out the check columns if there is no check critic.

Round 0 scores the starting point before any change, so the table shows what the loop actually bought.
If you must fix a reference image after round 0 (a bad crop, the wrong screen), re-score round 0, and the calibration screen if you used one, with the corrected set; then freeze it and log the correction.

## When 9 is the wrong target

Depending on the task, the critic may never reach 9, however good the design gets.
A screen inside a host app, a dense work tool, or anything bound by a platform's conventions can be marked down for things the design should not change, and the critic marks down professional work in those settings too.
A stalled score is a signal about the task, not a reason to keep looping.

So when there is a comparable screen to measure against, let it set the target with the same instrument:

1. Take the calibration screen the user confirmed at the Discover gate: for a design inside a host, the host's own best comparable screen (for a game, its Settings screen is a good default); otherwise the reference that is closest to this screen's job. Screenshot it at the same device and scale as the design, with every control whole: the critic scores a clipped edge as a flaw, and a crop that cuts off one button can cost a point.
2. Before round 0, score it through the same frozen prompt and blind directory, with that screenshot as `subject.png`. Nothing tells the critic what it is. If it is also one of the references, the critic may notice the two match; leave the frozen references alone.
3. The critic's score for the calibration screen is the target, in place of 9 in the stop rule below. With a check critic, its own score for that screen is its target. Log it as a `calibration` row above round 0 and add a `Gap to calibration` column to the table.

For example, a host app's own settings screen might score only 7 on this prompt; a design that lives inside that app should not be held to 9, and chasing 9 there pulls it away from the host, which is worse than matching it.

Where no calibration screen exists, the target stays 9, and the plateau limit in the stop rule is what catches a task where 9 is out of reach.
Either way, a design that stalls goes to the user with the gap and the score history shown, and the user makes the call; never chase the number.

### A design inside a host: keep its native patterns

For a design inside a host, calibration changes what reaches the builder as well as the target.
A critic that does not know the host will ask to replace its native furniture: a custom control or font where the host uses its own, a different icon family, or a "fix" to the host's own screens.
Drop every critique point that would pull the design away from the host's native patterns, act on the remaining points as written, and record each dropped point in the log under "dropped for native conformity".
Never buy the last point by departing from the host's patterns.

## Each round

1. **Screenshot** the design at the same device, viewport and state as every other round, and copy it over `subject.png` in the blind directory. For several states, use the same set every round.
2. **Call the critic**, and the check critic if you have one, as `critics.md` describes, with the same frozen prompt.
3. **Record** every score, rank and critique in full under the round's heading in the log.
4. **Apply the stop rule** below. If it says continue, act on the chosen critique as it was written, with nothing added and nothing removed except points dropped for native conformity.

## The stop rule

"Target" below is 9, or the calibration score.

- **Critic below target:** act on the critic's critique; next round.
- **Critic at or above target, no check critic:** done; go to the gate.
- **Critic and check critic both at or above target in the same round:** done; go to the gate.
- **Critic at or above target, check critic below:** for up to two rounds, act on the check critic's critique instead (both critiques, if the critic also drops below target), while both keep scoring. The first round in which both reach the target is done. If they are still split after two rounds, **stop and escalate**: show the user both critiques from the last round and both score histories, and let them decide whether it is done.
- **Check critic stops working mid-loop:** carry on with the critic alone, and log when and why.

Two limits stop a loop that is not getting anywhere, because a critic that is never satisfied will use up tokens indefinitely:

- **Plateau.** If two rounds in a row fail to beat the critic's best score so far, round 0 included, stop. Show the user the score history and the gap to the target, and ask whether the design is done or worth more rounds. A plateau below target usually means the target is out of reach for this task, as above, not that one more round will crack it.
- **Eight rounds.** Never run more than eight rounds without the user's go-ahead. At eight, stop and escalate as above.

## Generated imagery and motion

Optional, and only if the user handed over a dedicated API key with a tight spending cap at the Discover gate.
Without one this section does not apply; never use, look for or ask for any other key.

Coding agents rarely use real imagery and make do with whatever they can draw in code, and that substitution is one of the plainest signs a machine made the design.
Real imagery also shows more care than surface polish does.

- **Key handling.** Store the key in a gitignored env file in the project, and confirm it is ignored (`git check-ignore <file>`) before writing it. Note beside it that it is for development only. It never goes into code, a commit, the log, a screenshot or any prompt.
- **Images** from an image-generation API, combined with shaders or 3D effects where they suit the direction. Check the result frame by frame in the browser, not by reading the code.
- **Motion** through a hosted service that offers many video models, so you can pick a current model instead of wiring one up. Two uses: a looping clip rendered on a solid background and then keyed out, so it layers into the UI like a native element; and a transition generated between two keyframe stills, played on an action or scrubbed with scroll or a gesture.

Imagery is a move you make inside the loop, not a stage of its own: the critic judges the result like any other change.
For a work tool, the critique and the user decide whether imagery belongs at all.

## The gate

Present, with the screenshots inline: the round 0 and final screenshots side by side, the score table (with the calibration score and gap, if you used one), the final round's critiques, and any points dropped for native conformity.
Then ask:

> Is this ready for polish, or does it go back for more rounds - and if so, what should change?

End your turn and wait.
Sent back: the user's notes become your next steering input, the critic prompt stays frozen, and the round count continues.
Accepted: record it in the log, then open `deliver.md`.
