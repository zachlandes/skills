# Deliver: polish by taking away

Read this only after the user has accepted the design at the Define gate.
It is the only file in this skill that names the overused patterns, and it stays unread until now on purpose: the article warns that banning them up front makes a model overthink and reach for stranger patterns instead.
Nothing in this file is ever passed to a variant builder, the critic or the polish reviewer.

Models add and rarely remove, and removing feels risky to them, so they will not make these cuts on their own.
In this stage the user decides; you find the candidates and carry out the decisions.

## 1. Cut what adds nothing

Restraint reads as premium, and the surest sign of an AI-made design is elements that do nothing or explain what is already obvious.
The article gives an example of its own: a calorie-tracking app the author had asked to keep clean and minimal still came back with decorative glows, scattered accent colours, needless labels and containers, and home-made controls that were worse than the platform's own.
Stripped back to its content, standard controls and tighter type, it looked far better.

1. Screenshot every state of the design and run the polish reviewer on them: `prompts/polish-reviewer.md` in a fresh blind context, prepared and called as `critics.md` describes, with the images as `screen-1.png` onwards.
2. Make your own pass against the hard requirements: anything on screen the brief does not need.
3. Merge both into one numbered cut list, each item with the element, where it is, and the proposed cut or replacement. Mark which source raised it. For a design inside a host, leave out any item that would replace the host's native furniture, as in Define.
4. Show the user the list beside the screenshots, and ask them to mark each item cut, keep or replace.
5. Apply the approved items, and only those.

## 2. Review the overused patterns

These patterns are fine on their own; they become tells because they show up everywhere.
This is not a ban list: be deliberate about each one, keep the instances that earn their place, and let the user choose.

The article names four, each with a better default; paraphrased:

| Overused pattern | Try instead |
| --- | --- |
| Eyebrow text: small labels above a heading that restate the obvious | Remove it. On this one the article is blunt: "Nine times out of 10, you can just remove it and lose nothing of value." |
| Generic background gradients | A real background image, a pattern, or a plain solid colour |
| Too many cards and containers | A flatter layout, such as a grid or tiles |
| Too many fonts, text styles and type levels | "Start with 1-2 fonts and 2-4 styles until you need more", and keep accent colours and italics rare |

For each pattern, in order:

1. Find every instance in the design, naming the element. None: say so and move on.
2. Build the alternative, kept separate so the current version survives.
3. Show the user the two side by side, and ask which they prefer, per instance where they differ.
4. Keep what the user picks.

Deal with one pattern at a time, so each decision is about one thing.

## 3. The user rewrites the copy

Copy may decide, more than any visual, whether a design reads as tasteful or as filler.
Treat every line the model wrote as lorem ipsum: there to show the structure, and a placeholder until a person rewrites it.
The person's version is almost always shorter, plainer and easier to read.

1. Extract every user-visible string, in reading order, into `design/craft/copy.md` as a table with the columns `Where`, `Current` and `Rewrite`. Include labels, buttons, placeholders, empty states, errors and tooltips.
2. Hand it to the user to fill in the `Rewrite` column, writing `keep` where a line stays. Do not draft rewrites, suggest wording or tidy anything up first; any line you write is one more placeholder.
3. When every row is filled, apply the rewrites verbatim. Then check every row against the built screen, and report any that the layout forced you to change.

## 4. A final score, for the record

Optionally, run the critic once more with Define's frozen prompt and blind directory, and add the result to the score table as the final row, with its gap to the calibration score if Define used one.
It is information, not a gate: a lower score after the cuts does not reopen Define unless the user asks.

## The gate

Present the end-of-Define and final screenshots side by side, the applied cuts, each pattern decision, the copy table, and the final score row if you ran it.
Then ask:

> Is this the finished design?

End your turn and wait.
On yes, record the sign-off in the log; the run is complete.
On anything else, make the change the user asked for and ask again.
