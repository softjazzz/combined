import type { SupabaseClient } from '@supabase/supabase-js';
export declare function setSupabase(client: SupabaseClient | null): void;
export declare function getSupabase(): SupabaseClient | null;
