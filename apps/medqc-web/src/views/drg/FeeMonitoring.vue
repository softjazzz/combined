<template>
  <div class="fee-monitoring">
    <a-page-header
      title="付费监测"
      sub-title="按DRG付费标准实时监测与修正建议"
      @back="() => $router.back()"
    />

    <div class="content-wrapper">
      <a-card
        :bordered="false"
        style="margin-bottom: 16px"
      >
        <a-space wrap>
          <a-segmented
            v-model:value="activeListTab"
            :options="listTabOptions"
          />
          <a-input
            v-model:value="keyword"
            allow-clear
            style="width: 260px"
            placeholder="搜索住院号/姓名/诊断"
          />
          <a-button
            :loading="loading"
            @click="loadData"
          >
            <ReloadOutlined />
            刷新
          </a-button>
          <a-button
            :loading="exporting"
            @click="handleExport"
          >
            <DownloadOutlined />
            导出清单
          </a-button>
        </a-space>
      </a-card>

      <a-card
        title="病例清单"
        :bordered="false"
      >
        <TableSkeleton
          v-if="loading"
          :rows="10"
          :columns="12"
        />
        <a-table
          v-else
          :columns="columns"
          :data-source="filteredRows"
          :pagination="{ pageSize: 10 }"
          :scroll="{ x: 2600 }"
          row-key="admission_id"
          :custom-row="customRow"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'groupingStatus'">
              <a-tag
                v-if="record.groupingStatus === 'grouped'"
                color="success"
              >
                入组成功
              </a-tag>
              <a-tag
                v-else
                color="error"
              >
                未入组
              </a-tag>
            </template>

            <template v-else-if="column.key === 'drg'">
              <span v-if="record.grouping">
                {{ record.grouping.drg_code }}
                <span style="color: #999">{{ record.grouping.drg_name }}</span>
              </span>
              <span v-else>-</span>
            </template>

            <template v-else-if="column.key === 'baseline'">
              <span v-if="typeof record.baselinePayment === 'number'">{{
                formatCurrency(record.baselinePayment)
              }}</span>
              <span v-else>-</span>
            </template>

            <template v-else-if="column.key === 'actualCost'">
              <span>{{ formatCurrency(record.actualCost) }}</span>
            </template>

            <template v-else-if="column.key === 'costRate'">
              <span v-if="typeof record.costRate === 'number'">
                <a-tag
                  :color="
                    record.costRate > 120 ? 'error' : record.costRate > 100 ? 'warning' : 'success'
                  "
                >
                  {{ formatPercentage(record.costRate, 2) }}
                </a-tag>
              </span>
              <span v-else>-</span>
            </template>

            <template v-else-if="column.key === 'profit'">
              <span
                v-if="typeof record.profitMargin === 'number'"
                :style="{ color: record.profitMargin >= 0 ? '#3f8600' : '#cf1322' }"
              >
                {{ formatCurrency(record.profitMargin) }}
              </span>
              <span v-else>-</span>
            </template>

            <template v-else-if="column.key === 'ungroupedReason'">
              <div class="cell-wrap">
                <div class="cell-ellipsis">
                  {{ record.ungroupedReason || '-' }}
                </div>
                <a-button
                  v-if="record.ungroupedReason"
                  type="link"
                  size="small"
                  @click.stop="openDrawer(record as FeeMonitoringRow, 'fix')"
                >
                  详情
                </a-button>
              </div>
            </template>

            <template v-else-if="column.key === 'fixSuggestion'">
              <div class="cell-wrap">
                <div class="cell-ellipsis">
                  {{ record.fixSuggestion || '-' }}
                </div>
                <a-button
                  v-if="record.fixSuggestion"
                  type="link"
                  size="small"
                  @click.stop="openDrawer(record as FeeMonitoringRow, 'fix')"
                >
                  详情
                </a-button>
              </div>
            </template>

            <template v-else-if="column.key === 'action'">
              <a-button
                type="link"
                size="small"
                @click.stop="openDrawer(record as FeeMonitoringRow)"
              >
                详情
              </a-button>
              <a-button
                type="link"
                size="small"
                @click.stop="goFix((record as FeeMonitoringRow).admission_id)"
              >
                去修正
              </a-button>
            </template>
          </template>
        </a-table>
      </a-card>

      <a-drawer
        v-model:open="drawerOpen"
        :title="drawerTitle"
        placement="right"
        :width="activeDrawerTab === 'feeDetail' ? 900 : 520"
        destroy-on-close
      >
        <template v-if="selectedRow">
          <div style="margin-bottom: 12px">
            <a-space>
              <a-tag
                v-if="selectedRow.groupingStatus === 'grouped'"
                color="success"
              >
                入组成功
              </a-tag>
              <a-tag
                v-else
                color="error"
              >
                未入组
              </a-tag>
              <a-tag
                v-if="activeListTab === 'loss'"
                color="error"
              >
                亏损
              </a-tag>
              <a-tag
                v-else-if="activeListTab === 'highRate'"
                color="warning"
              >
                高倍率
              </a-tag>
              <a-tag
                v-else-if="activeListTab === 'base'"
                color="processing"
              >
                基础组
              </a-tag>
              <a-tag
                v-else-if="activeListTab === 'ungrouped'"
                color="default"
              >
                未入组
              </a-tag>
              <a-tag
                v-else
                color="default"
              >
                更优推荐
              </a-tag>
            </a-space>
          </div>

          <div class="drawer-kpi">
            <div class="kpi-top">
              <div class="kpi-left">
                <div class="kpi-drg">
                  <div class="kpi-label">
                    DRG组
                  </div>
                  <div class="kpi-value">
                    <template v-if="selectedRow.grouping">
                      <span class="kpi-drg-code">{{ selectedRow.grouping.drg_code }}</span>
                      <span class="kpi-drg-name">{{ selectedRow.grouping.drg_name }}</span>
                    </template>
                    <template v-else>
                      <span class="kpi-drg-name">未入组</span>
                    </template>
                  </div>
                </div>

                <div class="kpi-row">
                  <div class="kpi-item">
                    <div class="kpi-label">
                      权重
                    </div>
                    <div class="kpi-value">
                      <span v-if="selectedRow.grouping">{{
                        formatWeight(selectedRow.grouping.weight)
                      }}</span>
                      <span v-else>-</span>
                    </div>
                  </div>
                  <div class="kpi-item">
                    <div class="kpi-label">
                      付费标准
                    </div>
                    <div class="kpi-value">
                      <span v-if="typeof selectedRow.baselinePayment === 'number'">{{
                        formatCurrency(selectedRow.baselinePayment)
                      }}</span>
                      <span v-else>-</span>
                    </div>
                  </div>
                </div>

                <div class="kpi-row">
                  <div class="kpi-item">
                    <div class="kpi-label">
                      医疗总费用
                    </div>
                    <div class="kpi-value">
                      {{ formatCurrency(selectedRow.actualCost) }}
                    </div>
                  </div>
                  <div class="kpi-item">
                    <div class="kpi-label">
                      盈亏
                    </div>
                    <div
                      class="kpi-value"
                      :style="{
                        color:
                          typeof selectedRow.profitMargin === 'number' &&
                          selectedRow.profitMargin < 0
                            ? '#cf1322'
                            : '#3f8600',
                      }"
                    >
                      <span v-if="typeof selectedRow.profitMargin === 'number'">{{
                        formatCurrency(selectedRow.profitMargin)
                      }}</span>
                      <span v-else>-</span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="kpi-right">
                <div class="kpi-bar">
                  <div class="kpi-bar-title">
                    <span>支付率</span>
                    <span class="kpi-bar-value">
                      <span v-if="typeof selectedRow.costRate === 'number'">{{
                        formatPercentage(selectedRow.costRate, 2)
                      }}</span>
                      <span v-else>-</span>
                    </span>
                  </div>
                  <a-progress
                    :percent="
                      typeof selectedRow.costRate === 'number'
                        ? Math.min(100, selectedRow.costRate)
                        : 0
                    "
                    :status="
                      typeof selectedRow.costRate === 'number' && selectedRow.costRate > 120
                        ? 'exception'
                        : 'active'
                    "
                    size="small"
                    :show-info="false"
                  />
                </div>

                <div
                  v-if="
                    typeof selectedRow.profitMargin === 'number' &&
                      typeof selectedRow.baselinePayment === 'number'
                  "
                  class="kpi-bar"
                >
                  <div class="kpi-bar-title">
                    <span>亏损</span>
                    <span
                      class="kpi-bar-value"
                      style="color: #cf1322"
                    >
                      {{ formatCurrency(Math.max(0, -selectedRow.profitMargin)) }}
                    </span>
                  </div>
                  <a-progress
                    :percent="
                      Math.min(
                        100,
                        (Math.max(0, -selectedRow.profitMargin) /
                          Math.max(1, selectedRow.baselinePayment)) *
                          100,
                      )
                    "
                    status="exception"
                    size="small"
                    :show-info="false"
                  />
                </div>
              </div>
            </div>
          </div>

          <a-tabs
            v-model:active-key="activeDrawerTab"
            type="card"
          >
            <a-tab-pane
              key="basic"
              tab="基本信息"
            >
              <a-descriptions
                bordered
                size="small"
                :column="1"
              >
                <a-descriptions-item label="住院号">
                  {{ selectedRow.admission_id }}
                </a-descriptions-item>
                <a-descriptions-item label="姓名">
                  {{ selectedRow.patient_name }}
                </a-descriptions-item>
                <a-descriptions-item label="性别/年龄">
                  {{ getGenderText(selectedRow.patient_gender) }} / {{ selectedRow.patient_age }}岁
                </a-descriptions-item>
                <a-descriptions-item label="主要诊断">
                  {{ selectedRow.primary_diagnosis_code }} {{ selectedRow.primary_diagnosis_name }}
                </a-descriptions-item>
                <a-descriptions-item label="主要手术">
                  <span v-if="selectedRow.main_procedure_code">
                    {{ selectedRow.main_procedure_code }} {{ selectedRow.main_procedure_name }}
                  </span>
                  <span v-else>-</span>
                </a-descriptions-item>
                <a-descriptions-item label="当前医疗总费用">
                  {{ formatCurrency(selectedRow.actualCost) }}
                </a-descriptions-item>
                <a-descriptions-item label="预估医保支付价格">
                  <span v-if="typeof selectedRow.baselinePayment === 'number'">{{
                    formatCurrency(selectedRow.baselinePayment)
                  }}</span>
                  <span v-else>-</span>
                </a-descriptions-item>
                <a-descriptions-item label="医保支付率检测">
                  <span v-if="typeof selectedRow.costRate === 'number'">
                    <a-progress
                      :percent="Math.min(100, selectedRow.costRate)"
                      size="small"
                    />
                  </span>
                  <span v-else>-</span>
                </a-descriptions-item>
              </a-descriptions>

              <a-divider style="margin: 12px 0" />

              <a-collapse>
                <a-collapse-panel
                  key="complete"
                  :header="`诊断及手术操作完整性`"
                >
                  <a-space
                    direction="vertical"
                    style="width: 100%"
                  >
                    <a-alert
                      type="success"
                      show-icon
                      message="入组核心要素校验通过（演示）"
                    />
                  </a-space>
                </a-collapse-panel>

                <a-collapse-panel
                  key="accuracy"
                  :header="`编码准确性`"
                >
                  <a-space
                    direction="vertical"
                    style="width: 100%"
                  >
                    <a-alert
                      type="info"
                      show-icon
                      message="编码准确性校验：演示占位"
                    />
                  </a-space>
                </a-collapse-panel>

                <a-collapse-panel
                  key="order"
                  :header="`诊断/手术顺序推荐`"
                >
                  <a-space
                    direction="vertical"
                    style="width: 100%"
                  >
                    <div class="recommend-row">
                      <div class="recommend-title">
                        诊断顺序推荐
                      </div>
                      <a-space>
                        <a-tag color="blue">
                          C98.200
                        </a-tag>
                        <a-button
                          size="small"
                          @click="copyText('C98.200')"
                        >
                          <CopyOutlined />
                          复制
                        </a-button>
                        <a-button
                          size="small"
                          @click="showEvidence"
                        >
                          查看依据
                        </a-button>
                      </a-space>
                    </div>

                    <div class="recommend-row">
                      <div class="recommend-title">
                        手术操作顺序推荐
                      </div>
                      <a-space>
                        <a-tag color="blue">
                          09.2300
                        </a-tag>
                        <a-button
                          size="small"
                          @click="copyText('09.2300')"
                        >
                          <CopyOutlined />
                          复制
                        </a-button>
                        <a-button
                          size="small"
                          @click="showEvidence"
                        >
                          查看依据
                        </a-button>
                      </a-space>
                    </div>
                  </a-space>
                </a-collapse-panel>

                <a-collapse-panel
                  key="grouping"
                  header="DRG入组结果"
                >
                  <div v-if="selectedRow.grouping">
                    <a-descriptions
                      bordered
                      size="small"
                      :column="1"
                    >
                      <a-descriptions-item label="DRG组名">
                        {{ selectedRow.grouping.drg_name }}
                      </a-descriptions-item>
                      <a-descriptions-item label="DRG组权重">
                        {{ formatWeight(selectedRow.grouping.weight) }}
                      </a-descriptions-item>
                      <a-descriptions-item label="DRG成本系数">
                        -
                      </a-descriptions-item>
                      <a-descriptions-item label="DRG医疗总费用上限">
                        -
                      </a-descriptions-item>
                    </a-descriptions>
                  </div>
                  <div v-else>
                    <a-alert
                      type="error"
                      show-icon
                      message="未入组（演示）：主要诊断与主要手术不一致"
                    />
                  </div>
                </a-collapse-panel>
              </a-collapse>
            </a-tab-pane>

            <a-tab-pane
              key="feeDetail"
              tab="费用详情"
            >
              <!-- 骨架屏加载状态 -->
              <div
                v-if="loading"
                class="fee-dashboard-skeleton"
              >
                <!-- 第一行：核心指标骨架屏 -->
                <a-row :gutter="16">
                  <a-col
                    v-for="i in 3"
                    :key="i"
                    :span="8"
                  >
                    <div class="stat-card skeleton">
                      <a-skeleton
                        active
                        :paragraph="{ rows: 1 }"
                        :title="{ width: '40%' }"
                      />
                    </div>
                  </a-col>
                </a-row>

                <!-- 第二行：图表分析骨架屏 -->
                <a-row
                  :gutter="16"
                  style="margin-top: 16px"
                >
                  <a-col :span="14">
                    <a-card
                      size="small"
                      :bordered="false"
                      class="chart-card"
                    >
                      <template #title>
                        <a-skeleton-button
                          active
                          size="small"
                          :style="{ width: '120px' }"
                        />
                      </template>
                      <div
                        style="
                          height: 320px;
                          display: flex;
                          align-items: center;
                          justify-content: center;
                          background: #fafafa;
                          border-radius: 8px;
                        "
                      >
                        <a-skeleton-image />
                      </div>
                    </a-card>
                  </a-col>
                  <a-col :span="10">
                    <a-card
                      size="small"
                      :bordered="false"
                      class="chart-card"
                    >
                      <template #title>
                        <a-skeleton-button
                          active
                          size="small"
                          :style="{ width: '120px' }"
                        />
                      </template>
                      <div
                        style="
                          height: 320px;
                          display: flex;
                          align-items: center;
                          justify-content: center;
                          background: #fafafa;
                          border-radius: 8px;
                        "
                      >
                        <a-skeleton-avatar
                          :size="120"
                          active
                          shape="circle"
                        />
                      </div>
                    </a-card>
                  </a-col>
                </a-row>

                <!-- 第三行：高值耗材骨架屏 -->
                <a-card
                  size="small"
                  :bordered="false"
                  class="chart-card"
                  style="margin-top: 16px"
                >
                  <template #title>
                    <a-skeleton-button
                      active
                      size="small"
                      :style="{ width: '120px' }"
                    />
                  </template>
                  <a-row :gutter="16">
                    <a-col
                      v-for="i in 3"
                      :key="i"
                      :span="8"
                    >
                      <div
                        style="
                          height: 120px;
                          background: #fafafa;
                          border-radius: 8px;
                          padding: 16px;
                        "
                      >
                        <a-skeleton
                          active
                          avatar
                          :paragraph="{ rows: 2 }"
                        />
                      </div>
                    </a-col>
                  </a-row>
                </a-card>
              </div>

              <!-- 实际内容 -->
              <div
                v-else
                class="fee-dashboard"
              >
                <!-- 第一行：核心指标 -->
                <a-row :gutter="16">
                  <a-col :span="8">
                    <div class="stat-card blue">
                      <div class="stat-label">
                        医疗总费用
                      </div>
                      <div class="stat-value">
                        ¥{{ formatCurrency(selectedRow?.actualCost || 0) }}
                      </div>
                      <div
                        v-if="selectedRow?.grouping"
                        class="stat-trend"
                      >
                        <span>参考标准: {{ formatCurrency(selectedRow?.baselinePayment || 0) }}</span>
                      </div>
                    </div>
                  </a-col>
                  <a-col :span="8">
                    <div class="stat-card purple">
                      <div class="stat-label">
                        医保支付率
                      </div>
                      <div class="stat-value">
                        {{ formatPercentage(selectedRow?.costRate || 0, 1) }}
                      </div>
                      <div class="stat-bar">
                        <a-progress
                          :percent="Math.min(100, selectedRow?.costRate || 0)"
                          :show-info="false"
                          :stroke-color="{ '0%': '#9254de', '100%': '#b37feb' }"
                          size="small"
                        />
                      </div>
                    </div>
                  </a-col>
                  <a-col :span="8">
                    <div
                      class="stat-card"
                      :class="
                        typeof selectedRow?.profitMargin === 'number' &&
                          selectedRow.profitMargin < 0
                          ? 'red'
                          : 'green'
                      "
                    >
                      <div class="stat-label">
                        预估盈亏
                      </div>
                      <div class="stat-value">
                        {{
                          typeof selectedRow?.profitMargin === 'number'
                            ? selectedRow.profitMargin > 0
                              ? '+'
                              : ''
                            : ''
                        }}
                        {{ formatCurrency(selectedRow?.profitMargin) }}
                      </div>
                      <div class="stat-trend">
                        <span
                          v-if="
                            typeof selectedRow?.profitMargin === 'number' &&
                              selectedRow.profitMargin < 0
                          "
                        >
                          建议重点管控高值耗材
                        </span>
                        <span v-else>费用控制良好</span>
                      </div>
                    </div>
                  </a-col>
                </a-row>

                <!-- 第二行：图表分析 -->
                <a-row
                  :gutter="16"
                  style="margin-top: 16px"
                >
                  <a-col :span="14">
                    <a-card
                      size="small"
                      :bordered="false"
                      class="chart-card"
                    >
                      <template #title>
                        <div class="card-title">
                          费用累计趋势
                        </div>
                      </template>
                      <FeeTrendChart
                        v-if="feeTrend.length > 0"
                        :trend="feeTrend"
                        :baseline-payment="selectedRow?.baselinePayment || null"
                      />
                      <a-empty
                        v-else
                        description="暂无数据"
                        :image="Empty.PRESENTED_IMAGE_SIMPLE"
                      />
                    </a-card>
                  </a-col>
                  <a-col :span="10">
                    <a-card
                      size="small"
                      :bordered="false"
                      class="chart-card"
                    >
                      <template #title>
                        <div class="card-title">
                          费用构成分析
                        </div>
                      </template>
                      <FeeCompositionChart
                        v-if="feeComposition"
                        :composition="feeComposition"
                      />
                      <a-empty
                        v-else
                        description="暂无数据"
                        :image="Empty.PRESENTED_IMAGE_SIMPLE"
                      />
                    </a-card>
                  </a-col>
                </a-row>

                <!-- 第三行：高值耗材 -->
                <a-card
                  size="small"
                  :bordered="false"
                  class="chart-card"
                  style="margin-top: 16px"
                >
                  <template #title>
                    <div class="card-title">
                      高值耗材清单
                    </div>
                  </template>
                  <HighValueMaterialsList :materials="highValueMaterials" />
                </a-card>
              </div>
            </a-tab-pane>

            <a-tab-pane
              key="fix"
              tab="修正建议"
            >
              <a-space
                direction="vertical"
                style="width: 100%"
              >
                <a-alert
                  v-if="selectedRow.groupingStatus !== 'grouped'"
                  type="error"
                  show-icon
                  message="未入组"
                  :description="`原因：${selectedRow.ungroupedReason || '—'}`"
                />

                <a-card
                  size="small"
                  title="入组详情建议"
                  :bordered="false"
                >
                  <a-space
                    direction="vertical"
                    style="width: 100%"
                    size="middle"
                  >
                    <div
                      v-for="(item, index) in drawerSuggestions"
                      :key="`${index}-${item.title}`"
                      class="suggestion-item"
                    >
                      <div class="suggestion-index">
                        {{ index + 1 }}
                      </div>
                      <div class="suggestion-main">
                        <div class="suggestion-title">
                          {{ item.title }}
                        </div>
                        <a-typography-paragraph
                          :ellipsis="{ rows: 2, expandable: true }"
                          style="margin-bottom: 8px"
                        >
                          {{ item.description }}
                        </a-typography-paragraph>
                        <a-space>
                          <a-button
                            size="small"
                            @click="showSuggestionDetail(item.title, item.description)"
                          >
                            详情
                          </a-button>
                          <a-button
                            size="small"
                            @click="copyText(item.description)"
                          >
                            <CopyOutlined />
                            复制
                          </a-button>
                          <a-button
                            size="small"
                            type="primary"
                            @click="goFix(selectedRow!.admission_id)"
                          >
                            去修正
                          </a-button>
                        </a-space>
                      </div>
                    </div>
                  </a-space>
                </a-card>

                <a-card
                  size="small"
                  title="更多建议"
                  :bordered="false"
                >
                  <a-space
                    direction="vertical"
                    style="width: 100%"
                    size="middle"
                  >
                    <div
                      v-for="(item, index) in drawerMoreSuggestions"
                      :key="`${index}-${item.title}`"
                      class="suggestion-item"
                    >
                      <div class="suggestion-index">
                        {{ index + 1 }}
                      </div>
                      <div class="suggestion-main">
                        <div class="suggestion-title">
                          {{ item.title }}
                        </div>
                        <a-typography-paragraph
                          :ellipsis="{ rows: 2, expandable: true }"
                          style="margin-bottom: 8px"
                        >
                          {{ item.description }}
                        </a-typography-paragraph>
                        <a-space>
                          <a-button
                            size="small"
                            @click="showSuggestionDetail(item.title, item.description)"
                          >
                            详情
                          </a-button>
                          <a-button
                            size="small"
                            @click="copyText(item.description)"
                          >
                            <CopyOutlined />
                            复制
                          </a-button>
                          <a-button
                            size="small"
                            type="primary"
                            @click="goFix(selectedRow!.admission_id)"
                          >
                            去修正
                          </a-button>
                        </a-space>
                      </div>
                    </div>
                  </a-space>
                </a-card>

                <a-modal
                  v-model:open="suggestionDetailOpen"
                  :title="suggestionDetailTitle"
                  :footer="null"
                  width="640"
                >
                  <div style="white-space: pre-wrap">
                    {{ suggestionDetailContent }}
                  </div>
                </a-modal>
              </a-space>
            </a-tab-pane>
          </a-tabs>
        </template>
      </a-drawer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { message, Empty } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import {
  CopyOutlined,
  ReloadOutlined,
  WarningOutlined,
  DownloadOutlined,
} from '@ant-design/icons-vue'
import type { FeeMonitoringRow } from '@/types/drg-fee'
import { useFeeMonitoring } from '@/composables/drg/useFeeMonitoring'
import { exportToExcel } from '@/utils/export'
import FeeCompositionChart from '@/components/drg/FeeCompositionChart.vue'
import FeeTrendChart from '@/components/drg/FeeTrendChart.vue'
import HighValueMaterialsList from '@/components/drg/HighValueMaterialsList.vue'
import TableSkeleton from '@/components/common/TableSkeleton.vue'
import {
  formatCurrency,
  formatDateTime,
  formatPercentage,
  formatWeight,
  getGenderText,
} from '@/utils/drg'

