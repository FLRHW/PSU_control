"""Bounded-memory, offline report for large CPX400DP measurement CSV files.

For large logs only. The original self-contained report remains unchanged
for small logs. Detail is split into local JavaScript chunks so file:// viewers
can load narrow time windows without HTTP or an external JavaScript library.
Keep the generated *_report_data directory alongside the HTML file.
"""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import csv
import html
import json
import math
import shutil

SERIES = ("vs", "cs", "vm", "cm", "p")
FIELDS = ("set_voltage_v", "current_limit_a", "measured_voltage_v",
          "measured_current_a")
COMMAND_EVENTS = {"initial_ramp", "setpoint", "final_ramp",
                  "pause_hold", "manual_setpoint"}
MAX_CHUNK_ROWS = 4096
OVERVIEW_BINS = 1200
MAX_ANNOTATIONS = 10000


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _points(row):
    t = _number(row.get("elapsed_s"))
    if t is None:
        return []
    kind = row.get("event")
    result = []
    if kind in COMMAND_EVENTS:
        for key, field in (("vs", "set_voltage_v"),
                           ("cs", "current_limit_a")):
            v = _number(row.get(field))
            if v is not None:
                result.append((key, [t, v]))
    if kind == "readback":
        v = _number(row.get("measured_voltage_v"))
        i = _number(row.get("measured_current_a"))
        if v is not None:
            result.append(("vm", [t, v]))
        if i is not None:
            result.append(("cm", [t, i]))
        if v is not None and i is not None:
            p = v * i
            if math.isfinite(p):
                result.append(("p", [t, 0.0 if abs(p) < .0005 else p]))
    return result


def _empty_channel():
    return {"energy": 0.0, "pmax": None, "psum": 0.0, "pcount": 0,
            "last_power": None, "initial_ramp": None, "final_ramp": None,
            "first_profile": None, "last_final_ramp": None,
            "snapshot_enable": None, "transitions": [],
            "pauses": [], "physical": None, "verified": False}


def _set_min(info, name, t):
    if t is not None and (info[name] is None or t < info[name]):
        info[name] = t


def _inspect(log_file):
    """First CSV pass: counters, annotations, statistics, and max time only."""
    infos = {1: _empty_channel(), 2: _empty_channel()}
    count = 0
    events = defaultdict(int)
    max_t = 0.0
    tstamp = None
    mode = "linear"
    local_sent = False
    max_lateness = None
    restoration_start = None
    diagnostic_rows = []
    overflow = 0
    with log_file.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            count += 1
            event = row.get("event", "")
            events[event] += 1
            if tstamp is None and row.get("utc_time"):
                tstamp = row["utc_time"]
            if event == "config" and "mode=step" in row.get("note", ""):
                mode = "step"
            if event == "local_sent":
                local_sent = True
            t = _number(row.get("elapsed_s"))
            if t is not None:
                max_t = max(max_t, t)
            late = _number(row.get("lateness_ms"))
            if late is not None:
                max_lateness = late if max_lateness is None else max(late, max_lateness)
            if event in ("final_state_sent", "final_state_verified",
                         "final_state_error"):
                if t is not None:
                    restoration_start = (t if restoration_start is None
                                         else min(t, restoration_start))
            if event in ("diagnostic", "diagnostic_error"):
                if len(diagnostic_rows) < 100:
                    diagnostic_rows.append([event, row.get("note", "")[:300]])
                else:
                    overflow += 1
            chs = row.get("channel", "").strip()
            if chs not in ("1", "2"):
                if event in ("pause", "resume") and t is not None:
                    for channel in infos.values():
                        if len(channel["pauses"]) < MAX_ANNOTATIONS:
                            channel["pauses"].append([t, event])
                continue
            ch = infos[int(chs)]
            if event == "snapshot" and ch["snapshot_enable"] is None:
                ch["snapshot_enable"] = row.get("requested_enable")
            if event == "output_transition" and t is not None:
                if len(ch["transitions"]) < MAX_ANNOTATIONS:
                    ch["transitions"].append([t, row.get("requested_enable")])
            if event in ("pause", "resume") and t is not None:
                if len(ch["pauses"]) < MAX_ANNOTATIONS:
                    ch["pauses"].append([t, event])
            if event == "initial_ramp":
                _set_min(ch, "initial_ramp", t)
            if event == "final_ramp":
                _set_min(ch, "final_ramp", t)
                if t is not None:
                    ch["last_final_ramp"] = max(t, ch["last_final_ramp"] or 0)
            if event == "setpoint":
                _set_min(ch, "first_profile", t)
            if event == "final_state_verified":
                ch["verified"] = True
            if event in ("physical_output_checked",
                         "physical_output_warning", "physical_output_skipped"):
                ch["physical"] = event
            if event == "readback":
                v = _number(row.get("measured_voltage_v"))
                i = _number(row.get("measured_current_a"))
                if t is not None and v is not None and i is not None:
                    p = v * i
                    if math.isfinite(p):
                        ch["pmax"] = p if ch["pmax"] is None else max(ch["pmax"], p)
                        ch["psum"] += p
                        ch["pcount"] += 1
                        last = ch["last_power"]
                        if last is not None:
                            dt = t - last[0]
                            if dt >= 0:
                                ch["energy"] += dt * (last[1] + p) / 2
                        ch["last_power"] = (t, p)
    if count == 0:
        raise ValueError("Measurement log contains no events")
    seen = []
    for ch in (1, 2):
        # Channel data can be present without a valid plotted sample.
        # Inspect a second pass to enumerate channels exactly, not just metadata.
        if infos[ch]["verified"] or infos[ch]["pcount"] or \
           infos[ch]["initial_ramp"] is not None or \
           infos[ch]["first_profile"] is not None or \
           infos[ch]["final_ramp"] is not None or \
           infos[ch]["transitions"] or infos[ch]["physical"] or \
           infos[ch]["snapshot_enable"] is not None:
            seen.append(ch)
    # A row such as readback_error can establish a channel without samples;
    # the second pass determines available traces, if any.
    return locals()


