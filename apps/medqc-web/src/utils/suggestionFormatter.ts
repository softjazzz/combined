import type { QCSuggestion } from '@/types'

export interface StructuredSuggestion extends QCSuggestion {
  steps: string[]
}

export const parseSuggestionDescription = (description: string): string[] => {
  if (!description) return []

  const normalized = description.replace(/\s+/g, ' ').trim()

  const numberedMatches = Array.from(
    normalized.matchAll(/(?:\(\d+\)|（\d+）)\s*(.*?)(?=(?:\(\d+\)|（\d+）|$))/g)
  )
    .map(match => match[1].trim())
    .filter(Boolean)
  if (numberedMatches.length > 0) {
    return numberedMatches
  }

  const withParens = normalized
    .split(/(?=(?:\(\d+\)|（\d+）))/)
    .map(item => item.replace(/^(?:\(\d+\)|（\d+）)\s*/, '').trim())
    .filter(Boolean)
  if (withParens.length > 1) {
    return withParens.map(item => item.replace(/[;；]$/, '').trim())
  }

  const withDigits = normalized
    .split(/(?=\d+[\.、])/)
    .map(item => item.replace(/^\d+[\.、]\s*/, '').trim())
    .filter(Boolean)
  if (withDigits.length > 1) {
    return withDigits.map(item => item.replace(/[;；]$/, '').trim())
  }

  const splitByPunctuation = normalized
    .split(/(?:；|;|。)(?![^()]*\))/)
    .map(item => item.trim())
    .filter(Boolean)
  if (splitByPunctuation.length > 1) {
    return splitByPunctuation
  }

  return [normalized]
}

export const structureSuggestions = (suggestions: QCSuggestion[]): StructuredSuggestion[] =>
  suggestions.map((suggestion, index) => ({
    ...suggestion,
    id: suggestion.id || `suggestion-${index}`,
    steps: parseSuggestionDescription(suggestion.description)
  }))
