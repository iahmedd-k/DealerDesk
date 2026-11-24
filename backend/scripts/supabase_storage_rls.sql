-- ==============================================================================
-- DealerDesk Supabase Storage Row-Level Security (RLS) Policies
-- Buckets: 'brand-logos' and 'vehicle-images'
-- ==============================================================================

-- 1. Ensure buckets exist and are marked as public
INSERT INTO storage.buckets (id, name, public)
VALUES ('brand-logos', 'brand-logos', true)
ON CONFLICT (id) DO UPDATE SET public = true;

INSERT INTO storage.buckets (id, name, public)
VALUES ('vehicle-images', 'vehicle-images', true)
ON CONFLICT (id) DO UPDATE SET public = true;

-- 2. Enable RLS on storage.objects
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------
-- Brand Logos Policies
-- ------------------------------------------------------------------------------

-- Allow public read access to brand logos
DROP POLICY IF EXISTS "Public Read Brand Logos" ON storage.objects;
CREATE POLICY "Public Read Brand Logos"
ON storage.objects FOR SELECT
USING (bucket_id = 'brand-logos');

-- Allow authenticated dealership staff or service role to upload brand logos
DROP POLICY IF EXISTS "Authenticated Upload Brand Logos" ON storage.objects;
CREATE POLICY "Authenticated Upload Brand Logos"
ON storage.objects FOR INSERT
TO authenticated, service_role
WITH CHECK (bucket_id = 'brand-logos');

-- Allow authenticated dealership staff or service role to update brand logos
DROP POLICY IF EXISTS "Authenticated Update Brand Logos" ON storage.objects;
CREATE POLICY "Authenticated Update Brand Logos"
ON storage.objects FOR UPDATE
TO authenticated, service_role
USING (bucket_id = 'brand-logos');

-- Allow authenticated dealership staff or service role to delete brand logos
DROP POLICY IF EXISTS "Authenticated Delete Brand Logos" ON storage.objects;
CREATE POLICY "Authenticated Delete Brand Logos"
ON storage.objects FOR DELETE
TO authenticated, service_role
USING (bucket_id = 'brand-logos');

-- ------------------------------------------------------------------------------
-- Vehicle Images Policies
-- ------------------------------------------------------------------------------

-- Allow public read access to vehicle images
DROP POLICY IF EXISTS "Public Read Vehicle Images" ON storage.objects;
CREATE POLICY "Public Read Vehicle Images"
ON storage.objects FOR SELECT
USING (bucket_id = 'vehicle-images');

-- Allow authenticated dealership staff or service role to upload vehicle images
DROP POLICY IF EXISTS "Authenticated Upload Vehicle Images" ON storage.objects;
CREATE POLICY "Authenticated Upload Vehicle Images"
ON storage.objects FOR INSERT
TO authenticated, service_role
WITH CHECK (bucket_id = 'vehicle-images');

-- Allow authenticated dealership staff or service role to update vehicle images
DROP POLICY IF EXISTS "Authenticated Update Vehicle Images" ON storage.objects;
CREATE POLICY "Authenticated Update Vehicle Images"
ON storage.objects FOR UPDATE
TO authenticated, service_role
USING (bucket_id = 'vehicle-images');

-- Allow authenticated dealership staff or service role to delete vehicle images
DROP POLICY IF EXISTS "Authenticated Delete Vehicle Images" ON storage.objects;
CREATE POLICY "Authenticated Delete Vehicle Images"
ON storage.objects FOR DELETE
TO authenticated, service_role
USING (bucket_id = 'vehicle-images');
