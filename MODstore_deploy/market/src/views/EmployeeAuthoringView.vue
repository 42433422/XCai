<template>
  <div :class="['employee-authoring', isFullscreenMode ? 'employee-authoring--fullscreen' : '']">
    <div class="page-header">
      <div class="page-hero">
        <div>
          <h1 class="page-title">员工制作工作台</h1>
          <p class="page-desc">统一完成设计、打包、测试、审核、上架，形成可复用的 AI 员工资产。</p>
          <div class="hero-chips">
            <span class="hero-chip">Whiteboard Builder</span>
            <span class="hero-chip">Package Pipeline</span>
            <span class="hero-chip">Sandbox + Audit</span>
            <span class="hero-chip">Catalog Listing</span>
          </div>
        </div>
        <div class="hero-metrics">
          <div class="metric-card">
            <span class="metric-label">当前阶段</span>
            <strong>{{ cardModeEnabled ? '并行卡片' : `步骤 ${currentStep + 1}` }}</strong>
          </div>
          <div class="metric-card">
            <span class="metric-label">V2 校验</span>
            <strong :class="employeeConfigErrors.length ? 'metric-warn' : 'metric-ok'">{{ employeeConfigErrors.length ? '待修复' : '已通过' }}</strong>
          </div>
          <div class="metric-card">
            <span class="metric-label">Workflow 心脏</span>
            <strong :class="safeResolvedWorkflowId > 0 ? 'metric-ok' : 'metric-warn'">{{ safeResolvedWorkflowId > 0 ? `#${safeResolvedWorkflowId}` : '未配置' }}</strong>
          </div>
        </div>
      </div>
      <aside class="guide-inline" aria-label="与 XCAGI manifest 的对应关系">
        <p v-if="showGuideInline">
          宿主侧「全局员工包」对应 manifest 中 <code>artifact: &quot;employee_pack&quot;</code>，安装至
          <code>mods/_employees/&lt;pack_id&gt;/</code>；普通 Mod 内的自动化卡片由
          <code>workflow_employees[]</code> 声明。完整字段见宿主仓库 <strong>MOD_AUTHORING_GUIDE.md</strong> §11、§14。
          若只需把声明落成可下载的 <code class="mono">employee_pack</code> 并登记到本地 <code class="mono">/v1/packages</code>，可在<strong>Mod 源码库</strong>或<strong>Mod 制作页</strong>对应条目旁使用「一键登记」；依赖 Mod 内 Python 电话路由时仍建议在本页走导出与向导。
        </p>
        <button type="button" class="btn btn-sm" @click="showGuideInline = !showGuideInline">
          {{ showGuideInline ? '收起说明' : '展开详细说明' }}
        </button>
      </aside>
    </div>

    <div v-if="showSessionSaveHint" class="session-save-hint" role="status">
      <span>编排内容主要保存在本页会话；对外分发请用「上传打包」「发布上架」或「导出员工包」生成可安装资产。</span>
      <button type="button" class="btn btn-sm" @click="showSessionSaveHint = false">知道了</button>
    </div>

    <div class="workbench-toolbar">
      <button type="button" class="btn btn-sm" @click="goBackWorkbench">返回工作台</button>
      <button type="button" class="btn btn-sm btn-primary" @click="toggleFullscreen">
        {{ isFullscreenMode ? '退出全屏' : '进入全屏' }}
      </button>
      <button type="button" class="btn btn-sm" @click="togglePanel('package')">上传打包</button>
      <button type="button" class="btn btn-sm" @click="togglePanel('testing')">测试审核</button>
      <button type="button" class="btn btn-sm" @click="togglePanel('publish')">发布上架</button>
      <button type="button" class="btn btn-sm" @click="togglePanel('employees')">员工列表</button>
      <button type="button" class="btn btn-sm" @click="togglePanel('help')">帮助</button>
      <button
        type="button"
        class="btn btn-sm btn-toolbar-danger"
        :disabled="openPanelCount <= 0"
        @click="closeAllPanels"
      >
        {{ openPanelCount > 0 ? `收起全部(${openPanelCount})` : '收起全部' }}
      </button>
    </div>

    <div v-if="showOnboarding" class="onboarding-mask" @click.self="skipOnboarding">
      <div class="onboarding-card">
        <h3>上手引导（{{ onboardingStep + 1 }}/{{ onboardingSteps.length }}）</h3>
        <p class="onboarding-title">{{ currentOnboarding.title }}</p>
        <p class="onboarding-desc">{{ currentOnboarding.desc }}</p>
        <div class="ops">
          <button type="button" class="btn" :disabled="onboardingStep <= 0" @click="prevOnboardingStep">上一步</button>
          <button type="button" class="btn" @click="skipOnboarding">跳过</button>
          <button v-if="onboardingStep < onboardingSteps.length - 1" type="button" class="btn btn-primary" @click="nextOnboardingStep">下一步</button>
          <button v-else type="button" class="btn btn-primary" @click="finishOnboarding">完成</button>
        </div>
      </div>
    </div>

    <div :class="['authoring-grid', isFullscreenMode ? 'authoring-grid--fullscreen' : '']">
      <div class="authoring-form-section workbench-surface">
        <section id="builder-section" class="employee-v2-wizard">
          <Step0TemplateSelect :template-id="employeeTemplateId" @change="applyTemplate" />
          <div class="workbench-header">
            <div>
              <h2 class="section-title section-title--tight">员工制作工作台</h2>
              <p class="workbench-subtitle">三栏编排（模块库 / 画布 / 属性）+ 并行卡片（包文件 / 测试 / 发布）</p>
            </div>
            <div class="workbench-badges">
              <span class="wb-badge">Build</span>
              <span class="wb-badge">Package</span>
              <span class="wb-badge">Audit</span>
              <span class="wb-badge">Publish</span>
            </div>
          </div>
          <EmployeeBlockBuilder
            :config="employeeConfigV2"
            :template-id="employeeTemplateId"
            :guide-target="activeGuideTarget"
            :immersive="true"
            @update:config="onBuilderConfigUpdate"
            @template-change="applyTemplate"
            @export-zip="exportBuilderEmployeePackZip"
          />
          <p v-if="employeeConfigErrors.length" class="flash flash-warn">V2 校验：{{ employeeConfigErrors.join('；') }}</p>
        </section>

        <section v-if="linkedModId && showLinkedModPanel" class="linked-mod-panel">
          <h2 class="section-title section-title--tight">来自 Mod 库的工作流声明</h2>
          <p class="linked-mod-meta">
            <span class="mono">{{ linkedModId }}</span>
            <span v-if="linkedModName"> · {{ linkedModName }}</span>
            · manifest.artifact：<strong>{{ linkedModArtifact }}</strong>
            · <code class="mono">workflow_employees[{{ linkedWorkflowIndex }}]</code>
          </p>
          <p class="linked-mod-hint">
            <strong>要上架或提取 Mod 里的 AI 员工，请用下方蓝色「导出员工包」</strong>（生成 <code class="mono">employee_pack</code>，与整 Mod zip 不同）。<strong>仅当员工依赖 Mod 内 Python 路由</strong>（如 <code class="mono">phone_agent_base_path</code>）时，才需要右侧较淡的「导出完整 Mod zip」。
            编辑 JSON 后点「保存到 manifest」写回磁盘；服务端导出读磁盘数据。若导出接口不可用，会自动用本页 <strong>manifest 快照 + 下方 JSON</strong> 在浏览器内生成同结构 zip。成功后浏览器会<strong>下载 zip</strong>并填入下方上传区。
            加载本 Mod 后会根据 manifest 与当前条目<strong>自动补全表单中仍为空的</strong>名称与描述；行业与价格在「上架信息」步骤填写。可点「从声明同步到表单」再次套用。
          </p>
          <label class="label" for="wf-json">workflow_employees 条目（JSON）</label>
          <textarea
            id="wf-json"
            v-model="workflowJsonText"
            class="input textarea code-textarea"
            rows="14"
            spellcheck="false"
          />
          <div class="linked-mod-actions">
            <button type="button" class="btn" :disabled="workflowSaving" @click="saveWorkflowToManifest">
              {{ workflowSaving ? '保存中…' : '保存到 manifest' }}
            </button>
            <button type="button" class="btn" :disabled="!linkedManifestSnapshot" @click="syncFormFromLinkedPanel">
              从声明同步到表单
            </button>
            <button type="button" class="btn btn-primary" :disabled="exportZipBusy" @click="attachExportedEmployeePack">
              {{ exportZipBusy ? '导出中…' : '导出员工包（manifest）' }}
            </button>
            <button
              type="button"
              class="btn btn--mod-zip-secondary"
              :disabled="exportZipBusy"
              title="包含 Mod 全部代码与资源，体积大；一般用于备份，或员工必须随 Mod 内 Python 路由一起分发时使用。提取只要 AI 员工请用蓝色按钮。"
              @click="attachExportedModZip"
            >
              {{ exportZipBusy ? '导出中…' : '导出完整 Mod zip' }}
            </button>
            <router-link class="btn" :to="{ name: 'mod-authoring', params: { modId: linkedModId } }">去 Mod 制作页</router-link>
            <router-link
              v-if="workflowEditQuery"
              class="btn"
              :to="{ name: 'workbench-unified', query: { focus: 'workflow', edit: workflowEditQuery, tab: 'editor' } }"
            >打开关联工作流</router-link>
            <router-link
              v-if="workflowEditQuery"
              class="btn btn-primary"
              :to="{ name: 'workbench-unified', query: { focus: 'workflow', edit: workflowEditQuery, tab: 'sandbox' } }"
            >拆解与沙盒测试</router-link>
          </div>
          <p v-if="workflowPanelErr" class="flash flash-err">{{ workflowPanelErr }}</p>
          <p v-if="workflowPanelOk" class="flash flash-success">{{ workflowPanelOk }}</p>
        </section>
        <div v-if="linkedModId" class="panel-toggle-row">
          <button type="button" class="btn btn-sm" @click="showLinkedModPanel = !showLinkedModPanel">
            {{ showLinkedModPanel ? '收起 Mod JSON 编辑器（兼容）' : '展开 Mod JSON 编辑器（兼容）' }}
          </button>
        </div>

        <div class="workspace-card-grid pipeline-grid">
          <!-- 包文件 I/O 卡片 -->
          <div id="package-section" v-show="panels.package" :class="['publish-wizard-block','card-block','pipeline-card','pipeline-card--package','floating-panel','floating-panel--package', isGuideTarget('package') ? 'spotlight-card' : '']">
          <div class="card-kicker">Package</div>
          <h2 class="section-title">包文件与提交流程</h2>
          <p class="audit-muted publish-wizard-lead">
            本步用于选择实际上传包（.zip/.xcemp）和基础信息；V2 配置作为审核/上架 metadata 一并提交，不会直接改写你本地原包。
          </p>
          <form class="authoring-form" @submit.prevent="goTestingStep">
            <div class="form-group">
              <label for="employee-name">员工名称</label>
              <input
                type="text"
                id="employee-name"
                v-model="form.name"
                required
                placeholder="例如：文档分析员"
              >
            </div>

            <div class="form-group">
              <label for="employee-description">描述</label>
              <textarea
                id="employee-description"
                v-model="form.description"
                required
                rows="4"
                placeholder="详细描述员工的能力和使用场景..."
              ></textarea>
            </div>

            <div v-if="linkedModId" class="form-group">
              <label for="pkg-artifact">登记包类型（与 zip 内容一致）</label>
              <select id="pkg-artifact" v-model="form.packageArtifact" class="input">
                <option value="">自动（与来源 Mod 的 artifact 一致）</option>
                <option value="mod">mod（普通扩展）</option>
                <option value="employee_pack">employee_pack（全局员工包）</option>
              </select>
            </div>

            <div class="form-group">
              <label for="employee-file">员工包文件 (.xcemp 或 .zip)</label>
              <div class="file-upload-area" :class="{ 'has-file': selectedFile }">
                <input
                  type="file"
                  id="employee-file"
                  @change="handleFileChange"
                  accept=".xcemp,.zip"
                >
                <div class="file-upload-content">
                  <div v-if="!selectedFile" class="file-upload-placeholder">
                    <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                      <polyline points="17 8 12 3 7 8"></polyline>
                      <line x1="12" y1="3" x2="12" y2="15"></line>
                    </svg>
                    <p>点击选择文件或拖拽文件到此处</p>
                    <span>支持 .xcemp 和 .zip 格式</span>
                  </div>
                  <div v-else class="file-info">
                    <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                    <div class="file-details">
                      <p class="file-name">{{ selectedFile.name }}</p>
                      <p class="file-size">{{ formatFileSize(selectedFile.size) }}</p>
                    </div>
                    <button type="button" class="btn-remove-file" @click.stop="removeFile">&times;</button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="packageScanMessage" :class="['flash', packageScanFlashClass]">{{ packageScanMessage }}</div>
            <div v-if="packageIoDiffSummary.length" class="flash flash-info">
              配置差异摘要：{{ packageIoDiffSummary.join('；') }}
            </div>

            <div v-if="error" class="flash flash-err">{{ error }}</div>
            <div v-if="success" class="flash flash-success">{{ success }}</div>

            <div class="form-actions">
              <button type="submit" :class="['btn','btn-primary', isGuideTarget('package') ? 'spotlight' : '']" :disabled="uploading || !canGoToTesting">
                下一步：测试与审核
              </button>
            </div>
          </form>
          </div>

          <div id="testing-section" v-show="panels.testing" :class="['card-block','pipeline-card','pipeline-card--testing','floating-panel','floating-panel--testing', isGuideTarget('testing') ? 'spotlight-card' : '']">
            <div class="card-kicker">Audit</div>
            <Step8Testing
              :selected-file="selectedFile"
              :resolved-workflow-id="safeResolvedWorkflowId"
              :wf-sandbox-input-json="wfSandboxInputJson"
              :wf-sandbox-loading="wfSandboxLoading"
              :wf-sandbox-err="wfSandboxErr"
              :docker-local-ack="dockerLocalAck"
              :sandbox-gate-ok="sandboxGateOk"
              :audit-loading="auditLoading"
              :audit-err="auditErr"
              :audit-report="auditReport"
              @update:wfSandboxInputJson="(v)=>wfSandboxInputJson=v"
              @update:dockerLocalAck="(v)=>dockerLocalAck=v"
              @sandbox="runEmployeeWorkflowSandbox"
              @audit="() => runFiveDimAuditClick(form.packageArtifact)"
              @next="goListingStep"
              @back="backToComposeFromTesting"
            />
          </div>

          <div id="publish-section" v-show="panels.publish" :class="['card-block','pipeline-card','pipeline-card--publish','floating-panel','floating-panel--publish', isGuideTarget('publish') ? 'spotlight-card' : '']">
            <div class="card-kicker">Publish</div>
            <Step9Listing
              :listing-hints="listingHints"
              :industry="form.industry"
              :price="Number(form.price || 0)"
              :error="error"
              :success="success"
              :uploading="uploading"
              :can-confirm="canConfirmListingUpload"
              :is-catalog-edit="isCatalogEdit"
              @update:industry="(v)=>form.industry=v"
              @update:price="(v)=>form.price=v"
              @submit="handleSubmit"
              @back="backToTestingFromListing"
            />
          </div>
        </div>
      </div>

      <div v-if="panels.help" class="authoring-tips-section floating-panel floating-panel--help">
        <h2 class="section-title">制作指南</h2>
        <div class="tips-card">
          <h3>员工包要求</h3>
          <ul class="tips-list">
            <li>文件格式：.xcemp 或 .zip（与 zip 同结构时可自动读取 manifest）</li>
            <li>流程：选包并填写名称与描述 → 进入测试页（沙盒；有关联工作流则 API 沙盒运行；否则勾选本地/Docker）→ 获取五维审核 → 通过后选择行业与价格 → 确认上架</li>
            <li>HTTP 探测 status 需在服务器 .env 配置 MODSTORE_SANDBOX_PROBE_BASE_URL（见 .env.example）</li>
            <li>包含员工的核心逻辑和配置</li>
            <li>支持 DeepSeek AI 和 OCR 技术</li>
          </ul>
        </div>
        <div class="tips-card">
          <h3>可创建的任务类型</h3>
          <ul class="tips-list">
            <li>文档分析与提取</li>
            <li>数据处理与转换</li>
            <li>报表生成</li>
            <li>智能识别</li>
          </ul>
        </div>
        <div class="tips-card">
          <h3>定价建议</h3>
          <ul class="tips-list">
            <li>通用型员工：免费或低定价</li>
            <li>专业型员工：根据行业价值定价</li>
            <li>批量购买可设置折扣</li>
          </ul>
        </div>
      </div>
    </div>

    <div v-if="panels.employees && editPkgId" class="catalog-version-panel floating-panel floating-panel--employees-meta">
      <h2 class="section-title">版本历史</h2>
      <p class="audit-muted">包 ID <code class="mono">{{ editPkgId }}</code>。测试版可多次保存；「发布正式」会生成新的 stable 版本（semver patch+1）。</p>
      <ul v-if="catalogVersionRows.length" class="ver-history-list">
        <li v-for="row in catalogVersionRows" :key="row.version" class="ver-history-li">
          <span class="mono ver-v">{{ row.version }}</span>
          <span
            class="ver-ch"
            :class="String(row.release_channel || 'stable').toLowerCase() === 'draft' ? 'ver-ch--draft' : 'ver-ch--stable'"
          >
            {{ String(row.release_channel || 'stable').toLowerCase() === 'draft' ? '测试' : '正式' }}
          </span>
          <button type="button" class="btn btn-sm" @click="applyCatalogVersionRow(row)">以此版本为包</button>
        </li>
      </ul>
      <p v-else class="audit-muted">暂无版本记录</p>
      <div class="promote-row">
        <label class="label" for="promote-draft-sel">将测试版发布为正式</label>
        <select id="promote-draft-sel" v-model="promoteDraftVer" class="input promote-select">
          <option value="">选择 draft 版本</option>
          <option v-for="d in draftVersions" :key="d.version" :value="d.version">{{ d.version }}</option>
        </select>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="!promoteDraftVer || promoteBusy"
          @click="() => void promoteCatalogRelease()"
        >
          {{ promoteBusy ? '处理中…' : '发布正式' }}
        </button>
      </div>
    </div>

    <div id="employees-section" v-if="panels.employees" class="my-employees-section floating-panel floating-panel--employees">
      <h2 class="section-title">员工与登记</h2>
      <p class="audit-muted my-emp-lead">
        <strong>已登记员工包</strong>来自本地 <code class="mono">/v1/packages</code> 或商店目录。可在 <strong>Mod 源码库 / Mod 制作页</strong>对声明点「一键登记」直接写入；「带入员工制作」只预填上方表单与 JSON，须完成向导并上传登记后也会出现在下列表。
      </p>
      <p v-if="v1CatalogLoadError" class="flash flash-err my-emp-catalog-err" role="alert">
        {{ v1CatalogLoadError }}
      </p>
      <div v-if="repoPrefillBanner.show" class="flash flash-info my-emp-banner">
        已从 Mod 仓库带入 <code class="mono">{{ repoPrefillBanner.modId }}</code> 的声明，请在上半区继续操作。
        <button type="button" class="btn btn-sm btn-ghost" @click="repoPrefillBanner.show = false">关闭提示</button>
      </div>
      <div v-if="linkedManifestWorkflowRows.length" class="mod-declaration-block">
        <h3 class="my-emp-subtitle">当前关联 Mod 的 manifest 声明</h3>
        <p class="audit-muted">
          Mod <code class="mono">{{ linkedModId }}</code> · 点击切换右侧「workflow_employees」JSON 与当前索引。
        </p>
        <ul class="mod-declaration-list">
          <li
            v-for="r in linkedManifestWorkflowRows"
            :key="'mwrow-' + r.index"
            class="mod-declaration-li"
            :class="{ 'is-active': r.isActive }"
          >
            <button
              type="button"
              class="btn btn-sm"
              :class="{ 'btn-primary': r.isActive }"
              @click="selectLinkedWorkflowIndex(r.index)"
            >
              {{ r.label }}
            </button>
            <span v-if="r.linkedWorkflowId" class="muted small mono">workflow_id {{ r.linkedWorkflowId }}</span>
            <span v-else class="muted small">未写 workflow_id</span>
          </li>
        </ul>
      </div>
      <h3 class="my-emp-subtitle">已登记的员工包</h3>
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="myEmployees.length === 0" class="empty-state">
        <p>暂无已登记的员工包</p>
        <p v-if="linkedManifestWorkflowRows.length" class="empty-hint">
          你已从仓库带入 Mod 声明（见上方列表），完成打包上架并写入包目录后即会出现在此处。
        </p>
        <p v-else class="empty-hint">
          从「Mod 源码库」点「带入员工制作」可预填本页；或在此上传 .zip / .xcemp 走向导。
        </p>
      </div>
      <div v-else class="employees-grid">
        <div v-for="emp in myEmployees" :key="emp.id" class="employee-card">
          <div class="employee-card-header">
            <h3>{{ emp.name }}</h3>
            <span class="employee-badge">{{ emp.industry || '通用' }}</span>
          </div>
          <p class="employee-desc">{{ truncate(emp.description, 80) }}</p>
          <div class="employee-card-footer">
            <span class="employee-price" :class="{ free: emp.price <= 0 }">
              {{ emp.price <= 0 ? '免费' : '¥' + Number(emp.price).toFixed(2) }}
            </span>
            <span class="employee-version">{{ emp.sourceLabel }} · {{ emp.pkg_id }}@{{ emp.version }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { unzip } from 'fflate'
import { api } from '../api'
import { buildEmployeePackZipFromPanel, buildEmployeePackZipFromV2 } from '../employeePackClientExport'
import {
  applyTemplateV2,
  upgradeLegacyToV2,
  validateEmployeeConfigV2,
} from '../employeeConfigV2'
import EmployeeBlockBuilder from './employee-steps/EmployeeBlockBuilder.vue'
import Step0TemplateSelect from './employee-steps/Step0TemplateSelect.vue'
import Step8Testing from './employee-steps/Step8Testing.vue'
import Step9Listing from './employee-steps/Step9Listing.vue'
import { useEmployeePublishFlow } from '../composables/useEmployeePublishFlow'
import { useEmployeeWorkbenchState } from '../composables/useEmployeeWorkbenchState'

const route = useRoute()
const router = useRouter()

const PREFILL_KEY = 'modstore_employee_prefill'
const ONBOARDING_KEY = 'employee_workbench_onboarding_seen_v1'
const showOnboarding = ref(false)
const showGuideInline = ref(false)
const showSessionSaveHint = ref(true)
const isFullscreenMode = ref(false)
const panels = reactive({
  package: false,
  testing: false,
  publish: false,
  employees: false,
  help: false,
})
const onboardingStep = ref(0)
const onboardingSteps = [
  { key: 'library', title: '第 1 步：从左侧模块库开始', desc: '先选模板，或直接点击样板员工快速生成可运行配置。' },
  { key: 'canvas', title: '第 2 步：在中间画布编排模块', desc: '拖拽排序并添加连线，协作模块是心脏不可移除。' },
  { key: 'config', title: '第 3 步：右侧属性完善细节', desc: '按模块填写关键参数，检查状态徽章和摘要。' },
  { key: 'package', title: '第 4 步：准备上传包', desc: '导入或替换 zip/.xcemp，并检查配置差异摘要。' },
  { key: 'testing', title: '第 5 步：测试与审核', desc: '先跑沙盒再拿五维审核，定位失败原因。' },
  { key: 'publish', title: '第 6 步：发布上架', desc: '审核通过后填写行业和价格完成发布。' },
]

/** 从仓库「带入」后提示：与已登记包列表区分 */
const repoPrefillBanner = reactive({ show: false, modId: '' })

const form = ref({
  name: '',
  description: '',
  industry: '',
  price: 0,
  packageArtifact: '',
})

const {
  employeeTemplateId,
  employeeConfigV2,
  employeeConfigErrors,
  currentStep,
  cardModeEnabled,
  wizardSteps,
  listingHints,
  selectedFile,
  packageScanMessage,
  packageScanKind,
  uploading,
  loading,
  v1CatalogLoadError,
  error,
  success,
  myEmployees,
  linkedModId,
  linkedWorkflowIndex,
  linkedModName,
  linkedModArtifact,
  workflowJsonText,
  workflowSaving,
  exportZipBusy,
  workflowPanelErr,
  workflowPanelOk,
  linkedManifestSnapshot,
  showLinkedModPanel,
  packageManifestWorkflowId,
  packageScanFlashClass,
  resolvedWorkflowId,
  safeResolvedWorkflowId,
} = useEmployeeWorkbenchState({
  parseWorkflowIdFromEntry,
  inferWorkflowIdFromManifest,
})

/** Catalog 编辑：同包 id 多版本（测试 draft / 正式 stable） */
const editPkgId = ref('')
const catalogVersionRows = ref([])
const promoteDraftVer = ref('')
const promoteBusy = ref(false)
let lastLoadedCatalogEditKey = ''


const ALLOWED_INDUSTRIES = new Set(['通用', '电商', '制造', '金融', '医疗', '教育', '物流'])
const openPanelCount = computed(() => Object.values(panels).filter(Boolean).length)

function togglePanel(key) {
  if (!Object.prototype.hasOwnProperty.call(panels, key)) return
  const next = !panels[key]
  Object.keys(panels).forEach((k) => { panels[k] = false })
  panels[key] = next
}
function closeAllPanels() {
  Object.keys(panels).forEach((k) => { panels[k] = false })
}
function goBackWorkbench() {
  if (isFullscreenMode.value && document.fullscreenElement) {
    document.exitFullscreen().catch(() => {})
  }
  void router.push({ name: 'workbench-unified', query: { focus: 'hybrid' } })
}

async function toggleFullscreen() {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen()
    } else {
      await document.exitFullscreen()
    }
  } catch {
    isFullscreenMode.value = !isFullscreenMode.value
  }
}