const {
  loading,
  keyword,
  activeListTab,
  drawerOpen,
  selectedRow,
  activeDrawerTab,
  feeComposition,
  feeTrend,
  highValueMaterials,
  feeWarningRecords,
  loadData,
  filteredRows,
  openDrawer,
  goFix,
} = useFeeMonitoring()

const listTabOptions = [
  { label: '亏损', value: 'loss' },
  { label: '高倍率', value: 'highRate' },
  { label: '基础组', value: 'base' },
  { label: '更优推荐', value: 'better' },
  { label: '未入组', value: 'ungrouped' },
]

const columns: TableColumnsType<FeeMonitoringRow> = [
  { title: '住院号', dataIndex: 'admission_id', width: 160 },
  { title: '出院科室', dataIndex: 'department', width: 140 },
  { title: '姓名', dataIndex: 'patient_name', width: 110 },
  {
    title: '主要诊断',
    dataIndex: 'primary_diagnosis_name',
    width: 260,
    ellipsis: true,
    customRender: ({ record }: any) =>
      `${record.primary_diagnosis_code || ''} ${record.primary_diagnosis_name || ''}`,
  },
  {
    title: '入院时间',
    dataIndex: 'admitAt',
    width: 160,
    customRender: ({ text }: any) => formatDateTime(text),
  },
  {
    title: '出院时间',
    dataIndex: 'dischargeAt',
    width: 160,
    customRender: ({ text }: any) => formatDateTime(text),
  },
  {
    title: '入组状态',
    key: 'groupingStatus',
    width: 100,
    slots: { customRender: 'groupingStatus' },
  },
  { title: 'DRG', key: 'drg', width: 260, slots: { customRender: 'drg' } },
  {
    title: '是否命中基础组',
    dataIndex: 'isBaseGroup',
    width: 140,
    customRender: ({ text }: any) => (text === true ? '是' : text === false ? '否' : '-'),
  },
  {
    title: '结算类型',
    dataIndex: 'settlementType',
    width: 140,
  },
  {
    title: '结算办法',
    dataIndex: 'settlementMethod',
    width: 140,
  },
  { title: '付费标准', key: 'baseline', width: 140, slots: { customRender: 'baseline' } },
  { title: '医疗总费用', key: 'actualCost', width: 140, slots: { customRender: 'actualCost' } },
  {
    title: '个人自费(元)',
    dataIndex: 'selfPay',
    width: 140,
    customRender: ({ text }: any) => formatCurrency(text),
  },
  { title: '支付率', key: 'costRate', width: 120, slots: { customRender: 'costRate' } },
  { title: '盈亏', key: 'profit', width: 140, slots: { customRender: 'profit' } },
  {
    title: '未入组原因',
    key: 'ungroupedReason',
    width: 240,
    slots: { customRender: 'ungroupedReason' },
  },
  {
    title: '修正建议',
    key: 'fixSuggestion',
    width: 320,
    slots: { customRender: 'fixSuggestion' },
  },
  {
    title: '操作',
    key: 'action',
    width: 140,
    fixed: 'right' as const,
    slots: { customRender: 'action' },
  },
]

