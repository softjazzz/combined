import { defineStore } from 'pinia'

export interface LLMParseResultState {
  lastResult: unknown | null
}

export const useLLMParseStore = defineStore('llmParse', {
  state: (): LLMParseResultState => ({ lastResult: null }),
  actions: {
    setResult(result: unknown) {
      this.lastResult = result
      try {
        if (typeof sessionStorage !== 'undefined') {
          sessionStorage.setItem('llm.lastResult', JSON.stringify(result))
        }
      } catch (error) {
        void error
      }
    },
    loadFromSession() {
      try {
        if (typeof sessionStorage !== 'undefined') {
          const raw = sessionStorage.getItem('llm.lastResult')
          if (raw) this.lastResult = JSON.parse(raw)
        }
      } catch (error) {
        void error
      }
    },
    clear() {
      this.lastResult = null
      try {
        if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem('llm.lastResult')
      } catch (error) {
        void error
      }
    },
  },
})
