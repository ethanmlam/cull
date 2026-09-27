# cull demo video - 90 seconds, quicktime screen record (cmd-shift-5) + voiceover

0:00-0:10 - terminal, one line: "cull reads the morning firehose and decides what's worth my time. here's today's run."

    python3 cull.py run

0:10-0:30 - scroll the briefing: "100+ items from hacker news and arxiv, judged in under a second. five survivors, each with its reason on the tin."

0:30-0:50 - `cat memory/taste.md` : "here's the part i care about. the taste profile it judged with is a plain file. i can read it, edit it, delete it. the agent's memory is mine - that's the gbrain model."

0:50-1:10 - the learning moment: "it's wrong about number one. so:"

    python3 cull.py feedback 1 down
    python3 cull.py run

"watch the ranking move. same sources, sharper judgment. that's memory doing work."

1:10-1:30 - close: "every judgment is logged in plain files. tomorrow it runs again and never repeats itself. next: mirror this memory into hosted gbrain, add my own feeds, run it every morning. cull - own your intelligence."

tips: bump terminal font (cmd-+), keep it one take, the rerun is instant because of the cache - that's a feature, mention it if asked.
