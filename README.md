# Noclout Fashion Store Scraper - Smart Edition

A production-ready scraper with intelligent product management:

- **Smart Upsert**: Only updates products that have actually changed
- **Batch Processing**: 50 products per database batch (vs 1 by 1)
- **Skip Unchanged**: Don't re-generate embeddings for unchanged products
- **Conditional Embeddings**: Only regenerate when images change
- **Stale Cleanup**: Auto-removes products not seen in 2 consecutive runs
- **Error Handling**: 3 retries with detailed logging
- **Run Summary**: Clear stats at the end of each run
- **GitHub Actions**: Manual trigger + daily schedule

## Quick Start

### Option 1: GitHub Actions (Recommended)

1. **Add Secrets to GitHub**:
   - Go to your repo: `https://github.com/Samuel-Pawlas/scraper-noclout/settings/secrets/actions`
   - Click "New repository secret" and add:
     - `SUPABASE_URL` = `https://yqawmzggcgpeyaaynrjk.supabase.co`
     - `SUPABASE_KEY` = `your-service-role-key`

2. **Run Manually**:
   - Go to Actions tab → "Noclout Scraper" → "Run workflow"
   - Select "full" to run, or "verify_only" to test

3. **Automatic**:
   - Already configured to run daily at midnight (UTC)

### Option 2: Local Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run scraper
python scraper.py
```

### Option 3: Windows Batch

```batch
run_manual.bat
```

### Option 4: Windows Task Scheduler

```powershell
.\setup_scheduler.ps1
```

## Database Migration (Required - Run Once)

Go to [Supabase SQL Editor](https://supabase.com/dashboard) and run:

```sql
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS last_seen_run integer DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_products_source ON public.products(source);
```

## GitHub Actions Setup

### Adding Secrets

1. Navigate to: `Settings → Secrets and variables → Actions`
2. Click "New repository secret" for each:

| Secret Name | Value |
|------------|-------|
| `SUPABASE_URL` | `https://yqawmzggcgpeyaaynrjk.supabase.co` |
| `SUPABASE_KEY` | Your service role key |

### Running Manually

1. Go to **Actions** tab
2. Select **"Noclout Scraper"** workflow
3. Click **"Run workflow"** button (green)
4. Choose run type:
   - `full` - Run full scraper (default)
   - `verify_only` - Test imports and connection only
5. Click "Run workflow"

### Schedule

- Daily at midnight (UTC) = 1AM CET, midnight EST
- Modify in `.github/workflows/scrape.yml` if needed

## Run Summary Example

```
============================================================
RUN SUMMARY
============================================================
  New products added:     5
  Products updated:       12
  Products unchanged:    80
  Stale products deleted: 3
  Embeddings generated:  7
  Batches inserted:      1
  Errors logged:         0
============================================================
```

## Project Structure

```
scraper-noclout/
├── .github/
│   └── workflows/
│       └── scrape.yml          # GitHub Actions workflow
├── scraper.py                  # Main scraper
├── migrate.py                  # DB migration helper
├── migrations/
│   └── 001_add_columns.sql
├── run_manual.bat              # Windows batch (manual)
├── run_automated.ps1          # PowerShell (automation)
├── setup_scheduler.ps1         # Task Scheduler setup
├── requirements.txt
├── config.env
└── README.md
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPABASE_URL` | (hardcoded) | Supabase project URL |
| `SUPABASE_KEY` | (hardcoded) | Supabase API key |

### Scraper Constants

In `scraper.py`:

```python
BATCH_SIZE = 50              # Products per database batch
EMBEDDING_DELAY = 0.5        # Seconds between API calls
MAX_RETRIES = 3             # Retry attempts per batch
STALE_THRESHOLD_RUNS = 2     # Runs before deleting stale products
```

## Smart Features

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

### Stale Product Cleanup
```
After each run:
  1. Find all products from this source NOT seen in current run
  2. Increment last_seen_run for those products
  3. If last_seen_run >= 2 consecutive runs:
     - DELETE from database
```

### Conditional Embedding Regeneration
Embeddings are expensive (SigLIP API calls). Regenerate ONLY when:
- Product is NEW
- Product image URL changed

Skip embeddings for:
- Price changes
- Description changes
- Size availability changes

## Troubleshooting

### "Workflow not appearing in Actions"
Make sure the file is at `.github/workflows/scrape.yml` (not `scrape.yaml`)

### "Secrets not found"
Check that secrets are added to **Repository secrets** (not Organization secrets)

### "Missing columns error"
Run the migration SQL in Supabase SQL Editor

### "All products showing as New"
Check that `source` column is set to `"scraper-noclout"` for existing products

## License

MIT
