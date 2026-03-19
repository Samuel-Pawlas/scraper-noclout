#!/usr/bin/env python3
"""
Noclout Fashion Store Scraper - Smart Edition
- Batch inserts (50 products per batch)
- Smart upsert logic
- Stale product cleanup
- Skip unchanged products
- Conditional embedding regeneration
- Staggered API calls
- Comprehensive error handling
- Run summary
"""

import json
import re
import time
import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict, field
from collections import defaultdict

import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client
from PIL import Image
import numpy as np
import io

import torch
from transformers import AutoProcessor, AutoModel
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://yqawmzggcgpeyaaynrjk.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4")

MODEL_NAME = "google/siglip-base-patch16-384"
EMBEDDING_DIM = 768
BATCH_SIZE = 50
EMBEDDING_DELAY = 0.5
MAX_RETRIES = 3
STALE_THRESHOLD_RUNS = 2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

BASE_URL = "https://noclout.fr"
PRODUCTS_URL = f"{BASE_URL}/collections/tous-les-articles"
SOURCE = "scraper-noclout"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_errors.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class Product:
    id: str
    source: str
    product_url: str
    affiliate_url: Optional[str]
    image_url: str
    brand: str
    title: str
    description: Optional[str]
    category: Optional[str]
    gender: Optional[str]
    search_tsv: Optional[str]
    created_at: str
    updated_at: Optional[str]
    metadata: Optional[str]
    size: Optional[str]
    second_hand: bool
    image_embedding: Optional[List[float]]
    country: str
    compressed_image_url: Optional[str]
    tags: Optional[list]
    search_vector: Optional[str]
    title_tsv: Optional[str]
    brand_tsv: Optional[str]
    description_tsv: Optional[str]
    other: Optional[str]
    price: str
    sale: str
    additional_images: Optional[str]
    info_embedding: Optional[List[float]]
    last_seen_run: int = 0


@dataclass
class RunStats:
    """Track statistics for the current run"""
    new_products: int = 0
    products_updated: int = 0
    products_unchanged: int = 0
    stale_products_deleted: int = 0
    embeddings_generated: int = 0
    batches_inserted: int = 0
    errors_logged: int = 0
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print("RUN SUMMARY")
        print("=" * 60)
        print(f"  New products added:     {self.new_products}")
        print(f"  Products updated:       {self.products_updated}")
        print(f"  Products unchanged:     {self.products_unchanged}")
        print(f"  Stale products deleted: {self.stale_products_deleted}")
        print(f"  Embeddings generated:   {self.embeddings_generated}")
        print(f"  Batches inserted:       {self.batches_inserted}")
        print(f"  Errors logged:          {self.errors_logged}")
        print("=" * 60)