function syncFullscreenFlag() {
  isFullscreenMode.value = Boolean(document.fullscreenElement)
}

watch(
  () => linkedModId.value,
  (v) => {
    if (String(v || '').trim()) showLinkedModPanel.value = true
  },
)

const publishFlow = useEmployeePublishFlow({
  form,
  selectedFile,
  resolvedWorkflowId: safeResolvedWorkflowId,
  linkedModId,
  listingHints,
  employeeConfigV2,
})
const {
  publishWizardStep,
  listingDefaultsApplied,
  wfSandboxInputJson,
  wfSandboxLoading,
  wfSandboxErr,
  wfSandboxReport,
  wfSandboxOk,
  dockerLocalAck,
  auditReport,
  auditLoading,
  auditErr,
  sandboxGateOk,
  canConfirmListingUpload,
  runEmployeeWorkflowSandbox,
  runFiveDimAuditClick,
} = publishFlow

const DIMENSION_LABELS = {
  manifest_compliance: '清单合规',
  declaration_completeness: '声明完整',
  api_testability_static: '接口可测（静态）',
  security_and_size: '安全与体积',
  metadata_quality: '元数据与描述',
}

function dimLabel(key) {
  return DIMENSION_LABELS[key] || key
}


function coerceIndustry(raw) {
  if (raw == null || typeof raw !== 'string') return ''
  const t = raw.trim()
  return ALLOWED_INDUSTRIES.has(t) ? t : ''
}

