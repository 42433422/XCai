<template>
  <div>
    <h1 class="page-title">资金与记录</h1>

    <div class="balance-card">
      <div class="balance-label">当前余额</div>
      <div class="balance-value" :class="{ 'balance-updating': isUpdating }">¥{{ balance !== null ? balance.toFixed(2) : '--' }}</div>
      <div v-if="balance !== null" class="balance-gauge" aria-hidden="true">
        <template v-if="(membershipReferenceYuan ?? 0) > 0">
          <div class="balance-gauge__track">
            <div class="balance-gauge__fill" :style="{ width: balanceGaugeFill + '%' }" />
          </div>
          <p class="balance-gauge__hint">
            会员随单「可用额度」参考线
            <strong>¥{{ (membershipReferenceYuan ?? 0).toFixed(0) }}</strong>
            ：多笔/升级时累加（退款会冲抵）；无流水时按当前有效套餐的对应整数额度。条长为当前余额相对本线，满格即达参考线。其它入金不计入本线，以实际扣费为准。
          </p>
        </template>
        <p v-else class="balance-gauge__empty">
          暂无会员参考线：成为会员后，会按随单赠额与当前套餐价显示参考线；也可先
          <router-link to="/plans" class="inline-link">选套餐</router-link>。
        </p>
      </div>
    </div>
    <div class="card" v-if="myPlan">
      <h3 class="card-title">我的套餐</h3>
      <p class="recharge-intro">{{ myPlan.name }} · 到期 {{ formatDate(myPlan.expires_at) }}</p>
      <div class="quota-chips">
        <span v-for="q in myQuotas" :key="q.quota_type" class="quota-chip">
          {{ quotaLabel(q.quota_type) }} {{ q.remaining }}/{{ q.total }}
        </span>
      </div>
      <p class="plan-extra-links">
        <router-link :to="{ name: 'account', hash: '#api-keys' }" class="inline-link">API 密钥</router-link>
        <span class="plan-extra-sep">·</span>
        <router-link to="/analytics" class="inline-link">使用统计</router-link>
        <span class="plan-extra-sep">·</span>
        <router-link to="/refunds" class="inline-link">退款申请</router-link>
      </p>
    </div>

    <div class="card recharge-card">
      <h3 class="card-title">支付宝充值</h3>
      <p class="recharge-intro">输入金额后跳转支付宝完成付款，到账后余额与交易记录会自动更新。</p>
      <div v-if="payErr" class="flash flash-err">{{ payErr }}</div>
      <div v-if="payHint" class="flash flash-ok">{{ payHint }}</div>
      <div class="recharge-form">
        <input
          class="input"
          type="number"
          v-model.number="payAmount"
          placeholder="金额（元）"
          min="0.01"
          step="0.01"
          :class="{ 'input-error': payAmount && payAmount <= 0 }"
          @input="validateAmount"
        />
        <input class="input" v-model="payNote" placeholder="备注（可选）" maxlength="50" />
        <button class="btn btn-primary-solid" type="button" :disabled="paying || !isValidAmount" @click="startAlipayRecharge">
          {{ paying ? '正在拉起支付…' : '支付宝充值' }}
        </button>
      </div>
      <p v-if="amountError" class="error-message">{{ amountError }}</p>
      <p class="recharge-hint">
        若按钮无反应，请确认服务端已配置支付宝密钥与
        <code>ALIPAY_NOTIFY_URL</code>。套餐购买请前往
        <router-link to="/plans" class="inline-link">套餐页</router-link>。
      </p>
    </div>

    <div class="card finance-center-card">
      <div class="finance-head">
        <div>
          <h3 class="card-title">资金账户中心</h3>
          <p class="recharge-intro">订单付款会先进入钱包，再从钱包扣款；退款审核通过后退回钱包余额。</p>
        </div>
        <button type="button" class="btn btn-ghost" :disabled="financeLoading" @click="loadWalletOverview">
          {{ financeLoading ? '刷新中…' : '刷新' }}
        </button>
      </div>
      <div class="finance-grid">
        <section class="finance-panel">
          <div class="finance-panel-head">
            <h4>最近订单</h4>
            <div class="finance-panel-head__actions">
              <button
                v-if="recentOrders.length"
                type="button"
                class="btn btn-ghost finance-dismiss-btn"
                :disabled="dismissOrdersLoading || financeLoading"
                @click="dismissNonActiveOrders"
              >
                {{ dismissOrdersLoading ? '处理中…' : '清理展示' }}
              </button>
              <router-link to="/orders" class="inline-link">全部订单</router-link>
            </div>
          </div>
          <p
            v-if="!financeLoading && orderListTotal > RECENT_ORDERS_PANEL_LIMIT"
            class="finance-orders-omit"
          >
            本卡片仅显示最近 {{ RECENT_ORDERS_PANEL_LIMIT }} 单；当前列表共
            <strong>{{ orderListTotal }}</strong> 单，可点「全部订单」查看。点击「清理展示」可隐藏已关闭/失败/已退款等终态，仅保留待付、已付与退款中。
          </p>
          <div v-if="financeLoading" class="loading">加载中...</div>
          <div v-else-if="recentOrders.length" class="finance-list">
            <button
              v-for="order in recentOrdersPanel"
              :key="order.out_trade_no"
              type="button"
              class="finance-row"
              @click="goOrder(order)"
            >
              <span>
                <strong>{{ order.subject }}</strong>
                <small>{{ order.out_trade_no }}</small>
              </span>
              <span class="finance-row-side">
                <b>¥{{ money(order.total_amount) }}</b>
                <small>{{ orderStatusText(order.status) }}</small>
              </span>
            </button>
          </div>
          <div v-else class="empty-state">暂无订单</div>
        </section>
        <section class="finance-panel">
          <div class="finance-panel-head">
            <h4>退款记录</h4>
            <router-link to="/refunds" class="inline-link">申请退款</router-link>
          </div>
          <div v-if="financeLoading" class="loading">加载中...</div>
          <div v-else-if="recentRefunds.length" class="finance-list">
            <div v-for="refund in recentRefunds" :key="refund.id" class="finance-row finance-row--static">
              <span>
                <strong>{{ refund.refund_no }}</strong>
                <small>{{ refund.order_no }}</small>
              </span>
              <span class="finance-row-side">
                <b>¥{{ money(refund.amount) }}</b>
                <small>{{ refundStatusText(refund.status) }}</small>
              </span>
            </div>
          </div>
          <div v-else class="empty-state">暂无退款记录</div>
        </section>
      </div>
    </div>

    <div class="card">
      <h3 class="card-title">交易记录</h3>
      <div v-if="txLoading" class="loading">加载中...</div>
      <template v-else-if="transactions.length">
        <table class="tx-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>类型</th>
              <th>金额</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in visibleTransactions" :key="t.id">
              <td>{{ formatDate(t.created_at) }}</td>
              <td>{{ txnTypeLabel(t.type) }}</td>
              <td :class="t.amount > 0 ? 'amount-pos' : 'amount-neg'">
                {{ t.amount > 0 ? '+' : '' }}¥{{ t.amount.toFixed(2) }}
              </td>
              <td>
                {{ t.description }}
                <small v-if="t.order_no || t.refund_no" class="tx-ref">
                  {{ t.order_no ? `订单 ${t.order_no}` : '' }}
                  {{ t.refund_no ? `退款 ${t.refund_no}` : '' }}
                </small>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="transactions.length > RECENT_TX_PANEL_LIMIT" class="tx-more-wrap">
          <button type="button" class="btn btn-ghost" @click="txListExpanded = !txListExpanded">
            {{ txListExpanded ? '收起' : `展开其余 ${hiddenTxCount} 条` }}
          </button>
        </div>
      </template>
      <div v-else class="empty-state">暂无交易记录</div>
    </div>

    <div class="card llm-card">
      <header class="llm-card-head">
        <div class="llm-card-head__row">
          <span class="llm-card-head__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M12 3v2M5.6 5.6l1.4 1.4M3 12h2M5.6 18.4l1.4-1.4M12 21v-2M18.4 18.4l-1.4-1.4M21 12h-2M18.4 5.6l-1.4 1.4"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
              />
              <circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="1.5" />
            </svg>
          </span>
          <div class="llm-card-head__text">
            <h3 class="llm-section-title">大模型 API</h3>
            <p class="llm-intro">
              模型目录由各厂商接口拉取并缓存约 10 分钟，可随时刷新；下方按「语言 / 视觉 / 生图 / 视频」分组。默认模型写入账户；BYOK 经服务端加密保存。除<strong>小米 MiMo</strong>外，磁贴「已配置」仅看 BYOK；小米若服务端配置了环境变量密钥，会显示「平台密钥」并视为已配置。
            </p>
          </div>
        </div>
      </header>
      <div v-if="llmErr" class="flash flash-err">{{ llmErr }}</div>
      <div v-if="llmNote" class="flash flash-ok">{{ llmNote }}</div>
      <div class="llm-toolbar">
        <div class="llm-toolbar__main">
          <button
            type="button"
            class="btn llm-refresh-btn"
            :disabled="llmCatalogLoading"
            @click="refreshCatalog(true)"
          >
            <span class="llm-refresh-btn__icon" :class="{ 'llm-refresh-btn__icon--spin': llmCatalogLoading }" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M4.5 12a7.5 7.5 0 0 1 12.74-5.33M19.5 12a7.5 7.5 0 0 1-12.74 5.33M19.5 3v4.5H15M4.5 21v-4.5H9"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </span>
            <span>{{ llmCatalogLoading ? '加载中…' : '刷新模型列表' }}</span>
          </button>
          <div v-if="catalogSyncMeta" class="llm-sync-meta">
            <span class="llm-pill" :title="`ISO ${catalogSyncMeta.fetchedAt}`">
              <svg class="llm-pill__icon" viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" />
                <path d="M12 7v5l3 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              最近拉取 {{ formatCatalogFetchedAt(catalogSyncMeta.fetchedAt) }}
            </span>
            <span class="llm-pill llm-pill--accent">缓存 TTL {{ catalogSyncMeta.ttlSec }}s</span>
          </div>
        </div>
        <p
          v-if="catalog && catalog.fernet_configured === false"
          class="llm-toolbar-hint"
          role="note"
        >
          <span class="llm-toolbar-hint__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.4" />
              <path d="M12 10v5M12 8h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
            </svg>
          </span>
          <span class="llm-toolbar-hint__text">
            保存 BYOK 需在服务端配置 Fernet 主密钥
            <code class="llm-code llm-code--hint">MODSTORE_LLM_MASTER_KEY</code>
          </span>
        </p>
      </div>
      <div v-if="llmCatalogLoading && !catalog" class="loading">加载模型目录…</div>
      <template v-else-if="catalog">
        <div class="llm-grid" role="list">
          <button
            v-for="block in catalog.providers"
            :key="block.provider"
            type="button"
            class="llm-tile"
            :class="{
              'llm-tile--active': selectedProvider === block.provider,
              'llm-tile--keyed': providerTileState(block) !== 'inactive',
              'llm-tile--keywarn': providerTileState(block) === 'warn',
              'llm-tile--keydanger': providerTileState(block) === 'danger',
            }"
            role="listitem"
            :aria-pressed="selectedProvider === block.provider"
            :aria-label="`选择 ${block.label}，共 ${block.models.length} 个模型`"
            :title="providerTileTitle(block)"
            @click="selectProvider(block.provider)"
          >
            <span
              class="llm-tile__icon"
              :class="'llm-tile__icon--' + providerTileState(block)"
              aria-hidden="true"
            >
              <img
                v-if="llmTileShowsImg(block)"
                class="llm-tile__img"
                :src="llmProviderIconImgSrc(block.provider)"
                alt=""
                width="36"
                height="36"
                loading="lazy"
                @error="iconLoadFailed[llmTileIconFailKey(block)] = true"
              />
              <span v-else class="llm-tile__fallback" :class="'llm-tile__fallback--' + providerTileState(block)">{{
                llmInitials(block.label)
              }}</span>
            </span>
            <span class="llm-tile__name">{{ block.label }}</span>
            <span class="llm-tile__count">{{ block.models.length }} 个模型</span>
          </button>
        </div>
        <div v-if="currentProviderBlock" class="llm-model-panel">
          <div class="llm-model-panel__head">
            <span class="llm-model-panel__label">当前模型</span>
            <span v-if="selectedModel" class="llm-model-panel__hint">在列表中按分类快速定位</span>
          </div>
          <div class="llm-select-wrap">
            <select v-model="selectedModel" class="llm-select" @change="schedulePersistPreferences">
              <template v-for="cat in LLM_CATEGORY_ORDER" :key="cat">
                <optgroup v-if="modelsForCategory(cat).length" :label="categoryLabel(cat)">
                  <option v-for="row in modelsForCategory(cat)" :key="row.id" :value="row.id">
                    {{ modelOptionLabel(row) }}
                  </option>
                </optgroup>
              </template>
            </select>
          </div>
          <p v-if="catalog?.gate_hints" class="llm-gate-hint">
            闸门：平台目录校验 {{ catalog.gate_hints.platform_catalog_gate ? '开' : '关' }} · BYOK 目录校验
            {{ catalog.gate_hints.byok_catalog_gate ? '开' : '关' }} · 平台须登记定价
            {{ catalog.gate_hints.platform_require_priced ? '开' : '关' }}。未登记定价时预授权可能上浮。
          </p>
        </div>
        <div v-else-if="catalog.providers.length" class="llm-empty-models">请选择供应商。</div>
        <div
          v-if="currentProviderBlock && !currentProviderBlock.models.length"
          class="llm-empty-models"
        >
          暂无可用模型：请配置 BYOK 的 API Key 后点击「刷新模型列表」。
        </div>

        <details class="llm-details">
          <summary class="llm-details__summary">
            <span class="llm-details__chevron" aria-hidden="true" />
            <span class="llm-details__summary-text">我的 API 密钥（BYOK）</span>
            <span
              v-if="byokConfiguredCount > 0"
              class="llm-byok-summary-badge"
            >{{ byokConfiguredCount }} 个已保存</span>
            <span
              v-else
              class="llm-byok-summary-badge llm-byok-summary-badge--muted"
            >未配置 BYOK</span>
          </summary>
          <p class="llm-byok-intro">
            密钥经服务端主密钥加密入库；接口仅返回掩码。可粘贴整段 .env 一键匹配厂商保存，无需逐行打开各厂商表单。
          </p>

          <div class="llm-byok-import">
            <label class="llm-byok-import__label" for="byok-bulk">一键导入</label>
            <textarea
              id="byok-bulk"
              v-model="byokBulkPaste"
              class="input llm-byok-bulk"
              rows="8"
              autocomplete="off"
              spellcheck="false"
              placeholder="粘贴 .env 片段或直接贴密钥，例如：&#10;OPENAI_API_KEY=sk-...&#10;OPENAI_BASE_URL=https://api.openai.com&#10;DEEPSEEK_API_KEY=sk-...&#10;moonshot=sk-...&#10;sk-...（无标签也可，将自动识别厂商）"
            />
            <p class="llm-byok-import__hint">
              支持环境变量名（与部署文档一致）、<code class="llm-code llm-code--hint">厂商id=密钥</code>，或直接粘贴裸密钥——会依次试拉各厂商 <code class="llm-code llm-code--hint">/models</code> 自动匹配归属。
            </p>
            <div class="llm-byok-import__actions">
              <button
                type="button"
                class="btn btn-primary-solid"
                :disabled="byokImportDisabled"
                @click="importByokBulk"
              >
                {{ byokImportBusy ? '保存中…' : '解析并保存' }}
              </button>
              <button type="button" class="btn btn-ghost" :disabled="byokImportBusy" @click="byokBulkPaste = ''">
                清空输入
              </button>
            </div>
          </div>

          <div class="llm-byok-list-head">各厂商状态</div>
          <ul class="llm-byok-list" role="list">
            <li v-for="st in llmStatusList" :key="st.provider" class="llm-byok-row" role="listitem">
              <div class="llm-byok-row__main">
                <span class="llm-byok-row__name">{{ st.label || st.provider }}</span>
                <span class="llm-byok-tags">
                  <span v-if="st.has_user_override" class="tag tag-user">BYOK</span>
                  <span v-if="st.provider === 'xiaomi' && st.has_platform_key" class="tag">平台密钥</span>
                  <span v-if="st.masked_key" class="llm-mask">{{ st.masked_key }}</span>
                  <span
                    v-else-if="!st.has_user_override && !(st.provider === 'xiaomi' && st.has_platform_key)"
                    class="llm-byok-row__dash"
                  >—</span>
                </span>
              </div>
              <button
                v-if="st.has_user_override"
                type="button"
                class="btn btn-ghost llm-byok-row__clear"
                :disabled="byokSaving === st.provider || byokImportBusy"
                @click="clearByok(st.provider)"
              >
                清除
              </button>
            </li>
          </ul>

          <details class="llm-details llm-details--nested">
            <summary class="llm-details__summary llm-details__summary--nested">
              <span class="llm-details__chevron" aria-hidden="true" />
              <span class="llm-details__summary-text">高级：逐厂商填写</span>
            </summary>
            <p class="llm-byok-intro llm-byok-intro--nested">适合只改单个 Key 或 Base URL 时使用。</p>
            <div v-for="st in llmStatusList" :key="'adv-' + st.provider" class="llm-byok-block">
              <div class="llm-byok-head">
                <strong>{{ st.label || st.provider }}</strong>
                <span class="llm-byok-tags">
                  <span v-if="st.has_user_override" class="tag tag-user">BYOK</span>
                  <span v-if="st.provider === 'xiaomi' && st.has_platform_key" class="tag">平台密钥</span>
                  <span v-if="st.masked_key" class="llm-mask">{{ st.masked_key }}</span>
                </span>
              </div>
              <div v-if="LLM_OAI_COMPAT_BASE_URL_PROVIDERS.includes(st.provider)" class="llm-byok-fields">
                <input
                  v-model="byokBaseUrl[st.provider]"
                  class="input"
                  type="text"
                  autocomplete="off"
                  placeholder="可选：自定义 Base URL（OpenAI 兼容）"
                />
              </div>
              <input
                v-model="byokKey[st.provider]"
                class="input"
                type="password"
                autocomplete="new-password"
                :placeholder="'粘贴 ' + st.provider + ' 的 API Key'"
              />
              <div class="llm-byok-actions">
                <button type="button" class="btn btn-primary-solid" :disabled="byokSaving === st.provider || byokImportBusy" @click="saveByok(st.provider)">
                  {{ byokSaving === st.provider ? '保存中…' : '保存密钥' }}
                </button>
                <button type="button" class="btn btn-ghost" :disabled="byokSaving === st.provider || byokImportBusy" @click="clearByok(st.provider)">
                  清除 BYOK
                </button>
              </div>
            </div>
          </details>
        </details>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, reactive, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { parseByokPaste } from '../byokEnvImport'
