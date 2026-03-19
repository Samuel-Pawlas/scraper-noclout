#!/usr/bin/env python3
"""
Noclout Fashion Store Scraper
Scrapes products, generates SigLIP embeddings, and imports to Supabase
"""

import json
import re
import time
import hashlib
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse

import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client
from PIL import Image
import numpy as np
import io

import torch
from transformers import AutoProcessor, AutoModel
from torchvision import transforms

SUPABASE_URL = "https://yqawmzggcgpeyaaynrjk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4"

MODEL_NAME = "google/siglip-base-patch16-384"
EMBEDDING_DIM = 768

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

BASE_URL = "https://noclout.fr"
PRODUCTS_URL = f"{BASE_URL}/collections/tous-les-articles"


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
    metadata: Optional[str]
    size: Optional[str]
    second_hand: bool
    image_embedding: list
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
    info_embedding: list


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
            print(f"Error downloading image {url}: {e}")
        return None

    def generate_image_embedding(self, image_url: str) -> Optional[list]:
        img = self.download_image(image_url)
        if img is None:
            return None
        
        inputs = self.processor(images=img, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.get_image_features(**inputs)
            embedding = outputs.cpu().numpy().flatten().tolist()
        
        return embedding

    def generate_text_embedding(self, text: str) -> Optional[list]:
        inputs = self.processor(text=text, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.get_text_features(**inputs)
            embedding = outputs.cpu().numpy().flatten().tolist()
        
        return embedding


class ShopifyScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.verify = False

    def extract_product_json(self, html: str) -> Optional[dict]:
        patterns = [
            r'window\.futureblink_free_shipping_upsellProd\s*=\s*({.*?});',
            r'"product":\s*({[^}]+})',
            r'data-product-id="[^"]+"\s+data-product="([^"]+)"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            if matches:
                try:
                    if pattern.startswith('window'):
                        return json.loads(matches[0])
                    elif pattern.startswith('"product"'):
                        return json.loads(matches[0])
                except json.JSONDecodeError:
                    continue
        
        soup = BeautifulSoup(html, 'html.parser')
        script_tags = soup.find_all('script')
        
        for script in script_tags:
            if script.string and 'price' in script.string and 'title' in script.string:
                try:
                    match = re.search(r'price["\s:]+(\d+)', script.string)
                    if match:
                        return {"raw_html": script.string}
                except:
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
            
            image_tags = soup.find_all('img', src=re.compile(r'cdn/shop/files'))
            images = []
            for img in image_tags:
                src = img.get('src', '')
                if src and ('cdn.shopify.com' in src or 'cdn/shop/files' in src):
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/') and not src.startswith('//'):
                        src = 'https://noclout.fr' + src
                    if src not in images and ('.jpg' in src.lower() or '.png' in src.lower() or '.webp' in src.lower()):
                        images.append(src)
            
            if not images:
                og_image = soup.find('meta', property='og:image')
                if og_image:
                    img_url = og_image.get('content', '')
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    images.append(img_url)
            
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
            print(f"Error fetching product {product_url}: {e}")
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
                print(f"Error: {e}")
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


def parse_price(price_text: str, html: str = "") -> tuple:
    prices = []
    sale = ""
    
    if not price_text:
        price_pattern = r'["\']?(\d+[.,]\d{2})[€$£]?["\']?'
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
    
    soup = BeautifulSoup(html, 'html.parser') if html else None
    
    og_price = None
    og_currency = None
    if soup:
        og_price = soup.find('meta', property='og:price:amount')
        og_currency = soup.find('meta', property='og:price:currency')
        
        if og_price:
            price_val = og_price.get('content', '')
            currency = og_currency.get('content', 'EUR') if og_currency else 'EUR'
            if price_val:
                price_str = f"{price_val}{currency}"
                if price_str not in prices:
                    prices.append(price_str)
                sale = price_str
    
    compare_at = None
    if soup:
        compare_at = soup.find('s', class_=re.compile(r'compare|original', re.I))
    if compare_at:
        sale = ",".join(prices)
    
    if not prices:
        prices = [""]
    
    return ",".join(prices) if prices else "", sale


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
                if cat_type == 'hoodies' and 'Sweatshirt' in [category]:
                    categories.extend(['Hoodies', 'Sweaters'])
                elif cat_type == 'sweaters' and 'Sweatshirt' in [category]:
                    categories.append('Sweaters')
                else:
                    categories.append(keyword if keyword != 'Zip' else 'Zips')
                break
    
    if not categories:
        categories = [category]
    
    return ", ".join(list(dict.fromkeys(categories)))


def create_product_record(product_data: dict, embedder: SigLIPEmbedder) -> Optional[Product]:
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
        
        print(f"  Generating embeddings for: {title}")
        
        image_embedding = embedder.generate_image_embedding(image_url) if image_url else [0.0] * EMBEDDING_DIM
        
        info_text = f"""
        Title: {title}
        Brand: Noclout
        Description: {description}
        Category: {category}
        Price: {price}
        Sizes: {', '.join(sizes) if sizes else 'One Size'}
        Gender: Unisex
        """.strip()
        
        info_embedding = embedder.generate_text_embedding(info_text) if info_text else [0.0] * EMBEDDING_DIM
        
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
        
        return Product(
            id=product_id,
            source="scraper-noclout",
            product_url=product_data.get('url', f"{BASE_URL}/products/{handle}"),
            affiliate_url=None,
            image_url=image_url,
            brand="Noclout",
            title=title,
            description=description,
            category=format_categories(category),
            gender=None,
            search_tsv=None,
            created_at=datetime.utcnow().isoformat(),
            metadata=json.dumps(metadata, ensure_ascii=False),
            size=", ".join(sizes) if sizes else None,
            second_hand=False,
            image_embedding=image_embedding if image_embedding else [0.0] * EMBEDDING_DIM,
            country="France",
            compressed_image_url=None,
            tags=None,
            search_vector=None,
            title_tsv=None,
            brand_tsv=None,
            description_tsv=None,
            other=None,
            price=price,
            sale=sale if sale else price,
            additional_images=additional_images if additional_images else None,
            info_embedding=info_embedding if info_embedding else [0.0] * EMBEDDING_DIM
        )
        
    except Exception as e:
        print(f"Error creating product record: {e}")
        return None


class NocloutScraper:
    def __init__(self):
        self.scraper = ShopifyScraper()
        self.embedder = SigLIPEmbedder()
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def scrape_all_products(self) -> list:
        print("Fetching all product handles...")
        product_handles = self.scraper.get_all_product_handles()
        print(f"Found {len(product_handles)} total products")
        
        products = []
        for i, product_info in enumerate(product_handles):
            print(f"[{i+1}/{len(product_handles)}] Processing: {product_info['handle']}")
            
            details = self.scraper.get_product_details(product_info['url'])
            if details:
                details['url'] = product_info['url']
                details['handle'] = product_info['handle']
                products.append(details)
            else:
                print(f"  Could not fetch details for {product_info['handle']}")
            
            time.sleep(0.5)
        
        return products

    def upload_to_supabase(self, products: list):
        print(f"\nUploading {len(products)} products to Supabase...")
        
        existing = self.check_existing_products([p.get('handle', '') for p in products])
        
        new_products = [p for p in products if p.get('handle') not in existing]
        update_products = [p for p in products if p.get('handle') in existing]
        
        print(f"  New products: {len(new_products)}")
        print(f"  Products to update: {len(update_products)}")
        
        batch_size = 10
        for i in range(0, len(new_products), batch_size):
            batch = new_products[i:i+batch_size]
            self.upload_batch(batch, 'insert')
            print(f"  Uploaded batch {i//batch_size + 1}/{(len(new_products) + batch_size - 1)//batch_size}")
        
        if update_products:
            print(f"\nUpdating {len(update_products)} existing products...")
            for i in range(0, len(update_products), batch_size):
                batch = update_products[i:i+batch_size]
                self.upload_batch(batch, 'upsert')
                print(f"  Updated batch {i//batch_size + 1}/{(len(update_products) + batch_size - 1)//batch_size}")

    def check_existing_products(self, handles: list) -> set:
        existing = set()
        try:
            response = self.supabase.table('products').select('product_url').in_('product_url', [f"{BASE_URL}/products/{h}" for h in handles]).execute()
            for row in response.data:
                match = re.search(r'/products/([^/?]+)', row.get('product_url', ''))
                if match:
                    existing.add(match.group(1))
        except Exception as e:
            print(f"Error checking existing products: {e}")
        return existing

    def upload_batch(self, products: list, mode: str = 'insert'):
        records = []
        
        for product_data in products:
            record = create_product_record(product_data, self.embedder)
            if record:
                records.append(asdict(record))
        
        if not records:
            return
        
        try:
            if mode == 'upsert':
                for record in records:
                    self.supabase.table('products').upsert(
                        record,
                        on_conflict='source,product_url'
                    ).execute()
            else:
                self.supabase.table('products').insert(records).execute()
            
            print(f"  Successfully uploaded {len(records)} products")
            
        except Exception as e:
            print(f"  Error uploading batch: {e}")
            for record in records:
                try:
                    if mode == 'upsert':
                        self.supabase.table('products').upsert(
                            record,
                            on_conflict='source,product_url'
                        ).execute()
                    else:
                        self.supabase.table('products').insert(record).execute()
                except Exception as ex:
                    print(f"    Failed to upload {record.get('title', 'unknown')}: {ex}")

    def run(self):
        print("=" * 60)
        print("Noclout Fashion Store Scraper")
        print("=" * 60)
        
        products = self.scrape_all_products()
        
        if products:
            print(f"\nScraped {len(products)} products successfully")
            self.upload_to_supabase(products)
            print("\nScraping and upload complete!")
        else:
            print("\nNo products found")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings('ignore')
    
    scraper = NocloutScraper()
    scraper.run()