function firstNonEmptyString(...vals) {
  for (const v of vals) {
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return ''
}

function unzipToFiles(arrayBuffer) {
  return new Promise((resolve, reject) => {
    unzip(new Uint8Array(arrayBuffer), (err, data) => {
      if (err) reject(err)
      else resolve(data && typeof data === 'object' ? data : {})
    })
  })
}

/** 在 zip 条目里选取 manifest.json（优先浅路径，兼容顶层与 pack_id/manifest.json） */
function pickManifestPath(entries) {
  const keys = Object.keys(entries).filter((k) => k && !k.endsWith('/'))
  const cands = keys.filter((k) => k === 'manifest.json' || /(^|\/)manifest\.json$/i.test(k))
  if (!cands.length) return null
  cands.sort((a, b) => {
    const da = a.split('/').length
    const db = b.split('/').length
    if (da !== db) return da - db
    return a.localeCompare(b)
  })
  return cands[0]
}

function rawIndustryFromManifest(manifest, wfEntry) {
  const wf = wfEntry && typeof wfEntry === 'object' && !Array.isArray(wfEntry) ? wfEntry : {}
  const r = wf.industry ?? manifest.industry ?? manifest.library_industry
  return typeof r === 'string' ? r.trim() : ''
}

/** 轻量审核：不替代服务端校验，仅提示明显问题 */
function auditPackageManifest(manifest, wfEntry) {
  const notes = []
  if (!manifest || typeof manifest !== 'object') {
    notes.push('manifest 无效')
    return notes
  }
  const art = String(manifest.artifact || 'mod').toLowerCase()
  if (art === 'employee_pack') {
    const emp = manifest.employee
    if (!emp || typeof emp !== 'object') {
      notes.push('employee_pack 建议在 manifest 中包含 employee 对象')
    } else if (!String(emp.id || '').trim()) {
      notes.push('employee_pack 建议填写 employee.id')
    }
  }
  const ri = rawIndustryFromManifest(manifest, wfEntry)
  if (ri && !coerceIndustry(ri)) {
    notes.push(`包内行业「${ri}」不在预设列表，请在下拉中手动选择`)
  }
  const mid = typeof manifest.id === 'string' ? manifest.id.trim() : ''
  if (!mid) notes.push('manifest 缺少 id')
  return notes
}

async function scanPackageFile(file) {
  packageScanMessage.value = ''
  packageManifestWorkflowId.value = 0
  resetListingHints()
  if (!file) return
  let files
  try {
    files = await unzipToFiles(await file.arrayBuffer())
  } catch {
    packageScanKind.value = 'warn'
    packageScanMessage.value =
      '未能作为 zip 解压；若文件不是 zip 结构，请核对包内容；行业与价格将在测试通过后的上架步骤填写。'
    return
  }
  const mpath = pickManifestPath(files)
  if (!mpath || !files[mpath]) {
    packageScanKind.value = 'warn'
    packageScanMessage.value = '压缩包内未找到 manifest.json，无法读取上架参考。'
    return
  }
  let manifest
  try {
    manifest = JSON.parse(new TextDecoder('utf-8').decode(files[mpath]))
  } catch {
    packageScanKind.value = 'warn'
    packageScanMessage.value = 'manifest.json 不是合法 JSON。'
    return
  }
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) {
    packageScanKind.value = 'warn'
    packageScanMessage.value = 'manifest 根节点须为 JSON 对象。'
    return
  }
  const wfArr = manifest.workflow_employees
  const wfEntry =
    Array.isArray(wfArr) && wfArr[0] != null && typeof wfArr[0] === 'object' && !Array.isArray(wfArr[0])
      ? wfArr[0]
      : {}

  hydrateListingHintsFromManifest(manifest, wfEntry)

  packageManifestWorkflowId.value = inferWorkflowIdFromManifest(manifest, 0)

  const before = {
    name: String(form.value.name || '').trim(),
    description: String(form.value.description || '').trim(),
  }
  applyLinkedManifestToForm(manifest, wfEntry)
  const audits = auditPackageManifest(manifest, wfEntry)
  const filled = []
  if (!before.name && String(form.value.name || '').trim()) {
    filled.push('名称')
  }
  if (!before.description && String(form.value.description || '').trim()) {
    filled.push('描述')
  }
  let msg = ''
  if (filled.length) {
    msg = `已从包内 manifest 自动填入：${filled.join('、')}。`
  } else {
    msg = '已读取 manifest；已有内容不会被覆盖，未识别到新的可填项。'
  }
  if (audits.length) {
    packageScanKind.value = 'warn'
    packageScanMessage.value = `${msg} 审核提示：${audits.join('；')}`
  } else {
    packageScanKind.value = filled.length ? 'ok' : 'info'
    packageScanMessage.value = msg
  }
}

/**
 * 用 manifest + 当前 workflow_employees 条目填充表单（仅填空项，不覆盖已填）。
 * 行业与价格在「上架信息」步骤填写；包内参考由 hydrateListingHintsFromManifest 写入 listingHints。
 */
function applyLinkedManifestToForm(manifest, wfEntry) {
  if (!manifest || typeof manifest !== 'object') return
  const wf = wfEntry && typeof wfEntry === 'object' && !Array.isArray(wfEntry) ? wfEntry : {}

  const title = firstNonEmptyString(
    wf.label,
    wf.panel_title,
    typeof manifest.name === 'string' ? manifest.name : '',
  )
  if (!String(form.value.name || '').trim() && title) {
    form.value.name = title.slice(0, 200)
  }

  const desc = firstNonEmptyString(
    wf.panel_summary,
    wf.description,
    typeof manifest.description === 'string' ? manifest.description : '',
  )
  if (!String(form.value.description || '').trim() && desc) {
    form.value.description = desc.slice(0, 4000)
  }

  const upgraded = upgradeLegacyToV2(manifest)
  if (wf && typeof wf === 'object') {
    const wid = Number.parseInt(String(wf.workflow_id ?? wf.workflowId ?? 0), 10)
    if (Number.isFinite(wid) && wid > 0) {
      upgraded.collaboration.workflow.workflow_id = wid
    }
  }
  upgraded.identity.name = String(form.value.name || '').trim() || upgraded.identity.name
  upgraded.identity.description = String(form.value.description || '').trim() || upgraded.identity.description
  employeeConfigV2.value = upgraded
  refreshV2Validation()
}

