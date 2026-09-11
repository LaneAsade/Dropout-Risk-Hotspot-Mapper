# Demo Video Script — target 2:30

Practical notes before you record:
- Run `uvicorn app.main:app --port 8000` and `python3 -m http.server 5173`
  first, and load `localhost:5173` once so tiles are cached before you
  hit record — don't burn video time on a loading spinner.
- Screen-record at 1440px+ width; the ledger panel gets cramped narrower.
- Have the Deploy Units tab's K already set to 20 (the default) before
  you start, so the ILP-vs-greedy gap shows up on the first run —
  don't fish for a parameter combo on camera.

---

**[0:00–0:15] Hook — problem, not product**

*Screen: static, maybe a blank browser tab or your title slide.*

> "In Karnataka, real government data puts secondary school dropout at
> 17.8% — almost one in five kids who reach 9th grade don't finish
> 10th. That's not a slide number. It's computed live, by the tool
> I'm about to show you, from real UDISE+ data — and it matches a
> published national study almost exactly. The question isn't whether
> this is a crisis. It's where to send help first."

**[0:15–0:45] The map — state, then hotspot**

*Screen: load the Hotspots tab. Let the choropleth render, then pan/zoom
slightly to show real Karnataka's shape.*

> "This is every one of Karnataka's 74,000-plus real, geocoded schools.
> The shading is real district-level risk. The circles are hotspots —
> not just 'where schools are dense,' but where risk is concentrated
> relative to the state average."

*Click a hotspot circle — let it fly in and show individual school markers.*

> "Click in, and you get real schools, real names, real locations —
> colored by risk tier, not by a placeholder."

**[0:45–1:15] The honesty layer**

*Click "About this data & responsible-AI notes" to expand it.*

> "This part matters as much as the map. We say plainly what's real
> and what's a modeling choice. The infrastructure signal — toilets,
> library, computer, internet access — is real 2019-20 data. The
> weighting rule that turns it into a risk score is a documented
> choice, not a fitted model. We'd rather be useful and honest than
> falsely precise."

**[1:15–1:55] Deploy Units — the optimizer**

*Click the "Deploy units" tab. Click "Run optimizer."*

> "Knowing where risk is concentrated is half the problem. The other
> half: with a limited budget, where do you actually put help? This
> runs a real integer linear program — not a rule of thumb — to place
> mobile tutoring units for maximum coverage, with a constraint that
> spreads them across districts instead of dumping all of them into
> the two biggest cities."

*Point at the results panel — Coverage (ILP) vs Greedy baseline vs gap.*

> "And we don't just claim the optimizer is smarter — we benchmark it
> against a standard greedy approach, live, on our own data, right
> here. Today that's a real, provable gap of about 54 risk-units at
> zero extra cost."

**[1:55–2:15] How it was actually built**

*Screen: can be the README or just talking over the map.*

> "Two things I want to flag because they're the honest story of
> building this. First, our initial hotspot approach was a direct port
> of a clustering method from a different domain, and it broke — schools
> aren't events, they're fixed infrastructure, so density alone was
> the wrong signal. We caught that and fixed it with a grid-based
> relative-risk approach instead. Second, this environment couldn't
> reach India's live data portals — so instead of falling back to fake
> numbers, we found a public archive that had already pulled the exact
> real indicators we needed, for all 34 districts."

**[2:15–2:30] Close**

*Screen: back to the full map, zoomed to show the whole state.*

> "Real school data. Real infrastructure data. A real optimizer,
> benchmarked honestly. And a responsible-AI layer that says what it
> knows and what it doesn't. That's the Dropout-Risk Hotspot Mapper."

---

## If you need to cut for time (aim for under 2:00)

Drop, in this order: the "How it was actually built" section (2:15 gets
folded into a one-line mention), then shorten the honesty-layer beat to
one sentence instead of the full expand-and-read. Keep the hook, the
map, and the optimizer comparison — those three carry the pitch.
