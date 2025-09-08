import { createClient } from "@supabase/supabase-js";
import type { SupabaseClient } from "@supabase/supabase-js";

export interface SupabaseInitOptions {
  url?: string;
  anonKey?: string;
  clientOptions?: any;
}

export function createSupabase(options?: SupabaseInitOptions): SupabaseClient {
  const url = (options?.url ?? ((typeof process !== "undefined" && (process as any)?.env) ? (process as any).env.VITE_SUPABASE_URL : "")) || "";
  const anonKey = (options?.anonKey ?? ((typeof process !== "undefined" && (process as any)?.env) ? (process as any).env.VITE_SUPABASE_ANON_KEY : "")) || "";
  return createClient(url, anonKey, options?.clientOptions ?? {
    auth: { persistSession: true, autoRefreshToken: true },
  });
}

// Note: Do NOT create a default client at module load time.
// Many apps import utilities from this package without configuring Supabase.
// Creating a client here would throw when env is missing and break unrelated pages.
