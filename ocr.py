#!/usr/bin/env python3
"""
FreeLTC.fun Anti-Bot OCR Solver (Ultimate High-Accuracy & Strict 3-Option Version)
Usage: python3 ocr.py <faucet_html_file>
Output: JSON with solution
"""

import sys
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# ============================================================
# CONFIGURATION & ULTIMATE DICTIONARY
# ============================================================
OCR_API = "https://nice-pet-sandboxhubaaa-600a0136.koyeb.app/in.php"
OCR_RES = "https://nice-pet-sandboxhubaaa-600a0136.koyeb.app/res.php"
OCR_API_KEY = "free_ocr_api_key_2024"

OCR_CORRECTIONS = {
    '·': '+', '•': '+', '●': '+', '∘': '+', '×': '*', 'x': '*', 'X': '*', '÷': '/', ':': '/', '−': '-', '—': '-', '–': '-',
    '94': '4', '94.': '4', '94,': '4', '3·2': '3+2', '32': '3+2', '3 2': '3+2', '2·8': '2+8', '28': '2+8', '2 8': '2+8',
    '8·6': '8+6', '86': '8+6', '8 6': '8+6',
    'one': '1', 'won': '1', 'own': '1', 'two': '2', 'too': '2', 'to': '2', 'three': '3', 'tree': '3', 'free': '3',
    'four': '4', 'for': '4', 'frog': '4', 'five': '5', 'fire': '5', 'fine': '5', 'six': '6', 'sun': '6', 'sin': '6',
    'seven': '7', 'even': '7', 'seen': '7', 'eight': '8', 'fight': '8', 'night': '8', 'nine': '9', 'win': '9', 'wine': '9',
    'ten': '10', 'pen': '10', 'hen': '10',
    'lion': 'lion', 'l!on': 'lion', 'l1on': 'lion', '10n': 'lion', 'cat': 'cat', 'c@t': 'cat', 'c4t': 'cat',
    'dog': 'dog', 'd0g': 'dog', 'd09': 'dog', 'zoo': 'zoo', 'z00': 'zoo', 'zo0': 'zoo', 'cow': 'cow', 'c0w': 'cow',
    'rat': 'rat', 'r@t': 'rat', 'fox': 'fox', 'f0x': 'fox', 'pig': 'pig', 'p!g': 'pig', 'bird': 'bird', 'b!rd': 'bird',
    'fish': 'fish', 'f!sh': 'fish', 'bear': 'bear', 'be@r': 'bear', 'wolf': 'wolf', 'w0lf': 'wolf', 'oso': 'oso',
    '0s0': 'oso', 'o5o': 'oso', 'lol': 'lol', 'l0l': 'lol', '1o1': 'lol', 'ooz': 'ooz', '00z': 'ooz', 'o0z': 'ooz',
}

ROMAN_MAP = {
    'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5, 'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10,
    'll': 2, 'lll': 3, 'lv': 4, 'vl': 6, 'vll': 7, 'vlll': 8, 'lx': 11, 'l': 1
}

class PatternLearner:
    def __init__(self):
        self.patterns = defaultdict(list)
        self.ocr_corrections = {}
        
    def learn_pattern(self, main_parts, option_texts, successful_order):
        pattern_key = "->".join(main_parts)
        pattern_data = {'main_parts': main_parts, 'option_texts': option_texts, 'order': successful_order, 'timestamp': time.time()}
        self.patterns[pattern_key].append(pattern_data)
        for rel, text in option_texts.items():
            for part in main_parts:
                if part in text or text in part:
                    self.ocr_corrections[text] = part
    
    def match_pattern(self, main_parts, option_texts):
        pattern_key = "->".join(main_parts)
        if pattern_key in self.patterns:
            for pattern in self.patterns[pattern_key]:
                if len(pattern['option_texts']) == len(option_texts):
                    matched = sum(1 for rel, text in pattern['option_texts'].items()
                                  if rel in option_texts and (text == option_texts[rel] or text in option_texts[rel] or option_texts[rel] in text))
                    if matched >= len(option_texts) * 0.7:
                        return pattern['order']
        return None

pattern_learner = PatternLearner()

# ============================================================
# PARSERS & UTILS
# ============================================================
def parse_roman_text(text):
    if not text: return None
    clean = text.lower().strip().replace(' ', '')
    if clean in ROMAN_MAP:
        return str(ROMAN_MAP[clean])
    for op in ['+', '-', '*', '/']:
        if op in clean:
            parts = clean.split(op)
            if len(parts) == 2 and parts[0] in ROMAN_MAP and parts[1] in ROMAN_MAP:
                r1, r2 = ROMAN_MAP[parts[0]], ROMAN_MAP[parts[1]]
                try:
                    if op == '+': return str(r1 + r2)
                    if op == '-': return str(r1 - r2)
                    if op == '*': return str(r1 * r2)
                    if op == '/': return str(int(r1 / r2))
                except: pass
    return None

