<!--
  临床质控演示平台主页面
  Clinical Workstation Demo - Main View
-->
<template>
  <div class="clinical-workstation-demo">
    <!-- Top Navigation Bar (Dark Mode) -->
    <header class="top-navbar">
      <div class="navbar-left">
        <!-- Logo -->
        <div class="logo">
          <svg
            class="logo-icon"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path d="M19 3H5C3.89543 3 3 3.89543 3 5V19C3 20.1046 3.89543 21 5 21H19C20.1046 21 21 20.1046 21 19V5C21 3.89543 20.1046 3 19 3ZM10 17H8V13H5V11H8V7H10V11H13V13H10V17ZM19 19H12V17H15V13H19V19Z" />
          </svg>
          <div class="brand-info">
            <span class="logo-text">灵医智慧</span>
            <span class="subtitle">临床质控工作站</span>
          </div>
        </div>

        <!-- Main Nav -->
        <nav class="main-nav">
          <a class="nav-item">门诊医生站</a>
          <a class="nav-item active">住院医生站</a>
          <a class="nav-item">医务管理</a>
          <a class="nav-item">统计报表</a>
        </nav>
      </div>

      <div class="navbar-right">
        <div class="tool-item">
          <span class="label">当前科室:</span>
          <span class="value">心血管内科</span>
          <DownOutlined class="arrow" />
        </div>
        
        <div class="divider" />
        
        <div class="user-profile">
          <a-avatar
            size="small"
            style="background-color: #1890ff"
          >
            李
          </a-avatar>
          <span class="username">李医生</span>
          <DownOutlined class="arrow" />
        </div>
        
        <div class="system-actions">
          <SettingOutlined class="action-icon" />
          <LogoutOutlined class="action-icon" />
        </div>
      </div>
    </header>

    <!-- Patient Info Banner -->
    <div
      v-if="store.currentCase"
      class="patient-banner"
    >
      <div class="patient-basic">
        <span class="name">{{ store.currentCase.patientInfo.name }}</span>
        <div class="tags">
          <span class="tag-item">{{ store.currentCase.patientInfo.gender }}</span>
          <span class="tag-item">{{ store.currentCase.patientInfo.age }}岁</span>
          <span class="tag-item highlight">ID: {{ store.currentCase.patientInfo.idNumber || '-' }}</span>
        </div>
      </div>
      
      <div class="patient-clinical">
        <div class="info-group">
          <span class="label">入院日期:</span>
          <span class="value">{{ store.currentCase.visitInfo.admissionDate }}</span>
        </div>
        <div class="info-group">
          <span class="label">费别:</span>
          <span class="value">医保</span>
        </div>
        <div class="info-group warning">
          <span class="label">过敏史:</span>
          <span class="value">无</span>
        </div>
        <div class="info-group diagnosis">
          <span class="label">诊断:</span>
          <span class="value">{{ store.currentCase.diagnosisInfo.diseaseType }}</span>
        </div>
      </div>
      
      <div class="banner-actions">
        <a-button
          type="primary"
          size="small"
          ghost
        >
          切换患者
        </a-button>
      </div>
    </div>

    <!-- Main Layout: 三栏布局 -->
    <div class="main-layout">
      <!-- Left Sidebar: 病例选择 + 文书导航 -->
      <aside class="left-sidebar">
        <div class="sidebar-section case-section">
          <CaseSelector />
        </div>
        <div class="sidebar-section document-section">
          <DocumentNavigator />
        </div>
      </aside>

      <!-- Center Content: 文书展示 -->
      <main class="center-content">
        <DocumentViewer />
      </main>

      <!-- Right Panel: 质控面板 -->
      <aside class="right-panel">
        <QCPanel />
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useClinicalWorkstationStore } from '@/stores/clinicalWorkstation'
import CaseSelector from './components/CaseSelector.vue'
import DocumentNavigator from './components/DocumentNavigator.vue'
import DocumentViewer from './components/DocumentViewer.vue'
import QCPanel from './components/QCPanel.vue'
import { 
  DownOutlined, 
  UserOutlined, 
  SettingOutlined,
  LogoutOutlined 
} from '@ant-design/icons-vue'

// ========== Store ==========
const store = useClinicalWorkstationStore()

// ========== Lifecycle ==========
onMounted(() => {
  // 初始化：加载预置病例
  store.initialize()
})
</script>

