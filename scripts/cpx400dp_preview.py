#!/usr/bin/env python3
"""Offline, instant CPX400DP CSV profile preview. No network or PSU access.

Reusable entry point for a future GUI:
    generate_preview(profile_path, output_path=None) -> pathlib.Path
    profile_summary(profile_path) -> dict

Requires matplotlib only when rendering an HTML preview.
"""
import argparse
import base64
import html
import io
import math
from pathlib import Path


def _model(load_profile=None, at_time=None):
    if load_profile is None or at_time is None:
        from cpx400dp_run_enhanced import load_profile as imported_loader, at_time as imported_at_time
        load_profile = load_profile or imported_loader
        at_time = at_time or imported_at_time
    return load_profile, at_time


def profile_summary(profile_path, load_profile=None, overrides=None):
    loader, _ = _model(load_profile=load_profile)
    (host, channels, mode, interval, rb_interval, log_path, points,
     restores, initial, final, heartbeat) = (loader(Path(profile_path), overrides=overrides)
                                           if overrides is not None else loader(Path(profile_path)))
    from cpx400dp_run_enhanced import validate_schedule
    smallest = validate_schedule(points, interval, initial, final, any(restores.values()))
    transitions = {ch: [] for ch in channels}
    previous_explicit = {ch: None for ch in channels}
    for t, values in points:
        for ch in channels:
            enable = values[ch][2]
            if enable is not None:
                # Preserve every explicit enable directive, including repeated directives.
                transitions[ch].append({'time_s': t, 'command': 'ON' if enable else 'OFF'})
                previous_explicit[ch] = enable
    return {
        'host': host, 'channels': channels, 'mode': mode, 'interval_s': interval,
        'readback_interval_s': rb_interval, 'duration_s': points[-1][0],
        'initial_ramp_s': initial, 'final_ramp_s': final,
        'restore': restores, 'point_count': len(points),
        'enable_commands': transitions,
        'keyframes': [t for t, _ in points],
        'min_scheduled_gap_s': smallest,
    }


def _sample_times(points, duration, mode, max_regular=1201):
    # Bounded number of samples even for multi-hour profiles. Include every
    # keyframe and samples just before step transitions for crisp step graphs.
    n = max(2, min(max_regular, math.ceil(duration / 0.5) + 1))
    times = {duration * k / (n - 1) for k in range(n)}
    for t, _ in points:
        times.add(t)
        if mode == 'step' and t > 0:
            times.add(math.nextafter(t, -math.inf))
    return sorted(times)


def generate_preview(profile_path, output_path=None, load_profile=None, at_time=None, overrides=None):
    """Make a self-contained HTML preview without sleeping or contacting the PSU."""
    loader, interp = _model(load_profile, at_time)
    path = Path(profile_path)
    (host, channels, mode, interval, rb_interval, log_path, points,
     restores, initial, final, heartbeat) = (loader(path, overrides=overrides)
                                           if overrides is not None else loader(path))
    summary = profile_summary(path, loader, overrides=overrides)
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError('Install python3-matplotlib to render previews') from exc

    times = _sample_times(points, points[-1][0], mode)
    values = [interp(points, t, mode) for t in times]
    sections = []
    for ch in channels:
        fig, ax_v = plt.subplots(figsize=(6.8, 3.6))
        ax_i = ax_v.twinx()
        fig.subplots_adjust(left=0.105, right=0.88, bottom=0.36, top=0.92)
        voltages = [row[ch][0] for row in values]
        currents = [row[ch][1] for row in values]
        lv, = ax_v.plot(times, voltages, color='#2369b7', lw=2, label='Voltage setpoint')
        li, = ax_i.plot(times, currents, color='#c36918', lw=2, label='Current limit')
        ax_v.set_ylabel('Voltage (V)', color='#2369b7')
        ax_i.set_ylabel('Current (A)', color='#c36918')
        ax_v.set_xlim(0, max(0.001, points[-1][0]))
        ax_v.set_ylim(bottom=0)
        ax_i.set_ylim(bottom=0)
        ax_v.set_xlabel('Profile time (seconds)')
        # The strip shows effective enable state (ON/OFF/unknown), and
        # hatching distinguishes inherited HOLD from an explicit command.
        # Do not share x ticks with the main axes: set_xticks([]) on a
        # shared axis also removes the main plot's numeric time labels.
        strip = fig.add_axes([0.105, 0.085, 0.775, 0.075])
        strip.set_xlim(ax_v.get_xlim())
        commands = summary['enable_commands'][ch]
        duration = points[-1][0]
        # At each keyframe, a HOLD retains the most recent explicit state.
        stages = []
        known = None
        for t, row in points:
            directive = row[ch][2]
            if directive is not None:
                known = 'ON' if directive else 'OFF'
                source = known
            else:
                source = 'HOLD'
            stages.append((t, known, source))
        collapsed = []
        for t, state, source in stages:
            if collapsed and collapsed[-1][1:] == (state, source):
                continue
            collapsed.append((t, state, source))
        stages = collapsed
        for j, (t, state, source) in enumerate(stages):
            end = stages[j+1][0] if j+1 < len(stages) else duration
            if end <= t: continue
            color = '#cce8d9' if state == 'ON' else '#e3e7ed' if state == 'OFF' else '#f0e6c8'
            strip.broken_barh([(t, end-t)], (0, 1), facecolors=color,
                              edgecolors='#a0a8b1', linewidth=.45,
                              hatch='//' if source == 'HOLD' else None)
            if (end-t) >= duration*0.07:
                caption = ('HOLD (ON)' if state == 'ON' else
                           'HOLD (OFF)' if state == 'OFF' else 'HOLD (?)') if source == 'HOLD' else source
                strip.text((t+end)/2, .5, caption, ha='center', va='center',
                           fontsize=7.5, color='#253145')
        strip.set_ylim(0,1); strip.set_yticks([]); strip.set_xticks([])
        strip.set_ylabel('Output', rotation=0, labelpad=28, fontsize=9)
        # Channel identification is in the section heading; keep axes uncluttered.
        ax_v.grid(True, alpha=0.25)
        # Shared legend is rendered once below both charts by HTML/GUI.
        out = io.BytesIO()
        fig.savefig(out, format='png', dpi=140, facecolor='white')
        plt.close(fig)
        b64 = base64.b64encode(out.getvalue()).decode('ascii')
        commands = summary['enable_commands'][ch]
        if commands:
            enable_text = '; '.join(f'{e["time_s"]:g} s: {e["command"]}' for e in commands)
        else:
            enable_text = 'No ON/OFF commands; all rows hold existing output state.'
        initial_cmd = next((e['command'] for e in commands if e['time_s'] == 0), None)
        if not commands:
            notice = 'HOLD throughout: this channel retains its initial PSU output state. The voltage setpoint is not proof of an enabled physical output.'
        elif all(e['command'] == 'OFF' for e in commands) and initial_cmd == 'OFF':
            notice = 'OFF throughout: this channel will program voltage settings without energising the output.'
        elif initial_cmd is None:
            notice = 'Initial HOLD: the output state is unknown until the PSU is read at run start; later explicit ON/OFF commands take effect.'
        else:
            notice = 'The shaded strip shows commanded output states, not measured physical output.'
        sections.append(f'<section class="panel"><h2>Channel {ch}</h2>'
                        f'<img alt="Channel {ch} voltage and current-limit preview" '
                        f'src="data:image/png;base64,{b64}">'
                        f'<p><strong>Output-enable directives:</strong> {html.escape(enable_text)}</p>'
                        f'<p><strong>Output note:</strong> {html.escape(notice)}</p></section>')

    path_out = Path(output_path) if output_path is not None else path.with_name(path.stem + '_preview.html')
    html_text = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CPX400DP profile preview — {html.escape(path.name)}</title>
