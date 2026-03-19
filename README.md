# Noclout Fashion Store Scraper

A production-ready scraper for Noclout fashion store that:
- Scrapes all products from the Shopify store
- Extracts detailed product information
- Generates SigLIP image and text embeddings (768-dim)
- Imports everything to Supabase
- Supports automated daily runs

## Quick Start

### Option 1: Manual Run (Recommended for first time)
```bash
# Double-click run_manual.bat
# Or from command line:
run_manual.bat
```

### Option 2: Automated Daily Run
```powershell
# Open PowerShell as Administrator and run:
.\setup_scheduler.ps1

# This will set up a Windows Task Scheduler task to run
# the scraper daily at midnight (00:00)
```

### Option 3: Direct Python Run
```bash
"C:\Users\samip\AppData\Local\Programs\Python\Python312\python.exe" scraper.py
```

## Requirements

- Python 3.12+
- CUDA-capable GPU recommended for faster embedding generation (CPU fallback supported)
- Windows OS (for Task Scheduler automation)

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Download SigLIP model (first run will download ~1GB):
```bash
python -c "from transformers import AutoModel; AutoModel.from_pretrained('google/siglip-base-patch16-384')"
```

## Files Overview

| File | Description |
|------|-------------|
| `scraper.py` | Main scraper implementation |
| `run_manual.bat` | Double-click to run manually |
| `run_automated.ps1` | PowerShell script for automation |
| `setup_scheduler.ps1` | Set up Windows Task Scheduler |
| `verify.py` | Test all components |
| `requirements.txt` | Python dependencies |

## Automation Setup

### Set Up Daily Automation
```powershell
.\setup_scheduler.ps1
```

### Check Automation Status
```powershell
Get-ScheduledTask -TaskName "NocloutDailyScraper" | Get-ScheduledTaskInfo
```

### Remove Automation
```powershell
.\setup_scheduler.ps1 -Uninstall
```

### Run Now (for testing)
```powershell
.\setup_scheduler.ps1 -RunNow
```

### Manual Run
```batch
run_manual.bat
```

## Configuration

Edit these constants in `scraper.py`:

```python
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-key"
MODEL_NAME = "google/siglip-base-patch16-384"
```

## Output Fields

The scraper produces the following fields for each product:

| Field | Description |
|-------|-------------|
| id | SHA256 hash of product handle |
| source | "scraper-noclout" |
| product_url | Full URL to the product |
| image_url | Primary product image URL |
| brand | "Noclout" |
| title | Product name |
| description | Product description |
| category | Product category (e.g., "Zips", "Hoodies") |
| gender | NULL (unisex clothing) |
| size | Available sizes |
| second_hand | FALSE |
| image_embedding | 768-dim SigLIP image embedding |
| country | "France" |
| price | Price in format "89.99EUR" |
| sale | Same as price (if on sale) |
| additional_images | Comma-separated additional image URLs |
| metadata | JSON with all product details |
| info_embedding | 768-dim SigLIP text embedding |
| created_at | Timestamp of import |

## Database Schema

The scraper expects a `products` table in Supabase with a `vector` extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE public.products (
    id text PRIMARY KEY,
    source text,
    product_url text UNIQUE,
    image_url text,
    brand text,
    title text NOT NULL,
    description text,
    category text,
    gender text,
    image_embedding vector(768),
    country text,
    price text,
    sale text,
    additional_images text,
    metadata text,
    size text,
    second_hand boolean DEFAULT false,
    info_embedding vector(768),
    created_at timestamptz DEFAULT now(),
    CONSTRAINT products_product_url_key UNIQUE (source, product_url)
);
```

## Performance

- ~97 products to scrape
- ~5-10 seconds per product (includes embedding generation)
- Total runtime: ~15-30 minutes on CPU, ~5-10 minutes on GPU
- Embeddings: ~2-3 seconds per image, ~0.5 seconds per text

## Troubleshooting

### SSL Certificate Errors
The scraper automatically ignores SSL verification.

### Python Not Found
Update the Python path in these files:
- `run_manual.bat`
- `run_automated.ps1`
- `setup_scheduler.ps1`

### Dependencies Not Installed
```bash
pip install -r requirements.txt
```

### Check Last Run
```powershell
Get-ScheduledTask -TaskName "NocloutDailyScraper" | Get-ScheduledTaskInfo
```

### View Logs
Logs are saved in the project directory with format: `scraper_log_YYYYMMDD_HHMMSS.log`

## License

MIT
