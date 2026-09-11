# Submission checklist — Horizon Round 1

| Requirement | Status | Notes |
|---|---|---|
| Project description | ✅ Drafted | `PROJECT_DESCRIPTION.md` — paste directly into the submission form, trim if there's a word limit |
| Working MVP | ✅ Built | Full repo, real data, tested end to end (see main `README.md`) |
| 2–3 min demo video | 📝 Script ready, not recorded | `DEMO_VIDEO_SCRIPT.md` — timed, with a cut-for-time version if you're running long |
| GitHub repository | ⬜ Not pushed yet | This zip *is* the repo content — `git init`, commit, push. `.gitignore` is already in place |
| Live demo (optional) | ⬜ Not deployed | Your past stack for this exact pairing: Vercel (frontend) + Render (backend). Last time that combo needed a CORS fix and an explicit `/api` prefix — worth checking those first rather than rediscovering them under deadline pressure |

## Fastest path from here to submitted

1. Record the demo video following the script — run through it once
   un-recorded first so the optimizer run and hotspot click aren't
   fumbled live.
2. `git init && git add . && git commit -m "Horizon Round 1 submission"`,
   push to a new GitHub repo.
3. Paste `PROJECT_DESCRIPTION.md` into the submission form.
4. Deploy if you have time; skip it if you're tight — it's optional,
   the video covers the same ground.