<style>body{{background:#f3f5f9;font:15px system-ui,-apple-system,sans-serif;color:#182438;line-height:1.6;margin:0}}
main{{max-width:1100px;margin:25px auto;padding:0 18px}}h1{{font-size:26px}}
.panel{{background:#fff;padding:20px;border:1px solid #e0e5ed;border-radius:11px;margin:16px 0}}
img{{width:100%;height:auto;display:block}}.muted{{color:#536273}}.details{{display:flex;flex-wrap:wrap;gap:10px}}
.details span{{padding:6px 11px;background:#edf2f9;border-radius:7px}}
.shared-legend{{display:flex;justify-content:center;align-items:center;gap:12px;margin:8px 0 14px}}
.vline,.iline{{display:inline-block;width:28px;border-top:3px solid #2369b7;margin-left:12px}}
.iline{{border-color:#c36918}}.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(370px,1fr));gap:12px}}@media print{{body{{background:white}}}}</style>
</head><body><main><h1>CPX400DP — profile preview</h1>
<p class="muted">Source: {html.escape(path.name)} · Offline calculation only; no PSU connection and no elapsed-time simulation.</p>
<section class="panel"><h2>Profile information</h2><div class="details">
<span>Channels: {', '.join(map(str,channels))}</span><span>Interpolation: {html.escape(mode)}</span>
<span>Main profile: {points[-1][0]:g} s</span><span>Setpoint interval: {interval:g} s</span>
<span>Readback interval: {rb_interval:g} s</span><span>Keyframes: {len(points)}</span>
<span>Minimum scheduled update gap: {summary["min_scheduled_gap_s"]*1000:.1f} ms</span>
<span>Initial ramp setting: {initial:g} s</span><span>Final ramp setting: {final:g} s</span>
</div><p><strong>Important:</strong> The charts show only the CSV-defined main profile. They do not plot the initial or final ramps, because those depend on settings read from the live PSU. The configured ramp durations are shown for reference. Enable directives are listed separately; <em>hold</em> preserves the current state.</p></section>
<div class="charts">{''.join(sections)}</div>
<div class="shared-legend"><span class="vline"></span>Voltage setpoint (V)
<span class="iline"></span>Current limit (A)</div>
<p class="muted">This is a profile preview, not measured PSU behaviour or an electrical safety approval.</p>
</main></body></html>'''
    path_out.write_text(html_text, encoding='utf-8')
    return path_out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    parser.add_argument('--output', type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        print(f'Profile preview: {generate_preview(args.profile, args.output)}')
        return 0
    except (OSError, ValueError, KeyError, ImportError) as exc:
        parser.exit(1, f'PREVIEW ERROR: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
