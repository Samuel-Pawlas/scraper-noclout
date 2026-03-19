#!/usr/bin/env python3
"""Test to see how many products we can fetch with pagination"""

import warnings
warnings.filterwarnings('ignore')

import sys
sys.path.insert(0, 'C:/Finds/Scrapers/scraper-noclout')

from scraper import ShopifyScraper

scraper = ShopifyScraper()

print("Testing product pagination...")
products = scraper.get_all_product_handles(max_pages=10)

print(f"\nTotal products found: {len(products)}")
print("\nSample handles:")
for p in products[:10]:
    print(f"  - {p['handle']}")
