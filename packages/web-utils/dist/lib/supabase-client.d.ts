import type { SupabaseClient } from "@supabase/supabase-js";
export interface SupabaseInitOptions {
    url?: string;
    anonKey?: string;
    clientOptions?: any;
}
export declare function createSupabase(options?: SupabaseInitOptions): SupabaseClient;
