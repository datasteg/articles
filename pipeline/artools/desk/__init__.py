"""The data desk: a daily, low-cost article line that reads datasteg's own apps through the public API.

Code does everything that can be checked: it watches the apps for new data (watch), joins their views into one panel
and screens it for readings no single page shows (leads), fetches and computes every number (facts), draws the charts
and runs the checks. Models do the judgement and the prose, one bounded call per role (roles): an editor picks the
lead, an analyst asks for the numbers, a writer drafts, three reviewers criticise, a judge scores the result on the
standard the institutional benchmarks are scored on. A person approves the finished note in the admin site before it
is published (queue). Standard: guides/desk/standard.md.
"""