async function syncFormFromLinkedPanel() {
  workflowPanelErr.value = ''
  workflowPanelOk.value = ''
  if (!linkedModId.value) return
  let manifest = linkedManifestSnapshot.value
  if (!manifest) {
    try {
      const data = await api.getMod(linkedModId.value)
      manifest = data.manifest && typeof data.manifest === 'object' ? data.manifest : {}
      linkedManifestSnapshot.value = manifest
    } catch (e) {
      workflowPanelErr.value = e.message || String(e)
      return
    }
  }
  let wf = {}
  try {
    const parsed = JSON.parse(workflowJsonText.value || '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      workflowPanelErr.value = '须为 JSON 对象（非数组）才能同步到表单'
      return
    }
    wf = parsed
  } catch {
    workflowPanelErr.value = 'JSON 格式无效，无法同步到表单'
    return
  }
  applyLinkedManifestToForm(manifest, wf)
  hydrateListingHintsFromManifest(manifest, wf)
  workflowPanelOk.value = '已根据当前 JSON 与 manifest 同步名称与描述（仅填空项）；上架参考行业/价格已更新。'
  setTimeout(() => {
    workflowPanelOk.value = ''
  }, 4000)
}

/** 从 workflow_employees 单条解析 MODstore 工作流 ID（与字符串员工 id 区分） */
function parseWorkflowIdFromEntry(o: any): number {
  if (!o || typeof o !== 'object' || Array.isArray(o)) return 0
  const id =
    o.workflow_id ?? o.workflowId ?? o.modstore_workflow_id ?? o.modstoreWorkflowId
  if (id == null || id === '') return 0
  const n = parseInt(String(id), 10)
  return Number.isFinite(n) && n > 0 ? n : 0
}

/**
 * 从 manifest 推断工作流 ID：优先当前下标 → 单条 → 多条仅当已声明的 id 唯一一致。
 * 另支持 manifest.modstore.workflow_id、manifest.modstore_workflow_id。
 */
function inferWorkflowIdFromManifest(manifest: any, preferredIndex: number): number {
  if (!manifest || typeof manifest !== 'object') return 0
  const ms = manifest.modstore
  if (ms && typeof ms === 'object' && !Array.isArray(ms)) {
    const r = parseWorkflowIdFromEntry({
      workflow_id: ms.workflow_id ?? ms.workflowId,
    })
    if (r > 0) return r
  }
  const root = parseWorkflowIdFromEntry({
    workflow_id: manifest.modstore_workflow_id ?? manifest.modstoreWorkflowId,
  })
  if (root > 0) return root

  const arr = manifest.workflow_employees
  if (!Array.isArray(arr) || arr.length === 0) return 0
  const pi =
    Number.isFinite(preferredIndex) && preferredIndex >= 0 ? Math.floor(preferredIndex) : 0
  const atIdx = arr[pi]
  const direct = parseWorkflowIdFromEntry(
    atIdx && typeof atIdx === 'object' && !Array.isArray(atIdx) ? atIdx : {},
  )
  if (direct > 0) return direct
  if (arr.length === 1) {
    return parseWorkflowIdFromEntry(
      arr[0] && typeof arr[0] === 'object' && !Array.isArray(arr[0]) ? arr[0] : {},
    )
  }
  const ids = new Set<number>()
  for (const item of arr) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue
    const w = parseWorkflowIdFromEntry(item)
    if (w > 0) ids.add(w)
  }
  if (ids.size === 1) return [...ids][0] ?? 0
  return 0
}

/** 若编辑器 JSON 尚无 workflow_id，则写入 manifest 推断结果（便于旧包一键保存） */
function mergeWorkflowIdIfMissing(manifest: any, preferredIndex: number): void {
  const inferred = inferWorkflowIdFromManifest(manifest, preferredIndex)
  if (inferred <= 0) return
  let cur = {}
  try {
    cur = JSON.parse(workflowJsonText.value || '{}')
  } catch {
    return
  }
  if (!cur || typeof cur !== 'object' || Array.isArray(cur)) return
  if (parseWorkflowIdFromEntry(cur) > 0) return
  workflowJsonText.value = JSON.stringify({ ...cur, workflow_id: inferred }, null, 2)
}

function pickRouteQueryString(key) {
  const v = route.query[key]
  if (typeof v === 'string') return v
  if (Array.isArray(v) && typeof v[0] === 'string') return v[0]
  return ''
}

/** URL ?link_workflow_id= 显式关联（打开本页后写入 JSON 并去掉 query） */
function applyLinkWorkflowIdFromRoute() {
  const raw = pickRouteQueryString('link_workflow_id').trim()
  const n = parseInt(raw, 10)
  if (!Number.isFinite(n) || n <= 0) return
  let cur = {}
  try {
    cur = JSON.parse(workflowJsonText.value || '{}')
  } catch {
    return
  }
  if (!cur || typeof cur !== 'object' || Array.isArray(cur)) return
  if (parseWorkflowIdFromEntry(cur) > 0) return
  workflowJsonText.value = JSON.stringify({ ...cur, workflow_id: n }, null, 2)
  const next = { ...route.query }
  delete next.link_workflow_id
  void router.replace({ name: route.name, query: next })
}

const workflowEditQuery = computed(() =>
  safeResolvedWorkflowId.value > 0 ? String(safeResolvedWorkflowId.value) : '',
)

const packageIoDiffSummary = computed(() => {
  const rows = []
  const cfgName = String(employeeConfigV2.value?.identity?.name || '').trim()
  const cfgDesc = String(employeeConfigV2.value?.identity?.description || '').trim()
  const formName = String(form.value?.name || '').trim()
  const formDesc = String(form.value?.description || '').trim()
  if (formName && cfgName && formName !== cfgName) rows.push('名称（表单/配置）不一致')
  if (formDesc && cfgDesc && formDesc !== cfgDesc) rows.push('描述（表单/配置）不一致')
  if (!selectedFile.value) rows.push('未选择上传包')
  if (!(safeResolvedWorkflowId.value > 0)) rows.push('workflow_id 未就绪')
  return rows
})

/** 关联 Mod manifest 中全部 workflow_employees，便于与「已登记包」区分 */
const linkedManifestWorkflowRows = computed(() => {
  const snap = linkedManifestSnapshot.value
  const mid = (linkedModId.value || '').trim()
  if (!snap || typeof snap !== 'object' || !mid) return []
  const wf = snap.workflow_employees
  if (!Array.isArray(wf)) return []
  return wf.map((item, index) => {
    const o = item && typeof item === 'object' && !Array.isArray(item) ? item : {}
    const id = typeof o.id === 'string' ? o.id.trim() : ''
    const label =
      (typeof o.label === 'string' && o.label.trim()) ||
      (typeof o.panel_title === 'string' && o.panel_title.trim()) ||
      id ||
      `条目 ${index}`
    const widRaw = o.workflow_id ?? o.workflowId
    let wfNum = 0
    if (widRaw != null && widRaw !== '') {
      const n = parseInt(String(widRaw), 10)
      if (Number.isFinite(n) && n > 0) wfNum = n
    }
    return {
      index,
      id,
      label: String(label).slice(0, 200),
      linkedWorkflowId: wfNum,
      isActive: index === linkedWorkflowIndex.value,
    }
  })
})

function selectLinkedWorkflowIndex(idx) {
  const snap = linkedManifestSnapshot.value
  if (!snap || typeof snap !== 'object') return
  const wf = snap.workflow_employees
  if (!Array.isArray(wf) || idx < 0 || idx >= wf.length) return
  linkedWorkflowIndex.value = idx
  const entry = wf[idx]
  const obj = entry && typeof entry === 'object' && !Array.isArray(entry) ? entry : {}
  workflowJsonText.value = JSON.stringify(obj, null, 2)
  mergeWorkflowIdIfMissing(snap, idx)
  applyLinkedManifestToForm(snap, obj)
  hydrateListingHintsFromManifest(snap, obj)
  publishWizardStep.value = 'compose'
  wfSandboxOk.value = false
  wfSandboxReport.value = null
  wfSandboxErr.value = ''
  dockerLocalAck.value = false
  auditReport.value = null
  auditErr.value = ''
  listingDefaultsApplied.value = false
}


const canGoToTesting = computed(() => {
  if (!selectedFile.value) return false
  if (!String(form.value.name || '').trim()) return false
  if (!String(form.value.description || '').trim()) return false
  if (!v2HeartReady.value) return false
  return true
})

const v2HeartReady = computed(() => {
  const wid = Number.parseInt(
    String(employeeConfigV2.value?.collaboration?.workflow?.workflow_id || 0),
    10,
  )
  return Number.isFinite(wid) && wid > 0
})

function refreshV2Validation() {
  const ret = validateEmployeeConfigV2(employeeConfigV2.value)
  employeeConfigErrors.value = ret.errors || []
}

const canNextStep = computed(() => {
  if (currentStep.value === 6) return v2HeartReady.value
  if (currentStep.value === 8) return publishWizardStep.value === 'listing' || auditReport.value?.summary?.pass === true
  return currentStep.value < 9
})

function goStep(id) {
  currentStep.value = Math.max(0, Math.min(9, Number(id) || 0))
}
function nextWizardStep() {
  if (!canNextStep.value) return
  if (currentStep.value < 9) currentStep.value += 1
}
function prevWizardStep() {
  if (currentStep.value > 0) currentStep.value -= 1
}
function onBuilderConfigUpdate(v) {
  if (!v || typeof v !== 'object') return
  employeeConfigV2.value = JSON.parse(JSON.stringify(v))
  form.value.name = String(employeeConfigV2.value?.identity?.name || form.value.name || '').trim()
  form.value.description = String(employeeConfigV2.value?.identity?.description || form.value.description || '').trim()
  refreshV2Validation()
}

function applyTemplate(templateId) {
  employeeTemplateId.value = templateId
  const next = applyTemplateV2(templateId)
  next.identity.name = String(form.value.name || '').trim()
  next.identity.description = String(form.value.description || '').trim()
  const fallbackWorkflowId = safeResolvedWorkflowId.value
  if (fallbackWorkflowId > 0) {
    next.collaboration.workflow.workflow_id = fallbackWorkflowId
  }
  employeeConfigV2.value = next
  refreshV2Validation()
}

function syncFormToV2Identity() {
  employeeConfigV2.value.identity.name = String(form.value.name || '').trim()
  employeeConfigV2.value.identity.description = String(form.value.description || '').trim()
  refreshV2Validation()
}


function resetListingHints() {
  listingHints.value = { industryRaw: '', industryCoerced: '', priceFromManifest: null }
}