def _overview_add(bins, key, point, span):
    t, value = point
    index = max(0, min(OVERVIEW_BINS - 1,
                       int(t / span * OVERVIEW_BINS) if span else 0))
    bucket = bins[key].setdefault(index, [point, point, point, point])
    bucket[1] = point
    if value < bucket[2][1]:
        bucket[2] = point
    if value > bucket[3][1]:
        bucket[3] = point


def _flush_chunk(folder, ch, counter, data, start, end, manifest):
    if start is None:
        return
    chunk_id = f"c{ch}_{counter:06d}"
    filename = chunk_id + ".js"
    packet = {"id": chunk_id, "ch": str(ch), "series": data}
    payload = json.dumps(packet, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    (folder / filename).write_text("window.__reportChunk(" + payload + ");\n", encoding="utf-8")
    manifest[str(ch)].append({"id": chunk_id, "url": folder.name + "/" + filename,
                              "start": start, "end": end})


def _make_data(log_file, folder, span):
    """Second CSV pass: write bounded point chunks and fixed-size extrema overview."""
    overview_bins = {str(ch): {key: {} for key in SERIES} for ch in (1, 2)}
    manifest = {"1": [], "2": []}
    counts = {1: 0, 2: 0}
    records = {ch: {key: [] for key in SERIES} for ch in (1, 2)}
    starts = {1: None, 2: None}
    ends = {1: None, 2: None}
    present = set()
    with log_file.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            label = row.get("channel", "").strip()
            if label not in ("1", "2"):
                continue
            ch = int(label)
            present.add(ch)
            points = _points(row)
            if not points:
                continue
            t = points[0][1][0]
            if counts[ch] >= MAX_CHUNK_ROWS:
                _flush_chunk(folder, ch, len(manifest[label]), records[ch],
                             starts[ch], ends[ch], manifest)
                records[ch] = {key: [] for key in SERIES}
                starts[ch] = None
                ends[ch] = None
                counts[ch] = 0
            counts[ch] += 1
            starts[ch] = t if starts[ch] is None else min(starts[ch], t)
            ends[ch] = t if ends[ch] is None else max(ends[ch], t)
            for key, point in points:
                records[ch][key].append(point)
                _overview_add(overview_bins[label], key, point, span)
    for ch in (1, 2):
        if counts[ch]:
            _flush_chunk(folder, ch, len(manifest[str(ch)]), records[ch],
                         starts[ch], ends[ch], manifest)
    if not present:
        raise ValueError("Measurement log contains no channel data")
    overview = {}
    for ch in (1, 2):
        traces = {}
        for key, bins in overview_bins[str(ch)].items():
            pts = []
            for bucket in sorted(bins):
                points = sorted({tuple(p) for p in bins[bucket]}, key=lambda p: p[0])
                pts.extend([list(p) for p in points])
            traces[key] = pts
        overview[str(ch)] = traces
    return present, manifest, overview


def _details(info, end_time, restoration_start):
    transitions = sorted(info["transitions"], key=lambda p: p[0])
    off = []
    previous = info["snapshot_enable"]
    begin = 0.0
    for t, value in transitions + [[end_time, None]]:
        if str(previous).strip() in ("0", "OFF", "False") and t > begin:
            off.append([begin, t])
        begin = t
        if value is not None:
            previous = value
    first, profile, final, last = (info[x] for x in
                                   ("initial_ramp", "first_profile",
                                    "final_ramp", "last_final_ramp"))
    boundaries = [v for v in (profile, final) if v is not None and v > 1e-6]
    ramps = []
    if first is not None and profile is not None and profile > first:
        ramps.append([first, profile, "Ramp"])
    if final is not None:
        stop = restoration_start if restoration_start is not None else last
        if stop is not None and stop > final:
            ramps.append([final, stop, "Ramp"])
    return {"transitions": transitions, "pauses": info["pauses"],
            "off_regions": off, "ramp_regions": ramps, "boundaries": boundaries}


def generate(log_file, layout="separate", profile=None):
    if layout not in ("separate", "combined", "power"):
        raise ValueError("Unsupported initial report layout")
    log_file = Path(log_file)
    first = _inspect(log_file)
    filename = log_file.stem.replace("_measurements", "_report") + ".html"
    report = log_file.with_name(filename)
    folder = report.with_name(report.stem + "_data")
    # Build in a temporary sibling directory, then atomically replace when
    # complete so a failed generation does not corrupt the previous report.
    temp = folder.with_name(folder.name + "_building")
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True)
    try:
        present, manifest, overview = _make_data(log_file, temp, first["max_t"])
        # URLs must refer to the final folder, not to the transient path.
        for entries in manifest.values():
            for entry in entries:
                entry["url"] = folder.name + "/" + entry["id"] + ".js"
        channels = sorted(present)
        if first["tstamp"]:
            try:
                stamp = datetime.fromisoformat(first["tstamp"])
                date = stamp.strftime("%d %B %Y, %H:%M:%S %Z").strip()
            except ValueError:
                date = first["tstamp"]
        else:
            date = "Unknown"
        statuses = first["events"]
        if statuses["output_fault_abort"]:
            status = "ABORTED (OUTPUT FAULT)"
        elif statuses["interrupted"]:
            status = "INTERRUPTED"
        elif all(first["infos"][ch]["verified"] for ch in channels):
            status = "COMPLETED"
        else:
            status = "NOT VERIFIED"
        cards = [("Channels", ", ".join(map(str, channels))),
                 ("Run status", status),
                 ("Successful readbacks", statuses["readback"]),
                 ("Failed readbacks", statuses["readback_error"]),
                 ("Maximum setpoint lateness", f'{first["max_lateness"]:.3f} ms' if first["max_lateness"] is not None else "Not recorded"),
                 ("LOCAL command", "SENT" if first["local_sent"] else "NOT CONFIRMED"),
                 ("Output-health warnings", statuses["output_health_warning"]),
                 ("Unexplained high readbacks", statuses["implausible_high_readback"]),
                 ("Expected-settling readbacks", statuses["settling_readback"]),
                 ("Experiment health", "FAILED" if statuses["output_fault_abort"] else "WARNING" if statuses["output_health_warning"] or statuses["implausible_high_readback"] else "OK")]
        meta = {}
        for ch in channels:
            info = first["infos"][ch]
            physical = info["physical"]
            cards.extend([
                (f"Channel {ch} sampled physical output",
                 "MATCHED" if physical == "physical_output_checked" else
                 "WARNING" if physical == "physical_output_warning" else
                 "N/A (OFF or near-zero target)" if physical == "physical_output_skipped" else
                 "NOT CHECKED"),
                (f"Channel {ch} final state", "VERIFIED" if info["verified"] else "NOT VERIFIED"),
            ])
            meta[str(ch)] = _details(info, first["max_t"], first["restoration_start"])
            meta[str(ch)]["mode"] = first["mode"]
            meta[str(ch)]["max_t"] = first["max_t"]
            meta[str(ch)]["stats"] = {
                "peak": max(0, info["pmax"]) if info["pmax"] is not None else None,
                "mean": info["psum"] / info["pcount"] if info["pcount"] else None,
                "energy": info["energy"] if info["pcount"] else None,
            }
        stats_html = "".join('<div class="stat"><small>' + html.escape(str(k)) +
                             "</small><b>" + html.escape(str(v)) + "</b></div>"
                             for k, v in cards)
        selected = ("p",) if layout == "power" else ("vs", "vm", "cs", "cm", "p")
        labels = {"vs": "Voltage setpoint", "vm": "Measured voltage",
                  "cs": "Current limit", "cm": "Measured current",
                  "p": "Measured power"}
        section_parts = []
        for ch in channels:
            choices = "".join('<label><input type="checkbox" data-series="' + key +
                              '"' + (" checked" if key in selected else "") + '>' +
                              labels[key] + "</label>" for key in ("vs", "vm", "cs", "cm", "p"))
            st = meta[str(ch)]["stats"]
            fmt = lambda value, unit: "—" if value is None else f"{value:.2f} {unit}"
            section_parts.append(
                '<section class="panel channel" data-channel="' + str(ch) + '">' +
                f"<h2>Channel {ch} — selectable traces</h2>" +
                '<div class="controls">' + choices + '</div>' +
                '<div class="toolbar"><button type="button" class="reset">Reset zoom</button>' +
                '<button type="button" class="cursor">Cursors: OFF</button>' +
                '<span class="hint reading">Wheel to zoom · drag to pan · cursors for Δt/ΔV</span></div>' +
                '<svg class="plot" viewBox="0 0 880 420" aria-label="Waveform plot"></svg>' +
                '<p class="hint detail-state">Overview: extrema-preserving summary. Zoom in for full-resolution local chunks.</p>' +
                '<div class="stats"><div class="stat">Peak sampled power: ' + fmt(st["peak"], "W") +
                '</div><div class="stat">Mean sampled power: ' + fmt(st["mean"], "W") +
                '</div><div class="stat">Estimated energy: ' + fmt(st["energy"], "J") + '</div></div>' +
                '<p class="hint">Power is calculated from measured voltage and current; energy integrates logged samples. ' +
                'Grey areas are commanded OFF intervals, not a physical zero-voltage guarantee. ' +
                'Blue indicates pauses, gold initial/final ramps. No shared PSU/scope timestamp is implied.</p></section>')
        payload = json.dumps({"overview": overview, "manifest": manifest, "meta": meta},
                             separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
        page = PAGE.replace("__TITLE__", html.escape(str(profile.name if profile else log_file.name)))
        page = page.replace("__DATE__", html.escape(date))
        page = page.replace("__CARDS__", stats_html)
        page = page.replace("__CHANNELS__", "".join(section_parts))
        page = page.replace("__PAYLOAD__", payload)
        page = page.replace("__DETAIL_COUNT__", str(sum(len(v) for v in manifest.values())))
        page = page.replace("__DIAGNOSTICS__", html.escape("; ".join(
            kind + ": " + note for kind, note in first["diagnostic_rows"])) if
            first["diagnostic_rows"] else "Not collected in this run")
        report_temp = report.with_suffix(".html.tmp")
        report_temp.write_text(page, encoding="utf-8")
        if folder.exists():
            shutil.rmtree(folder)
        temp.rename(folder)
        report_temp.replace(report)
        return report
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CPX400DP experiment report</title>
<style>
*{box-sizing:border-box}body{font:15px system-ui,Segoe UI,sans-serif;background:#f3f5f9;color:#18243a;margin:0}
main{max-width:1180px;margin:25px auto;padding:0 16px}h1{margin:0;font-size:27px}
h2{font-size:20px}.panel{background:white;border:1px solid #dde3ed;border-radius:11px;padding:20px;margin:17px 0}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.stat{border:1px solid #dce3ed;border-radius:8px;padding:10px}.stat b{display:block;font-size:19px}
.stat small,.hint{font-size:13px;color:#536173}.controls,.toolbar{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}
.controls label{display:flex;gap:6px;align-items:center}button{padding:7px 11px;border:1px solid #ccd5df;background:#f5f8fc;border-radius:6px;cursor:pointer}
.plot{display:block;width:100%;height:auto;touch-action:none}.trace{fill:none;stroke-width:1.6;vector-effect:non-scaling-stroke}
.axis{fill:#536173;font-size:12px}.grid{stroke:#e3e8f0}.region-off{fill:#e2e7ed;opacity:.65}
.region-ramp{fill:#f4e9d2;opacity:.7}.region-pause{fill:#e6ecff;opacity:.65}
</style></head><body><main>
<header><h1>CPX400DP — experiment report</h1>
<p class="hint">Run started __DATE__ · Source: __TITLE__</p></header>
<section class="panel"><h2>Run summary</h2><div class="stats">__CARDS__</div>
<p class="hint">LOCAL is logged as a command sent, not an independently confirmed mode change.
This large-recording report uses local detail chunks (__DETAIL_COUNT__ files).
Keep this HTML and its matching _report_data directory together. No internet or server required.</p></section>
__CHANNELS__
<section class="panel"><h2>PSU diagnostics (first 100 logged events)</h2>
<p class="hint">Some diagnostic registers clear on reading. Raw notes only.</p>
<p style="overflow-wrap:anywhere">__DIAGNOSTICS__</p></section>
</main><script id="plot-data" type="application/json">__PAYLOAD__</script>
<script>
(function(){'use strict';
const DATA=JSON.parse(document.getElementById('plot-data').textContent);
const COLORS={vs:'#196cb5',vm:'#13a9c1',cs:'#d42b31',cm:'#eb7e24',p:'#7545b9'};
const AXIS={vs:'V',vm:'V',cs:'A',cm:'A',p:'W'};
const NS='http://www.w3.org/2000/svg';
const cache=new Map(),pending=new Set(),MAX_CACHE=6;
window.__reportChunk=function(packet){
  if(!packet || !packet.id || !packet.series)return;
  cache.delete(packet.id);cache.set(packet.id,packet.series);
  while(cache.size>MAX_CACHE)cache.delete(cache.keys().next().value);
};
function el(tag,attrs,text){
  const e=document.createElementNS(NS,tag);
  for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,String(v));
  if(text!==undefined)e.textContent=text;
  return e;
}
function add(svg,tag,attrs,text){const e=el(tag,attrs,text);svg.append(e);return e;}
function unit(span){return span>=172800?[86400,'days']:span>=7200?[3600,'h']:span>=120?[60,'min']:[1,'s'];}
function tick(t,span){const [div,name]=unit(span);let a=span/div/5;let places=Math.min(7,Math.max(0,Math.ceil(-Math.log10(Math.max(a,1e-12)))+1));return (t/div).toFixed(places)+' '+name;}
const PANELS=new Map();
function windowData(ch,start,end){
  const overview=DATA.overview[ch],manifest=DATA.manifest[ch];
  const items=manifest.filter(c=>c.end>=start&&c.start<=end);
  const full=(items.length>0 && items.length<=3 && (end-start)<DATA.meta[ch].max_t*.15);
  if(!full)return {series:overview,quality:'Overview: extrema-preserving summary. Zoom in for raw samples.'};
  const missing=items.filter(c=>!cache.has(c.id));
  for(const item of missing){
    if(pending.has(item.id))continue;
    pending.add(item.id);
    const script=document.createElement('script');
    script.src=item.url;
    script.onload=()=>{pending.delete(item.id);script.remove();const view=PANELS.get(ch);if(view)render(view);};
    script.onerror=()=>{pending.delete(item.id);script.remove();const view=PANELS.get(ch);if(view){view.status.textContent='Unable to load '+item.url+'. Keep report data folder beside the HTML.';}};
    document.body.append(script);
  }
  if(missing.length)return {series:overview,quality:'Loading detailed samples from local files…'};
  const series={vs:[],vm:[],cs:[],cm:[],p:[]};
  for(const item of items){
    const chunk=cache.get(item.id);
    if(!chunk)continue;
    for(const key of Object.keys(series))series[key].push(...(chunk[key]||[]));
  }
  return {series,quality:'Full resolution: loaded local detail chunks.'};
}
function drawLine(svg,pts,color,axis,x,y,start,end){
  const valid=pts.filter(p=>Number.isFinite(p[0])&&Number.isFinite(p[1]));
  if(!valid.length)return;
  const selected=[];
  for(let i=0;i<valid.length;i++){
    const p=valid[i];
    if(p[0]>=start&&p[0]<=end)selected.push(p);
    else if(p[0]<start&&(i===valid.length-1||valid[i+1][0]>=start))selected.push(p);
    else if(p[0]>end&&(i===0||valid[i-1][0]<=end)){selected.push(p);break;}
  }
  const bins=new Map();
  for(const p of selected){
    const k=Math.floor(x(p[0]));
    let b=bins.get(k);
    if(!b)bins.set(k,b=[p,p,p,p]);
    else{b[1]=p;if(p[1]<b[2][1])b[2]=p;if(p[1]>b[3][1])b[3]=p;}
  }
  const reduced=[];
  for(const b of bins.values())for(const p of [...new Set(b)].sort((a,b)=>a[0]-b[0]))
    if(reduced[reduced.length-1]!==p)reduced.push(p);
  if(!reduced.length)return;
  const d=reduced.map((p,i)=>(i?'L':'M')+x(p[0]).toFixed(2)+' '+y(axis,p[1]).toFixed(2)).join(' ');
  add(svg,'path',{d,stroke:color,class:'trace', 'stroke-dasharray':(axis==='V'||axis==='A')?'':'none'});
}
function render(view){
  const ch=view.ch,meta=DATA.meta[ch],svg=view.svg;
  const maxT=Math.max(meta.max_t,.0001);
  if(!view.range)view.range=[0,maxT];
  let [start,end]=view.range;
  start=Math.max(0,Math.min(start,maxT-.00001));
  end=Math.max(start+.00001,Math.min(maxT,end));view.range=[start,end];
  const span=end-start,L=75,R=125,T=25,B=50,W=880,H=420,PW=W-L-R,PH=H-T-B;
  const x=t=>L+(t-start)/span*PW;
  const got=windowData(ch,start,end),selected=[...view.panel.querySelectorAll('input[data-series]:checked')].map(e=>e.dataset.series);
  view.current=got.series;view.status.textContent=got.quality;
  const ranges={V:1,A:1,W:1};
  for(const key of selected)for(const p of got.series[key]){
    if(p[0]>=start&&p[0]<=end&&Number.isFinite(p[1])&&p[1]>ranges[AXIS[key]])ranges[AXIS[key]]=p[1];
  }
  for(const key of Object.keys(ranges))ranges[key]*=1.07;
  const y=(axis,v)=>T+PH*(1-Math.max(0,v)/ranges[axis]);
  svg.replaceChildren();
  add(svg,'rect',{x:L,y:T,width:PW,height:PH,fill:'white',stroke:'#cdd6e1'});
  const defs=add(svg,'defs',{}),clip=add(defs,'clipPath',{id:'clip'+ch});
  add(clip,'rect',{x:L,y:T,width:PW,height:PH});
  const traces=add(svg,'g',{'clip-path':'url(#clip'+ch+')'});
  for(let k=0;k<=5;k++){
    const px=L+k*PW/5;add(svg,'line',{x1:px,x2:px,y1:T,y2:T+PH,class:'grid'});
    add(svg,'text',{x:px,y:H-20,class:'axis','text-anchor':'middle'},tick(start+span*k/5,span));
  }
  for(const [a,b] of meta.off_regions)add(traces,'rect',{x:x(a),y:T,width:Math.max(0,x(b)-x(a)),height:PH,class:'region-off'});
  for(const [a,b] of meta.ramp_regions)add(traces,'rect',{x:x(a),y:T,width:Math.max(0,x(b)-x(a)),height:PH,class:'region-ramp'});
  let paused=null;
  for(const [t,kind] of meta.pauses){
    if(kind==='pause')paused=t;
    else if(kind==='resume'&&paused!==null){add(traces,'rect',{x:x(paused),y:T,width:Math.max(0,x(t)-x(paused)),height:PH,class:'region-pause'});paused=null;}
  }
  if(paused!==null)add(traces,'rect',{x:x(paused),y:T,width:Math.max(0,x(meta.max_t)-x(paused)),height:PH,class:'region-pause'});
  for(const t of meta.boundaries)if(t>=start&&t<=end)add(svg,'line',{x1:x(t),x2:x(t),y1:T,y2:T+PH,stroke:'#8c94a1','stroke-dasharray':'4 4'});
  for(const [t,state] of meta.transitions)if(t>=start&&t<=end)add(svg,'line',{x1:x(t),x2:x(t),y1:T,y2:T+PH,stroke:'#176a4a','stroke-dasharray':'5 3'});
  for(const [t] of meta.pauses)if(t>=start&&t<=end)add(svg,'line',{x1:x(t),x2:x(t),y1:T,y2:T+PH,stroke:'#596a9b','stroke-dasharray':'5 3'});
  for(const key of selected)drawLine(traces,got.series[key],COLORS[key],AXIS[key],x,y,start,end);
  const axes=[['V',L-10],['A',L+PW+9],['W',L+PW+65]];
  for(const [axis,at] of axes){
    if(!selected.some(k=>AXIS[k]===axis))continue;
    add(svg,'text',{x:at,y:14,class:'axis'},axis==='V'?'Voltage (V)':axis==='A'?'Current (A)':'Power (W)');
    for(let k=0;k<=5;k++)add(svg,'text',{x:at,y:T+PH*k/5+4,class:'axis'},(ranges[axis]*(1-k/5)).toFixed(2));
  }
  const near=t=>{
    const values=got.series.vm||[];
    let best=null;
    for(const p of values)if(!best||Math.abs(p[0]-t)<Math.abs(best[0]-t))best=p;
    return best;
  };
  for(let n=0;n<2;n++){
    const t=view.cursors[n];if(t===null||t<start||t>end)continue;
    add(svg,'line',{x1:x(t),x2:x(t),y1:T,y2:T+PH,stroke:'#7545b9','stroke-dasharray':'5 3'});
  }
  const [a,b]=view.cursors;
  if(a!==null&&b!==null){
    const va=near(a),vb=near(b);
    view.reading.textContent='Δt '+tick(Math.abs(b-a),span)+(va&&vb?' · V(A) '+va[1].toFixed(3)+' V · V(B) '+vb[1].toFixed(3)+' V · ΔV '+(vb[1]-va[1]).toFixed(3)+' V':'');
  }else view.reading.textContent=view.cursorMode?'Click twice on the chart to place A and B':'Wheel to zoom · drag to pan · cursors for Δt/ΔV';
  view.geom={L,PW,span,start, maxT};
}
document.querySelectorAll('.channel').forEach(panel=>{
  const ch=panel.dataset.channel,svg=panel.querySelector('svg.plot');
  const view={ch,panel,svg,status:panel.querySelector('.detail-state'),reading:panel.querySelector('.reading'),
              range:null,cursors:[null,null],cursorMode:false,geom:null};
  PANELS.set(ch,view);
  function mouseX(ev){const rect=svg.getBoundingClientRect();return (ev.clientX-rect.left)*880/rect.width;}
  panel.querySelector('.reset').onclick=()=>{view.range=null;view.cursors=[null,null];render(view);};
  panel.querySelector('.cursor').onclick=ev=>{view.cursorMode=!view.cursorMode;ev.target.textContent='Cursors: '+(view.cursorMode?'ON':'OFF');render(view);};
  panel.querySelectorAll('input[data-series]').forEach(c=>c.onchange=()=>render(view));
  svg.addEventListener('wheel',ev=>{
    const px=mouseX(ev),g=view.geom;if(px<g.L||px>g.L+g.PW)return;
    ev.preventDefault();const width=Math.min(g.maxT,Math.max(.00005,g.span*(ev.deltaY<0?.8:1.25)));
    const fraction=(px-g.L)/g.PW,center=g.start+fraction*g.span;
    const a=Math.max(0,Math.min(g.maxT-width,center-fraction*width));
    view.range=[a,a+width];render(view);
  },{passive:false});
  let drag=null;
  svg.addEventListener('pointerdown',ev=>{
    if(view.cursorMode)return;
    const px=mouseX(ev),g=view.geom;if(px<g.L||px>g.L+g.PW)return;
    drag={px,range:[...view.range]};svg.setPointerCapture(ev.pointerId);
  });
  svg.addEventListener('pointermove',ev=>{
    if(!drag)return;const g=view.geom;
    const width=drag.range[1]-drag.range[0];
    const low=Math.max(0,Math.min(g.maxT-width,drag.range[0]-(mouseX(ev)-drag.px)/g.PW*width));
    view.range=[low,low+width];render(view);
  });
  svg.addEventListener('pointerup',()=>drag=null);
  svg.addEventListener('pointercancel',()=>drag=null);
  svg.addEventListener('click',ev=>{
    if(!view.cursorMode)return;
    const px=mouseX(ev),g=view.geom;if(px<g.L||px>g.L+g.PW)return;
    const t=g.start+(px-g.L)/g.PW*g.span;
    if(view.cursors[0]===null||view.cursors[1]!==null)view.cursors=[t,null];
    else view.cursors[1]=t;
    render(view);
  });
  render(view);
});
})();
</script></body></html>'''