import { requestJson } from '../infrastructure/http/client'
import { llmUiMeta, LLM_OAI_COMPAT_BASE_URL_PROVIDERS } from '../llmModels'
import { classifyLlmCatalogIssue, hasAnyLlmKey } from '../llmProviderHealth'
import { llmProviderIconImgSrc } from '../llmIconUrls'
import { useWalletStore } from '../stores/wallet'

/** 与后端 llm_model_taxonomy.CATEGORY_ORDER 一致 */
const LLM_CATEGORY_ORDER = ['llm', 'vlm', 'image', 'video', 'other']

const router = useRouter()
const walletStore = useWalletStore()
const { balance, membershipReferenceYuan } = storeToRefs(walletStore)
const transactions = ref([])
const txLoading = ref(true)
const financeLoading = ref(true)
const recentOrders = ref([])
const orderListTotal = ref(0)
const dismissOrdersLoading = ref(false)
/** 资金页「最近订单」只展示前 N 条，避免与「全部订单」重复堆叠 */
const RECENT_ORDERS_PANEL_LIMIT = 5
/** 交易记录表默认只展示最近 N 条，其余由按钮展开 */
const RECENT_TX_PANEL_LIMIT = 5
const txListExpanded = ref(false)
const recentRefunds = ref([])
const payAmount = ref(null)
const payNote = ref('')
const paying = ref(false)
const payErr = ref('')
const payHint = ref('')
const isUpdating = ref(false)
const lastBalance = ref(null)
const amountError = ref('')
const myPlan = ref(null)
const myQuotas = ref([])
const isValidAmount = computed(() => {
  const amt = Number(payAmount.value)
  return !isNaN(amt) && amt > 0
})

