import type { QCSuggestion } from '@/types'

export interface StructuredSuggestion extends QCSuggestion {
  steps: string[]
}

const cleanSegment = (text: string): string =>
  text
    .replace(/^[\s\-•●◎☆★▪▫▶▷→\d①②③④⑤⑥⑦⑧⑨⑩\.、．\)（()]+/, '')
    .replace(/^(?:改进|整改|优化)?建议[:：]\s*/i, '')
    .replace(/[;；。.,，、]+\s*$/, '')
    .trim()

const extractByPattern = (text: string, pattern: RegExp): string[] => {
  const matches = Array.from(text.matchAll(pattern))
    .map(match => cleanSegment(match[1] ?? ''))
    .filter(Boolean)
  return matches.length > 1 ? matches : []
}

const splitByPattern = (text: string, pattern: RegExp): string[] => {
  const segments = text
    .split(pattern)
    .map(segment => cleanSegment(segment))
    .filter(Boolean)
  return segments.length > 1 ? segments : []
}

export const parseSuggestionDescription = (description: string): string[] => {
  if (!description) return []

  const normalized = description.replace(/\r\n/g, '\n').trim()
  if (!normalized) return []

  const text = cleanSegment(normalized)
  if (!text) return []

  const extractPatterns = [
    /(?:\(\d+\)|（\d+）)\s*([\s\S]*?)(?=(?:\(\d+\)|（\d+）|$))/g,
    /\d+\)\s*([\s\S]*?)(?=(?:\d+\)|$))/g,
    /\d+(?:\.|、|．)\s*([\s\S]*?)(?=(?:\d+(?:\.|、|．)|$))/g,
    /[\u2460-\u2473]\s*([\s\S]*?)(?=(?:[\u2460-\u2473]|$))/g,
    /[一二三四五六七八九十]+[\.、．)]\s*([\s\S]*?)(?=(?:[一二三四五六七八九十]+[\.、．)]|$))/g
  ]

  for (const pattern of extractPatterns) {
    const extracted = extractByPattern(text, pattern)
    if (extracted.length > 0) {
      return extracted
    }
  }

  const splitPatterns = [
    /(?:^|\n)(?:\(\d+\)|（\d+）)\s*/,
    /(?:^|\n)\d+\)\s*/,
    /(?:^|\n)\d+(?:\.|、|．)\s*/,
    /(?:^|\n)[\u2460-\u2473]\s*/,
    /(?:^|\n)[一二三四五六七八九十]+[\.、．)]\s*/
  ]

  for (const pattern of splitPatterns) {
    const segments = splitByPattern(text, pattern)
    if (segments.length > 0) {
      return segments
    }
  }

  const newlineSegments = text
    .split(/\n+/)
    .map(segment => cleanSegment(segment))
    .filter(Boolean)
  if (newlineSegments.length > 1) {
    return newlineSegments
  }

  const punctuationSegments = text
    .split(/(?:；|;|。|\.|！|!)(?![^()]*\))/)
    .map(segment => cleanSegment(segment))
    .filter(Boolean)
  if (punctuationSegments.length > 1) {
    return punctuationSegments
  }

  return [text]
}

export const structureSuggestions = (suggestions: QCSuggestion[]): StructuredSuggestion[] =>
  suggestions.map((suggestion, index) => ({
    ...suggestion,
    id: suggestion.id || `suggestion-${index}`,
    steps: parseSuggestionDescription(suggestion.description)
  }))
