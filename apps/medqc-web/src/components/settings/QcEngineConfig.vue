<template>
  <div class="ds-root">

    <!-- ══════════ Section 1: Prompt 策略 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">Prompt 策略</h2>
        <p class="ds-section-desc">
          控制发送给 LLM 的规则信息量。
          <code class="ds-code">plan_a</code> 在准确性和 Token 消耗之间取得最佳平衡。
        </p>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <div class="ds-card__body ds-divide">
            <div class="ds-row">
              <div class="ds-row__left">
                <div class="ds-row__label">Prompt 模式</div>
                <div class="ds-row__hint">决定发给 LLM 的规则上下文详细程度</div>
              </div>
              <select v-model="settings.prompt_mode" class="ds-select-native">
                <option value="plan_a">plan_a（标准，推荐）</option>
                <option value="current">current（精简）</option>
                <option value="plan_c">plan_c（详细）</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════ Section 2: 分段引擎 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">分段引擎</h2>
        <p class="ds-section-desc">
          控制质控任务的分批和并发策略。规则越少每次越精确但调用次数更多，
          并发数过高可能触发 API 限流。
        </p>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <div class="ds-card__body">
            <div class="ds-grid-section">
              <div class="ds-grid">
                <div class="ds-field">
                  <label class="ds-field__label">每批规则数</label>
                  <div class="ds-field__hint">分段模式下每次发给 LLM 的最大规则数（3-50）</div>
                  <div class="qc-input-group">
                    <input
                      v-model.number="settings.max_rules_per_batch"
                      type="number"
                      class="qc-input-group__input"
                      min="3" max="50"
                    />
                    <span class="qc-input-group__suffix">条</span>
                  </div>
                </div>
                <div class="ds-field">
                  <label class="ds-field__label">LLM 并发数</label>
                  <div class="ds-field__hint">同时请求 LLM 的最大数量（1-10）</div>
                  <div class="qc-input-group">
                    <input
                      v-model.number="settings.max_concurrency"
                      type="number"
                      class="qc-input-group__input"
                      min="1" max="10"
                    />
                    <span class="qc-input-group__suffix">个</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════ Section 3: LLM 参数 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">LLM 参数</h2>
        <p class="ds-section-desc">
          直接影响 LLM 输出质量和成本。质控场景建议低温度（0.1-0.3）以保证一致性，
          规则较多时需适当增大 Max Tokens。
        </p>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <div class="ds-card__body">
            <div class="ds-grid-section">
              <div class="ds-grid">
                <div class="ds-field">
                  <label class="ds-field__label">
                    Temperature
                    <span class="qc-param-badge" :class="settings.temperature <= 0.3 ? 'qc-param-badge--ok' : 'qc-param-badge--warn'">
                      {{ settings.temperature }}
                    </span>
                  </label>
                  <div class="ds-field__hint">越低越确定性，推荐 0.1-0.3</div>
                  <a-slider
                    v-model:value="settings.temperature"
                    :min="0" :max="1" :step="0.05"
                    :marks="{ 0: '0', 0.2: '推荐', 1: '1' }"
                  />
                </div>
                <div class="ds-field">
                  <label class="ds-field__label">Max Tokens</label>
                  <div class="ds-field__hint">LLM 最大输出 token 数（1024-65536）</div>
                  <div class="qc-input-group">
                    <input
                      v-model.number="settings.max_tokens"
                      type="number"
                      class="qc-input-group__input qc-input-group__input--wide"
                      min="1024" max="65536" step="1024"
                    />
                    <span class="qc-input-group__suffix">tokens</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="ds-card__footer">
            <button class="ds-btn ds-btn--ghost-text" @click="resetSettings">恢复默认</button>
            <button class="ds-btn ds-btn--primary" @click="saveSettings" :disabled="saving">
              保存质控配置
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import '@/styles/settings-design-system.css'

const saving = ref(false)

const settings = reactive({
  prompt_mode: 'plan_a',
  max_rules_per_batch: 15,
  max_concurrency: 3,
  temperature: 0.2,
  max_tokens: 16384,
})

const loadSettings = async () => {
  try {
    const resp = await fetch('/api/v1/qc/settings')
    if (resp.ok) {
      const data = await resp.json()
      Object.assign(settings, data.settings)
    }
  } catch {}
}

const saveSettings = async () => {
  saving.value = true
  try {
    const resp = await fetch('/api/v1/qc/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    })
    if (resp.ok) {
      message.success('质控配置已保存')
    } else {
      message.error('保存失败')
    }
  } catch {
    message.error('保存异常')
  } finally {
    saving.value = false
  }
}

const resetSettings = async () => {
  try {
    const resp = await fetch('/api/v1/qc/settings/reset', { method: 'POST' })
    if (resp.ok) {
      const data = await resp.json()
      Object.assign(settings, data.settings)
      message.success('已恢复默认质控配置')
    }
  } catch {
    message.error('重置失败')
  }
}

onMounted(loadSettings)
</script>

<style scoped>
/* 质控配置专用的 InputGroup（原生 input，避免 :deep 穿透问题） */
.qc-input-group {
  display: flex;
  align-items: stretch;
}
.qc-input-group__input {
  width: 80px;
  height: 34px;
  padding: 0 8px;
  border: 1px solid #d9d9d9;
  border-right: 0;
  border-radius: 6px 0 0 6px;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  text-align: center;
  outline: none;
  transition: border-color 0.2s;
  appearance: textfield;
  -moz-appearance: textfield;
}
.qc-input-group__input--wide { width: 120px; }
.qc-input-group__input::-webkit-inner-spin-button,
.qc-input-group__input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.qc-input-group__input:hover,
.qc-input-group__input:focus { border-color: #2563eb; }
.qc-input-group__input:focus { box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1); }
.qc-input-group__suffix {
  display: inline-flex;
  align-items: center;
  padding: 0 12px;
  background: #f1f5f9;
  border: 1px solid #d9d9d9;
  border-left: 0;
  border-radius: 0 6px 6px 0;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  white-space: nowrap;
  min-width: 40px;
  justify-content: center;
}

/* Temperature 当前值 Badge */
.qc-param-badge {
  display: inline-flex;
  align-items: center;
  margin-left: 6px;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 700;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}
.qc-param-badge--ok {
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #dcfce7;
}
.qc-param-badge--warn {
  background: #fffbeb;
  color: #d97706;
  border: 1px solid #fef3c7;
}

/* Slider 样式微调 */
:deep(.ant-slider) {
  margin-top: 4px;
}
</style>