/** 条长 = 当前余额 / 会员参考线（多笔单随单赠额与退款冲抵的净值；无则当前套餐价取整） */
const balanceGaugeFill = computed(() => {
  const refY = Math.max(0, Number(membershipReferenceYuan.value ?? 0))
  if (refY <= 0) return 0
  const b = Number(balance.value)
  if (!isFinite(b) || b < 0) return 0
  return Math.min(100, (b / refY) * 100)
})

const catalog = ref(null)
const llmStatusList = ref([])
const llmCatalogLoading = ref(false)
const llmErr = ref('')
const llmNote = ref('')
const selectedProvider = ref('openai')
const selectedModel = ref('')
const iconLoadFailed = reactive({})
const llmBootstrapped = ref(false)
const byokKey = reactive({})
const byokBaseUrl = reactive({})
const byokSaving = ref('')
const byokBulkPaste = ref('')
const byokImportBusy = ref(false)

let _prefTimer = null
let _catalogInterval = null

const recentOrdersPanel = computed(() =>
  (recentOrders.value || []).slice(0, RECENT_ORDERS_PANEL_LIMIT)
)

const visibleTransactions = computed(() => {
  const list = transactions.value || []
  if (txListExpanded.value || list.length <= RECENT_TX_PANEL_LIMIT) return list
  return list.slice(0, RECENT_TX_PANEL_LIMIT)
})

const hiddenTxCount = computed(() => {
  const n = (transactions.value || []).length
  return Math.max(0, n - RECENT_TX_PANEL_LIMIT)
})

const currentProviderBlock = computed(() => {
  if (!catalog.value) return null
  return catalog.value.providers.find((p) => p.provider === selectedProvider.value) || null
})

function categoryLabel(cat) {
  return catalog.value?.category_labels?.[cat] || cat
}

/** @param {{ id: string, category?: string, capability?: Record<string, unknown> }} row */
function modelOptionLabel(row) {
  const id = row.id || ''
  const c = row.capability
  if (!c || typeof c !== 'object') return id
  const tags = []
  if (c.l3_status === 'approved') tags.push('L3已通过')
  else if (c.l3_status === 'pending') tags.push('L3审核中')
  if (c.l1_status === 'ok') tags.push('L1探针通过')
  else if (c.l1_status === 'pending') tags.push('L1待探针')
  if (c.platform_billing_ok === false) tags.push('平台计费受限')
  return tags.length ? `${id}（${tags.join('·')}）` : id
}

function modelsForCategory(cat) {
  const block = currentProviderBlock.value
  const detailed = block?.models_detailed
  if (detailed && detailed.length) {
    return detailed.filter((r) => r.category === cat)
  }
  if (cat === 'llm' && block?.models?.length) {
    return block.models.map((id) => ({ id, category: 'llm' }))
  }
  return []
}

