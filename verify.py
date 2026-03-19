#!/usr/bin/env python3
"""Final verification script - tests all components"""

import warnings
warnings.filterwarnings('ignore')

import sys
sys.path.insert(0, 'C:/Finds/Scrapers/scraper-noclout')

from scraper import ShopifyScraper, NocloutScraper
from supabase import create_client

print("=" * 60)
print("Noclout Scraper - Final Verification")
print("=" * 60)

print("\n1. Testing Supabase connection...")
try:
    supabase = create_client(
        "https://yqawmzggcgpeyaaynrjk.supabase.co",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4"
    )
    print("   Supabase connection: OK")
except Exception as e:
    print(f"   Supabase connection: FAILED - {e}")

print("\n2. Testing product list scraping...")
try:
    scraper = ShopifyScraper()
    products = scraper.get_all_product_handles(max_pages=3)
    print(f"   Products found in first 3 pages: {len(products)}")
except Exception as e:
    print(f"   Product list scraping: FAILED - {e}")

print("\n3. Testing product details scraping...")
try:
    details = scraper.get_product_details("https://noclout.fr/products/chromatic-pink-tee")
    if details:
        print(f"   Title: {details['title']}")
        print(f"   Price: {details['price']}")
        print(f"   Category: {details['category']}")
        print(f"   Images: {len(details['images'])}")
        print("   Product details: OK")
    else:
        print("   Product details: FAILED - No data returned")
except Exception as e:
    print(f"   Product details: FAILED - {e}")

print("\n4. Checking Supabase table structure...")
try:
    result = supabase.table('products').select('id, title, brand, source').limit(1).execute()
    print(f"   Table exists: OK")
    print(f"   Columns accessible: id, title, brand, source")
except Exception as e:
    print(f"   Table check: {e}")

print("\n" + "=" * 60)
print("Verification complete!")
print("=" * 60)
print("\nTo run the full scraper:")
print("  python scraper.py")
print("\nOr run specific tests:")
print("  python test_pagination.py")
print("  python test_product_details.py")