const exporting = ref(false)

const handleExport = async () => {
  if (filteredRows.value.length === 0) {
    message.warning('暂无数据可导出')
    return
  }

  exporting.value = true
  try {
    const dateTag = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    const fileName = `费用监测清单_${activeListTab.value}_${dateTag}`

    const headerMap: Record<string, string> = {
      admission_id: '住院号',
      department: '科室',
      patient_name: '姓名',
      primary_diagnosis_name: '主要诊断',
      admitAt: '入院时间',
      drg_code: 'DRG编码',
      baselinePayment: '付费标准(元)',
      actualCost: '医疗总费用(元)',
      costRate: '支付率',
      profitMargin: '盈亏(元)',
      ungroupedReason: '未入组原因',
      fixSuggestion: '修正建议',
    }

    // 处理数据格式，特别是嵌套对象和日期
    const exportData = filteredRows.value.map((row) => ({
      ...row,
      drg_code: row.grouping?.drg_code || '-',
      admitAt: formatDateTime(row.admitAt),
      costRate: typeof row.costRate === 'number' ? formatPercentage(row.costRate) : '-',
    }))

    exportToExcel(exportData, fileName, '费用清单', headerMap)
    message.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    message.error('导出失败')
  } finally {
    exporting.value = false
  }
}

const suggestionDetailOpen = ref(false)
const suggestionDetailTitle = ref('')
const suggestionDetailContent = ref('')