const byokConfiguredCount = computed(() => llmStatusList.value.filter((s) => s.has_user_override).length)

const byokImportDisabled = computed(() => {
  if (!catalog.value?.fernet_configured) return true
  if (byokImportBusy.value) return true
  if (!(byokBulkPaste.value || '').trim()) return true
  return false
})

/** 目录同步元信息（用于工具栏徽章） */
const catalogSyncMeta = computed(() => {
  if (!catalog.value) return null
  const lines = catalog.value.providers.map((p) => p.fetched_at).filter(Boolean)
  if (!lines.length) return null
  return {
    fetchedAt: lines[lines.length - 1],
    ttlSec: catalog.value.cache_ttl_seconds ?? 600,
  }
})

/** provider id -> /api/llm/status 行 */
const llmStatusByProvider = computed(() => {
  const m = {}
  for (const s of llmStatusList.value || []) {
    if (s && s.provider) m[s.provider] = s
  }
  return m
})

function formatCatalogFetchedAt(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return String(iso)
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return String(iso)
  }
}

/** @param {{ provider: string, label?: string, error?: string|null, fetch_source?: string|null }} block */
function llmTileShowsImg(block) {
  const u = llmProviderIconImgSrc(block.provider)
  if (!u) return false
  return !iconLoadFailed[llmTileIconFailKey(block)]
}

/** @param {{ provider: string, label?: string, error?: string|null, fetch_source?: string|null }} block */
function providerTileState(block) {
  const st = llmStatusByProvider.value[block.provider]
  const keyPresent = hasAnyLlmKey(st)
  if (!keyPresent) return 'inactive'
  const issue = classifyLlmCatalogIssue(block.error, block.fetch_source)
  if (issue === 'expired') return 'danger'
  if (issue === 'danger') return 'danger'
  if (issue === 'warn') return 'warn'
  return 'ok'
}

/** 与图标 URL 联动，避免换色后仍沿用旧失败态 */
function llmTileIconFailKey(block) {
  return `${block.provider}__${providerTileState(block)}`
}

/** @param {{ provider: string, label?: string, error?: string|null, fetch_source?: string|null }} block */
function providerTileTitle(block) {
  const n = block.label || block.provider
  const st = llmStatusByProvider.value[block.provider]
  const ps = providerTileState(block)
  const keyTag =
    st?.has_user_override === true
      ? 'BYOK'
      : block.provider === 'xiaomi' && st?.has_platform_key
        ? '平台密钥'
        : 'BYOK'
  if (ps === 'inactive') {
    if (block.provider === 'xiaomi') {
      return `${n}：未配置 BYOK，且未检测到服务端小米密钥`
    }
    return `${n}：未配置 BYOK 密钥`
  }
  if (ps === 'warn') return `${n}：${keyTag} 已配置；模型列表拉取降级或限流，请检查网络、额度或稍后重试`
  if (classifyLlmCatalogIssue(block.error, block.fetch_source) === 'expired') {
    return `${n}：${keyTag} 已过期或失效；请删除旧密钥后重新配置`
  }
  if (ps === 'danger') return `${n}：${keyTag} 已配置；模型接口不可用（认证失败、额度/账单或配置错误）`
  return `${n}：${keyTag} 已配置，模型列表正常`
}

function llmInitials(label) {
  const parts = label.replace(/\s+/g, ' ').trim().split(' ')
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return label.slice(0, 2).toUpperCase()
}

function syncSelectionFromServerPrefs() {
  if (!catalog.value) return
  const pref = catalog.value.preferences || {}
  let prov = pref.provider || 'openai'
  if (!catalog.value.providers.some((p) => p.provider === prov)) {
    prov = catalog.value.providers[0]?.provider || 'openai'
  }
  selectedProvider.value = prov
  const block = catalog.value.providers.find((p) => p.provider === prov)
  const models = block?.models || []
  let mod = pref.model || ''
  if (!mod || !models.includes(mod)) mod = models[0] || ''
  selectedModel.value = mod
}

function validateSelectionAfterRefresh() {
  if (!catalog.value) return
  const block = catalog.value.providers.find((p) => p.provider === selectedProvider.value)
  if (!block) {
    syncSelectionFromServerPrefs()
    return
  }
  if (!selectedModel.value || !block.models.includes(selectedModel.value)) {
    selectedModel.value = block.models[0] || ''
  }
}

async function loadLlmStatus() {
  try {
    const res = await api.llmStatus()
    llmStatusList.value = res.providers || []
  } catch (e) {
    llmStatusList.value = []
    if (localStorage.getItem('modstore_token')) llmErr.value = e.message || String(e)
  }
}

async function loadCatalog(isManualRefresh) {
  if (!localStorage.getItem('modstore_token')) return
  llmCatalogLoading.value = true
  llmErr.value = ''
  try {
    const res = await api.llmCatalog(isManualRefresh)
    catalog.value = res
    if (!llmBootstrapped.value) {
      syncSelectionFromServerPrefs()
      llmBootstrapped.value = true
    } else if (isManualRefresh) {
      validateSelectionAfterRefresh()
    }
  } catch (e) {
    llmErr.value = e.message || String(e)
  } finally {
    llmCatalogLoading.value = false
  }
}

async function refreshCatalog(isManual) {
  await Promise.all([loadCatalog(isManual), loadLlmStatus()])
}

function selectProvider(id) {
  selectedProvider.value = id
  const block = catalog.value?.providers.find((p) => p.provider === id)
  const models = block?.models || []
  if (!selectedModel.value || !models.includes(selectedModel.value)) {
    selectedModel.value = models[0] || ''
  }
  schedulePersistPreferences()
}

function schedulePersistPreferences() {
  if (_prefTimer) clearTimeout(_prefTimer)
  _prefTimer = setTimeout(() => {
    persistPreferences()
  }, 450)
}

async function persistPreferences() {
  if (!selectedProvider.value || !selectedModel.value) return
  try {
    await api.llmSavePreferences(selectedProvider.value, selectedModel.value)
    llmNote.value = '已保存默认模型'
    setTimeout(() => {
      if (llmNote.value === '已保存默认模型') llmNote.value = ''
    }, 2000)
  } catch (e) {
    llmErr.value = e.message || String(e)
  }
}

async function saveByok(provider) {
  const key = (byokKey[provider] || '').trim()
  if (!key) {
    llmErr.value = '请先粘贴 API Key'
    return
  }
  byokSaving.value = provider
  llmErr.value = ''
  try {
    const base = LLM_OAI_COMPAT_BASE_URL_PROVIDERS.includes(provider)
      ? (byokBaseUrl[provider] || '').trim() || null
      : null
    await api.llmSaveCredentials(provider, key, base)
    byokKey[provider] = ''
    llmNote.value = '已保存 BYOK'
    setTimeout(() => {
      if (llmNote.value === '已保存 BYOK') llmNote.value = ''
    }, 2000)
    await refreshCatalog(false)
  } catch (e) {
    llmErr.value = e.message || String(e)
  } finally {
    byokSaving.value = ''
  }
}

function detectBareCredential(apiKey) {
  return requestJson('/api/llm/credentials/detect-bare', {
    method: 'POST',
    body: JSON.stringify({ api_key: apiKey }),
  })
}

