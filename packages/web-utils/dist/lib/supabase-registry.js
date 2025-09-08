let currentSupabase = null;
export function setSupabase(client) {
    currentSupabase = client;
}
export function getSupabase() {
    return currentSupabase;
}
