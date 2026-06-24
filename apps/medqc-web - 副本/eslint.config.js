import js from '@eslint/js'
import parserTs from '@typescript-eslint/parser'
import pluginTs from '@typescript-eslint/eslint-plugin'
import pluginVue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'

export default [
  {
    ignores: [
      'dist/**',
      'coverage/**',
      'node_modules/**',
      'third_party/**',
      '**/*.d.ts',
      'src/views/drg-grouper/sichuan2024Grouper.js',
      'src/views/drg-grouper/cnDrg2023Grouper.js',
    ],
  },
  {
    languageOptions: {
      globals: {
        RequestInit: 'readonly',
        NodeJS: 'readonly',
        process: 'readonly',
        EventListener: 'readonly',
      },
    },
  },
  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: parserTs,
        ecmaVersion: 'latest',
        sourceType: 'module',
        extraFileExtensions: ['.vue'],
      },
    },
    rules: {
      'no-unused-vars': 'off',
      'no-console': ['warn', { allow: ['log', 'info', 'debug', 'warn', 'error'] }],
      'vue/require-default-prop': 'off',
      'vue/no-v-html': 'off',
      'vue/no-template-shadow': 'off',
    },
  },
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: parserTs,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        extraFileExtensions: ['.vue'],
      },
    },
    plugins: {
      '@typescript-eslint': pluginTs,
    },
    rules: {
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/no-explicit-any': 'off',
      'no-console': [
        'warn',
        { allow: ['log', 'info', 'debug', 'warn', 'error', 'group', 'groupEnd'] },
      ],
    },
  },
  {
    // 迁移期噪声降噪：这些目录历史包袱较重，先聚焦 error 级问题
    files: [
      'src/services/**/*.ts',
      'src/utils/**/*.ts',
      'src/composables/**/*.ts',
      'src/types/**/*.ts',
      'src/api/**/*.ts',
      'src/stores/**/*.ts',
    ],
    rules: {
      '@typescript-eslint/no-unused-vars': 'off',
    },
  },
]