class SigLIPEmbedder:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading SigLIP model on {self.device}...")
        self.model = AutoModel.from_pretrained(MODEL_NAME)
        self.processor = AutoProcessor.from_pretrained(MODEL_NAME)
        self.model.to(self.device)
        self.model.eval()
        print(f"SigLIP model loaded successfully")

    def download_image(self, url: str) -> Optional[Image.Image]:
        try:
            response = requests.get(url, timeout=30, headers=HEADERS, verify=False)
            if response.status_code == 200:
                return Image.open(io.BytesIO(response.content)).convert("RGB")
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")
        return None

    def generate_image_embedding(self, image_url: str) -> Optional[List[float]]:
        img = self.download_image(image_url)
        if img is None:
            return None
        
        inputs = self.processor(images=img, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.get_image_features(**inputs)
            embedding = outputs.cpu().numpy().flatten().tolist()
        
        time.sleep(EMBEDDING_DELAY)
        return embedding

    def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        inputs = self.processor(text=text, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.get_text_features(**inputs)
            embedding = outputs.cpu().numpy().flatten().tolist()
        
        time.sleep(EMBEDDING_DELAY)
        return embedding


class ShopifyScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.verify = False

    def extract_product_json(self, html: str) -> Optional[dict]:
        patterns = [
            r'window\.futureblink_free_shipping_upsellProd\s*=\s*({.*?});',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            if matches:
                try:
                    return json.loads(matches[0])
                except json.JSONDecodeError:
                    continue
        return None

    def extract_products_from_list_page(self, html: str) -> list:
        products = []
        soup = BeautifulSoup(html, 'html.parser')
        product_links = soup.find_all('a', href=re.compile(r'/products/[^/?]+'))
        
        seen_urls = set()
        for link in product_links:
            url = link.get('href', '')
            if url.startswith('/'):
                url = BASE_URL + url
            
            product_handle = re.search(r'/products/([^/?]+)', url)
            if product_handle and url not in seen_urls:
                seen_urls.add(url)
                products.append({
                    'handle': product_handle.group(1),
                    'url': url
                })
        
        return products

    def get_product_details(self, product_url: str) -> Optional[dict]:
        try:
            response = self.session.get(product_url, timeout=30)
            if response.status_code != 200:
                return None
            
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            title = None
            title_tag = soup.find('h1', class_=re.compile(r'product.*title', re.I))
            if not title_tag:
                title_tag = soup.find('meta', property='og:title')
            if title_tag:
                if hasattr(title_tag, 'get_text'):
                    title = title_tag.get_text(strip=True)
                elif hasattr(title_tag, 'get'):
                    title = title_tag.get('content', '')
            
            price_text = ''
            price_meta = soup.find('meta', property='og:price:amount')
            if price_meta:
                price_amount = price_meta.get('content', '')
                price_currency = soup.find('meta', property='og:price:currency')
                currency = price_currency.get('content', 'EUR') if price_currency else 'EUR'
                price_text = f"{price_amount}{currency}"
            
            desc_tag = soup.find('div', class_=re.compile(r'product.*description', re.I))
            description = desc_tag.get_text(strip=True) if desc_tag else ''
            
            if not description:
                desc_meta = soup.find('meta', property='og:description')
                description = desc_meta.get('content', '') if desc_meta else ''
            
            images = []
            
            image_tags = soup.find_all('img', src=re.compile(r'cdn/shop/files'))
            for img in image_tags:
                src = img.get('src', '')
                if src and ('cdn.shopify.com' in src or 'cdn/shop/files' in src):
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/') and not src.startswith('//'):
                        src = 'https://noclout.fr' + src
                    if src not in images and ('.jpg' in src.lower() or '.png' in src.lower() or '.webp' in src.lower()):
                        images.append(src)
            
            script_content = html
            product_json = self.extract_product_json(script_content)
            
            if not title and product_json and 'title' in product_json:
                title = product_json['title']
            
            sizes = []
            variants = []
            
            if product_json and 'images' in product_json:
                for img_url in product_json['images']:
                    if img_url and isinstance(img_url, str):
                        clean_url = img_url
                        if clean_url.startswith('//'):
                            clean_url = 'https:' + clean_url
                        elif clean_url.startswith('/') and not clean_url.startswith('//'):
                            clean_url = 'https://noclout.fr' + clean_url
                        if not clean_url.startswith('http'):
                            clean_url = 'https://noclout.fr/' + clean_url.lstrip('/')
                        if clean_url not in images and ('.jpg' in clean_url.lower() or '.png' in clean_url.lower() or '.webp' in clean_url.lower()):
                            images.append(clean_url)
            
            if product_json and 'variants' in product_json:
                for variant in product_json['variants']:
                    variants.append(variant)
                    if 'title' in variant:
                        size_match = re.match(r'^([A-Z0-9+/]+)', variant['title'])
                        if size_match:
                            size = size_match.group(1)
                            if size not in sizes:
                                sizes.append(size)
            
            category = None
            
            if product_json and 'product_type' in product_json and product_json['product_type']:
                category = product_json['product_type']
            
            if not category:
                if title:
                    title_upper = title.upper()
                    if 'ZIP' in title_upper:
                        category = 'Zips'
                    elif 'HOODIE' in title_upper or 'HOOD' in title_upper:
                        category = 'Hoodies'
                    elif 'KNIT' in title_upper or 'KNITTED' in title_upper:
                        category = 'Knits'
                    elif 'TEE' in title_upper or 'TSHIRT' in title_upper:
                        category = 'T-Shirts'
                    elif 'JACKET' in title_upper or 'JERSEY' in title_upper:
                        category = 'Jackets'
                    elif 'SHORTS' in title_upper or 'PANT' in title_upper:
                        category = 'Bottoms'
                    elif 'CAP' in title_upper or 'HAT' in title_upper:
                        category = 'Caps'
                    elif 'BAG' in title_upper:
                        category = 'Bags'
                    elif 'KEY' in title_upper or 'CHAIN' in title_upper or 'CARD' in title_upper or 'WALLET' in title_upper:
                        category = 'Accessories'
            
            if not category:
                collection_links = soup.find_all('a', href=re.compile(r'/collections/'))
                for link in collection_links:
                    text = link.get_text(strip=True)
                    if text and text != 'Home' and 'products' not in text.lower() and 'shoes' not in text.lower() and 'accessories' not in text.lower():
                        category = text
                        break
            
            result = {
                'title': title,
                'price': price_text,
                'description': description,
                'images': images,
                'sizes': sizes,
                'variants': variants,
                'category': category,
                'handle': None
            }
            
            handle_match = re.search(r'/products/([^/?]+)', product_url)
            if handle_match:
                result['handle'] = handle_match.group(1)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching product {product_url}: {e}")
            return None

    def get_all_product_handles(self, max_pages: int = 100) -> list:
        all_products = []
        page = 1
        
        print(f"Fetching products from {PRODUCTS_URL}")
        
        while page <= max_pages:
            url = f"{PRODUCTS_URL}?page={page}"
            print(f"  Page {page}...", end=" ", flush=True)
            
            try:
                response = self.session.get(url, timeout=30)
                if response.status_code != 200:
                    print(f"Failed (status {response.status_code})")
                    break
                
                products = self.extract_products_from_list_page(response.text)
                
                if not products:
                    print(f"No products found")
                    break
                
                all_products.extend(products)
                print(f"Found {len(products)} products")
                
                if len(products) < 12:
                    break
                
                page += 1
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break
        
        seen = {}
        unique_products = []
        for p in all_products:
            handle = p.get('handle')
            if handle and handle not in seen:
                seen[handle] = True
                unique_products.append(p)
        
        print(f"\nTotal unique products: {len(unique_products)}")
        return unique_products


def generate_product_id(handle: str) -> str:
    return hashlib.sha256(f"noclout-{handle}".encode()).hexdigest()[:32]


def format_categories(category: str) -> str:
    if not category:
        return ""
    
    category_map = {
        'hoodies': ['Hoodie', 'Hoodies', 'Sweatshirt'],
        'sweaters': ['Sweater', 'Sweaters', 'Knit', 'Knitted'],
        't-shirts': ['T-Shirt', 'Tee', 'Tees', 'Top', 'Tops'],
        'zips': ['Zip', 'Zip-Up', 'Zips', 'Full-Zip'],
        'jackets': ['Jacket', 'Jackets', 'Coat', 'Outerwear'],
        'bottoms': ['Pants', 'Shorts', 'Jeans', 'Trousers'],
        'accessories': ['Cap', 'Hat', 'Bag', 'Accessory', 'Key', 'Chain', 'Card', 'Wallet'],
    }
    
    categories = []
    category_lower = category.lower()
    
    for cat_type, keywords in category_map.items():
        for keyword in keywords:
            if keyword.lower() in category_lower:
                categories.append(keyword if keyword != 'Zip' else 'Zips')
                break
    
    if not categories:
        categories = [category]
    
    return ", ".join(list(dict.fromkeys(categories)))


def parse_price(price_text: str) -> tuple:
    prices = []
    sale = ""
    
    if price_text:
        price_pattern = r'(\d+[.,]?\d*)'
        matches = re.findall(price_pattern, price_text)
        
        for match in matches:
            price_value = match.replace(',', '.')
            if '€' in price_text or 'EUR' in price_text:
                prices.append(f"{price_value}EUR")
            elif '$' in price_text or 'USD' in price_text:
                prices.append(f"{price_value}USD")
            elif '£' in price_text or 'GBP' in price_text:
                prices.append(f"{price_value}GBP")
            else:
                prices.append(f"{price_value}EUR")
    
    if not prices:
        prices = [""]
    
    return ",".join(prices) if prices else "", sale


def normalize_string(s: Optional[str]) -> str:
    """Normalize string for comparison"""
    if s is None:
        return ""
    return str(s).strip().lower()


def compare_products(scraped: dict, existing: dict) -> dict:
    """
    Compare scraped product data against existing database record.
    Returns dict with fields that have changed.
    """
    changes = {}
    
    scraped_title = normalize_string(scraped.get('title'))
    existing_title = normalize_string(existing.get('title'))
    if scraped_title != existing_title:
        changes['title'] = scraped.get('title')
    
    scraped_price = normalize_string(scraped.get('price'))
    existing_price = normalize_string(existing.get('price'))
    if scraped_price != existing_price:
        changes['price'] = scraped.get('price')
    
    scraped_desc = normalize_string(scraped.get('description'))
    existing_desc = normalize_string(existing.get('description'))
    if scraped_desc != existing_desc:
        changes['description'] = scraped.get('description')
    
    scraped_image = normalize_string(scraped.get('image_url'))
    existing_image = normalize_string(existing.get('image_url'))
    if scraped_image != existing_image:
        changes['image_url'] = scraped.get('image_url')
        changes['additional_images'] = scraped.get('additional_images')
    
    scraped_category = normalize_string(scraped.get('category'))
    existing_category = normalize_string(existing.get('category'))
    if scraped_category != existing_category:
        changes['category'] = scraped.get('category')
    
    scraped_sizes = normalize_string(scraped.get('size'))
    existing_sizes = normalize_string(existing.get('size'))
    if scraped_sizes != existing_sizes:
        changes['size'] = scraped.get('size')
    
    scraped_sale = normalize_string(scraped.get('sale'))
    existing_sale = normalize_string(existing.get('sale'))
    if scraped_sale != existing_sale:
        changes['sale'] = scraped.get('sale')
    
    scraped_metadata = normalize_string(scraped.get('metadata'))
    existing_metadata = normalize_string(existing.get('metadata'))
    if scraped_metadata != existing_metadata:
        changes['metadata'] = scraped.get('metadata')
    
    return changes


def create_product_record(
    product_data: dict,
    embedder: SigLIPEmbedder,
    generate_embeddings: bool = True,
    existing_record: Optional[dict] = None
) -> Optional[dict]:
    """Create a product record, optionally reusing existing embeddings"""
    try:
        handle = product_data.get('handle', '')
        title = product_data.get('title', 'Unknown Product')
        description = product_data.get('description', '')
        images = product_data.get('images', [])
        sizes = product_data.get('sizes', [])
        category = product_data.get('category', '')
        
        price_text = product_data.get('price', '') or ''
        price, sale = parse_price(str(price_text))
        
        image_url = images[0] if images else ""
        additional_images = ", ".join(images[1:]) if len(images) > 1 else ""
        
        product_id = generate_product_id(handle)
        
        metadata = {
            'title': title,
            'description': description,
            'sizes': sizes,
            'variants': product_data.get('variants', []),
            'colors': [],
            'material': '',
            'original_currency': 'EUR'
        }
        
        now = datetime.utcnow().isoformat()
        
        record = {
            'id': product_id,
            'source': SOURCE,
            'product_url': product_data.get('url', f"{BASE_URL}/products/{handle}"),
            'affiliate_url': None,
            'image_url': image_url,
            'brand': "Noclout",
            'title': title,
            'description': description,
            'category': format_categories(category),
            'gender': None,
            'search_tsv': None,
            'created_at': existing_record.get('created_at') if existing_record else now,
            'updated_at': now,
            'metadata': json.dumps(metadata, ensure_ascii=False),
            'size': ", ".join(sizes) if sizes else None,
            'second_hand': False,
            'country': "France",
            'compressed_image_url': None,
            'tags': None,
            'search_vector': None,
            'title_tsv': None,
            'brand_tsv': None,
            'description_tsv': None,
            'other': None,
            'price': price,
            'sale': sale if sale else price,
            'additional_images': additional_images if additional_images else None,
            'last_seen_run': 0
        }
        
        if generate_embeddings:
            print(f"    Generating embeddings for: {title}")
            record['image_embedding'] = embedder.generate_image_embedding(image_url) if image_url else [0.0] * EMBEDDING_DIM
            
            info_text = f"""
            Title: {title}
            Brand: Noclout
            Description: {description}
            Category: {category}
            Price: {price}
            Sizes: {', '.join(sizes) if sizes else 'One Size'}
            Gender: Unisex
            """.strip()
            
            record['info_embedding'] = embedder.generate_text_embedding(info_text) if info_text else [0.0] * EMBEDDING_DIM
        else:
            record['image_embedding'] = existing_record.get('image_embedding') if existing_record else [0.0] * EMBEDDING_DIM
            record['info_embedding'] = existing_record.get('info_embedding') if existing_record else [0.0] * EMBEDDING_DIM
        
        return record
        
    except Exception as e:
        logger.error(f"Error creating product record: {e}")
        return None


class NocloutScraper:
    def __init__(self):
        self.scraper = ShopifyScraper()
        self.embedder = SigLIPEmbedder()
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.stats = RunStats()
        self.current_run_id = int(time.time())
        self.existing_products: Dict[str, dict] = {}
        self.seen_handles: set = set()
        
    def get_existing_products(self) -> Dict[str, dict]:
        """Fetch all products from this source"""
        print("\nFetching existing products from database...")
        existing = {}
        
        try:
            offset = 0
            batch_size = 1000
            
            while True:
                response = self.supabase.table('products').select('*').eq('source', SOURCE).range(offset, offset + batch_size - 1).execute()
                
                if not response.data:
                    break
                
                for row in response.data:
                    handle_match = re.search(r'/products/([^/?]+)', row.get('product_url', ''))
                    if handle_match:
                        handle = handle_match.group(1)
                        existing[handle] = row
                
                offset += batch_size
                
                if len(response.data) < batch_size:
                    break
                    
        except Exception as e:
            logger.error(f"Error fetching existing products: {e}")
        
        print(f"  Found {len(existing)} existing products in database")
        return existing

    def scrape_all_products(self) -> list:
        print("\nFetching all product handles...")
        product_handles = self.scraper.get_all_product_handles()
        print(f"Found {len(product_handles)} total products")
        
        products = []
        for i, product_info in enumerate(product_handles):
            handle = product_info['handle']
            self.seen_handles.add(handle)
            
            print(f"[{i+1}/{len(product_handles)}] Processing: {handle}")
            
            details = self.scraper.get_product_details(product_info['url'])
            if details:
                details['url'] = product_info['url']
                details['handle'] = handle
                products.append(details)
            else:
                print(f"  Could not fetch details for {handle}")
            
            time.sleep(0.3)
        
        return products

    def process_products(self, products: list) -> tuple:
        """Process products with smart upsert logic"""
        print("\nProcessing products...")
        
        new_records = []
        records_to_update = []
        unchanged_handles = []
        
        for product_data in products:
            handle = product_data.get('handle', '')
            existing = self.existing_products.get(handle)
            
            if existing:
                changes = compare_products(product_data, existing)
                
                if not changes:
                    unchanged_handles.append(handle)
                    self.stats.products_unchanged += 1
                    print(f"  [{handle}] Unchanged - skipping")
                    continue
                
                image_changed = 'image_url' in changes
                generate_embeddings = image_changed
                
                print(f"  [{handle}] Changed: {list(changes.keys())}")
                
                record = create_product_record(
                    product_data,
                    self.embedder,
                    generate_embeddings=generate_embeddings,
                    existing_record=existing
                )
                
                if record:
                    if generate_embeddings:
                        self.stats.embeddings_generated += 1
                    
                    records_to_update.append(record)
                    self.stats.products_updated += 1
            else:
                print(f"  [{handle}] New product - generating embeddings")
                record = create_product_record(
                    product_data,
                    self.embedder,
                    generate_embeddings=True
                )
                
                if record:
                    new_records.append(record)
                    self.stats.embeddings_generated += 1
                    self.stats.new_products += 1
        
        return new_records, records_to_update

    def batch_insert(self, records: List[dict], mode: str = 'insert') -> bool:
        """Insert records in batches with retry logic"""
        if not records:
            return True
        
        total_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE
        
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            
            print(f"  Batch {batch_num}/{total_batches} ({len(batch)} products)...")
            
            for attempt in range(MAX_RETRIES):
                try:
                    if mode == 'upsert':
                        self.supabase.table('products').upsert(
                            batch,
                            on_conflict='source,product_url'
                        ).execute()
                    else:
                        self.supabase.table('products').insert(batch).execute()
                    
                    self.stats.batches_inserted += 1
                    print(f"    Success!")
                    break
                    
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"    Attempt {attempt + 1} failed: {e}, retrying...")
                        time.sleep(1)
                    else:
                        logger.error(f"    Batch insert failed after {MAX_RETRIES} attempts: {e}")
                        for record in batch:
                            try:
                                if mode == 'upsert':
                                    self.supabase.table('products').upsert(
                                        record,
                                        on_conflict='source,product_url'
                                    ).execute()
                                else:
                                    self.supabase.table('products').insert(record).execute()
                            except Exception as ex:
                                logger.error(f"    Failed to insert {record.get('title', 'unknown')}: {ex}")
                                self.stats.errors_logged += 1
        
        return True

    def cleanup_stale_products(self):
        """Delete products not seen in this run (after grace period)"""
        print("\nCleaning up stale products...")
        
        stale_handles = []
        
        for handle, existing in self.existing_products.items():
            if handle not in self.seen_handles:
                last_seen_run = existing.get('last_seen_run', 0)
                if last_seen_run >= STALE_THRESHOLD_RUNS:
                    stale_handles.append(handle)
        
        if stale_handles:
            print(f"  Found {len(stale_handles)} stale products to delete")
            
            for i in range(0, len(stale_handles), BATCH_SIZE):
                batch = stale_handles[i:i + BATCH_SIZE]
                product_urls = [f"{BASE_URL}/products/{h}" for h in batch]
                
                try:
                    self.supabase.table('products').delete().in_('product_url', product_urls).execute()
                    self.stats.stale_products_deleted += len(batch)
                    print(f"    Deleted {len(batch)} stale products")
                except Exception as e:
                    logger.error(f"    Error deleting stale products: {e}")
                    self.stats.errors_logged += 1
        else:
            print("  No stale products found")

    def mark_products_seen(self):
        """Update last_seen_run for all products"""
        print("\nMarking products as seen...")
        
        seen_urls = [f"{BASE_URL}/products/{h}" for h in self.seen_handles]
        
        if seen_urls:
            try:
                for i in range(0, len(seen_urls), BATCH_SIZE):
                    batch = seen_urls[i:i + BATCH_SIZE]
                    for url in batch:
                        self.supabase.table('products').update(
                            {'last_seen_run': 0}
                        ).eq('product_url', url).execute()
            except Exception as e:
                logger.error(f"Error marking products seen: {e}")

    def run(self):
        print("=" * 60)
        print("Noclout Fashion Store Scraper - Smart Edition")
        print(f"Run ID: {self.current_run_id}")
        print("=" * 60)
        
        self.existing_products = self.get_existing_products()
        
        products = self.scrape_all_products()
        
        if not products:
            print("\nNo products found")
            return
        
        print(f"\nScraped {len(products)} products successfully")
        
        new_records, records_to_update = self.process_products(products)
        
        if new_records:
            print(f"\nInserting {len(new_records)} new products...")
            self.batch_insert(new_records, mode='insert')
        
        if records_to_update:
            print(f"\nUpdating {len(records_to_update)} existing products...")
            self.batch_insert(records_to_update, mode='upsert')
        
        self.mark_products_seen()
        
        self.cleanup_stale_products()
        
        self.stats.print_summary()
        
        print("\nScraping and upload complete!")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings('ignore')
    
    scraper = NocloutScraper()
    scraper.run()
