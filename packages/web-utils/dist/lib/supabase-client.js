import { createClient } from "@supabase/supabase-js";
export function createSupabase(options) {
    const url = (options?.url ?? ((typeof process !== "undefined" && process?.env) ? process.env.VITE_SUPABASE_URL : "")) || "";
    const anonKey = (options?.anonKey ?? ((typeof process !== "undefined" && process?.env) ? process.env.VITE_SUPABASE_ANON_KEY : "")) || "";
    return createClient(url, anonKey, options?.clientOptions ?? {
        auth: { persistSession: true, autoRefreshToken: true },
    });
}
export const supabase = createSupabase();