function hydrateListingHintsFromManifest(manifest, wfEntry) {
  if (!manifest || typeof manifest !== 'object') {
    resetListingHints()
    return
  }
  const wf = wfEntry && typeof wfEntry === 'object' && !Array.isArray(wfEntry) ? wfEntry : {}
  const raw = rawIndustryFromManifest(manifest, wfEntry)
  const coerced =
    coerceIndustry(typeof wf.industry === 'string' ? wf.industry : '') ||
    coerceIndustry(typeof manifest.industry === 'string' ? manifest.industry : '') ||
    coerceIndustry(typeof manifest.library_industry === 'string' ? manifest.library_industry : '')
  let priceFromManifest = null
  const comm = manifest.commerce
  if (comm && typeof comm === 'object') {
    const n = Number(comm.price)
    if (Number.isFinite(n) && n >= 0) priceFromManifest = n
  }
  listingHints.value = {
    industryRaw: raw || '',
    industryCoerced: coerced || '',
    priceFromManifest,
  }
}


function goTestingStep() {
  error.value = ''
  if (!selectedFile.value) {
    error.value = '请先选择员工包文件'
    return
  }
  if (!String(form.value.name || '').trim()) {
    error.value = '请填写员工名称'
    return
  }
  if (!String(form.value.description || '').trim()) {
    error.value = '请填写描述'
    return
  }
  syncFormToV2Identity()
  refreshV2Validation()
  if (!v2HeartReady.value) {
    error.value = '工作流是员工心脏：请先填写 workflow_id'
    return
  }
  if (employeeConfigErrors.value.length) {
    error.value = `V2 配置未通过：${employeeConfigErrors.value[0]}`
    return
  }
  currentStep.value = 8
  publishWizardStep.value = 'testing'
}

function goListingStep() {
  publishFlow.goListingStep()
  if (publishWizardStep.value === 'listing') currentStep.value = 9
}

function backToTestingFromListing() {
  publishFlow.backToTestingFromListing()
  currentStep.value = 8
}

function backToComposeFromTesting() {
  publishFlow.backToComposeFromTesting()
}


function resetWizardAfterPackageChange() {
  publishWizardStep.value = 'compose'
  wfSandboxOk.value = false
  wfSandboxReport.value = null
  wfSandboxErr.value = ''
  dockerLocalAck.value = false
  auditReport.value = null
  auditErr.value = ''
  listingDefaultsApplied.value = false
  packageManifestWorkflowId.value = 0
}

const isCatalogEdit = computed(() => Boolean(editPkgId.value))

const draftVersions = computed(() =>
  catalogVersionRows.value.filter(
    (r) => String(r.release_channel || 'stable').toLowerCase() === 'draft',
  ),
)

watch(workflowJsonText, () => {
  publishWizardStep.value = 'compose'
  wfSandboxOk.value = false
  wfSandboxReport.value = null
  wfSandboxErr.value = ''
  auditReport.value = null
  auditErr.value = ''
  listingDefaultsApplied.value = false
  const wid = safeResolvedWorkflowId.value
  if (wid > 0) {
    employeeConfigV2.value.collaboration.workflow.workflow_id = wid
  }
  refreshV2Validation()
})

watch(dockerLocalAck, (v) => {
  if (!safeResolvedWorkflowId.value && !v) {
    auditReport.value = null
    auditErr.value = ''
  }
})

watch(
  () => [form.value.name, form.value.description],
  () => {
    syncFormToV2Identity()
  },
)

function consumePrefillFromSessionAndQuery() {
  try {
    const raw = sessionStorage.getItem(PREFILL_KEY)
    if (raw) {
      const o = JSON.parse(raw)
      if (o && typeof o === 'object') {
        if (typeof o.name === 'string' && o.name.trim()) form.value.name = o.name.trim().slice(0, 200)
        if (typeof o.description === 'string' && o.description.trim()) {
          form.value.description = o.description.trim().slice(0, 4000)
        }
        if (typeof o.industry === 'string' && o.industry.trim()) {
          const t = o.industry.trim()
          listingHints.value = {
            ...listingHints.value,
            industryRaw: t,
            industryCoerced: coerceIndustry(t),
          }
        }
        if (typeof o.modId === 'string' && o.modId.trim()) {
          const mid = o.modId.trim()
          linkedModId.value = mid
          repoPrefillBanner.show = true
          repoPrefillBanner.modId = mid
          linkedWorkflowIndex.value =
            typeof o.workflowIndex === 'number' && o.workflowIndex >= 0 ? o.workflowIndex : 0
          if (o.workflowEmployee && typeof o.workflowEmployee === 'object') {
            workflowJsonText.value = JSON.stringify(o.workflowEmployee, null, 2)
          } else {
            workflowJsonText.value = '{}'
          }
        }
      }
      sessionStorage.removeItem(PREFILL_KEY)
    }
  } catch {
    sessionStorage.removeItem(PREFILL_KEY)
  }
  const q = route.query
  const pick = (k) => {
    const v = q[k]
    if (typeof v === 'string') return v
    if (Array.isArray(v) && typeof v[0] === 'string') return v[0]
    return ''
  }
  const qName = pick('prefill_name').trim()
  const qDesc = pick('prefill_description').trim()
  if (qName) form.value.name = qName.slice(0, 200)
  if (qDesc) form.value.description = qDesc.slice(0, 4000)
  if (qName || qDesc) {
    const next = { ...route.query }
    delete next.prefill_name
    delete next.prefill_description
    delete next.prefill_mod_id
    router.replace({ name: route.name, query: next })
  }

  const fromAi = pick('fromAi').trim()
  if (fromAi === '1') {
    const aiName = pick('name').trim()
    const aiDesc = pick('desc').trim()
    const packId = pick('packId').trim()
    if (aiName) form.value.name = aiName.slice(0, 200)
    if (aiDesc) form.value.description = aiDesc.slice(0, 4000)
    if (packId) {
      success.value = `工作台已生成员工包「${packId}」并写入你的本地库；请打包为 .zip / .xcemp 后在此上架（商店执行器以已上架包为准）。`
    }
    const next = { ...route.query }
    delete next.fromAi
    delete next.packId
    delete next.name
    delete next.desc
    router.replace({ name: route.name, query: next })
  }
}

watch(
  () => [route.query.edit_pkg, route.query.edit_ver],
  () => {
    void syncEditQueryFromRoute()
  },
)

onMounted(async () => {
  applyTemplate(employeeTemplateId.value)
  consumePrefillFromSessionAndQuery()
  await syncEditQueryFromRoute()
  await loadLinkedModMeta()
  applyLinkWorkflowIdFromRoute()
  const wid = safeResolvedWorkflowId.value
  if (wid > 0) {
    employeeConfigV2.value.collaboration.workflow.workflow_id = wid
  }
  refreshV2Validation()
  await loadMyEmployees()
  showOnboarding.value = localStorage.getItem(ONBOARDING_KEY) !== '1'
  onboardingStep.value = 0
  document.addEventListener('fullscreenchange', syncFullscreenFlag)
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', syncFullscreenFlag)
})

function dismissOnboarding() {
  showOnboarding.value = false
  localStorage.setItem(ONBOARDING_KEY, '1')
}

const currentOnboarding = computed(() => onboardingSteps[onboardingStep.value] || onboardingSteps[0])
const activeGuideTarget = computed(() => (showOnboarding.value ? String(currentOnboarding.value?.key || '') : ''))
function isGuideTarget(key) { return showOnboarding.value && activeGuideTarget.value === key }
function prevOnboardingStep() { onboardingStep.value = Math.max(0, onboardingStep.value - 1) }
function nextOnboardingStep() { onboardingStep.value = Math.min(onboardingSteps.length - 1, onboardingStep.value + 1) }
function finishOnboarding() { dismissOnboarding() }
function skipOnboarding() { dismissOnboarding() }

async function loadLinkedModMeta() {
  if (!linkedModId.value) return
  workflowPanelErr.value = ''
  linkedManifestSnapshot.value = null
  try {
    const data = await api.getMod(linkedModId.value)
    const manifest = data.manifest && typeof data.manifest === 'object' ? data.manifest : {}
    linkedManifestSnapshot.value = manifest
    linkedModName.value = manifest.name || ''
    linkedModArtifact.value = String(manifest.artifact || 'mod').toLowerCase()
    const wf = manifest.workflow_employees
    let wfEntry = null
    if (Array.isArray(wf) && wf[linkedWorkflowIndex.value] != null) {
      wfEntry = wf[linkedWorkflowIndex.value]
      workflowJsonText.value = JSON.stringify(wfEntry, null, 2)
    }
    const wfEntryObj = wfEntry && typeof wfEntry === 'object' ? wfEntry : {}
    applyLinkedManifestToForm(manifest, wfEntryObj)
    hydrateListingHintsFromManifest(manifest, wfEntryObj)
    mergeWorkflowIdIfMissing(manifest, linkedWorkflowIndex.value)
  } catch (e) {
    workflowPanelErr.value = e.message || String(e)
  }
}

async function saveWorkflowToManifest() {
  workflowPanelErr.value = ''
  workflowPanelOk.value = ''
  if (!linkedModId.value) return
  let parsed
  try {
    parsed = JSON.parse(workflowJsonText.value || '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      workflowPanelErr.value = '须为 JSON 对象（非数组）'
      return
    }
  } catch {
    workflowPanelErr.value = 'JSON 格式无效'
    return
  }
  workflowSaving.value = true
  try {
    const data = await api.getMod(linkedModId.value)
    const manifest = { ...(data.manifest || {}) }
    const wf = Array.isArray(manifest.workflow_employees) ? [...manifest.workflow_employees] : []
    const idx = linkedWorkflowIndex.value
    while (wf.length <= idx) wf.push({})
    wf[idx] = parsed
    manifest.workflow_employees = wf
    const res = await api.putModManifest(linkedModId.value, manifest)
    linkedManifestSnapshot.value = manifest
    const w = res.warnings
    workflowPanelOk.value =
      '已写回 manifest。' + (Array.isArray(w) && w.length ? ` 校验提示：${w.join('；')}` : '')
    setTimeout(() => {
      workflowPanelOk.value = ''
    }, 5000)
  } catch (e) {
    workflowPanelErr.value = e.message || String(e)
  } finally {
    workflowSaving.value = false
  }
}

function triggerBrowserDownload(blob, filename) {
  if (!blob || !filename) return
  try {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 4000)
  } catch {
    /* 下载触发失败不影响已填入上传区的 File */
  }
}

async function exportBuilderEmployeePackZip() {
  workflowPanelErr.value = ''
  workflowPanelOk.value = ''
  try {
    const r = buildEmployeePackZipFromV2({
      config: employeeConfigV2.value,
      packId: employeeConfigV2.value?.identity?.id || employeeConfigV2.value?.identity?.name || 'employee-pack',
      industry: form.value.industry || listingHints.value?.industryCoerced || '通用',
      price: Number(form.value.price || 0),
      author: employeeConfigV2.value?.identity?.author || '',
      files: {
        'README.md': `# ${employeeConfigV2.value?.identity?.name || 'Employee Pack'}\n\nGenerated by Employee Block Builder.\n`,
      },
    })
    const fname = `${r.packId}.zip`
    triggerBrowserDownload(r.blob, fname)
    const zf = new File([r.blob], fname, { type: 'application/zip' })
    selectedFile.value = zf
    form.value.packageArtifact = 'employee_pack'
    resetWizardAfterPackageChange()
    await scanPackageFile(zf)
    workflowPanelOk.value = '已基于当前 V2 配置在浏览器内生成 employee_pack zip，并填入上传区。'
    setTimeout(() => {
      workflowPanelOk.value = ''
    }, 6000)
  } catch (e) {
    workflowPanelErr.value = e.message || String(e)
  }
}