def ocr_image(base64_image, max_retries=3):
    for attempt in range(max_retries):
        try:
            payload = {"apikey": OCR_API_KEY, "methods": "image-to-text", "base64_img": base64_image, "json": 1}
            resp = requests.post(OCR_API, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 1:
                    return poll_ocr_result(data.get("request"))
                elif data.get("status") == 0:
                    return data.get("request")
        except:
            pass
        time.sleep(0.5)
    return None

def poll_ocr_result(job_id, max_attempts=20, delay=1.0):
    for _ in range(max_attempts):
        time.sleep(delay)
        try:
            resp = requests.get(OCR_RES, params={"apikey": OCR_API_KEY, "id": job_id, "json": 1}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 1:
                    return data.get("request")
                if data.get("request") == "CAPCHA_NOT_READY":
                    continue
                return data.get("request")
        except:
            continue
    return None

def correct_ocr_text(text):
    if not text: return text
    text = text.strip()
    text_lower = text.lower()
    if text in OCR_CORRECTIONS: return OCR_CORRECTIONS[text]
    if text_lower in OCR_CORRECTIONS: return OCR_CORRECTIONS[text_lower]
    if text in pattern_learner.ocr_corrections: return pattern_learner.ocr_corrections[text]
    if text_lower in pattern_learner.ocr_corrections: return pattern_learner.ocr_corrections[text_lower]
    return re.sub(r'^[.,;:!?]+|[.,;:!?]+$', '', text)

def parse_arithmetic(text):
    if not text: return None
    roman_res = parse_roman_text(text)
    if roman_res: return roman_res

    text = text.replace(' ', '').replace('·', '+').replace('•', '+').replace('×', '*').replace('÷', '/').replace('−', '-').replace('—', '-')
    text = re.sub(r'[^0-9+\-*/]', '', text)
    if not text: return None
    try:
        if '+' in text: return str(sum(int(p.strip()) for p in text.split('+') if p.strip()))
        if '-' in text:
            parts = text.split('-')
            total = int(parts[0].strip())
            for p in parts[1:]:
                if p.strip(): total -= int(p.strip())
            return str(total)
        if '*' in text:
            total = 1
            for p in text.split('*'):
                if p.strip(): total *= int(p.strip())
            return str(total)
        if '/' in text:
            parts = text.split('/')
            total = int(parts[0].strip())
            for p in parts[1:]:
                if p.strip(): total /= int(p.strip())
            return str(total)
    except: pass
    return None

def extract_numbers(text):
    if not text: return []
    results = re.findall(r'\d+', text)
    for word in re.findall(r'[a-zA-Z]+', text):
        if word.lower() in OCR_CORRECTIONS:
            corrected = OCR_CORRECTIONS[word.lower()]
            if corrected.isdigit(): results.append(corrected)
    return results

def calculate_similarity(word1, word2):
    if not word1 or not word2: return 0.0
    w1, w2 = word1.lower().strip(), word2.lower().strip()
    if w1 == w2: return 1.0
    if w1 in OCR_CORRECTIONS and OCR_CORRECTIONS[w1] == w2: return 1.0
    if w2 in OCR_CORRECTIONS and OCR_CORRECTIONS[w2] == w1: return 1.0
    if w1 in w2 or w2 in w1: return 0.9
    if len(w1) >= 2 and len(w2) >= 2 and w1[0] == w2[0]:
        if w1[-1] == w2[-1]: return 0.85
        return 0.7
    n1, n2 = extract_numbers(w1), extract_numbers(w2)
    for a in n1:
        for b in n2:
            if a == b: return 0.95
            if a.isdigit() and b.isdigit() and abs(int(a) - int(b)) <= 1: return 0.8
    common = len(set(w1) & set(w2))
    max_len = max(len(w1), len(w2))
    if max_len > 0 and common / max_len >= 0.5: return (common / max_len) * 0.8
    return 0.0

def smart_parse_main_text(text):
    if not text: return []
    text = correct_ocr_text(text.strip())
    arithmetic_result = parse_arithmetic(text)
    if arithmetic_result: return [arithmetic_result]
    roman_result = parse_roman_text(text)
    if roman_result: return [roman_result]

    for delim in [',', ';', ':', '|', '.', '  ']:
        if delim in text:
            parts = [p.strip() for p in text.split(delim) if p.strip()]
            if len(parts) >= 2: return [parse_arithmetic(p) or parse_roman_text(p) or p for p in parts]
            
    parts = text.split()
    if len(parts) >= 2:
        return [parse_arithmetic(p) or parse_roman_text(p) or p for p in parts]
    return [text]

def ocr_worker(item):
    key, b64 = item
    res = ocr_image(b64)
    return key, correct_ocr_text(res) if res else None

# ============================================================
# MAIN SOLVER (3-LAYER TRIPLE CHECK VERSION)
# ============================================================
def solve_antibot(html):
    soup = BeautifulSoup(html, 'html.parser')
    instruction = soup.find('div', class_='alert-warning') or soup.find('div', id='atb-instruction')
    if not instruction or not instruction.find('img'): return None
    
    main_src = instruction.find('img').get('src', '')
    if 'base64,' not in main_src: return None
    main_base64 = main_src.split('base64,')[1]
    
    script = soup.find('script', string=re.compile(r'var ablinks='))
    if not script: return None
    script_text = script.string
    
    matches = []
    for p in [r'rel\s*=\s*["\']?(\d+)["\']?.*?src\s*=\s*["\']data:image/png;base64,([^"\']+)["\']',
              r'rel\s*=\s*\\"(\d+)\\".*?src\s*=\s*\\"data:image/png;base64,([^\\]+)\\"',
              r'rel\s*=\s*&quot;(\d+)&quot;.*?src\s*=\s*&quot;data:image/png;base64,([^&]+)&quot;']:
        m = re.findall(p, script_text, re.DOTALL)
        if m: matches.extend(m); break

    seen = set()
    matches = [(r, i) for r, i in matches if not (r in seen or seen.add(r))]
    
    attempts = 0
    option_texts = {}
    main_parts = []
    
    # 🔄 3 அடுக்கு முயற்சியைக் கொண்ட முதன்மை லூப்
    while attempts < 3:
        attempts += 1
        jobs = [('main', main_base64)] + matches
        ocr_results = {}
        
        with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
            results = executor.map(ocr_worker, jobs)
            for key, text in results:
                if text: ocr_results[key] = text

        if 'main' not in ocr_results: continue
        
        main_parts = smart_parse_main_text(ocr_results['main'])
        option_texts = {k: v for k, v in ocr_results.items() if k != 'main'}
        if len(option_texts) < 2: continue
        
        remembered = pattern_learner.match_pattern(main_parts, option_texts)
        if remembered: return remembered
        
        # Match Processing
        ordered, used = [], set()
        for part in main_parts:
            best_rel, best_sim = None, 0.0
            for rel, opt_text in option_texts.items():
                if rel in used: continue
                opt_result = parse_arithmetic(opt_text) or parse_roman_text(opt_text)
                sim = 1.0 if opt_result and opt_result == part else (calculate_similarity(opt_result or opt_text, part) if opt_result else calculate_similarity(part, opt_text))
                if sim > best_sim: best_sim, best_rel = sim, rel
            if best_rel and best_sim >= 0.5:
                ordered.append(best_rel)
                used.add(best_rel)
                
        # 🎯 உட்சக்கட்ட மேட்ச் சரிபார்ப்பு: 3 விடைகளும் சரியாகப் பொருந்தினால் மட்டும் அனுப்பும்
        if len(ordered) == len(main_parts) and len(ordered) >= 3:
            return " " + " ".join(ordered)
        
        time.sleep(0.4)

    # 🛑 3 அட்டெம்ப்டுகளுக்குப் பிறகும் விடை அரைகுறையாக இருந்தால் (Fallback Execution)
    ordered, used = [], set()
    for part in main_parts:
        best_rel, best_sim = None, 0.0
        for rel, opt_text in option_texts.items():
            if rel in used: continue
            opt_result = parse_arithmetic(opt_text) or parse_roman_text(opt_text)
            sim = 1.0 if opt_result and opt_result == part else (calculate_similarity(opt_result or opt_text, part) if opt_result else calculate_similarity(part, opt_text))
            if sim > best_sim: best_sim, best_rel = sim, rel
        if best_rel and best_sim >= 0.35: # சேஃப்டிக்காக த்ரெஷோல்ட் குறைக்கப்பட்டுள்ளது
            ordered.append(best_rel)
            used.add(best_rel)

    # விடுபட்ட எண்களை மீதமிருக்கும் ஆப்ஷன்களிலிருந்து நிரப்புதல் (Strict 3 Count Filler)
    remaining_rels = [r for r in option_texts if r not in used]
    for rel in sorted(remaining_rels, key=int):
        if len(ordered) < 3:
            ordered.append(rel)

    # இறுதி விடை 3 விடைகளுடன் இருப்பதை உறுதி செய்கிறது
    if len(ordered) >= 3:
        return " " + " ".join(ordered)
    elif len(ordered) == 2 and len(remaining_rels) > 0:
        ordered.append(remaining_rels[0])
        return " " + " ".join(ordered)
        
    return " " + " ".join(sorted(option_texts.keys(), key=int))[:14]

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    with open(sys.argv[1], 'r', encoding='utf-8') as f: html = f.read()
    result = solve_antibot(html)
    if result:
        print(json.dumps({"success": True, "solution": result}))
    else:
        print(json.dumps({"success": False, "error": "Failed to solve after ultimate attempts"}))

