#!/usr/bin/env python3
"""Offline CPX400DP report with independently selectable traces.

Usage: python3 cpx400dp_report.py measurements.csv [--layout separate|combined|power]
No PSU connection, external JavaScript library, AI service or internet required.
"""
import argparse
import csv
import html
import json
import math
from datetime import datetime
from pathlib import Path


def num(row, field):
    try:
        value = float(row.get(field) or '')
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def generate(log_file, layout='separate', profile=None):
    if layout not in ('separate', 'combined', 'power'):
        raise ValueError('Unsupported initial report layout')
    log_file = Path(log_file)
    with log_file.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError('Measurement log contains no events')
    channels = sorted({int(row['channel']) for row in rows if (row.get('channel') or '').strip() in ('1', '2')})
    if not channels:
        raise ValueError('Measurement log contains no channel data')
    tstamp = next((r.get('utc_time') for r in rows if r.get('utc_time')), None)
    try:
        dt = datetime.fromisoformat(tstamp)
        date_str = dt.strftime('%d %B %Y, %H:%M:%S %Z').strip()
        if not dt.tzinfo or not dt.tzname():
            date_str += ' UTC' if dt.tzinfo else ' (timezone unspecified)'
    except (TypeError, ValueError):
        date_str = tstamp or 'Unknown'
    successful = sum(r.get('event') == 'readback' for r in rows)
    failures = sum(r.get('event') == 'readback_error' for r in rows)
    lateness = [num(r, 'lateness_ms') for r in rows]
    lateness = [x for x in lateness if x is not None]
    interrupted = any(r.get('event') == 'interrupted' for r in rows)
    verified = {c: any(r.get('event') == 'final_state_verified' and r.get('channel') == str(c) for r in rows) for c in channels}
    local_sent = any(r.get('event') == 'local_sent' for r in rows)
    fault_aborted = any(r.get('event') == 'output_fault_abort' for r in rows)
    status = ('ABORTED (OUTPUT FAULT)' if fault_aborted else 'INTERRUPTED' if interrupted else ('COMPLETED' if all(verified.values()) else 'NOT VERIFIED'))
    cfg = next((r.get('note', '') for r in rows if r.get('event') == 'config'), '')
    mode = 'step' if 'mode=step' in cfg else 'linear'
    health_warnings = sum(r.get('event') == 'output_health_warning' for r in rows)
    high_readbacks = sum(r.get('event') == 'implausible_high_readback' for r in rows)
    settling_readbacks = sum(r.get('event') == 'settling_readback' for r in rows)
    fault_aborted = any(r.get('event') == 'output_fault_abort' for r in rows)
    physical = {ch: next((r.get('event') for r in reversed(rows)
                          if r.get('channel') == str(ch) and r.get('event') in
                          ('physical_output_checked', 'physical_output_warning', 'physical_output_skipped')), None)
                for ch in channels}
    data = {}
    stats = {}
    for ch in channels:
        c = [r for r in rows if r.get('channel') == str(ch)]
        commands = [r for r in c if r.get('event') in ('initial_ramp', 'setpoint', 'final_ramp', 'pause_hold', 'manual_setpoint')]
        readbacks = [r for r in c if r.get('event') == 'readback']
        def points(records, field):
            return [[num(r, 'elapsed_s'), num(r, field)] for r in records if num(r, 'elapsed_s') is not None and num(r, field) is not None]
        power = [[num(r,'elapsed_s'), num(r,'measured_voltage_v') * num(r,'measured_current_a')]
                 for r in readbacks if None not in (num(r,'elapsed_s'), num(r,'measured_voltage_v'), num(r,'measured_current_a'))]
        boundaries = []
        for phase in ('setpoint', 'final_ramp'):
            times = [num(r, 'elapsed_s') for r in commands if r.get('event') == phase]
            times = [t for t in times if t is not None]
            if times and min(times) > 1e-6:
                boundaries.append(min(times))
        initial_times = [num(row, 'elapsed_s') for row in c if row['event']=='initial_ramp' and num(row,'elapsed_s') is not None]
        final_times = [num(row, 'elapsed_s') for row in c if row['event']=='final_ramp' and num(row,'elapsed_s') is not None]
        first_profile = [num(row,'elapsed_s') for row in c if row['event']=='setpoint' and num(row,'elapsed_s') is not None]
        restoration_times = [num(row,'elapsed_s') for row in rows if row['event'] in ('final_state_sent','final_state_verified','final_state_error') and num(row,'elapsed_s') is not None]
        ramp_regions = []
        if initial_times and first_profile:
            ramp_regions.append([min(initial_times), min(first_profile), 'Ramp'])
        if final_times:
            end_ramp = min(restoration_times) if restoration_times else max(final_times)
            if end_ramp > min(final_times):
                ramp_regions.append([min(final_times), end_ramp, 'Ramp'])
        pauses = [[num(row, 'elapsed_s'), row.get('event')]
                  for row in rows if row.get('event') in ('pause', 'resume')
                  and num(row, 'elapsed_s') is not None]
        # Determine output-disabled regions from initial snapshot and explicit
        # output-transition commands. The physical voltage may decay later.
        snapshot = next((row for row in c if row.get('event') == 'snapshot'), None)
        initial_enable = (snapshot.get('requested_enable') if snapshot else None)
        transitions = sorted([[num(row, 'elapsed_s'), row.get('requested_enable')]
                              for row in c if row.get('event') == 'output_transition'
                              and num(row, 'elapsed_s') is not None], key=lambda x: x[0])
        off_regions = []
        last_state = initial_enable
        last_t = 0.0
        all_end_times = [num(row, 'elapsed_s') for row in rows]
        end_time = max((t for t in all_end_times if t is not None), default=0.0)
        for instant, state in transitions + [[end_time, None]]:
            if str(last_state).strip() in ('0', 'OFF', 'False') and instant > last_t:
                off_regions.append([last_t, instant])
            last_t = instant
            if state is not None:
                last_state = state
        data[str(ch)] = {
            'vs': points(commands, 'set_voltage_v'),
            'cs': points(commands, 'current_limit_a'),
            'vm': points(readbacks, 'measured_voltage_v'),
            'cm': points(readbacks, 'measured_current_a'),
            'p': power, 'transitions': [[num(r, 'elapsed_s'), r.get('requested_enable')] for r in c if r.get('event') == 'output_transition' and num(r, 'elapsed_s') is not None], 'boundaries': boundaries, 'pauses': pauses, 'ramp_regions': ramp_regions, 'off_regions': off_regions, 'mode': mode
        }
        if power:
            power = [[t, 0.0 if abs(val) < 0.0005 else val] for t, val in power]
            data[str(ch)]['p'] = power
            energy = sum((power[i][0] - power[i-1][0]) * (power[i][1] + power[i-1][1]) / 2 for i in range(1, len(power)))
            stats[ch] = (f'{max(0, max(p for _, p in power)):.2f} W', f'{sum(p for _,p in power)/len(power):.2f} W' if abs(sum(p for _,p in power)/len(power)) >= 0.005 else '0.00 W', f'{energy:.1f} J' if abs(energy) >= 0.05 else '0.0 J')
        else:
            stats[ch] = ('—', '—', '—')

    def card(label, value):
        return f'<div class="stat"><small>{html.escape(str(label))}</small><b>{html.escape(str(value))}</b></div>'
    overview = ''.join([
        card('Channels', ', '.join(map(str, channels))), card('Run status', status),
        card('Successful readbacks', successful), card('Failed readbacks', failures),
        card('Maximum logged setpoint lateness', f'{max(lateness):.3f} ms' if lateness else 'Not recorded'),
        card('LOCAL command', 'SENT' if local_sent else 'NOT CONFIRMED'),
        card('Output-health warnings', health_warnings),
        card('Unexplained high readbacks', high_readbacks),
        card('Expected-settling readbacks', settling_readbacks),
        card('Experiment health', 'FAILED' if fault_aborted else 'WARNING' if health_warnings or high_readbacks else 'OK'),
        *[card(f'Channel {ch} sampled physical output',
               'MATCHED' if physical[ch] == 'physical_output_checked' else
               'WARNING' if physical[ch] == 'physical_output_warning' else 'N/A (OFF or near-zero target)' if physical[ch] == 'physical_output_skipped' else 'NOT CHECKED')
          for ch in channels],
        *[card(f'Channel {ch} final state', 'VERIFIED' if verified[ch] else 'NOT VERIFIED') for ch in channels]
    ])
    diagnostic_rows = [r for r in rows if r.get('event') in ('diagnostic', 'diagnostic_error')]
    if diagnostic_rows:
        # Row-oriented side-by-side snapshots, preserving the exact raw response.
        import re
        by_key = {}
        for row in diagnostic_rows:
            note = row.get('note', '')
            match = re.match(r'^(initial|final):\s+(\*STB\?|LSR1\?|LSR2\?|\*ESR\?|EER\?|QER\?)\s*(?:=\s*([^ (]+)|:\s*(.*))', note)
            if match:
                stage, cmd, value, err = match.groups()
                by_key.setdefault(cmd, {})[stage] = (value if value is not None else 'ERROR: ' + str(err or note))
        descriptions = {
            '*STB?': 'Status byte: summary of instrument status flags (not a complete fault history).',
            'LSR1?': 'Channel 1 limit/status event register; bit meanings depend on PSU documentation.',
            'LSR2?': 'Channel 2 limit/status event register; bit meanings depend on PSU documentation.',
            '*ESR?': 'Standard event-status register; reading may clear latched events.',
            'EER?': 'Execution-error register, recording instrument command execution errors.',
            'QER?': 'Query-error register, recording instrument query/response errors.'
        }
        diagnostic_html = '<section class="panel"><h2>PSU diagnostic snapshots</h2><p class="hint">Raw integer responses from the instrument. Some event registers clear on read. No individual bit interpretation is claimed without matching the exact firmware programming manual.</p><table class="diag"><thead><tr><th>Query</th><th>Initial</th><th>Final</th><th>Meaning</th></tr></thead><tbody>'
        for cmd, description in descriptions.items():
            values = by_key.get(cmd, {})
            diagnostic_html += '<tr><td><code>' + html.escape(cmd) + '</code></td><td>' + html.escape(values.get('initial', '—')) + '</td><td>' + html.escape(values.get('final', '—')) + '</td><td>' + html.escape(description) + '</td></tr>'
        unmatched = [r.get('note', '') for r in diagnostic_rows if not re.match(r'^(initial|final):\s+(\*STB\?|LSR1\?|LSR2\?|\*ESR\?|EER\?|QER\?)', r.get('note', ''))]
        diagnostic_html += '</tbody></table>'
        if unmatched:
            diagnostic_html += '<p class="hint">Other diagnostic messages: ' + html.escape('; '.join(unmatched)) + '</p>'
        diagnostic_html += '</section>'
    else:
        diagnostic_html = '<section class="panel"><h2>PSU diagnostics</h2><p>Not collected in this run.</p></section>'
    default = {'separate': ('vs', 'vm', 'cs', 'cm', 'p'), 'combined': ('vs', 'vm', 'cs', 'cm', 'p'), 'power': ('p',)}[layout]
    names = [('vs','Voltage setpoint'),('vm','Measured voltage'),('cs','Current limit'),('cm','Measured current'),('p','Measured power')]
    sections = []
    for ch in channels:
        checks = ''.join(f'<label class="trace-option"><input type="checkbox" data-key="{key}" {"checked" if key in default else ""}><span class="swatch {key}"></span>{label}</label>' for key,label in names)
        peak, mean, energy = stats[ch]
        sections.append(f'''<section class="panel channel" data-channel="{ch}">
<h2>Channel {ch} — selectable traces</h2>
<div class="controls" role="group" aria-label="Channel {ch} visible curves">{checks}</div>
<div class="chart-toolbar"><button type="button" class="reset-zoom">Reset zoom</button><button type="button" class="cursor-toggle" aria-pressed="false">Cursors: OFF</button><span class="cursor-values">Wheel to zoom · drag to pan · enable cursors to measure Δt and ΔV (measured voltage)</span></div>
<div class="plot-area"><svg class="plot" role="img" aria-label="Channel {ch} interactive time-series chart"></svg><div class="legend" aria-label="Visible trace legend"></div></div>
<p class="hint">Grey shading indicates a commanded OFF output state, gold shading marks ramps and blue shading indicates pauses. OFF shading does not imply instantaneous zero terminal voltage. Voltage uses the left axis (V); current uses the right axis (A); power uses a second right axis (W). Axes appear only for selected quantities. Wheel zooms at pointer; drag pans; turn on cursors and click twice to place A and B (Δt, ΔV from nearest measured-voltage samples). Vertical dotted lines mark profile-phase transitions; pause/resume markers identify intervals where profile time was held but readbacks continued. All axes start at zero; negative measured samples, if present, are marked on the zero line.</p>
<div class="stats">{card('Peak sampled power',peak)}{card('Mean sampled power',mean)}{card('Estimated energy',energy)}</div>
<p class="hint">Power = measured voltage × measured current at each readback. Energy is estimated between readback samples; unsampled transients are not captured.</p>
</section>''')

    # Embed only inert numeric arrays. Escaping '<' prevents accidental script termination.
    payload = json.dumps(data, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CPX400DP experiment report</title>
<style>
:root{--ink:#172235;--muted:#536173;--line:#dce3ed}*{box-sizing:border-box}body{margin:0;background:#f3f5f9;color:var(--ink);font:15px system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.5}main{max-width:1180px;margin:30px auto;padding:0 18px}h1{font-size:27px;margin:0 0 3px}h2{font-size:19px;margin:0 0 14px}.muted,.hint{color:var(--muted)}.hint{font-size:13px}.panel{background:#fff;border:1px solid #e1e6ee;border-radius:12px;padding:22px;margin:18px 0;box-shadow:0 2px 10px #17223508}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px;margin:14px 0}.stat{border:1px solid var(--line);border-radius:9px;padding:12px}.stat b{display:block;font-size:20px}.stat small{color:var(--muted)}
.diag{border-collapse:collapse;width:100%;font-size:13px}.diag td,.diag th{padding:6px;border-bottom:1px solid #e0e5ed;text-align:left;overflow-wrap:anywhere}.controls{display:flex;flex-wrap:wrap;gap:8px 18px;padding:12px;margin-bottom:12px;border:1px solid var(--line);border-radius:9px}.trace-option{display:flex;align-items:center;gap:7px;cursor:pointer;white-space:nowrap}.trace-option input{width:17px;height:17px;cursor:pointer}.swatch{display:inline-block;width:20px;height:4px;border-radius:3px}.vs{background:#196cb5}.vm{background:#13a9c1}.cs{background:#d42b31}.cm{background:#eb7e24}.p{background:#7545b9}
.chart-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px}.chart-toolbar button{padding:6px 11px;border:1px solid #c7d0df;border-radius:6px;background:#f5f8fc;cursor:pointer;color:#172235}.chart-toolbar button[aria-pressed="true"]{background:#e5f2ff;border-color:#2863a6}.cursor-values{font-size:12px;color:#455a70}.plot-area{display:flex;gap:12px;align-items:flex-start;min-height:330px}.plot{width:min(100%,970px);height:auto;flex:1 1 auto;display:block}.legend{flex:0 0 145px;padding-top:32px;font-size:13px}.legend-item{display:flex;align-items:center;gap:7px;margin-bottom:13px}.legend-line{width:24px;height:0;border-top:3px solid;flex-shrink:0}.legend-line.measured{border-top-style:dashed}.axis-label{font-size:12px;fill:#46576b}.axis-name{font-size:12px;font-weight:650}.grid-line{stroke:#e5eaf0;stroke-width:1}.phase-line{stroke:#8c94a1;stroke-width:1;stroke-dasharray:3 5}.ramp-region{fill:#f4e9d2;opacity:.65}.off-region{fill:#e2e7ed;opacity:.55}.pause-region{fill:#e9effd;opacity:.52}.pause-line{stroke:#596a9b;stroke-width:1;stroke-dasharray:5 4}.pause-text{fill:#45588b;font-size:10px}.trace{fill:none;stroke-width:2;vector-effect:non-scaling-stroke}.measured-line{stroke-dasharray:6 4}.empty{fill:#596779;font-size:18px}
@media(max-width:740px){.plot-area{display:block}.legend{padding:0 10px;display:flex;flex-wrap:wrap;gap:4px 16px}.legend-item{margin-bottom:3px}}@media print{body{background:#fff}.panel{box-shadow:none;break-inside:avoid}.controls{display:none}.plot-area{min-height:250px}}
</style></head><body><main><header><h1>CPX400DP — experiment report</h1><div class="muted">Run started __DATE__ · Source: __SOURCE__</div></header>
<section class="panel"><h2>Run summary</h2><div class="stats">__OVERVIEW__</div><p class="hint">Timing statistic above is from logged setpoint rows; the terminal summary measures all phases. LOCAL is recorded as a sent command, not an independently confirmed mode change.</p></section>
__SECTIONS__
__DIAGNOSTICS__
</main><script id="plot-data" type="application/json">__DATA__</script>
<script>
(function(){'use strict';
const DATA=JSON.parse(document.getElementById('plot-data').textContent);
const DESC={vs:{label:'Voltage setpoint',axis:'v',color:'#196cb5'},vm:{label:'Measured voltage',axis:'v',color:'#13a9c1'},cs:{label:'Current limit',axis:'i',color:'#d42b31'},cm:{label:'Measured current',axis:'i',color:'#eb7e24'},p:{label:'Measured power',axis:'p',color:'#7545b9'}};
const NS='http://www.w3.org/2000/svg';
function svgEl(tag,attrs,text){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;return e;}
function add(svg,tag,attrs,text){const e=svgEl(tag,attrs,text);svg.appendChild(e);return e;}
function fmt(n){if(Math.abs(n)>=100)return n.toFixed(0);if(Math.abs(n)>=10)return n.toFixed(1);return n.toFixed(2).replace(/0+$/,'').replace(/\\.$/,'');}
function timeUnit(span){return span>=172800?[86400,'days']:span>=7200?[3600,'h']:span>=120?[60,'min']:[1,'s'];}
function timeLabel(seconds,span){
 const [factor,unit]=timeUnit(span);
 // Tick labels must not collapse to the same integer when zooming to
 // 50 ms near the end of a 1000-hour experiment.
 const grid=(span/factor)/5;
 const places=Math.min(6,Math.max(0,Math.ceil(-Math.log10(Math.max(grid,1e-12)))+1));
 return (seconds/factor).toFixed(places)+' '+unit;
}
const VIEWS=new WeakMap();
function render(panel){
 const view=VIEWS.get(panel);
 const svg=panel.querySelector('svg.plot'), legend=panel.querySelector('.legend');
 const d=DATA[panel.dataset.channel], chosen=[...panel.querySelectorAll('input[data-key]:checked')].map(x=>x.dataset.key);
 svg.replaceChildren();legend.replaceChildren();svg.setAttribute('viewBox','0 0 880 420');
 const W=880,H=420,L=75,R=140,T=28,B=55, PW=W-L-R,PH=H-T-B;
 const present=['v','i','p'].filter(axis=>chosen.some(k=>DESC[k].axis===axis));
 // Avoid spreading huge traces into Math.max() call arguments.
 let maxT=1;
 for(const key of Object.keys(DESC))for(const point of d[key])if(Number.isFinite(point[0])&&point[0]>maxT)maxT=point[0];
 for(const point of d.boundaries)if(point>maxT)maxT=point;
 for(const point of (d.pauses||[]))if(point[0]>maxT)maxT=point[0];
 for(const point of (d.ramp_regions||[]))if(point[1]>maxT)maxT=point[1];
 view.maxT=maxT;
 if(!view.range) view.range=[0,maxT];
 view.range[0]=Math.max(0,Math.min(view.range[0],maxT-.0001));
 view.range[1]=Math.max(view.range[0]+.0001,Math.min(maxT,view.range[1]));
 const xmin=view.range[0], xmax=view.range[1], span=xmax-xmin;
 const x=t=>L+PW*(t-xmin)/span;
 const xt=px=>xmin+(px-L)/PW*span;
 view.geometry={L,R,T,B,PW,PH,xt};
 const scales={};
 for(const axis of present){let hi=0;for(const key of chosen){if(DESC[key].axis!==axis)continue;for(const point of d[key])if(Number.isFinite(point[1])&&point[1]>hi)hi=point[1];}scales[axis]={lo:0,hi:hi>0?hi*1.07:1};}
 const y=(axis,v)=>T+PH*(scales[axis].hi-Math.max(0,v))/(scales[axis].hi-scales[axis].lo);
 add(svg,'rect',{x:L,y:T,width:PW,height:PH,fill:'#fff',stroke:'#cbd5df'});
 const clipId='clip-'+panel.dataset.channel;
 const defs=add(svg,'defs',{}); const cp=add(defs,'clipPath',{id:clipId});
 add(cp,'rect',{x:L,y:T,width:PW,height:PH});
 const tracesGroup=add(svg,'g',{'clip-path':'url(#'+clipId+')'});
 for(let j=0;j<=5;j++){const xx=L+PW*j/5;add(svg,'line',{x1:xx,x2:xx,y1:T,y2:T+PH,class:'grid-line'});add(svg,'text',{x:xx,y:T+PH+20,'text-anchor':'middle',class:'axis-label'},timeLabel(xmin+span*j/5,span));}
 add(svg,'text',{x:L+PW/2,y:H-12,'text-anchor':'middle',class:'axis-name'},'Elapsed time ('+timeUnit(span)[1]+')');
 // OFF bands indicate output-enable state, not instantaneous terminal voltage.
 for(const [a,b] of (d.off_regions||[])){if(b>a)add(tracesGroup,'rect',{x:x(a),y:T,width:x(b)-x(a),height:PH,class:'off-region'});}
 for(const [a,b,label] of (d.ramp_regions||[])){if(b>a)add(tracesGroup,'rect',{x:x(a),y:T,width:x(b)-x(a),height:PH,class:'ramp-region'});}
 // Assign annotation lanes with a minimum horizontal label separation.
 const placed=[];
 function annotate(t,label,preferred=0){if(t<xmin || t>xmax)return;const xx=x(t);const widths={Ramp:32,ON:18,OFF:20,Pause:34,Resume:44};const width=widths[label]||38;
   for(let lane=preferred;lane<5;lane++){if(placed.every(e=>e.lane!==lane||xx>=e.x+e.width+5||e.x>=xx+width+5)){placed.push({lane,x:xx,width});add(svg,'text',{x:Math.min(xx+3,L+PW-width-2),y:T+12+lane*13,class:'pause-text'},label);return;}}
 }
 for(const [a,b] of (d.ramp_regions||[])){if(b>a)annotate(a,'Ramp',0);}
 // Pause intervals use wall-clock times, so a stationary setpoint is
 // shown as a plateau while measured readings continue changing.
 let holdStart=null;
 for(const [pt,kind] of (d.pauses||[])){
   if(kind==='pause') holdStart=pt;
   if(kind==='resume' && holdStart!==null){
     add(tracesGroup,'rect',{x:x(holdStart),y:T,width:Math.max(0,x(pt)-x(holdStart)),height:PH,class:'pause-region'});
     holdStart=null;
   }
 }
 if(holdStart!==null)add(tracesGroup,'rect',{x:x(holdStart),y:T,width:Math.max(0,x(maxT)-x(holdStart)),height:PH,class:'pause-region'});
 for(const t of d.boundaries){if(t<xmin||t>xmax)continue;let xx=x(t);add(svg,'line',{x1:xx,x2:xx,y1:T,y2:T+PH,class:'phase-line'});}
 for(const [pt,state] of (d.transitions||[])){if(pt<xmin||pt>xmax)continue;const xx=x(pt);add(svg,'line',{x1:xx,x2:xx,y1:T,y2:T+PH,stroke:'#176a4a','stroke-dasharray':'5 3'});annotate(pt,state==='1'?'ON':'OFF',1);}
 for(const [pt,kind] of (d.pauses||[])){
   if(pt<xmin||pt>xmax)continue;const xx=x(pt);add(svg,'line',{x1:xx,x2:xx,y1:T,y2:T+PH,class:'pause-line'});
   annotate(pt,kind==='pause'?'Pause':'Resume',0);
 }
 const axisInfo={v:{at:L,anchor:'end',offset:-10,name:'Voltage (V)',color:'#196cb5'},i:{at:L+PW,anchor:'start',offset:10,name:'Current (A)',color:'#d42b31'},p:{at:L+PW+74,anchor:'start',offset:8,name:'Power (W)',color:'#7545b9'}};
 for(const axis of present){const info=axisInfo[axis],s=scales[axis];for(let j=0;j<=5;j++){const yy=T+PH*j/5;add(svg,'text',{x:info.at+info.offset,y:yy+4,'text-anchor':info.anchor,class:'axis-label',fill:info.color},fmt(s.hi-(s.hi-s.lo)*j/5));}add(svg,'text',{x:info.at+info.offset,y:14,'text-anchor':info.anchor,class:'axis-name',fill:info.color},info.name);}
 for(const key of chosen){const a=d[key];if(!a.length)continue;const def=DESC[key],valid=a.filter(p=>Number.isFinite(p[0])&&Number.isFinite(p[1]));if(!valid.length)continue;
 // Select the viewport with one adjacent sample for continuous curves.
 // Bin by pixel, keeping first/last/min/max so narrow excursions survive.
 const visible=[];
 for(let i=0;i<valid.length;i++){
   if(valid[i][0]>=xmin&&valid[i][0]<=xmax)visible.push(valid[i]);
   else if(valid[i][0]<xmin && (i===valid.length-1||valid[i+1][0]>=xmin))visible.push(valid[i]);
   else if(valid[i][0]>xmax && (i===0||valid[i-1][0]<=xmax)){visible.push(valid[i]);break;}
 }
 const bins=new Map();
 for(const p of visible){
   const k=Math.floor(x(p[0]));
   let b=bins.get(k);
   if(!b){bins.set(k,b=[p,p,p,p]);continue;}
   b[3]=p;
   if(p[1]<b[1][1])b[1]=p;
   if(p[1]>b[2][1])b[2]=p;
 }
 const sampled=[];
 for(const b of bins.values()){
   const unique=[...new Set(b)];unique.sort((a,b)=>a[0]-b[0]);
   for(const p of unique)if(sampled[sampled.length-1]!==p)sampled.push(p);
 }
 // Step-profile voltage/current limits render with vertical transitions;
 // initial/final ramps retain the ordinary linear segments.
 const stepped=(d.mode==='step' && (key==='vs'||key==='cs'));
 const boundaries=d.boundaries||[];
 const profileBegin=boundaries.length?boundaries[0]:0;
 const profileEnd=boundaries.length>1?boundaries[1]:Infinity;
 const path=sampled.map((p,i)=>{
   const pt=x(p[0]).toFixed(2)+' '+y(def.axis,p[1]).toFixed(2);
   if(!i)return 'M'+pt;
   const prev=sampled[i-1];
   if(stepped && p[0]>=profileBegin && p[0]<profileEnd &&
      prev[0]>=profileBegin && prev[0]<profileEnd && p[1]!==prev[1]){
     return 'L'+x(p[0]).toFixed(2)+' '+y(def.axis,prev[1]).toFixed(2)+'L'+pt;
   }
   return 'L'+pt;
 }).join(' ');
 add(tracesGroup,'path',{d:path,stroke:def.color,class:'trace'+(['vm','cm','p'].includes(key)?' measured-line':'')});
 // Never draw a negative ordinate: instead mark each negative sample at y=0.
 const negative=valid.filter(p=>p[1]<0);for(const point of negative.filter((_,i)=>i%Math.max(1,Math.ceil(negative.length/150))===0)){add(svg,'circle',{cx:x(point[0]),cy:y(def.axis,0),r:3,fill:def.color,stroke:'#fff','stroke-width':1});}
 const item=document.createElement('div');item.className='legend-item';const line=document.createElement('span');line.className='legend-line'+(['vm','cm','p'].includes(key)?' measured':'');line.style.borderColor=def.color;item.appendChild(line);item.appendChild(document.createTextNode(def.label));legend.appendChild(item);
 }
 // Cursor markings refer to measured voltage, not the PSU command curve.
 function nearVoltage(t){const arr=d.vm||[];if(!arr.length)return null;
   let best=arr[0];for(const pt of arr){if(Math.abs(pt[0]-t)<Math.abs(best[0]-t))best=pt;}return best;}
 const renderCursor=(t,label)=>{
   if(t===null || t<xmin || t>xmax)return;
   const xx=x(t);add(svg,'line',{x1:xx,x2:xx,y1:T,y2:T+PH,stroke:'#7545b9','stroke-width':1.5,'stroke-dasharray':'5 3'});
   add(svg,'text',{x:Math.min(xx+5,L+PW-52),y:T+PH-8,fill:'#7545b9','font-size':11},label+' '+timeLabel(t,span));
 };
 renderCursor(view.cursors[0],'A');renderCursor(view.cursors[1],'B');
 const cv=panel.querySelector('.cursor-values');
 if(view.cursors[0]!==null && view.cursors[1]!==null){
   const a=nearVoltage(view.cursors[0]),b=nearVoltage(view.cursors[1]);
   cv.textContent='A '+timeLabel(view.cursors[0],span)+' · B '+timeLabel(view.cursors[1],span)+' · Δt '+timeLabel(Math.abs(view.cursors[1]-view.cursors[0]),span)+
     (a&&b?' · measured V(A) '+fmt(a[1])+' V · V(B) '+fmt(b[1])+' V · ΔV '+fmt(b[1]-a[1])+' V':' · no voltage samples');
 }else cv.textContent=view.cursorMode?'Click chart to place cursor '+(view.cursors[0]===null?'A':'B')+' (second click completes pair)':'Wheel to zoom · drag to pan · cursors for Δt/ΔV';
 if(!chosen.length)add(svg,'text',{x:L+PW/2,y:T+PH/2,'text-anchor':'middle',class:'empty'},'Select one or more curves above');
}
document.querySelectorAll('.channel').forEach(panel=>{
 const view={range:null,maxT:1,cursors:[null,null],cursorMode:false,geometry:null};VIEWS.set(panel,view);
 const svg=panel.querySelector('svg.plot');
 const plotX=ev=>{const rect=svg.getBoundingClientRect();return (ev.clientX-rect.left)*880/rect.width;};
 const within=px=>view.geometry&&px>=view.geometry.L&&px<=view.geometry.L+view.geometry.PW;
 panel.querySelector('.reset-zoom').addEventListener('click',()=>{view.range=[0,view.maxT];view.cursors=[null,null];render(panel);});
 const toggle=panel.querySelector('.cursor-toggle');toggle.addEventListener('click',()=>{
   view.cursorMode=!view.cursorMode;toggle.textContent='Cursors: '+(view.cursorMode?'ON':'OFF');
   toggle.setAttribute('aria-pressed',String(view.cursorMode));render(panel);});
 panel.querySelectorAll('input[data-key]').forEach(input=>input.addEventListener('change',()=>render(panel)));
 svg.addEventListener('wheel',ev=>{const px=plotX(ev);if(!within(px))return;ev.preventDefault();
   const [a,b]=view.range,old=b-a,factor=ev.deltaY<0?.8:1.25,span=Math.min(view.maxT,Math.max(.02,old*factor));
   const anchor=(px-view.geometry.L)/view.geometry.PW,center=a+anchor*old;
   let low=center-anchor*span;low=Math.max(0,Math.min(view.maxT-span,low));view.range=[low,low+span];render(panel);
 },{passive:false});
 let drag=null;
 svg.addEventListener('pointerdown',ev=>{const px=plotX(ev);if(!within(px))return;
   if(view.cursorMode)return;
   drag={x:px,range:[...view.range]};svg.setPointerCapture(ev.pointerId);});
 svg.addEventListener('pointermove',ev=>{if(!drag)return;const px=plotX(ev),span=drag.range[1]-drag.range[0];
   let low=drag.range[0]-(px-drag.x)/view.geometry.PW*span;
   low=Math.max(0,Math.min(view.maxT-span,low));view.range=[low,low+span];render(panel);});
 svg.addEventListener('pointerup',()=>{drag=null;});svg.addEventListener('pointercancel',()=>{drag=null;});
 svg.addEventListener('click',ev=>{if(!view.cursorMode)return;const px=plotX(ev);if(!within(px))return;
   const t=Math.max(0,Math.min(view.maxT,view.geometry.xt(px)));
   if(view.cursors[0]===null || view.cursors[1]!==null)view.cursors=[t,null];else view.cursors[1]=t;
   render(panel);});
 render(panel);
});
})();
</script></body></html>'''
    substitutions = {'__DATE__': html.escape(date_str),'__SOURCE__':html.escape(str(profile.name if profile else log_file.name)), '__OVERVIEW__':overview,'__SECTIONS__':''.join(sections),'__DIAGNOSTICS__':diagnostic_html,'__DATA__':payload}
    for key, value in substitutions.items():
        page = page.replace(key, value)
    prefix, sep, suffix = log_file.stem.partition('_measurements')
    out = log_file.with_name(prefix + '_report' + suffix + '.html' if sep else log_file.stem + '_report.html')
    out.write_text(page, encoding='utf-8')
    return out


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('measurements',type=Path)
    parser.add_argument('--layout',choices=['separate','combined','power'],default='separate',help='Initial checkbox selection for compatibility')
    opts=parser.parse_args()
    print(generate(opts.measurements,opts.layout))
