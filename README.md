# cull

an agent that reads 100+ new items every morning and decides which 5 are worth your time.
every judgment it makes lives in plain markdown files you can open, edit, and own.

built at the own your intelligence hackathon (yc, sf, sept 27 2026). zero dependencies, one file, python 3.8+.

## run it

    python3 cull.py run
    python3 cull.py feedback 2 up
    python3 cull.py run      # the ranking moves. it learned.

## what it does

- pulls the hacker news front page + today's arxiv (cs.AI / cs.LG / cs.CL) - 100+ items
- scores each against `memory/taste.md`, a taste profile you can read and edit
- writes the 5 worth your time to `briefing.md`, each with a one-line reason
- `feedback <n> up|down` rewrites taste.md - the next run is visibly sharper
- every pick is logged to `memory/judgments.md`, so it never recommends the same thing twice
- 10-minute source cache: reruns are instant and free
- stage-wifi insurance: if every live source fails, it falls back to a bundled snapshot of today's items and says so

## why gbrain

gbrain's bet is that an agent's memory should be yours - plain files, not a vendor's black box. cull is built on that shape: `memory/` is the whole brain (`taste.md`, `judgments.md`, `feedback.md`). the tedious task it automates is the daily firehose: 100+ things you could read, culled to the 5 you should.

to mirror memory into hosted gbrain (hackathon credits at gbrain.io/gratis/own-your-intelligence):

    export GBRAIN_API_URL=<your instance endpoint>
    export GBRAIN_API_KEY=<your key>

every memory write then mirrors upstream. local files stay the source of truth.

## optional llm judging

    export OPENAI_API_KEY=sk-...

an llm re-judges the shortlist (gpt-4o-mini, ~$0.001/run). without a key, a transparent keyword scorer runs - every point in every score is explainable, which is half the point.

## extending

sources are two small functions (`fetch_hn`, `fetch_arxiv`). add reddit, rss, or substack in ~10 lines. the morning-cron version is `while true; do python3 cull.py run; sleep 86400; done` - or just launchd.
