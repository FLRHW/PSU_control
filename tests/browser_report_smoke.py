#!/usr/bin/env python3
"""Real headless-browser acceptance for the long-report file:// viewer.

Requires Playwright Chromium (installed only in CI browser job).
Produces synthetic data; never connects to any PSU or external service.
"""
import csv
import os
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from cpx400dp_report import generate


FIELDS = ['utc_time', 'elapsed_s', 'event', 'scheduled_s', 'channel',
          'set_voltage_v', 'current_limit_a', 'requested_enable',
          'measured_voltage_v', 'measured_current_a', 'lateness_ms',
          'readback_duration_ms', 'note']


def fixture(path):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow({'event':'config', 'note':'SYNTHETIC mode=step'})
        writer.writerow({'event':'snapshot','channel':'1','requested_enable':'0'})
        writer.writerow({'event':'setpoint','channel':'1','elapsed_s':'0',
                         'set_voltage_v':'2','current_limit_a':'0.1','requested_enable':'0'})
        for i in range(9000):
            t = i * 400.0
            writer.writerow({'event':'readback','channel':'1','elapsed_s':f'{t:.6f}',
                             'measured_voltage_v':'2','measured_current_a':'0.05'})
        # Two samples 50 ms apart near the end of a 1000-hour recording.
        writer.writerow({'event':'readback','channel':'1',
                         'elapsed_s':'3599950.050000','measured_voltage_v':'39',
                         'measured_current_a':'0.05'})
        writer.writerow({'event':'readback','channel':'1',
                         'elapsed_s':'3599950.100000','measured_voltage_v':'2',
                         'measured_current_a':'0.05'})
        writer.writerow({'event':'readback','channel':'1',
                         'elapsed_s':'3600000.000000','measured_voltage_v':'2',
                         'measured_current_a':'0.05'})
        writer.writerow({'event':'final_state_verified','channel':'1',
                         'elapsed_s':'3600000'})
        writer.writerow({'event':'local_sent','elapsed_s':'3600000'})


def main():
    with tempfile.TemporaryDirectory() as dirname:
        folder = Path(dirname)
        sample = folder/'synthetic_measurements.csv'
        fixture(sample)
        output = generate(sample, force_stream=True)
        errors = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--allow-file-access-from-files'])
            page = browser.new_page(viewport={'width':1280,'height':900})
            page.on('pageerror', lambda err: errors.append(str(err)))
            page.goto(output.as_uri(), wait_until='load')
            assert page.locator('.channel').count() == 1
            assert 'Overview:' in page.locator('.detail-state').inner_text()
            page.locator('.jump-time').fill('3599950.05')
            page.locator('.jump-span').fill('1')
            page.locator('button.jump').click()
            page.wait_for_function(
                "() => document.querySelector('.detail-state').textContent.includes('Full resolution')",
                timeout=15000)
            assert page.locator('svg.plot path[stroke="#13a9c1"]').count() == 1, 'Voltage trace absent'
            assert '41.73' in page.locator('svg.plot').text_content(), '39 V spike missing from axis scale'
            page.locator('button.cursor').click()
            page.locator('svg.plot').click(position={'x':400,'y':180})
            page.locator('svg.plot').click(position={'x':520,'y':180})
            assert 'Δt' in page.locator('.reading').inner_text()
            screenshot = os.environ.get('CPX_BROWSER_SCREENSHOT_DIR')
            if screenshot:
                dest = Path(screenshot)/'synthetic_1000h_detail.png'
                dest.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(dest), full_page=True)
                print('Synthetic browser screenshot:', dest)
            assert not errors, 'Browser JavaScript exceptions: ' + '; '.join(errors)
            browser.close()
        print('PASS: file:// report, on-demand chunk loading, 50ms spike, jump, cursors')


if __name__ == '__main__':
    main()
