export async function analyzeWithDeepSeek(content: string): Promise<Record<string, unknown>> {
  return {
    contentLength: content.length,
    issues: [],
    suggestions: [],
  }
}