async function importByokBulk() {
  if (byokImportDisabled.value) return
  byokImportBusy.value = true
  llmErr.value = ''
  try {
    const { entries, bareKeys, warnings } = parseByokPaste(byokBulkPaste.value)
    if (!entries.length && !bareKeys.length) {
      llmNote.value = [...warnings].filter(Boolean).join(' ') || '未解析到可保存项'
      return
    }

    const ok = []
    const fail = []

    if (entries.length) {
      const settled = await Promise.allSettled(
        entries.map((e) =>
          api.llmSaveCredentials(
            e.provider,
            e.api_key,
            LLM_OAI_COMPAT_BASE_URL_PROVIDERS.includes(e.provider) ? e.base_url || null : null,
          ),
        ),
      )
      settled.forEach((r, i) => {
        const id = entries[i].provider
        if (r.status === 'fulfilled') ok.push(id)
        else {
          const msg = r.reason && typeof r.reason === 'object' && r.reason.message ? r.reason.message : String(r.reason || '失败')
          fail.push(`${id}: ${msg}`)
        }
      })
    }

    const detected = []
    if (bareKeys.length) {
      const settled = await Promise.allSettled(bareKeys.map((k) => detectBareCredential(k)))
      settled.forEach((r, i) => {
        const tag = `裸密钥#${i + 1}`
        if (r.status === 'fulfilled') {
          const provider = (r.value && r.value.provider) || ''
          if (provider) {
            ok.push(provider)
            detected.push(provider)
          } else {
            fail.push(`${tag}: 后端未返回命中厂商`)
          }
        } else {
          const msg = r.reason && typeof r.reason === 'object' && r.reason.message ? r.reason.message : String(r.reason || '失败')
          fail.push(`${tag}: ${msg}`)
        }
      })
    }

    const parts = []
    if (ok.length) parts.push(`已保存 ${ok.length} 个：${ok.join('、')}`)
    if (detected.length) parts.push(`自动识别命中：${detected.join('、')}`)
    if (fail.length) parts.push(`失败 ${fail.length}：${fail.join('；')}`)
    if (warnings.length) parts.push(warnings.join(' '))
    llmNote.value = parts.filter(Boolean).join('。') || '完成'
    if (ok.length && !fail.length) byokBulkPaste.value = ''
    await Promise.all([loadLlmStatus(), loadCatalog(false)])
  } catch (e) {
    llmErr.value = e.message || String(e)
  } finally {
    byokImportBusy.value = false
  }
}

async function clearByok(provider) {
  byokSaving.value = provider
  llmErr.value = ''
  try {
    await api.llmDeleteCredentials(provider)
    llmNote.value = '已清除 BYOK'
    await refreshCatalog(false)
  } catch (e) {
    llmErr.value = e.message || String(e)
  } finally {
    byokSaving.value = ''
  }
}

function onVisibilityRefresh() {
  if (document.visibilityState === 'visible' && localStorage.getItem('modstore_token')) {
    refreshCatalog(false)
  }
}

onMounted(async () => {
  await Promise.all([loadWalletOverview(), loadMyPlan(), refreshCatalog(false)])
  _catalogInterval = setInterval(() => {
    if (localStorage.getItem('modstore_token')) refreshCatalog(false)
  }, 8 * 60 * 1000)
  document.addEventListener('visibilitychange', onVisibilityRefresh)
})

async function loadMyPlan() {
  try {
    const res = await api.paymentMyPlan()
    myPlan.value = res.plan
    myQuotas.value = res.quotas || []
  } catch {
    myPlan.value = null
    myQuotas.value = []
  }
}

function quotaLabel(t) {
  const m = { employee_count: '员工数', llm_calls: 'LLM 调用', storage_mb: '存储(MB)' }
  return m[t] || t
}

onUnmounted(() => {
  if (_catalogInterval) clearInterval(_catalogInterval)
  document.removeEventListener('visibilitychange', onVisibilityRefresh)
  if (_prefTimer) clearTimeout(_prefTimer)
})

watch(selectedProvider, () => {
  schedulePersistPreferences()
})

function txnTypeLabel(type) {
  const m = {
    recharge: '管理员充值',
    admin_self_credit: '管理员本人加款',
    alipay_wallet: '支付宝充值',
    alipay_recharge: '支付宝入账',
    alipay_payment: '支付入账',
    plan_purchase: '套餐购买',
    item_purchase: '商品购买',
    purchase: '购买',
    wallet_refund: '退款入账',
  }
  return m[type] || type || '—'
}

function orderStatusText(status) {
  const m = {
    pending: '待支付',
    paid: '已支付',
    refunding: '退款中',
    refunded: '已退款',
    partial_refunded: '部分退款',
    failed: '失败',
    closed: '已关闭',
  }
  return m[status] || status || '—'
}

function refundStatusText(status) {
  const m = {
    pending: '待审核',
    approved: '已退回钱包',
    rejected: '已拒绝',
    failed: '失败',
  }
  return m[status] || status || '—'
}

function money(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(2) : '0.00'
}

function goOrder(order) {
  if (!order?.out_trade_no) return
  router.push({ name: 'order-detail', params: { orderId: order.out_trade_no } })
}

async function loadWalletOverview() {
  financeLoading.value = true
  txLoading.value = true
  try {
    const res = await api.walletOverview(20, 0)
    const walletBalance = res?.wallet?.balance
    if (walletBalance !== undefined) {
      walletStore.setBalance(walletBalance)
    }
    if (res?.wallet?.membership_reference_yuan !== undefined) {
      walletStore.setMembershipReferenceYuan(res.wallet.membership_reference_yuan)
    }
    transactions.value = (res.transactions || []).map(normalizeTransaction)
    recentOrders.value = res.orders || []
    if (res.order_total != null) {
      orderListTotal.value = Number(res.order_total)
    } else {
      orderListTotal.value = (res.orders || []).length
    }
    recentRefunds.value = res.refunds || []
  } catch {
    recentOrders.value = []
    orderListTotal.value = 0
    recentRefunds.value = []
    await Promise.all([loadBalance(), loadTransactions()])
  } finally {
    financeLoading.value = false
    txLoading.value = false
  }
}

async function dismissNonActiveOrders() {
  if (dismissOrdersLoading.value) return
  if (
    !confirm('将已关闭/失败/已退款等终态单从「订单列表」中隐藏（不删单），并保留待支付、已支付、退款中。是否继续？')
  ) {
    return
  }
  dismissOrdersLoading.value = true
  try {
    const res = await api.paymentDismissNonActiveOrders()
    if (res?.ok === false) {
      payErr.value = res?.message || '清理失败'
    } else {
      payHint.value = `已隐藏 ${Number(res?.dismissed || 0)} 条，列表仅保留可跟进或已成功的单。`
      setTimeout(() => {
        payHint.value = ''
      }, 5000)
    }
    await loadWalletOverview()
  } catch (e) {
    payErr.value = e?.message || String(e)
  } finally {
    dismissOrdersLoading.value = false
  }
}

async function loadBalance() {
  try {
    const newBalance = await walletStore.refreshBalance()

    // 检测余额变化并触发动画
    if (balance.value !== null && newBalance !== balance.value) {
      isUpdating.value = true
      lastBalance.value = balance.value

      // 短暂延迟后更新余额
      setTimeout(() => {
        walletStore.setBalance(newBalance)
        // 动画结束后重置状态
        setTimeout(() => {
          isUpdating.value = false
        }, 500)
      }, 100)
    } else {
      walletStore.setBalance(newBalance)
    }
  } catch {
    walletStore.clear()
  }
}

async function loadTransactions() {
  txLoading.value = true
  try {
    const res = await api.transactions()
    transactions.value = (res.transactions || []).map(normalizeTransaction)
  } catch {
    transactions.value = []
  } finally {
    txLoading.value = false
  }
}

function normalizeTransaction(t) {
  return {
    ...t,
    amount: Number(t?.amount ?? 0),
  }
}

function validateAmount() {
  const amt = Number(payAmount.value)
  if (!amt || amt <= 0) {
    amountError.value = '请输入大于 0 的金额'
  } else if (amt > 999999) {
    amountError.value = '充值金额不能超过 999,999 元'
  } else {
    amountError.value = ''
  }
}