<style scoped lang="less">
.clinical-workstation-demo {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  background: #f0f2f5;

  // ========== 顶部导航栏 (Dark) ==========
  .top-navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 50px; // More compact
    background: #001529; // Dark Navy Blue
    padding: 0 20px;
    flex-shrink: 0;
    color: rgba(255, 255, 255, 0.85);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    z-index: 20;

    .navbar-left {
      display: flex;
      align-items: center;
      gap: 40px;

      .logo {
        display: flex;
        align-items: center;
        gap: 10px;

        .logo-icon {
          width: 26px;
          height: 26px;
          color: #1890ff;
        }
        
        .brand-info {
          display: flex;
          flex-direction: column;
          line-height: 1.2;

          .logo-text {
            font-size: 16px;
            font-weight: bold;
            color: #fff;
            letter-spacing: 1px;
          }
          
          .subtitle {
            font-size: 10px;
            color: rgba(255, 255, 255, 0.45);
            text-transform: uppercase;
          }
        }
      }

      .main-nav {
        display: flex;
        align-items: center;
        gap: 4px;

        .nav-item {
          font-size: 14px;
          color: rgba(255, 255, 255, 0.65);
          cursor: pointer;
          padding: 0 16px;
          height: 50px;
          line-height: 50px;
          transition: all 0.3s;

          &:hover {
            color: #fff;
            background: rgba(255, 255, 255, 0.08);
          }

          &.active {
            color: #fff;
            font-weight: 500;
            background: #1890ff;
          }
        }
      }
    }

    .navbar-right {
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 13px;

      .tool-item {
        display: flex;
        align-items: center;
        gap: 6px;
        cursor: pointer;
        padding: 4px 8px;
        border-radius: 4px;
        
        &:hover { background: rgba(255, 255, 255, 0.1); }
        
        .label { color: rgba(255, 255, 255, 0.45); }
        .value { color: #fff; }
        .arrow { font-size: 10px; color: rgba(255, 255, 255, 0.45); }
      }
      
      .divider {
        width: 1px;
        height: 14px;
        background: rgba(255, 255, 255, 0.2);
      }

      .user-profile {
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
        padding: 4px 8px;
        border-radius: 4px;
        
        &:hover { background: rgba(255, 255, 255, 0.1); }
        
        .username { color: #fff; }
        .arrow { font-size: 10px; color: rgba(255, 255, 255, 0.45); }
      }
      
      .system-actions {
        display: flex;
        gap: 12px;
        margin-left: 8px;
        
        .action-icon {
          font-size: 16px;
          color: rgba(255, 255, 255, 0.65);
          cursor: pointer;
          &:hover { color: #fff; }
        }
      }
    }
  }
  
  // ========== 患者信息栏 ==========
  .patient-banner {
    height: 48px;
    background: #fff;
    border-bottom: 1px solid #d9d9d9;
    display: flex;
    align-items: center;
    padding: 0 20px;
    flex-shrink: 0;
    gap: 32px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
    z-index: 10;
    
    .patient-basic {
      display: flex;
      align-items: baseline;
      gap: 12px;
      
      .name {
        font-size: 18px;
        font-weight: bold;
        color: #262626;
      }
      
      .tags {
        display: flex;
        gap: 8px;
        
        .tag-item {
          font-size: 13px;
          color: #595959;
          background: #f5f5f5;
          padding: 1px 8px;
          border-radius: 2px;
          border: 1px solid #e8e8e8;
          
          &.highlight {
            color: #0052CC;
            background: #f0f5ff;
            border-color: #adc6ff;
          }
        }
      }
    }
    
    .patient-clinical {
      flex: 1;
      display: flex;
      align-items: center;
      gap: 24px;
      
      .info-group {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        
        .label { color: #8c8c8c; }
        .value { color: #262626; font-weight: 500; }
        
        &.diagnosis {
          .value { color: #0052CC; }
        }
        
        &.warning {
          .value { color: #f5222d; }
        }
      }
    }
  }

  // ========== 主布局 ==========
  .main-layout {
    flex: 1;
    display: flex;
    overflow: hidden;
    
    // 左侧栏
    .left-sidebar {
      width: 250px; // Slightly wider for better readability
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      border-right: 1px solid #e8e8e8;
      background: #fff;

      .sidebar-section {
        overflow: hidden;

        &.case-section {
          height: 40%; // Adjusted ratio
          border-bottom: 1px solid #e8e8e8;
        }

        &.document-section {
          height: 60%;
        }
      }
    }

    // 中间内容
    .center-content {
      flex: 1;
      overflow: hidden;
      background: #f0f2f5; // Gray background for document container
      position: relative;
      padding: 16px; // Add padding around the document
    }

    // 右侧面板
    .right-panel {
      width: 420px; // Slightly wider for the new sidebar layout
      flex-shrink: 0;
      overflow: hidden;
      border-left: 1px solid #e8e8e8;
      background: #fff;
    }
  }
}
</style>
