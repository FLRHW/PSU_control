# Large-recording HTML reports (v13.6 development)

## Purpose and selection

The legacy scripts/cpx400dp_report.py report loads the entire CSV and embeds
all waveform points in one self-contained HTML. That original format remains
unchanged for measurement CSV logs smaller than **8 MiB**.

Larger files automatically use scripts/cpx400dp_report_stream.py, a two-pass
CSV report processor. The large-file generator keeps summary counters,
limited annotations, fixed overview extrema buckets and point chunks instead
of every row. It has no PSU/SCPI access and needs no new runtime dependencies.

Run the new mode on a smaller test fixture with the CLI option --stream.

## Output layout

For X_measurements.csv the files are:

- X_report.html: summary, SVG viewer, overview traces and chunk-time manifest
- X_report_data/c1_000000.js, c2_000000.js and subsequent numbered chunks:
  per-channel local waveform data, at most 4096 plottable records each

The HTML and its matching report_data directory MUST stay together.
The original measurements CSV remains the authoritative raw evidence.

The initial overview has 1200 time buckets and retains each bucket's first,
last, minimum and maximum value per trace, protecting isolated peaks.
When zoomed below 15 percent of total duration with at most three
overlapping chunks, the viewer loads detail using script elements and
local relative paths. This works for file:// links without an HTTP server
or fetch/CORS permissions. The viewer retains at most six detail chunks
in its browser cache.

The viewer supports per-trace selection, wheel zoom, drag pan,
measured-voltage cursor Delta t / Delta V, step-mode vertical transitions,
negative sample markers at the zero baseline, and OFF/ramp/pause
annotations. The Jump to elapsed second and Window (s) controls
allow direct exploration of 50 ms windows near the end of a long run.

Power uses sampled V times I, with energy from adjacent logged samples.

## Limits and retention

- Report generation never connects to or commands the PSU, and cannot
  affect runner restoration/LOCAL-last control behaviour.
- It makes two sequential CSV passes. Time and disk use still grow with
  log size; it writes extra files and is not a streaming *live* viewer.
- Python trace buffers are limited to 4096 plotted records per chunk,
  while the chunk manifest itself grows with the number of chunks.
  Do not claim a mathematically constant memory footprint for an
  infinitely long experiment.
- Annotations are capped at 10000 per channel and diagnostic notes at
  100. Original raw CSV retains all records even if the HTML omits some.
- Large overviews are lossy extrema-preserving summaries; on-demand
  zoom detail is full-resolution only when corresponding chunk files
  are present and loaded.
- Keep the report HTML and data folder together when moving or archiving.
  Preserve the original CSV for accurate post-processing.
- Mid-run disk monitoring, power-failure recovery, unattended multi-day
  runtime and real instrument endurance remain unverified.

## Offline validation

Run full GitHub Actions Python regression suite including
tests/test_v13_6_report_stream.py, synthetic dual-channel peak fixtures,
small-report compatibility, bounded-memory checks and viewer JavaScript
syntax checks when Node is available. UI acceptance in a real desktop
browser is a separate test and must not be claimed solely from CI.
