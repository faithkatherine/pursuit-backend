---
description: "Add or update a seed scenario for the Pursuit backend"
---

Add or update seed data in the Pursuit backend.

Read the existing seed script(s) before writing anything.
Confirm which management command file handles seeding.

Seed requirements — always:

- Use get_or_create for all records — script must be idempotent
- Running the seed twice must produce the same result (no duplicates)
- Cover all six test scenarios:

  Scenario A — Normal (User A):
  allowLocationSharing=true, active EditorsPick for Nairobi,
  ~12 events across categories, 2-3 within next 24h

  Scenario B — Has trip (User D):
  Same as A but with an upcoming Trip object 2-4 weeks out,
  2 events linked to the trip

  Scenario C — No pick:
  allowLocationSharing=true, NO active EditorsPick for user's location
  home hero shows top recommendation without badge

  Scenario D — Location disabled (User C):
  allowLocationSharing=false
  home shows State B pill, no weather data returned

  Scenario E — Reinstall simulation:
  allowLocationSharing=true, lat/lng present on backend
  (simulate by logging in as this user on a fresh simulator with no OS permission)

  Scenario F — Empty filter:
  Events exist but NONE fall in Tonight date range
  selecting Tonight filter produces empty state

- At least one event per category slug
- At least one event with curator_note populated (for EditorsPick)
- EditorsPick for nairobi and mombasa both active
- Document the seed commands in a comment at the top of the seed file