async function startAlipayRecharge() {
  if (!localStorage.getItem('modstore_token')) {
    await router.push({ name: 'login', query: { redirect: '/wallet' } })
    return
  }
  validateAmount()
  if (amountError.value) {
    return
  }
  paying.value = true
  payErr.value = ''
  payHint.value = ''
  const amt = Number(payAmount.value)
  try {
    const res = await api.paymentCheckout({
      wallet_recharge: true,
      total_amount: amt,
      subject: payNote.value.trim() || 'XC AGI 钱包充值',
    })
    if (!res.ok) {
      payErr.value = res.message || '下单失败'
      return
    }
    if (res.type === 'page' || res.type === 'wap') {
      if (res.redirect_url) {
        window.location.href = res.redirect_url
        return
      }
      payErr.value = '未返回支付跳转地址'
      return
    }
    if ((res.type === 'precreate' || res.type === 'wechat_native') && res.order_id) {
      await router.push({ name: 'checkout', params: { orderId: res.order_id } })
      return
    }
    payErr.value = '未知的支付类型'
  } catch (e) {
    payErr.value = e.message || String(e)
  } finally {
    paying.value = false
  }
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN')
}
</script>

<style scoped>
.page-title { font-size: 22px; margin-bottom: 20px; color: #ffffff; }
.balance-card { background: #111111; border: 0.5px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 24px; margin-bottom: 20px; }
.balance-label { font-size: 14px; color: rgba(255,255,255,0.5); }
.balance-value { font-size: 36px; font-weight: 700; margin-top: 4px; color: #ffffff; transition: all 0.5s ease-out; }
.balance-gauge { margin-top: 18px; }
.balance-gauge__track {
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
  box-shadow: inset 0 0 0 0.5px rgba(255, 255, 255, 0.06);
}
.balance-gauge__fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2dd4bf 0%, #22c55e 50%, #eab308 100%);
  background-size: 200% 100%;
  transition: width 0.6s ease-out;
  min-width: 0;
  box-shadow: 0 0 12px rgba(45, 212, 191, 0.25);
}
.balance-gauge__hint {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.38);
}
.balance-gauge__empty {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.4);
}
.balance-gauge__hint strong {
  color: rgba(255, 255, 255, 0.75);
  font-weight: 600;
}
.finance-center-card { margin-bottom: 20px; }
.finance-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.finance-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 16px; }
.finance-panel { border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 14px; background: rgba(0,0,0,0.18); }
.finance-panel-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 10px; }
.finance-panel-head h4 { margin: 0; font-size: 15px; color: rgba(255,255,255,0.86); }
.finance-panel-head__actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; justify-content: flex-end; }
.finance-dismiss-btn { font-size: 12px; padding: 4px 10px; }
.finance-orders-omit {
  margin: 0 0 10px;
  font-size: 11px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.38);
}
.finance-orders-omit strong { color: rgba(255, 255, 255, 0.55); font-weight: 600; }
.finance-list { display: grid; gap: 8px; }
.finance-row { width: 100%; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 10px; background: rgba(255,255,255,0.035); color: #fff; display: flex; justify-content: space-between; gap: 12px; text-align: left; cursor: pointer; }
.finance-row--static { cursor: default; }
.finance-row strong { display: block; font-size: 14px; font-weight: 650; }
.finance-row small { display: block; margin-top: 3px; color: rgba(255,255,255,0.46); font-size: 12px; word-break: break-all; }
.finance-row-side { text-align: right; flex-shrink: 0; }
.finance-row-side b { display: block; color: #c7d2fe; }
.tx-ref { display: block; margin-top: 4px; color: rgba(255,255,255,0.38); font-size: 12px; }
.tx-more-wrap {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 0.5px solid rgba(255, 255, 255, 0.06);
  text-align: center;
}

.balance-updating {
  animation: balanceUpdate 0.5s ease-out;
}

@keyframes balanceUpdate {
  0% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.8; }
  100% { transform: scale(1); opacity: 1; }
}
.recharge-intro { font-size: 13px; color: rgba(255,255,255,0.45); margin: 0 0 12px; line-height: 1.5; }
.recharge-card .recharge-form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.recharge-form .input { flex: 1; min-width: 120px; }
.recharge-hint { font-size: 12px; color: rgba(255,255,255,0.3); margin-top: 10px; line-height: 1.5; }
.recharge-hint code { font-size: 11px; color: rgba(255,255,255,0.45); }
.inline-link { color: #ffffff; font-weight: 500; text-decoration: underline; text-underline-offset: 2px; }
.plan-extra-links {
  margin: 0.75rem 0 0;
  font-size: 0.88rem;
}
.plan-extra-sep {
  margin: 0 0.35rem;
  color: rgba(255, 255, 255, 0.35);
}
.input-error { border-color: #ff6b6b !important; background-color: rgba(255, 107, 107, 0.1) !important; }
.error-message { font-size: 12px; color: #ff6b6b; margin-top: 8px; margin-bottom: 0; }

@media (max-width: 768px) {
  .finance-head,
  .finance-row {
    flex-direction: column;
  }
  .finance-grid {
    grid-template-columns: 1fr;
  }
  .finance-row-side {
    text-align: left;
  }
  .recharge-form {
    flex-direction: column;
  }
  .recharge-form .input {
    width: 100%;
    min-width: unset;
  }
  .recharge-form .btn {
    width: 100%;
  }
}
.tx-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.tx-table th { text-align: left; padding: 8px 12px; border-bottom: 0.5px solid rgba(255,255,255,0.1); color: rgba(255,255,255,0.4); font-weight: 600; }
.tx-table td { padding: 8px 12px; border-bottom: 0.5px solid rgba(255,255,255,0.06); }
.amount-pos { color: #4ade80; font-weight: 600; }
.amount-neg { color: #ff6b6b; font-weight: 600; }
.loading { text-align: center; padding: 20px; color: rgba(255,255,255,0.4); }
.empty-state { text-align: center; padding: 20px; color: rgba(255,255,255,0.4); }
.quota-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.quota-chip { font-size: 12px; border-radius: 999px; padding: 4px 8px; background: rgba(129,140,248,0.15); color: #c7d2fe; }

.llm-card {
  margin-top: 4px;
  background: linear-gradient(165deg, rgba(255, 255, 255, 0.04) 0%, rgba(17, 17, 17, 1) 42%, rgba(17, 17, 17, 1) 100%);
  border-color: rgba(255, 255, 255, 0.12);
}

.llm-card-head {
  margin-bottom: 18px;
  padding-bottom: 2px;
}
.llm-card-head__row {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.llm-card-head__icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c7d2fe;
  background: linear-gradient(145deg, rgba(129, 140, 248, 0.22), rgba(15, 23, 42, 0.9));
  border: 1px solid rgba(165, 180, 252, 0.35);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}
.llm-card-head__icon svg {
  width: 22px;
  height: 22px;
}
.llm-card-head__text {
  min-width: 0;
}
.llm-section-title {
  margin: 0 0 8px;
  font-size: 1.2rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: #f8fafc;
  line-height: 1.25;
}
.llm-intro {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
  line-height: 1.65;
  max-width: 56rem;
}
.llm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(152px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.llm-tile {
  --llm-tile-radius: 12px;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
  padding: 16px 12px;
  border-radius: var(--llm-tile-radius);
  border: 0.5px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.03);
  color: #fff;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
  font: inherit;
}
.llm-tile:hover:not(.llm-tile--keyed) {
  border-color: rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.06);
}
/* 已配置 BYOK：底层 conic 铺满卡片 + 全幅半透明磨砂，流光完整可见 */
.llm-tile--keyed {
  /* 旋转层略大于卡片，避免矩形旋转时四角露底；可单独加大到 1.65 等 */
  --llm-rainbow-scale: 1.55;
  z-index: 0;
  isolation: isolate;
  overflow: hidden;
  clip-path: inset(0 round var(--llm-tile-radius));
  contain: paint;
  border-color: transparent;
  background: transparent;
  box-shadow: 0 0 20px rgba(99, 102, 241, 0.12);
}
/* 与父同形的矩形旋转时四角会露底；用略放大+居中旋转，再靠父级 overflow/clip 裁切，旋转任意角度也铺满 */
.llm-tile--keyed::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  transform: rotate(0deg) scale(var(--llm-rainbow-scale, 1.55));
  transform-origin: 50% 50%;
  border-radius: inherit;
  background: conic-gradient(
    from 0deg,
    #f472b6,
    #a855f7,
    #6366f1,
    #38bdf8,
    #22d3ee,
    #4ade80,
    #facc15,
    #fb923c,
    #f43f5e,
    #f472b6
  );
  animation: llm-tile-rainbow-spin 3.2s linear infinite;
  will-change: transform;
  pointer-events: none;
}
.llm-tile--keyed::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  border-radius: inherit;
  /* 不缩进，整卡覆盖；透明度让底层旋转 conic 整面可见，毛玻璃会带着颜色流动 */
  background: linear-gradient(
    160deg,
    rgba(99, 102, 241, 0.14) 0%,
    rgba(15, 23, 42, 0.38) 38%,
    rgba(15, 23, 42, 0.48) 100%
  );
  backdrop-filter: blur(12px) saturate(1.2);
  -webkit-backdrop-filter: blur(12px) saturate(1.2);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    inset 0 -1px 0 rgba(0, 0, 0, 0.2);
  pointer-events: none;
}
/* 模型目录拉取异常：在内缘叠一层提示，不改变「有密钥即流光」的主语义 */
.llm-tile--keyed.llm-tile--keywarn::after {
  box-shadow:
    inset 0 0 0 1px rgba(250, 204, 21, 0.38),
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    inset 0 -1px 0 rgba(0, 0, 0, 0.22);
}
.llm-tile--keyed.llm-tile--keydanger::after {
  box-shadow:
    inset 0 0 0 1px rgba(239, 68, 68, 0.42),
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    inset 0 -1px 0 rgba(0, 0, 0, 0.22);
}
.llm-tile--keyed > * {
  position: relative;
  z-index: 2;
}
.llm-tile--keyed .llm-tile__name,
.llm-tile--keyed .llm-tile__count {
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
}
.llm-tile--keyed:hover::after {
  background: linear-gradient(
    160deg,
    rgba(129, 140, 248, 0.2) 0%,
    rgba(15, 23, 42, 0.34) 40%,
    rgba(15, 23, 42, 0.44) 100%
  );
}
/* 当前选中的厂商：无密钥时仅用边框高亮；有密钥时在拟态内缘加「选中环」 */
.llm-tile--active:not(.llm-tile--keyed) {
  border-color: rgba(255, 255, 255, 0.38);
  background: rgba(255, 255, 255, 0.09);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.2);
}
.llm-tile--active.llm-tile--keyed::after {
  box-shadow:
    inset 0 0 0 2px rgba(255, 255, 255, 0.52),
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    inset 0 -1px 0 rgba(0, 0, 0, 0.22);
}
.llm-tile--active.llm-tile--keyed.llm-tile--keywarn::after {
  box-shadow:
    inset 0 0 0 2px rgba(255, 255, 255, 0.5),
    inset 0 0 0 1px rgba(250, 204, 21, 0.38),
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    inset 0 -1px 0 rgba(0, 0, 0, 0.22);
}
.llm-tile--active.llm-tile--keyed.llm-tile--keydanger::after {
  box-shadow:
    inset 0 0 0 2px rgba(255, 255, 255, 0.5),
    inset 0 0 0 1px rgba(239, 68, 68, 0.42),
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    inset 0 -1px 0 rgba(0, 0, 0, 0.22);
}
@keyframes llm-tile-rainbow-spin {
  from {
    transform: rotate(0deg) scale(var(--llm-rainbow-scale, 1.55));
  }
  to {
    transform: rotate(360deg) scale(var(--llm-rainbow-scale, 1.55));
  }
}
@media (prefers-reduced-motion: reduce) {
  .llm-tile--keyed::before {
    animation: none;
    transform: rotate(22deg) scale(var(--llm-rainbow-scale, 1.55));
    opacity: 0.92;
  }
}
.llm-tile:focus-visible {
  outline: 2px solid rgba(147, 197, 253, 0.75);
  outline-offset: 2px;
}
.llm-tile--active:focus-visible {
  outline-color: rgba(255, 255, 255, 0.55);
}
.llm-tile--active.llm-tile--keywarn .llm-tile__icon {
  box-shadow: 0 0 0 2px rgba(250, 204, 21, 0.55);
}
.llm-tile--active.llm-tile--keydanger .llm-tile__icon {
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.55);
}
.llm-tile__icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: rgba(0,0,0,0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.llm-tile__img {
  width: 28px;
  height: 28px;
  object-fit: contain;
  display: block;
}
.llm-tile__icon--inactive .llm-tile__img {
  filter: grayscale(1) brightness(1.2) opacity(0.48);
}
.llm-tile__icon--ok .llm-tile__img {
  filter: none;
  opacity: 1;
}
.llm-tile__icon--warn .llm-tile__img {
  filter: drop-shadow(0 0 5px rgba(250, 204, 21, 0.75));
}
.llm-tile__icon--danger .llm-tile__img {
  filter: drop-shadow(0 0 5px rgba(248, 113, 113, 0.85));
}
/* 有密钥卡片背景较花：图标区衬底与字/图整体提亮一档 */
.llm-tile--keyed .llm-tile__icon {
  background: linear-gradient(165deg, rgba(255, 255, 255, 0.22) 0%, rgba(0, 0, 0, 0.28) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.3),
    0 2px 10px rgba(0, 0, 0, 0.22);
}
.llm-tile--keyed .llm-tile__icon--ok .llm-tile__img {
  filter: brightness(1.14) contrast(1.05) drop-shadow(0 0 4px rgba(255, 255, 255, 0.35));
}
.llm-tile--keyed .llm-tile__icon--warn .llm-tile__img {
  filter: brightness(1.1) drop-shadow(0 0 7px rgba(253, 224, 71, 0.85));
}
.llm-tile--keyed .llm-tile__icon--danger .llm-tile__img {
  filter: brightness(1.1) drop-shadow(0 0 7px rgba(252, 165, 165, 0.9));
}
.llm-tile--keyed .llm-tile__fallback--ok {
  color: #e8f3ff;
  text-shadow:
    0 0 14px rgba(191, 219, 254, 0.85),
    0 1px 2px rgba(0, 0, 0, 0.45);
}
.llm-tile--keyed .llm-tile__fallback--warn {
  color: #fef9c3;
  text-shadow:
    0 0 12px rgba(253, 224, 71, 0.55),
    0 1px 2px rgba(0, 0, 0, 0.4);
}
.llm-tile--keyed .llm-tile__fallback--danger {
  color: #ffe4e6;
  text-shadow:
    0 0 12px rgba(252, 165, 165, 0.6),
    0 1px 2px rgba(0, 0, 0, 0.4);
}
.llm-tile__fallback {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.42);
}
.llm-tile__fallback--inactive {
  color: rgba(255, 255, 255, 0.42);
}
.llm-tile__fallback--ok {
  color: #93c5fd;
  text-shadow: 0 0 12px rgba(147, 197, 253, 0.45);
}
.llm-tile__fallback--warn {
  color: #fde047;
  text-shadow: 0 0 10px rgba(253, 224, 71, 0.35);
}
.llm-tile__fallback--danger {
  color: #fca5a5;
  text-shadow: 0 0 10px rgba(252, 165, 165, 0.4);
}
.llm-tile__name {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}
.llm-tile__model {
  font-size: 11px;
  color: rgba(255,255,255,0.42);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  word-break: break-all;
  line-height: 1.35;
  max-width: 100%;
}
.btn-ghost {
  background: transparent;
  border: 0.5px solid rgba(255,255,255,0.2);
  color: rgba(255,255,255,0.85);
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
}
.btn-ghost:hover { background: rgba(255,255,255,0.06); }

.llm-toolbar {
  margin-bottom: 18px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.28);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.llm-toolbar__main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
}
.llm-refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02));
  color: #f1f5f9;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}