async function attachExportedEmployeePack() {
  if (!linkedModId.value) return
  exportZipBusy.value = true
  workflowPanelErr.value = ''
  try {
    let blob = null
    let fname = ''
    let usedClient = false
    let apiErr = ''
    try {
      blob = await api.exportEmployeePackZip(linkedModId.value, linkedWorkflowIndex.value)
      fname = `${linkedModId.value}-employee-pack.zip`
    } catch (e) {
      apiErr = e.message || String(e)
      try {
        const r = buildEmployeePackZipFromPanel({
          modId: linkedModId.value,
          workflowIndex: linkedWorkflowIndex.value,
          modManifest: linkedManifestSnapshot.value,
          workflowJsonText: workflowJsonText.value,
        })
        blob = r.blob
        fname = `${linkedModId.value}-employee-pack-${r.packId}.zip`
        usedClient = true
      } catch (e2) {
        const local = e2.message || String(e2)
        workflowPanelErr.value = `服务端导出: ${apiErr}；浏览器内生成: ${local}`
        return
      }
    }
    triggerBrowserDownload(blob, fname)
    const zf = new File([blob], fname, { type: 'application/zip' })
    selectedFile.value = zf
    form.value.packageArtifact = 'employee_pack'
    resetWizardAfterPackageChange()
    await scanPackageFile(zf)
    workflowPanelOk.value = usedClient
      ? '服务端导出未成功，已用本页 manifest 与 workflow JSON 在浏览器内生成 employee_pack zip（已下载并填入上传区）。请仍建议「保存到 manifest」并重启 API，以便库内与校验一致。含 Mod 内 Python 路由时需「导出完整 Mod」。'
      : '已下载 zip 到本机，并已填入下方上传区；登记类型已设为 employee_pack。含 Mod 内 Python 路由时请改用「导出完整 Mod」。'
    setTimeout(() => {
      workflowPanelOk.value = ''
    }, 6000)
  } catch (e) {
    workflowPanelErr.value = e.message || String(e)
  } finally {
    exportZipBusy.value = false
  }
}

async function attachExportedModZip() {
  if (!linkedModId.value) return
  exportZipBusy.value = true
  workflowPanelErr.value = ''
  try {
    const blob = await api.exportModZip(linkedModId.value)
    const fname = `${linkedModId.value}.zip`
    triggerBrowserDownload(blob, fname)
    const zf = new File([blob], fname, { type: 'application/zip' })
    selectedFile.value = zf
    form.value.packageArtifact = ''
    resetWizardAfterPackageChange()
    await scanPackageFile(zf)
    workflowPanelOk.value = '已下载完整 Mod zip 到本机，并已填入下方上传区；登记类型为自动（通常为 mod）。'
    setTimeout(() => {
      workflowPanelOk.value = ''
    }, 5000)
  } catch (e) {
    let m = e.message || String(e)
    if (/^not found$/i.test(String(m).trim()) || String(m).includes('"detail":"Not Found"')) {
      m = `${m} — 请重启 8765 上的 modstore_server 后再试；在 http://127.0.0.1:8765/docs 应能搜到 GET …/api/mods/…/export。`
    }
    workflowPanelErr.value = m
  } finally {
    exportZipBusy.value = false
  }
}

function routeQueryPick(q, k) {
  const v = q[k]
  if (typeof v === 'string') return v
  if (Array.isArray(v) && typeof v[0] === 'string') return v[0]
  return ''
}

async function loadCatalogVersions() {
  if (!editPkgId.value) {
    catalogVersionRows.value = []
    return
  }
  try {
    const res = await api.listCatalogPackageVersions(editPkgId.value)
    catalogVersionRows.value = Array.isArray(res.versions) ? res.versions : []
  } catch {
    catalogVersionRows.value = []
  }
}

async function enterEditFromCatalog(pkgId, ver) {
  const pid = (pkgId || '').trim()
  const v = (ver || '').trim()
  if (!pid || !v) return
  const key = `${pid}@${v}`
  error.value = ''
  try {
    const blob = await api.downloadCatalogPackageBlob(pid, v)
    const zf = new File([blob], `${pid}-${v}.zip`, { type: 'application/zip' })
    editPkgId.value = pid
    selectedFile.value = zf
    wfSandboxOk.value = false
    wfSandboxReport.value = null
    wfSandboxErr.value = ''
    dockerLocalAck.value = false
    auditReport.value = null
    auditErr.value = ''
    await scanPackageFile(zf)
    publishWizardStep.value = 'compose'
    await loadCatalogVersions()
    lastLoadedCatalogEditKey = key
    const curPid = routeQueryPick(route.query, 'edit_pkg').trim()
    const curVer = routeQueryPick(route.query, 'edit_ver').trim()
    if (curPid !== pid || curVer !== v) {
      await router.replace({ name: route.name, query: { ...route.query, edit_pkg: pid, edit_ver: v } })
    }
  } catch (e) {
    error.value = e.message || String(e)
    editPkgId.value = ''
    catalogVersionRows.value = []
    lastLoadedCatalogEditKey = ''
  }
}

async function applyCatalogVersionRow(row) {
  if (!row?.version || !editPkgId.value) return
  await enterEditFromCatalog(editPkgId.value, String(row.version))
}

async function promoteCatalogRelease() {
  if (!editPkgId.value || !promoteDraftVer.value) return
  promoteBusy.value = true
  error.value = ''
  try {
    await api.promoteCatalogPackage(editPkgId.value, promoteDraftVer.value)
    success.value = '已发布为正式版本'
    promoteDraftVer.value = ''
    await loadCatalogVersions()
    await loadMyEmployees()
    setTimeout(() => {
      success.value = ''
    }, 4000)
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    promoteBusy.value = false
  }
}

async function syncEditQueryFromRoute() {
  const pid = routeQueryPick(route.query, 'edit_pkg').trim()
  const ver = routeQueryPick(route.query, 'edit_ver').trim()
  if (pid && ver) {
    if (lastLoadedCatalogEditKey === `${pid}@${ver}` && selectedFile.value) {
      await loadCatalogVersions()
      return
    }
    await enterEditFromCatalog(pid, ver)
  } else {
    editPkgId.value = ''
    catalogVersionRows.value = []
    promoteDraftVer.value = ''
    lastLoadedCatalogEditKey = ''
    publishWizardStep.value = 'compose'
  }
}

async function loadMyEmployees() {
  loading.value = true
  v1CatalogLoadError.value = ''
  try {
    let v1Res = { packages: [], total: 0 }
    try {
      v1Res = await api.listV1Packages('', '', 80, 0)
    } catch (e) {
      const detail = e?.message || String(e)
      console.error('listV1Packages', e)
      v1CatalogLoadError.value =
        import.meta.env.DEV
          ? `无法连接本地包目录（/v1/packages）：${detail}。请确认 Vite 已将「/v1」代理到后端（与 /api 相同目标），修改 vite.config.js 后需重启 npm run dev。`
          : `无法加载本地包目录（/v1/packages）：${detail}`
    }
    const sqlRes = await api.catalog('', 'employee_pack', 40, 0).catch(() => ({ items: [], total: 0 }))
    const rows = []
    const seen = new Set()
    for (const p of v1Res.packages || []) {
      const art = String(p.artifact || 'mod').toLowerCase()
      if (art !== 'employee_pack' && art !== 'mod') continue
      const pid = String(p.id || '').trim()
      const ver = String(p.version || '').trim()
      if (!pid || !ver) continue
      const k = `v1:${pid}@${ver}`
      if (seen.has(k)) continue
      seen.add(k)
      const comm = p.commerce && typeof p.commerce === 'object' ? p.commerce : {}
      const price = Number(comm.price != null ? comm.price : p.price != null ? p.price : 0) || 0
      rows.push({
        id: k,
        pkg_id: pid,
        version: ver,
        name: p.name || pid,
        description: typeof p.description === 'string' ? p.description : '',
        price,
        industry: p.industry || '通用',
        sourceLabel: '本地包目录',
      })
    }
    for (const it of sqlRes.items || []) {
      const k = `sql:${it.id}`
      if (seen.has(k)) continue
      seen.add(k)
      rows.push({
        id: k,
        pkg_id: it.pkg_id || String(it.id),
        version: it.version || '',
        name: it.name || it.pkg_id,
        description: it.description || '',
        price: Number(it.price) || 0,
        industry: it.industry || '通用',
        sourceLabel: '商店',
      })
    }
    myEmployees.value = rows
  } catch (e) {
    console.error('加载员工失败:', e)
  } finally {
    loading.value = false
  }
}

async function handleFileChange(e) {
  const file = e.target.files[0]
  if (file) {
    const validExtensions = ['.xcemp', '.zip']
    const fileName = file.name.toLowerCase()
    const isValid = validExtensions.some(ext => fileName.endsWith(ext))
    
    if (!isValid) {
      error.value = '请选择 .xcemp 或 .zip 格式的文件'
      return
    }
    
    selectedFile.value = file
    error.value = ''
    resetWizardAfterPackageChange()
    await scanPackageFile(file)
  } else {
    packageScanMessage.value = ''
  }
}

