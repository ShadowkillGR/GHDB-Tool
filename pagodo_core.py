import time
import random

def run_pagodo_scan(dorks, domain=""):
    results = {}
    for dork in dorks:
        query = f"site:{domain} {dork}" if domain else dork
        time.sleep(random.uniform(0.1, 0.3))  # Simulate scan delay
        results[dork] = [f"https://www.google.com/search?q={query}"]
    return results
