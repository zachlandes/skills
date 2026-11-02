# Calibrations

Both calibrations used HAP-E-2 (Brown's human-AI parallel corpus 2), academic and news genres, one sentence per text, seed 194, jev-1.14.0, and the rule set before labelling: keep a tell when the AI-to-human ratio at its yes cutoff is 2.0 or more and held-out precision is 0.8 or more.
Labels were written by Claude Opus 5.5 (pilot) and Claude Sonnet 5.5 (rerun), blind to Jev's probability and to the source. No person labelled anything.

## scr194-pilot (2026-11-01)

300 human and 300 Claude Haiku 4.5 sentences; 11 questions (revision q1); 40 labels per tell.

| Tell | Yes cutoff | Ratio (95% interval) | Held-out precision | Result |
| --- | --- | --- | --- | --- |
| Participial clause | 0.5 | 2.83 (1.47 to 5.43) | 10 of 10 | kept |
| Tricolon | 0.7 | 2.38 (1.32 to 4.30) | 8 of 8 | kept |
| Corrective framing | 0.7 | 4.14 (1.30 to 13.17) | 5 of 7 | not kept: additive "not only X but also Y" lists |
| Importance flag, signpost opener, clause-subject passive | | too rare at a calibrated cutoff | | not kept |

## opus55-rerun (2026-11-02)

299 human and 299 Claude Opus 5.5 sentences (Opus wrote about 200-word continuations of the same HAP-E-2 chunk_1 openings, in ten batches of 30; a batch is not a separate request per passage); revision q2 questions; fresh labels, 40 per tell; 54 answers near a cutoff run a second time.
q2 changes: corrective framing excludes additive "not only X but also Y"; importance flag excludes attributive uses ("an important gap").

| Tell | Yes cutoff | Ratio (95% interval) | Held-out precision | Result |
| --- | --- | --- | --- | --- |
| Tricolon | 0.5 | 2.94 (1.69 to 5.11) | 8 of 10 | kept |
| Participial clause | 0.5 | 1.59 (0.82 to 3.09) | 9 of 10 | not kept: Opus 5.5 writes fewer of them; now a lead |
| Corrective framing | 0.9 | 1.29 (0.32 to 5.15) | 2 of 3 | not kept |
| Importance flag | 0.7 | 0.71 | 2 of 2 | not kept |
| Signpost opener | 0.5 | 0.53 | 2 of 5 | not kept |
| Clause-subject passive | 0.9 | 1.00 | none | too rare |

What it shows:

- Only tricolon holds against both AI controls.
- The participial clause is an AI tell relative to Haiku 4.5 but not clearly relative to Opus 5.5 (human rate 4.3%, Opus 7.0%). It stays as a lead.
- The tighter questions did not rescue corrective framing or the importance flag: both are rare in Opus text at a precise cutoff.
- Held-out sets are small (3 to 10 yes answers), so single sentences move precision by 10 points or more.
