-- Migration: Add updated_at and last_seen_run columns
-- Run this in your Supabase SQL Editor (https://supabase.com/dashboard)

-- Add updated_at column to track when products were last modified
ALTER TABLE public.products 
ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Add last_seen_run column to track consecutive runs without seeing this product
-- Used for stale product cleanup
ALTER TABLE public.products 
ADD COLUMN IF NOT EXISTS last_seen_run integer DEFAULT 0;

-- Create index for faster queries on source column
CREATE INDEX IF NOT EXISTS idx_products_source ON public.products(source);

-- Create index for stale product cleanup queries
CREATE INDEX IF NOT EXISTS idx_products_last_seen ON public.products(last_seen_run);

-- Grant necessary permissions (adjust role name as needed)
GRANT USAGE ON SCHEMA public TO service_role;
GRANT ALL ON public.products TO service_role;
