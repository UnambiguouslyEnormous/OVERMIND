#!/usr/bin/env python3
"""Regenerate original GAFAW vector skin; deterministic, no external assets/dependencies."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'overmind' / 'skins' / 'black-titanium' / 'assets'
ROOT.mkdir(exist_ok=True)

def save(name, width, height, defs, body):
    (ROOT / name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><defs>{defs}</defs>{body}</svg>\n')

save('titanium.svg', 512, 512,
     '<linearGradient id="metal" x2="0.8" y2="1"><stop stop-color="#42484c"/><stop offset=".22" stop-color="#1d2225"/><stop offset=".5" stop-color="#303639"/><stop offset="1" stop-color="#121719"/></linearGradient>',
     '<path fill="url(#metal)" d="M0 0h512v512H0z"/>' + ''.join(
         f'<path d="M0 {y}.5h512" stroke="{["#738087", "#020608", "#434d51"][y % 3]}" stroke-opacity="{.07 + (y * 17 % 5) * .012}"/>' for y in range(512)))
save('lcd.svg', 240, 80,
     '<linearGradient id="lcd" x2="0" y2="1"><stop stop-color="#07130e"/><stop offset=".5" stop-color="#11271a"/><stop offset="1" stop-color="#09160e"/></linearGradient>',
     '<path fill="url(#lcd)" d="M0 0h240v80H0z"/>' + ''.join(f'<path d="M0 {y}h240" stroke="#7aff9c" stroke-opacity=".035"/>' for y in range(0,80,3)))
ROOT = Path(__file__).resolve().parents[1] / 'overmind' / 'assets'
save('gafaw-mark.svg', 160, 160,
     '<linearGradient id="rim" x2="1" y2="1"><stop stop-color="#d3dde0"/><stop offset=".4" stop-color="#3c494e"/><stop offset=".6" stop-color="#87969d"/><stop offset="1" stop-color="#182125"/></linearGradient>',
     '<rect x="4" y="4" width="152" height="152" rx="24" fill="url(#rim)"/><rect x="12" y="12" width="136" height="136" rx="19" fill="#0b1212" stroke="#050808" stroke-width="3"/><path d="M65 31h30m-24 0v37l-26 47q-8 16 10 16h50q18 0 10-16L89 68V31" fill="#152c21" stroke="#a5e9b2" stroke-width="5"/><path d="M59 99h42l12 23H47z" fill="#7deba0"/><circle cx="76" cy="87" r="4" fill="#7deba0"/><circle cx="88" cy="109" r="3" fill="#102d1c"/>')
print('Regenerated original Black Titanium textures and GAFAW emblem.')
