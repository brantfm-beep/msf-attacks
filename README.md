# MSF Attack Planner Web v0.3.8 — Public Test Edition

This is the web project derived from MSF Attack Planner desktop v0.4.0.
The desktop/Qt application is not modified by this project.

## Public-site architecture

The browser app is static HTML/CSS/JavaScript and is suitable for GitHub Pages.
Visitors do not run Python and do not contact Marvel Church directly.

Shared files under `data/` contain:
- War and Cosmic Crucible counters
- Marvel Church team directory
- Team rosters
- MSF character directory
- Last-refresh status

Each visitor's personal War defenses are stored in that visitor's browser
`localStorage`. They are not written to GitHub and therefore do not overwrite
another user's defenses.

## Local static test

From the project root:

    python3 -m http.server 8081

Open:

    http://localhost:8081

This tests the same static application model that GitHub Pages will serve.

## One-time live data refresh before publishing

Install the refresh dependencies:

    python3 -m pip install -r tools/requirements.txt
    python3 -m playwright install chromium

Then:

    python3 tools/refresh_data.py

The refresher first tries ordinary HTTPS. Chromium is only a fallback for pages
that cannot be read directly. It validates fetched data before replacing the
published JSON.

After the refresh completes, start the static server again:

    python3 -m http.server 8081

## GitHub Actions refresh

`.github/workflows/refresh-data.yml` supports:
- a scheduled daily refresh
- manual **Run workflow** refreshes from the Actions tab

The workflow refreshes the JSON under `data/` and commits it only when the data
changed.

GitHub Actions schedules use UTC. The included schedule runs at 10:17 UTC
(about 6:17 AM Eastern during daylight time and 5:17 AM during standard time).

## GitHub Pages

Upload the *contents of this project folder* to the repository root so that
`index.html`, `css/`, `js/`, `data/`, `tools/`, and `.github/` are all at the
top level of the repository.

Then enable GitHub Pages for the repository using the main branch/root folder.

## v0.3.8 fix

Restored the five War Defense character dropdown controls that were accidentally removed while converting the local API calls to static GitHub Pages data. `Use Team` now populates those controls and modified defenses can be saved normally.

## v0.3.8 fix

Character dropdowns now merge the Marvel Church character directory with all refreshed Team Breakdown roster members. Refreshed public rosters take precedence over stale browser roster caches, and the invalid counter-text-derived fallback character list was removed.

## v0.3.8 fix

Static CSS/JavaScript assets now use versioned URLs so a browser testing multiple
builds on the same localhost port cannot silently keep an older app.js. The War
Defense editor also reports the number of characters loaded into its dropdowns.

## v0.3.8 fix

Replaced the five native browser character selects with searchable in-page
dropdowns. This avoids macOS/Chrome native-select rendering problems with the
398-character roster. Defense saves strictly validate each entry against the
current character directory, so misspellings cannot be saved.

## v0.3.8 fix

Restored the `enrichCharactersFromRosters()` helper that was accidentally
removed in v0.3.4. Its absence caused startup to abort before team templates
and saved-defense counts were rendered. Core UI initialization now completes
before optional character enrichment, so a future character-data problem
cannot prevent War/Crucible data and saved defenses from loading.

## v0.3.8 change

Team Breakdown refreshes now retain partial team rosters when Marvel Church
exposes at least 3 valid members. `Use Team` fills those known members and leaves
the remaining character slots blank for manual selection. Save Defense still
requires exactly five unique valid characters.

## v0.3.8 change

The Other Counters section now shows the full strategy note for every alternate
counter, not just a [strategy] marker. This makes it possible to immediately
switch to another available team and still see how the matchup should be played.

## v0.3.8 change

Cosmic Crucible counter choices are now interactive. Clicking a counter locks
that choice for the room and recalculates all unlocked rooms. Named counters
such as `Illuminati (with Cap Britain)` are expanded through the refreshed team
roster so individual-character reuse (for example Hank Pym) is detected.
Alternatives that overlap a locked room are disabled and identify the reused
character. Clicking a locked choice again returns that room to automatic mode.
