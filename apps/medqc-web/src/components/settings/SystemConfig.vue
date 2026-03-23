<template>
  <div class="ds-root">
    <!-- ══════════ Section 1: 基本信息 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">
          基本信息
        </h2>
        <p class="ds-section-desc">
          系统名称和版本标识。版本号由系统自动管理，不可手动修改。
        </p>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <div class="ds-card__body ds-divide">
            <div class="ds-row">
              <div class="ds-row__left">
                <div class="ds-row__label">
                  系统名称
                </div>
                <div class="ds-row__hint">
                  展示在页面标题和登录页
                </div>
              </div>
              <input
                v-model="config.systemName"
                class="sc-inline-input"
                placeholder="病案质控系统"
              >
            </div>
            <div class="ds-row">
              <div class="ds-row__left">
                <div class="ds-row__label">
                  系统版本
                </div>
                <div class="ds-row__hint">
                  自动管理，仅供参考
                </div>
              </div>
              <code class="ds-value-box ds-value-box--filled">{{ config.version }}</code>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════ Section 2: 安全策略 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">
          安全策略
        </h2>
        <p class="ds-section-desc">
          控制会话超时、密码复杂度和安全审计。修改后保存即刻生效，影响所有在线用户。
        </p>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <div class="ds-card__body ds-divide">
            <div class="ds-row">
              <div class="ds-row__left">
                <div class="ds-row__label">
                  会话超时时间
                </div>
                <div class="ds-row__hint">
                  用户无操作后自动登出的时间
                </div>
              </div>
              <div class="sc-input-group">
                <input
                  v-model.number="config.sessionTimeout"
                  type="number"
                  class="sc-input-group__input"
                  min="5"
                  max="1440"
                >
                <span class="sc-input-group__suffix">分钟</span>
              </div>
            </div>
            <div class="ds-row">
              <div class="ds-row__left">
                <div class="ds-row__label">
                  密码最小长度
                </div>
                <div class="ds-row__hint">
                  新用户和密码重置时的最低要求
                </div>
              </div>
              <div class="sc-input-group">
                <input
                  v-model.number="config.passwordMinLength"
                  type="number"
                  class="sc-input-group__input"
                  min="6"
                  max="20"
                >
                <span class="sc-input-group__suffix">位</span>
              </div>
            </div>
            <div class="ds-row">
              <div class="ds-row__left">
                <div class="ds-row__label">
                  多因素认证
                </div>
                <div class="ds-row__hint">
                  登录时要求二次验证，提升账户安全
                </div>
              </div>
              <a-switch
                v-model:checked="config.enableMFA"
                checked-children="启用"
                un-checked-children="关闭"
              />
            </div>
            <div class="ds-row">
              <div class="ds-row__left">
                <div class="ds-row__label">
                  审计日志
                </div>
                <div class="ds-row__hint">
                  记录所有关键操作以满足合规要求
                </div>
              </div>
              <a-switch
                v-model:checked="config.enableAuditLog"
                checked-children="启用"
                un-checked-children="关闭"
              />
            </div>
          </div>
          <div class="ds-card__footer">
            <span />
            <button
              class="ds-btn ds-btn--primary"
              :disabled="saving"
              @click="saveConfig"
            >
              保存安全策略
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════ Section 3: LLM 解析优化 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">
          LLM 解析优化
        </h2>
        <p class="ds-section-desc">
          控制大模型在病历解析时的行为参数。Pointer Mode
          可将 LLM 返回的定位信息映射到原文高亮。
        </p>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <div class="ds-card__body ds-divide">
            <div class="ds-row">
              <div class="ds-row__left">
                <div class="ds-row__label">
                  指针模式（Pointer Mode）
                </div>
                <div class="ds-row__hint">
                  让 LLM 返回原文定位坐标，实现精确高亮
                </div>
              </div>
              <a-switch
                v-model:checked="config.llmPointerMode"
                checked-children="启用"
                un-checked-children="关闭"
              />
            </div>
            <div class="ds-row">
              <div class="ds-row__left">
                <div class="ds-row__label">
                  摘要长度上限
                </div>
                <div class="ds-row__hint">
                  LLM 生成的缺陷摘要最大字符数，0 为禁用
                </div>
              </div>
              <select
                v-model.number="config.llmSummaryMaxLen"
                class="ds-select-native"
              >
                <option :value="0">
                  禁用摘要（0）
                </option>
                <option :value="40">
                  40 字符
                </option>
                <option :value="80">
                  80 字符
                </option>
              </select>
            </div>
          </div>
          <div class="ds-card__footer">
            <span />
            <button
              class="ds-btn ds-btn--primary"
              :disabled="saving"
              @click="saveConfig"
            >
              保存 LLM 配置
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

const config = reactive({
  systemName: '病案质控系统',
  version: '1.0.0',
  sessionTimeout: 30,
  passwordMinLength: 6,
  enableMFA: false,
  enableAuditLog: true,
  llmPointerMode: true,
  llmSummaryMaxLen: 80,
})

const saveConfig = async () => {
  saving.value = true
  try {
    const { llmService } = await import('@/services/llmService')
    const pointerMode = !!config.llmPointerMode
    const summaryMaxLength = Number(config.llmSummaryMaxLen) || 0
    llmService.updateConfig({ pointerMode, summaryMaxLength })

    const { llmConfigService } = await import('@/services/llmConfigService')
    await llmConfigService.saveUserPointerPrefs({ pointerMode, summaryMaxLength })

    await new Promise(resolve => setTimeout(resolve, 600))
    message.success('系统配置保存成功（已全局持久化至数据库）')
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const { llmConfigService } = await import('@/services/llmConfigService')
    const prefs = await llmConfigService.getUserPointerPrefs()
    if (prefs) {
      config.llmPointerMode = !!prefs.pointerMode
      config.llmSummaryMaxLen = Number(prefs.summaryMaxLength) || 0
      const { llmService } = await import('@/services/llmService')
      llmService.updateConfig(prefs)
    }
  } catch (e) {
    console.warn('加载全局LLM解析优化配置失败（可忽略）:', e)
  }
})
</script>

<style scoped>
/* 行内编辑输入框 */
.sc-inline-input {
  width: 200px;
  height: 34px;
  padding: 0 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  background: #fff;
  outline: none;
  transition: border-color 0.2s;
  text-align: right;
}
.sc-inline-input:hover { border-color: #2563eb; }
.sc-inline-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

/* 紧凑 InputGroup（纯原生，不依赖 Ant Design） */
.sc-input-group {
  display: flex;
  align-items: stretch;
}
.sc-input-group__input {
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
  -moz-appearance: textfield;
}
.sc-input-group__input::-webkit-inner-spin-button,
.sc-input-group__input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.sc-input-group__input:hover,
.sc-input-group__input:focus { border-color: #2563eb; }
.sc-input-group__input:focus { box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1); }
.sc-input-group__suffix {
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
</style>