const drawerTitle = computed(() => {
  if (!selectedRow.value) return '付费监测'
  return `付费监测 - ${selectedRow.value.patient_name}（${selectedRow.value.admission_id}）`
})

const drawerSuggestions = computed(() => {
  if (!selectedRow.value) return []
  if (selectedRow.value.groupingStatus === 'grouped') {
    return [
      {
        title: '存在更优入组选项（演示）',
        description:
          '当前编码可能导致入组不稳定，建议核对主要诊断/主要手术是否一致，并检查并发症标记。',
      },
    ]
  }

  return [
    {
      title: '补充/修正主要手术或主要诊断',
      description:
        '在忽略此手术操作代码的情况下，可以入到相关的DRG组。建议核对“主要手术或操作”是否填写正确。',
    },
    {
      title: '修正主要手术或操作为“主要手术或操作”',
      description: '如果主要手术未被选择为“主要手术或操作”，仍然无法预入组。',
    },
    {
      title: '找相似度最高3个手术操作',
      description: '可用于替换：腹腔镜下阑门肌层切开术 / 腹腔镜下胃病损切除术 / …（演示占位）',
    },
  ]
})

const drawerMoreSuggestions = computed(() => {
  if (!selectedRow.value) return []
  return [
    {
      title: '以更合适的主要诊断尝试入组（演示）',
      description:
        '若以“创伤性蛛网膜下出血（S06.600）”为主要诊断，可尝试入组ZB19（多发性严重创伤开胸术）等。',
    },
    {
      title: '关注费用消耗与高值耗材',
      description: '支付率接近或超过100%时，建议提前控制关键费用结构，并关注后续医疗行为。',
    },
  ]
})

