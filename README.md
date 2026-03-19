# Noclout Fashion Store Scraper - Smart Edition

A production-ready scraper with intelligent product management:

- **Smart Upsert**: Only updates products that have actually changed
- **Batch Processing**: 50 products per database batch (vs 1 by 1)
- **Skip Unchanged**: Don't re-generate embeddings for unchanged products
- **Conditional Embeddings**: Only regenerate when images change
- **Stale Cleanup**: Auto-removes products not seen in 2 consecutive runs
- **Error Handling**: 3 retries with detailed logging
- **Run Summary**: Clear stats at the end of each run

## Quick Start

### 1. Run Database Migration (One-time setup)

Go to your [Supabase SQL Editor](https://supabase.com/dashboard) and run:

```sql
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS last_seen_run integer DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_products_source ON public.products(source);
```

### 2. Manual Run
```batch
run_manual.bat
```

### 3. Automated Daily Run
```powershell
.\setup_scheduler.ps1
```

## New Features Explained

### Smart Upsert Logic
```
For each scraped product:
  1. Check if exists in database (by source + product_url)
  2. Compare scraped data against existing record
  3. If ANY field changed (price, title, images, etc):
     - Update only the changed fields
     - Set updated_at = now()
     - Regenerate embeddings IF image changed
  4. If nothing changed:
     - Skip completely (no DB write, no embeddings)
```

### Batch Processing
- Collects products into batches of 50
- Single database request per batch (vs 50 requests before)
- ~50x fewer database round trips

### Stale Product Cleanup
```
After each run:
  1. Find all products from this source NOT seen in current run
  2. Increment last_seen_run for those products
  3. If last_seen_run >= 2 consecutive runs:
     - DELETE from database
```

This handles:
- Out-of-stock products
- Discontinued items
- Products removed from store

### Conditional Embedding Regeneration
Embeddings are expensive (SigLIP API calls). Regenerate ONLY when:
- Product is NEW
- Product image URL changed

Skip embeddings for:
- Price changes
- Description changes
- Size availability changes

### Staggered API Calls
- 0.5 second delay between embedding generation calls
- Prevents overwhelming the HuggingFace endpoint
- More reliable operation

### Error Handling
- 3 retries per batch before giving up
- Failed individual records logged separately
- All errors written to `scraper_errors.log`

## Run Summary Example
```
============================================================
RUN SUMMARY
============================================================
  New products added:     5
  Products updated:       12
  Products unchanged:     80
  Stale products deleted: 3
  Embeddings generated:    7
  Batches inserted:       1
  Errors logged:          0
============================================================
```

## Files

| File | Description |
|------|-------------|
| `scraper.py` | Main scraper with smart features |
| `migrate.py` | Database migration helper |
| `migrations/001_add_columns.sql` | SQL migration script |
| `run_manual.bat` | Manual run script |
| `run_automated.ps1` | PowerShell automation |
| `setup_scheduler.ps1` | Task Scheduler setup |

## Configuration

Constants in `scraper.py`:

```python
BATCH_SIZE = 50              # Products per database batch
EMBEDDING_DELAY = 0.5        # Seconds between API calls
MAX_RETRIES = 3              # Retry attempts per batch
STALE_THRESHOLD_RUNS = 2     # Runs before deleting stale products
```

## Requirements

- Python 3.12+
- Supabase project with `products` table
- Added columns: `updated_at`, `last_seen_run`

## Troubleshooting

### Missing columns error
Run the migration SQL above in Supabase SQL Editor

### All products showing as "New"
Check that `source` column is set to `"scraper-noclout"` for existing products

### Embeddings taking too long
Reduce `EMBEDDING_DELAY` in scraper.py (minimum 0.1)

### Memory issues
The scraper processes all products in memory. For very large catalogs (>10k products), consider chunking.

## License

MIT