.llm-refresh-btn:hover:not(:disabled) {
  border-color: rgba(165, 180, 252, 0.45);
  background: linear-gradient(180deg, rgba(129, 140, 248, 0.15), rgba(255, 255, 255, 0.03));
  box-shadow: 0 0 0 1px rgba(129, 140, 248, 0.12);
}
.llm-refresh-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.llm-refresh-btn__icon {
  display: flex;
  color: #c7d2fe;
}
.llm-refresh-btn__icon--spin {
  animation: llm-spin 0.85s linear infinite;
}
@keyframes llm-spin {
  to {
    transform: rotate(360deg);
  }
}
.llm-sync-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.llm-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 12px;
  color: rgba(226, 232, 240, 0.88);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  letter-spacing: 0.01em;
}
.llm-pill--accent {
  color: #e0e7ff;
  background: rgba(99, 102, 241, 0.12);
  border-color: rgba(129, 140, 248, 0.28);
}
.llm-pill__icon {
  flex-shrink: 0;
  opacity: 0.75;
}
.llm-toolbar-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 6px 10px 6px 8px;
  border-radius: 8px;
  font-size: 11.5px;
  line-height: 1.45;
  color: rgba(203, 213, 225, 0.72);
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-left: 2px solid rgba(148, 163, 184, 0.35);
}
.llm-toolbar-hint__icon {
  flex-shrink: 0;
  display: flex;
  color: rgba(148, 163, 184, 0.85);
  opacity: 0.9;
}
.llm-toolbar-hint__text {
  min-width: 0;
}
.llm-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.35);
  color: #fef3c7;
}
.llm-code--hint {
  margin-left: 0.25em;
  font-size: 10.5px;
  padding: 1px 5px;
  color: rgba(226, 232, 240, 0.88);
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.llm-tile__count { font-size: 11px; color: rgba(255,255,255,0.4); }

.llm-model-panel {
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.llm-model-panel__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.llm-model-panel__label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.45);
}
.llm-model-panel__hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.32);
}
.llm-gate-hint {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.38);
}
.llm-select-wrap {
  position: relative;
}
.llm-select-wrap::after {
  content: '';
  position: absolute;
  right: 14px;
  top: 50%;
  width: 8px;
  height: 8px;
  margin-top: -6px;
  border-right: 2px solid rgba(255, 255, 255, 0.35);
  border-bottom: 2px solid rgba(255, 255, 255, 0.35);
  transform: rotate(45deg);
  pointer-events: none;
}
.llm-select {
  width: 100%;
  box-sizing: border-box;
  min-height: 48px;
  padding: 12px 40px 12px 14px;
  font-size: 14px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  line-height: 1.35;
  color: #f8fafc;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.07) 0%, rgba(0, 0, 0, 0.35) 100%);
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.llm-select:hover {
  border-color: rgba(255, 255, 255, 0.2);
}
.llm-select:focus {
  outline: none;
  border-color: rgba(165, 180, 252, 0.65);
  box-shadow: 0 0 0 3px rgba(129, 140, 248, 0.22);
}
.llm-select option,
.llm-select optgroup {
  background: #1a1a1f;
  color: #e2e8f0;
}

.llm-empty-models { font-size: 13px; color: rgba(255,255,255,0.45); margin-bottom: 14px; }

.llm-details {
  margin: 18px 0;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0;
  background: rgba(0, 0, 0, 0.22);
  overflow: hidden;
}
.llm-details__summary {
  list-style: none;
  cursor: pointer;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
  color: rgba(248, 250, 252, 0.95);
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid transparent;
  transition: background 0.15s ease;
}
.llm-details__summary--nested {
  font-size: 13px;
  font-weight: 600;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  margin-top: 4px;
}
.llm-details__summary-text {
  flex: 1;
  min-width: 8rem;
  user-select: none;
}
.llm-byok-summary-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(129, 140, 248, 0.18);
  border: 1px solid rgba(165, 180, 252, 0.35);
  color: #e0e7ff;
}
.llm-byok-summary-badge--muted {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.1);
  color: rgba(148, 163, 184, 0.85);
}
.llm-byok-import {
  margin: 0 16px 16px;
  padding: 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.llm-byok-import__label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 8px;
}
.llm-byok-bulk {
  width: 100%;
  box-sizing: border-box;
  min-height: 160px;
  resize: vertical;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.45;
}
.llm-byok-import__hint {
  margin: 8px 0 12px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.38);
  line-height: 1.5;
}
.llm-byok-import__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.llm-byok-list-head {
  margin: 0 16px 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.38);
}
.llm-byok-list {
  list-style: none;
  margin: 0 16px 16px;
  padding: 0;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
}
.llm-byok-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 13px;
}
.llm-byok-row:last-child {
  border-bottom: none;
}
.llm-byok-row__main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 10px;
  min-width: 0;
}
.llm-byok-row__name {
  font-weight: 600;
  color: rgba(248, 250, 252, 0.92);
}
.llm-byok-row__dash {
  color: rgba(255, 255, 255, 0.25);
  font-size: 12px;
}
.llm-byok-row__clear {
  flex-shrink: 0;
  padding: 4px 12px;
  font-size: 12px;
}
.llm-details--nested {
  margin: 0 16px 12px;
  border-radius: 10px;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.15);
}
.llm-details--nested .llm-byok-intro--nested {
  margin-top: 0;
}
.llm-details__summary::-webkit-details-marker {
  display: none;
}
.llm-details__summary:hover {
  background: rgba(255, 255, 255, 0.05);
}
.llm-details[open] > .llm-details__summary {
  border-bottom-color: rgba(255, 255, 255, 0.08);
}
.llm-details--nested[open] > .llm-details__summary {
  border-bottom-color: rgba(255, 255, 255, 0.08);
}
.llm-details__chevron {
  width: 0;
  height: 0;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 7px solid rgba(255, 255, 255, 0.48);
  flex-shrink: 0;
  transition: transform 0.2s ease, border-left-color 0.15s ease;
}
.llm-details__summary:hover .llm-details__chevron {
  border-left-color: rgba(199, 210, 254, 0.95);
}
.llm-details[open] > .llm-details__summary > .llm-details__chevron {
  transform: rotate(90deg);
}
.llm-details[open] {
  padding-bottom: 4px;
}
.llm-details .llm-byok-intro {
  margin: 12px 16px 14px;
}
.llm-details .llm-byok-block {
  margin-left: 16px;
  margin-right: 16px;
}
.llm-details--nested .llm-byok-block {
  margin-left: 12px;
  margin-right: 12px;
}
.llm-details .llm-byok-block:last-child {
  border-bottom: none;
  margin-bottom: 14px;
  padding-bottom: 6px;
}
.llm-byok-intro { font-size: 12px; color: rgba(255,255,255,0.4); margin: 10px 0 14px; line-height: 1.5; }
.llm-byok-block { margin-bottom: 18px; padding-bottom: 16px; border-bottom: 0.5px solid rgba(255,255,255,0.08); }
.llm-byok-block:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.llm-byok-head { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; margin-bottom: 8px; align-items: center; }
.llm-byok-head strong { color: #fff; font-size: 14px; }
.llm-byok-tags { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 11px; }
.tag { padding: 2px 8px; border-radius: 6px; background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.65); }
.tag-user { background: rgba(129, 140, 248, 0.2); color: #c7d2fe; }
.llm-mask { color: rgba(255,255,255,0.45); font-family: ui-monospace, monospace; }
.llm-byok-fields { margin-bottom: 8px; }
.llm-byok-block .input { width: 100%; margin-bottom: 8px; box-sizing: border-box; }
.llm-byok-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
</style>