const showSuggestionDetail = (title: string, content: string) => {
  suggestionDetailTitle.value = title
  suggestionDetailContent.value = content
  suggestionDetailOpen.value = true
}

const customRow = (record: FeeMonitoringRow) => {
  return {
    onClick: () => openDrawer(record),
  }
}

const copyText = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制')
  } catch {
    message.info(text)
  }
}

const showEvidence = () => {
  message.info('演示：此处将展示病历原文证据片段并支持定位')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.fee-monitoring {
  .content-wrapper {
    padding: 16px;
  }

  .recommend-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 8px 0;
  }

  .recommend-title {
    font-weight: 500;
  }

  .cell-wrap {
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }

  .cell-ellipsis {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .suggestion-item {
    display: flex;
    gap: 12px;
    padding: 12px;
    border: 1px solid #f0f0f0;
    border-radius: 8px;
    background: #fff;
  }

  .suggestion-index {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #2b6cf6;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    flex: 0 0 28px;
  }

  .suggestion-main {
    flex: 1;
    min-width: 0;
  }

  .suggestion-title {
    font-weight: 600;
    margin-bottom: 4px;
    color: #1f1f1f;
  }
}

.fee-dashboard {
  .stat-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 16px;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all 0.3s;
    border: 1px solid #f0f0f0;

    &:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
      border-color: #e6f7ff;
      background: #fff;
    }

    &.blue {
      background: linear-gradient(135deg, #e6f7ff 0%, #f0f5ff 100%);
      border-color: #adc6ff;
    }
    &.purple {
      background: linear-gradient(135deg, #f9f0ff 0%, #f3e6ff 100%);
      border-color: #d3adf7;
    }
    &.red {
      background: linear-gradient(135deg, #fff1f0 0%, #fff2e8 100%);
      border-color: #ffccc7;
    }
    &.green {
      background: linear-gradient(135deg, #f6ffed 0%, #e6fffb 100%);
      border-color: #b7eb8f;
    }

    .stat-label {
      font-size: 13px;
      color: #8c8c8c;
      margin-bottom: 8px;
    }

    .stat-value {
      font-size: 24px;
      font-weight: 600;
      color: #262626;
      font-family:
        'Din Alternate',
        -apple-system,
        BlinkMacSystemFont,
        sans-serif;
      margin-bottom: 8px;
    }

    .stat-trend {
      font-size: 12px;
      color: #595959;
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .stat-bar {
      margin-top: 4px;
    }
  }

  .chart-card {
    background: #fff;
    border: 1px solid #f0f0f0;
    border-radius: 8px;
    transition: all 0.3s;

    &:hover {
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
      border-color: #e6f7ff;
    }

    :deep(.ant-card-head) {
      min-height: 48px;
      padding: 0 16px;
      border-bottom: 1px solid #f5f5f5;

      .ant-card-head-title {
        padding: 12px 0;
      }
    }

    .card-title {
      font-weight: 600;
      font-size: 14px;
      color: #1f1f1f;
      display: flex;
      align-items: center;

      &::before {
        content: '';
        display: block;
        width: 3px;
        height: 14px;
        background: #2b6cf6;
        margin-right: 8px;
        border-radius: 2px;
      }
    }
  }
}
</style>
