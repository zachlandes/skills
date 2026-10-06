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

## License

MIT. See [LICENSE](LICENSE).