function removeFile() {
  selectedFile.value = null
  packageScanMessage.value = ''
  packageManifestWorkflowId.value = 0
  auditReport.value = null
  auditErr.value = ''
  wfSandboxOk.value = false
  wfSandboxReport.value = null
  wfSandboxErr.value = ''
  dockerLocalAck.value = false
  publishWizardStep.value = 'compose'
  form.value.industry = ''
  form.value.price = 0
  resetListingHints()
  listingDefaultsApplied.value = false
  if (editPkgId.value) {
    const q = { ...route.query }
    delete q.edit_pkg
    delete q.edit_ver
    void router.replace({ name: route.name, query: q })
  }
  editPkgId.value = ''
  catalogVersionRows.value = []
  promoteDraftVer.value = ''
  lastLoadedCatalogEditKey = ''
  const fileInput = document.getElementById('employee-file') as HTMLInputElement | null
  if (fileInput) fileInput.value = ''
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function truncate(text, length) {
  if (!text) return ''
  return text.length > length ? text.substring(0, length) + '...' : text
}

async function handleSubmit() {
  if (publishWizardStep.value !== 'listing') {
    error.value = '请在上架信息步骤确认上传'
    return
  }
  if (!selectedFile.value) {
    error.value = '请选择员工包文件'
    return
  }
  if (!sandboxGateOk.value) {
    error.value = '请先完成沙盒测试（工作流沙盒运行，或勾选本地/Docker 确认）'
    return
  }
  if (auditErr.value || !auditReport.value || auditReport.value.summary?.pass !== true) {
    error.value = '请先点击「获取五维审核」且综合评分达到上架阈值'
    return
  }

  error.value = ''
  success.value = ''
  uploading.value = true

  try {
    let pkgId = `employee_${Date.now()}_${Math.floor(Math.random() * 1000)}`
    let version = '1.0.0'
    let release_channel = 'stable'
    if (isCatalogEdit.value) {
      pkgId = editPkgId.value
      version = `draft-${Date.now()}`
      release_channel = 'draft'
    }

    const artifactPick = (form.value.packageArtifact || '').trim().toLowerCase()
    const artifact =
      artifactPick === 'mod' || artifactPick === 'employee_pack'
        ? artifactPick
        : linkedModId.value
          ? linkedModArtifact.value === 'employee_pack'
            ? 'employee_pack'
            : 'mod'
          : 'employee_pack'

    const metadata: Record<string, unknown> = {
      id: pkgId,
      version: version,
      name: form.value.name,
      description: form.value.description,
      artifact,
      industry: form.value.industry || '通用',
      commerce: {
        price: form.value.price
      },
      release_channel,
      employee_config_v2: employeeConfigV2.value,
    }
    const probe = (linkedModId.value || '').trim()
    if (probe) metadata.probe_mod_id = probe

    await api.uploadPackage(metadata, selectedFile.value)
    if (isCatalogEdit.value) {
      success.value = '已保存测试版'
      promoteDraftVer.value = version
      lastLoadedCatalogEditKey = `${pkgId}@${version}`
      await router.replace({ name: route.name, query: { ...route.query, edit_pkg: pkgId, edit_ver: version } })
      wfSandboxOk.value = false
      wfSandboxReport.value = null
      wfSandboxErr.value = ''
      dockerLocalAck.value = false
      auditReport.value = null
      auditErr.value = ''
      publishWizardStep.value = 'compose'
      listingDefaultsApplied.value = false
      await loadCatalogVersions()
    } else {
      success.value = '员工上架成功！'
      form.value = {
        name: '',
        description: '',
        industry: '',
        price: 0,
        packageArtifact: '',
      }
      selectedFile.value = null
      packageScanMessage.value = ''
      auditReport.value = null
      auditErr.value = ''
      wfSandboxOk.value = false
      wfSandboxReport.value = null
      wfSandboxErr.value = ''
      dockerLocalAck.value = false
      publishWizardStep.value = 'compose'
      resetListingHints()
    }

    await loadMyEmployees()

    setTimeout(() => {
      success.value = ''
    }, 3000)
  } catch (e) {
    error.value = e.message || '上架失败，请重试'
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.employee-authoring {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  background:#050505;
}

.page-header {
  display:none;
}

.page-hero {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 1rem;
  align-items: flex-start;
  padding: 0.85rem 1rem;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.08);
  background: linear-gradient(160deg, rgba(18, 18, 18, 0.95), rgba(10, 10, 10, 0.94));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04), 0 12px 22px rgba(0, 0, 0, 0.45);
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 0.5rem;
}

.page-desc {
  font-size: 13px;
  color: rgba(226, 232, 240, 0.75);
  margin: 0 0 0.55rem;
}

.hero-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.hero-chip {
  font-size: 11px;
  letter-spacing: 0.02em;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.16);
  color: rgba(255,255,255,.82);
  background: rgba(255,255,255,.05);
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(120px, 1fr));
  gap: 0.55rem;
  min-width: 0;
  width: 100%;
}

.metric-card {
  padding: 0.42rem 0.55rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(2, 6, 23, 0.4);
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.metric-label {
  font-size: 11px;
  color: rgba(186, 230, 253, 0.75);
}

.metric-card strong {
  font-size: 12px;
  color: #e2e8f0;
}

.metric-ok { color: #86efac !important; }
.metric-warn { color: #fde047 !important; }

.guide-inline {
  margin: 0.65rem 0 0;
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(2, 6, 23, 0.35);
  font-size: 12px;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.45);
}

.session-save-hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 12px;
  padding: 10px 14px;
  border-radius: 8px;
  border: 0.5px solid rgba(96, 165, 250, 0.35);
  background: rgba(59, 130, 246, 0.08);
  color: rgba(255, 255, 255, 0.82);
  font-size: 13px;
  line-height: 1.45;
}

.session-save-hint span {
  flex: 1;
}

.workbench-toolbar {
  position: fixed;
  top: 8px;
  left: 8px;
  z-index: 60;
  display: inline-flex;
  flex-wrap: nowrap;
  gap: 0.4rem;
  margin: 0;
  padding: 0.35rem .45rem;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(6, 6, 6, 0.92);
  backdrop-filter: blur(6px);
  width: fit-content;
  max-width: calc(100vw - 16px);
  pointer-events: none;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
}

.workbench-toolbar .btn {
  pointer-events: auto;
  flex: 0 0 auto;
}

.workbench-toolbar .btn:disabled {
  opacity: .45;
  cursor: not-allowed;
}

.btn-toolbar-danger {
  border-color: rgba(248, 113, 113, 0.35);
  color: rgba(254, 202, 202, 0.92);
}

.btn-toolbar-danger:hover:not(:disabled) {
  background: rgba(248, 113, 113, 0.14);
  border-color: rgba(248, 113, 113, 0.5);
  color: #fee2e2;
}

.guide-inline code {
  font-size: 11px;
  background: rgba(0,0,0,0.35);
  padding: 0.1em 0.3em;
  border-radius: 3px;
  color: rgba(255,255,255,0.75);
}

.guide-inline p {
  margin: 0;
}

.authoring-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: .5rem;
  margin-bottom: 0;
}

.authoring-grid--fullscreen {
  margin-bottom: 0;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 0.85rem;
  padding-bottom: 0.75rem;
  border-bottom: 0.5px solid rgba(255,255,255,0.1);
}

.section-title--tight {
  margin-top: 0;
}

.linked-mod-panel {
  margin-bottom: 1.75rem;
  padding: 1.25rem 1.25rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(96, 165, 250, 0.4);
  background: transparent;
}

.linked-mod-meta {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  margin: 0 0 0.5rem;
  line-height: 1.5;
}

.linked-mod-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.42);
  margin: 0 0 1rem;
  line-height: 1.55;
}

.linked-mod-hint code {
  font-size: 11px;
  background: rgba(0, 0, 0, 0.35);
  padding: 0.1em 0.35em;
  border-radius: 3px;
}

.linked-mod-panel .label {
  display: block;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.65);
  margin-bottom: 0.5rem;
}

.code-textarea {
  width: 100%;
  box-sizing: border-box;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.45;
  min-height: 12rem;
  padding: 0.625rem 0.875rem;
  background: rgba(0, 0, 0, 0.28);
  border: 0.5px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: #ffffff;
  resize: vertical;
}

.code-textarea:focus {
  outline: none;
  border-color: #60a5fa;
}

.linked-mod-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
  margin-bottom: 0.5rem;
}

.linked-mod-actions .btn {
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* 整 Mod 导出：次要操作，避免与「员工包」主目标竞争 */
.btn--mod-zip-secondary {
  font-size: 0.78rem;
  font-weight: 400;
  padding: 0.45rem 0.75rem;
  color: rgba(255, 255, 255, 0.45);
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(0, 0, 0, 0.2);
}

.btn--mod-zip-secondary:hover:not(:disabled) {
  color: rgba(255, 255, 255, 0.75);
  border-color: rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.04);
}

.publish-wizard-block {
  margin-bottom: 1.5rem;
}

.publish-wizard-testing {
  padding-top: 0.25rem;
}

.publish-wizard-lead {
  margin: 0 0 0.75rem;
  max-width: 52rem;
}

.publish-wizard-back {
  margin-bottom: 1rem;
}

.listing-hints-panel {
  margin-bottom: 1.25rem;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.02);
}

.listing-hints-panel p {
  margin: 0.35rem 0;
}

.authoring-form-section {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  box-shadow: none;
}

.employee-v2-wizard {
  margin-bottom: 0;
  padding: 0;
  border-radius: 0;
  border: none;
  background: transparent;
}

.workbench-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.45rem;
}

.workbench-subtitle {
  margin: -0.45rem 0 0;
  color: rgba(255, 255, 255, 0.68);
  font-size: 12px;
}

.workbench-badges {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.wb-badge {
  font-size: 11px;
  padding: 0.16rem 0.5rem;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.18);
  color: rgba(255,255,255,.85);
  background: rgba(255,255,255,.05);
}

.mode-switch {
  margin: 0 0 0.6rem;
}

.card-block {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 14px;
  padding: 0.85rem;
  margin: 0.2rem 0;
  background: linear-gradient(180deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.52) 100%);
  backdrop-filter: blur(5px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 10px 24px rgba(2, 6, 23, 0.22);
}

#builder-section,
#package-section,
#testing-section,
#publish-section,
#employees-section {
  scroll-margin-top: 84px;
}

.workspace-card-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.85rem;
  align-items: start;
}

.pipeline-grid {
  position: static;
}

.pipeline-card--publish {
  grid-column: auto;
}

.floating-panel {
  position: fixed;
  right: 12px;
  bottom: 56px;
  top: auto;
  width: min(560px, calc(100vw - 24px));
  max-height: calc(100vh - 130px);
  overflow: auto;
  z-index: 80;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(18,18,18,.97), rgba(10,10,10,.95));
  box-shadow: 0 18px 30px rgba(0,0,0,.5);
  padding: .8rem;
}

.floating-panel--package { z-index: 84; }
.floating-panel--testing { z-index: 84; }
.floating-panel--publish { z-index: 84; }
.floating-panel--help { width: min(460px, calc(100vw - 24px)); z-index: 83; }
.floating-panel--employees-meta { left: auto; right: 12px; width: min(620px, calc(100vw - 24px)); z-index: 83; }
.floating-panel--employees { left: auto; right: 12px; width: min(760px, calc(100vw - 24px)); z-index: 82; }

.card-kicker {
  display: inline-flex;
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255,255,255,.82);
  border: 1px solid rgba(255,255,255,.18);
  background: rgba(255,255,255,.06);
  border-radius: 999px;
  padding: 0.1rem 0.45rem;
  margin-bottom: 0.4rem;
}

.onboarding-mask {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.72);
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.onboarding-card {
  width: min(680px, 95vw);
  border: 1px solid rgba(56, 189, 248, 0.4);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.96);
  padding: 1rem 1.1rem;
}

.onboarding-card h3 {
  margin: 0 0 0.5rem;
}

.onboarding-title {
  margin: 0 0 0.35rem;
  color: #dbeafe;
  font-weight: 600;
}

.onboarding-desc {
  margin: 0 0 0.8rem;
  color: rgba(255, 255, 255, 0.86);
}

.spotlight-card {
  box-shadow: 0 0 0 1px rgba(255,255,255,.26), 0 0 16px rgba(0,0,0,.45);
}

.spotlight {
  box-shadow: 0 0 0 1px rgba(255,255,255,.22), 0 0 12px rgba(0,0,0,.45);
}

.flow-clarify {
  margin: 0 0 0.7rem;
  font-size: 12px;
  border-left: 3px solid rgba(56, 189, 248, 0.45);
}

.panel-toggle-row {
  margin: 0 0 0.7rem;
}

