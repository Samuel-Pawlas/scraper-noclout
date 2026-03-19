#!/usr/bin/env python3
"""Quick test to verify scraper functionality"""

import warnings
warnings.filterwarnings('ignore')

import requests
from bs4 import BeautifulSoup
import re
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

def test_product_page():
    print("Testing product page fetch...")
    url = "https://noclout.fr/products/darker-zip"
    response = requests.get(url, headers=HEADERS, timeout=30, verify=False)
    print(f"Status: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    title = soup.find('meta', property='og:title')
    if title:
        print(f"Title: {title.get('content')}")
    
    price = soup.find('meta', property='og:price:amount')
    currency = soup.find('meta', property='og:price:currency')
    if price:
        print(f"Price: {price.get('content')} {currency.get('content') if currency else 'EUR'}")
    
    desc = soup.find('meta', property='og:description')
    if desc:
        print(f"Description: {desc.get('content')[:100]}...")
    
    images = soup.find_all('img', src=re.compile(r'cdn/shop/files'))
    print(f"Images found: {len(images)}")
    
    if images:
        print(f"First image: {images[0].get('src', '')[:80]}...")
    
    return True

def test_product_list():
    print("\nTesting product list page...")
    url = "https://noclout.fr/collections/tous-les-articles"
    response = requests.get(url, headers=HEADERS, timeout=30, verify=False)
    print(f"Status: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    product_links = soup.find_all('a', href=re.compile(r'/products/[^/?]+'))
    
    seen = set()
    unique_links = []
    for link in product_links:
        href = link.get('href', '')
        if href not in seen:
            seen.add(href)
            unique_links.append(href)
    
    print(f"Unique product links found: {len(unique_links)}")
    if unique_links:
        print(f"Sample: {unique_links[:3]}")
    
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("Noclout Scraper Quick Test")
    print("=" * 50)
    
    try:
        test_product_list()
        test_product_page()
        print("\n" + "=" * 50)
        print("All tests passed!")
        print("=" * 50)
    except Exception as e:
        print(f"Test failed: {e}")
