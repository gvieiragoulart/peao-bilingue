# Strider fixtures

Real public pages from `https://www.onstrider.com`, fetched on 2026-10-18 with the app's
User-Agent (no login):

- `jobs.html`: the jobs page (`/jobs`), 14 cards;
- `back-end-engineer-9bb259a7.html`: one job's page.

They are trimmed to what the adapter reads: the `<title>`, the JSON-LD scripts and `<main>`.
The SVG icons are emptied, and `<style>` and other `<script>` blocks are removed. Classes and
attributes stay as they were, since the adapter reads some of them.

There is no personal data: these are public job pages, and the company isn't named. The
"WhatsApp" text comes from the share buttons. When the fixtures are refreshed, check that
nothing personal came in.