.v2-template-row {
  margin: 0.7rem 0 0.85rem;
}

.v2-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem 1rem;
}

.v2-toggle-row {
  margin: 0.45rem 0 0.8rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem 1rem;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.step-actions {
  margin-top: 0.75rem;
  display: flex;
  gap: 0.5rem;
}

.authoring-form .form-group {
  margin-bottom: 1.25rem;
}

.authoring-form label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: rgba(255,255,255,0.7);
  margin-bottom: 0.5rem;
}

.authoring-form input[type="text"],
.authoring-form input[type="number"],
.authoring-form textarea,
.authoring-form select {
  width: 100%;
  padding: 0.625rem 0.875rem;
  background: rgba(255,255,255,0.04);
  border: 0.5px solid rgba(255,255,255,0.12);
  border-radius: 8px;
  color: #ffffff;
  font-size: 14px;
  transition: all 0.2s;
}

.authoring-form input:focus,
.authoring-form textarea:focus,
.authoring-form select:focus {
  outline: none;
  border-color: #60a5fa;
  background: rgba(255,255,255,0.06);
}

.authoring-form textarea {
  resize: vertical;
  min-height: 100px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.file-upload-area {
  position: relative;
  border: 0.5px dashed rgba(255,255,255,0.2);
  border-radius: 8px;
  padding: 1.5rem;
  text-align: center;
  transition: all 0.2s;
}

.file-upload-area:hover {
  border-color: rgba(255, 255, 255, 0.32);
  background: transparent;
}

.file-upload-area input[type="file"] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.file-upload-placeholder {
  color: rgba(255,255,255,0.4);
}

.upload-icon {
  width: 40px;
  height: 40px;
  margin-bottom: 0.75rem;
  opacity: 0.5;
}

.file-upload-placeholder p {
  font-size: 14px;
  margin-bottom: 0.25rem;
}

.file-upload-placeholder span {
  font-size: 12px;
  opacity: 0.6;
}

.file-upload-area.has-file {
  border-style: solid;
  border-color: rgba(255, 255, 255, 0.18);
  background: transparent;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-align: left;
}

.file-icon {
  width: 32px;
  height: 32px;
  color: #60a5fa;
  flex-shrink: 0;
}

.file-details {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  color: #ffffff;
  margin-bottom: 0.25rem;
  word-break: break-all;
}

.file-size {
  font-size: 12px;
  color: rgba(255,255,255,0.4);
}

.btn-remove-file {
  background: none;
  border: none;
  color: rgba(255,255,255,0.4);
  font-size: 20px;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
}

.btn-remove-file:hover {
  color: #ff6b6b;
}

.form-actions {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 0.5px solid rgba(255,255,255,0.1);
}

.authoring-tips-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.76), rgba(2, 6, 23, 0.5));
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 14px;
  padding: 0.9rem;
  position: static;
  max-height: none;
  overflow: visible;
}

.employee-authoring--fullscreen .page-header {
  display: none;
}

.employee-authoring--fullscreen .workbench-toolbar {
  margin-top: 0;
}

.employee-authoring--fullscreen .authoring-form-section {
  padding: 0.5rem;
  border: none;
  box-shadow: none;
  background: rgba(5,5,5,0.98);
}

.employee-authoring--fullscreen .employee-v2-wizard {
  margin-bottom: 0;
  padding: 0.4rem;
  border: none;
  background: transparent;
}

.tips-card {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 1.25rem;
}

.tips-card h3 {
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 0.75rem;
}

.tips-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.tips-list li {
  font-size: 13px;
  color: rgba(255,255,255,0.5);
  margin-bottom: 0.5rem;
  position: relative;
  padding-left: 1.25rem;
}

.tips-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #60a5fa;
}

.catalog-version-panel {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.25rem;
}

.ver-history-list {
  list-style: none;
  padding: 0;
  margin: 0.75rem 0 1rem;
}

.ver-history-li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.ver-history-li:last-child {
  border-bottom: none;
}

.ver-v {
  font-size: 0.875rem;
}

.ver-ch {
  font-size: 11px;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.ver-ch--draft {
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.35);
}

.ver-ch--stable {
  color: #4ade80;
  border-color: rgba(74, 222, 128, 0.35);
}

.promote-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.promote-select {
  min-width: 12rem;
}

.my-employees-section {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 1.5rem;
}

.my-emp-lead {
  margin: 0 0 1rem;
  line-height: 1.55;
  max-width: 52rem;
}

.my-emp-catalog-err {
  margin: 0 0 1rem;
  font-size: 13px;
  line-height: 1.45;
}

.my-emp-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  margin-bottom: 1rem;
}

.mod-declaration-block {
  margin-bottom: 1.25rem;
  padding: 1rem 1.1rem;
  border-radius: 10px;
  border: 1px solid rgba(96, 165, 250, 0.22);
  background: rgba(96, 165, 250, 0.06);
}

.my-emp-subtitle {
  font-size: 0.9rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.88);
  margin: 0 0 0.65rem;
}

.mod-declaration-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.mod-declaration-li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(0, 0, 0, 0.2);
}

.mod-declaration-li.is-active {
  border-color: rgba(96, 165, 250, 0.45);
  background: rgba(96, 165, 250, 0.08);
}

.empty-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.38);
  margin: 0.35rem 0 0;
  line-height: 1.45;
}

.employees-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 17.5rem), 1fr));
  gap: 1rem;
}

.employee-card {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 1.25rem;
  transition: border-color 0.2s;
}

.employee-card:hover {
  border-color: rgba(255, 255, 255, 0.2);
  background: transparent;
}

.employee-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.employee-card-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
}

.employee-badge {
  font-size: 11px;
  color: #60a5fa;
  background: transparent;
  border: 1px solid rgba(96, 165, 250, 0.4);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  white-space: nowrap;
}

.employee-desc {
  font-size: 13px;
  color: rgba(255,255,255,0.4);
  margin: 0 0 0.75rem;
  line-height: 1.5;
}

.employee-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 0.75rem;
  border-top: 0.5px solid rgba(255,255,255,0.06);
}

.employee-price {
  font-size: 14px;
  font-weight: 600;
  color: #ff6b6b;
}

.employee-price.free {
  color: #4ade80;
}

.employee-version {
  font-size: 12px;
  color: rgba(255,255,255,0.3);
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: rgba(255,255,255,0.4);
}

.loading {
  text-align: center;
  padding: 2rem;
  color: rgba(255,255,255,0.4);
}

.flash {
  padding: 10px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.45;
}

.flash-err {
  background: transparent;
  border: 1px solid rgba(255, 107, 107, 0.45);
  color: #ff8a8a;
}

.flash-success {
  background: transparent;
  border: 1px solid rgba(74, 222, 128, 0.4);
  color: #4ade80;
}

.flash-info {
  background: transparent;
  border: 1px solid rgba(96, 165, 250, 0.35);
  color: rgba(147, 197, 253, 0.95);
}

.flash-warn {
  background: transparent;
  border: 1px solid rgba(251, 191, 36, 0.4);
  color: #fcd34d;
}

.sandbox-gate-panel {
  margin-bottom: 1rem;
  padding: 1rem 1.125rem;
  border-radius: 10px;
  border: 1px solid rgba(34, 197, 94, 0.35);
  background: transparent;
}

.sandbox-gate-title {
  margin: 0 0 0.65rem;
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.88);
}

.sandbox-json-ta {
  width: 100%;
  margin-bottom: 0.75rem;
  box-sizing: border-box;
}

.sandbox-gate-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.sandbox-ack-label {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.65);
  cursor: pointer;
  margin: 0.5rem 0 0;
}

.sandbox-ack-label input {
  margin-top: 0.2rem;
}

.sandbox-mini-report {
  margin-top: 0.5rem;
}

.sandbox-pill {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.sandbox-pill--ok {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.sandbox-pill--fail {
  background: rgba(248, 113, 113, 0.2);
  color: #fca5a5;
}

.sandbox-err-list {
  margin: 0.5rem 0 0;
  padding-left: 1.1rem;
  font-size: 12px;
  color: rgba(252, 165, 165, 0.95);
}

.five-dim-actions {
  margin-bottom: 1rem;
}

.audit-panel {
  margin-bottom: 1rem;
  padding: 1rem 1.125rem;
  border-radius: 10px;
  border: 1px solid rgba(96, 165, 250, 0.35);
  background: transparent;
}

.audit-panel-title {
  margin: 0 0 0.75rem;
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.88);
}

.audit-muted {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.42);
}

.audit-flash {
  margin: 0 0 0.5rem;
}

.audit-summary-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1rem;
  margin-bottom: 1rem;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.72);
}

.audit-summary-row strong {
  color: #93c5fd;
  font-size: 1.1em;
}

.audit-pass-badge {
  font-size: 11px;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  background: transparent;
  border: 1px solid transparent;
}

.audit-pass-badge--ok {
  background: transparent;
  border: 1px solid rgba(74, 222, 128, 0.45);
  color: #4ade80;
}

.audit-pass-badge--fail {
  background: transparent;
  border: 1px solid rgba(248, 113, 113, 0.45);
  color: #fca5a5;
}

.audit-dims-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 13.5rem), 1fr));
  gap: 0.65rem;
  margin-bottom: 1rem;
}

.audit-dim-card {
  padding: 0.65rem 0.75rem;
  border-radius: 8px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.audit-dim-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.audit-dim-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}

.audit-dim-score {
  font-size: 16px;
  font-weight: 700;
  color: #e0f2fe;
}

.audit-reasons {
  margin: 0;
  padding-left: 1rem;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  line-height: 1.45;
}

.audit-ftests-title {
  margin: 0 0 0.5rem;
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.65);
}

.audit-ftests-list {
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 12px;
}

.audit-ftests-list li {
  padding: 0.35rem 0;
  border-bottom: 0.5px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.audit-ftests-list li:last-child {
  border-bottom: none;
}

.ft-name {
  font-weight: 500;
  color: rgba(255, 255, 255, 0.75);
}

.ft-detail {
  color: rgba(255, 255, 255, 0.45);
  word-break: break-word;
}

.ft-url {
  font-size: 10px;
  color: rgba(147, 197, 253, 0.7);
}

.ft-ok .ft-name {
  color: #86efac;
}

.ft-fail .ft-name {
  color: #fca5a5;
}

.ft-skip .ft-name {
  color: rgba(250, 204, 21, 0.85);
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.btn {
  padding: 0.625rem 1.25rem;
  border: 0.5px solid rgba(255,255,255,0.15);
  border-radius: 8px;
  background: transparent;
  color: rgba(255,255,255,0.7);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn:hover {
  background: rgba(255,255,255,0.06);
  color: #ffffff;
}

.btn-primary {
  background: #60a5fa;
  color: #0a0a0a;
  border: none;
}

.btn-primary:hover {
  background: #3b82f6;
  color: #0a0a0a;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 900px) {
  .hero-metrics {
    grid-template-columns: 1fr 1fr;
  }
  .workbench-toolbar { left: 4px; right: 4px; max-width: calc(100vw - 8px); }
  .workbench-header {
    flex-direction: column;
  }
  
  .authoring-tips-section {
    grid-template-columns: 1fr;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
