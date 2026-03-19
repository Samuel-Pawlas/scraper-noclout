#!/usr/bin/env python3
"""Test fetching product details"""

import warnings
warnings.filterwarnings('ignore')

import sys
import json
sys.path.insert(0, 'C:/Finds/Scrapers/scraper-noclout')

from scraper import ShopifyScraper

scraper = ShopifyScraper()

print("Testing product details fetch...")
product = scraper.get_product_details("https://noclout.fr/products/darker-zip")

if product:
    print(f"\nTitle: {product['title']}")
    print(f"Price: {product['price']}")
    print(f"Category: {product['category']}")
    print(f"Sizes: {product['sizes']}")
    print(f"Description: {product['description'][:100] if product['description'] else 'None'}...")
    print(f"Images count: {len(product['images'])}")
    print(f"First image: {product['images'][0] if product['images'] else 'None'}")
    print(f"Handle: {product['handle']}")
else:
    print("Failed to fetch product")
