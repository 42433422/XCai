<template>
  <div class="wb-home">
    <div
      class="wb-home-inner"
      :class="{
        'wb-home-inner--no-workflow': !hasWorkflow,
        'wb-home-inner--gears': hasWorkflow,
        'wb-home-inner--make': hasWorkflow && activeGear === 'make',
      }"
    >
      <header v-if="!hasWorkflow" class="wb-hero">
        <p v-if="greetingLine" class="wb-hero-kicker">{{ greetingLine }}</p>
        <h1 class="wb-hero-title">今天有什么安排？</h1>
      </header>

      <div
        v-if="hasWorkflow"
        class="wb-gear-layout"
        :class="{
          'wb-gear-layout--make': activeGear === 'make',
          'wb-gear-layout--nav-locked': gearNavHardLocked,
        }"
        @wheel="onGearWheel"
      >
        <nav class="wb-gear-rail" aria-label="工作台挡位">
          <div
            class="wb-gear-slider"
            :class="{ 'wb-gear-slider--dragging': gearDragging }"
            @pointerdown="onGearPointerDown"
            @pointermove="onGearPointerMove"
            @pointerup="onGearPointerUp"
            @pointercancel="onGearPointerCancel"
          >
            <span class="wb-gear-slider__track" aria-hidden="true">
              <span class="wb-gear-slider__fill" :style="{ height: `${gearThumbPercent}%` }"></span>
            </span>
            <button
              v-for="(scene, i) in gearScenes"
              :key="scene.key"
              type="button"
              class="wb-gear-stop"
              :class="{ 'wb-gear-stop--active': activeGear === scene.key }"
              :style="{ top: `${gearStopPercent(i)}%` }"
              :aria-current="activeGear === scene.key ? 'true' : undefined"
              @click.stop="setGear(scene.key)"
            >
              <span class="wb-gear-stop__num">{{ scene.num }}</span>
              <span class="wb-gear-stop__label">{{ scene.label }}</span>
            </button>
            <span
              class="wb-gear-thumb"
              :style="{ top: `${gearThumbPercent}%` }"
              aria-hidden="true"
            >
              <span class="wb-gear-thumb__num">{{ activeGearScene.num }}</span>
              <span class="wb-gear-thumb__label">{{ activeGearScene.label }}</span>
            </span>
          </div>
        </nav>
        <div class="wb-gear-viewport">
          <div
            v-if="gearNavHardLocked"
            class="wb-gear-nav-lock"
            role="status"
            aria-live="polite"
          >
            <span class="wb-gear-nav-lock__text">一档已有聊天记录，挡位已锁定，避免滚轮误切。</span>
            <button type="button" class="wb-gear-nav-lock__btn" @click="unlockGearNav">解锁挡位</button>
          </div>
          <div class="wb-gear-track" :style="{ transform: `translateY(-${gearIndex * (100 / gearScenes.length)}%)` }">
            <section class="wb-gear-scene wb-direct-scene" aria-label="一档直接聊天" :style="directFontPxStyle">
              <div v-if="!directMessages.length" class="wb-direct-empty-title">
                <h1 class="wb-direct-title">{{ activeBot ? activeBot.name : '有什么想问的？' }}</h1>
                <p class="wb-direct-sub">{{ activeBot?.desc || '像聊天一样提问，我直接帮你分析、总结和给出可执行答案。' }}</p>
              </div>
              <div
                class="wb-direct-shell"
                :class="{ 'wb-direct-shell--empty': !directMessages.length }"
              >
                <div
                  class="wb-direct-main"
                  :class="{
                    'wb-direct-main--empty': !directMessages.length,
                    'wb-direct-main--chatting': directMessages.length,
                    'wb-direct-main--drop': directIsDragging,
                  }"
                  @dragenter="onSurfaceDragEnter"
                  @dragover="onSurfaceDragOver"
                  @dragleave="onSurfaceDragLeave"
                  @drop="onSurfaceDrop"
                >
                  <div
                    v-if="directIsDragging"
                    class="wb-direct-dropzone"
                    aria-hidden="true"
                  >
                    <div class="wb-direct-dropzone__panel">
                      <div class="wb-direct-dropzone__icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M21.44 11.05l-8.49 8.48a5.66 5.66 0 01-8-8l9.19-9.2a3.77 3.77 0 015.33 5.33L8.95 19.07a2.36 2.36 0 01-3.33-3.33l8.49-8.48" />
                        </svg>
                      </div>
                      <p class="wb-direct-dropzone__title">松开以添加附件</p>
                      <p class="wb-direct-dropzone__sub">支持 PDF / Word / Excel / 文本，图片可粘贴或拖入</p>
                    </div>
                  </div>
                  <header v-if="activeBot" class="wb-direct-topbar">
                    <div class="wb-direct-topbar__l">
                      <span class="wb-direct-bot-chip">
                        <span aria-hidden="true">{{ activeBot.icon }}</span>
                        <span class="wb-direct-bot-chip__name">@{{ activeBot.name }}</span>
                        <button type="button" class="wb-direct-bot-chip__x" aria-label="切回通用助手" @click="clearActiveBot">×</button>
                      </span>
                    </div>
                  </header>

                  <p
                    v-if="directMessages.length"
                    class="wb-direct-hero wb-direct-hero--compact"
                    :title="directTaskLine"
                  >
                    {{ directTaskLine }}
                  </p>
                  <TransitionGroup
                    v-if="directMessages.length"
                    ref="directThreadRef"
                    name="wb-direct-msg-flow"
                    tag="div"
                    class="wb-direct-thread"
                    aria-live="polite"
                  >
                    <article
                      v-for="msg in directMessages"
                      :key="msg.id"
                      class="wb-direct-msg"
                      :class="msg.role === 'user' ? 'wb-direct-msg--user' : 'wb-direct-msg--assistant'"
                    >
                      <div class="wb-direct-msg__persona" aria-hidden="true">
                        <span class="wb-direct-msg__avatar">{{ msg.role === 'user' ? '你' : 'AI' }}</span>
                        <span class="wb-direct-msg__name">{{ msg.role === 'user' ? '你' : 'AI 助手' }}</span>
                      </div>
                      <div class="wb-direct-msg__stack">
                        <div class="wb-direct-msg__bubble">
                          <header
                            v-if="(msg.skills && msg.skills.length) || (msg.attachments && msg.attachments.length)"
                            class="wb-direct-msg__head"
                          >
                            <span v-if="msg.skills && msg.skills.length" class="wb-direct-msg__skills">
                              <span
                                v-for="s in msg.skills"
                                :key="`s-${msg.id}-${s}`"
                                class="wb-direct-msg__skill-chip"
                              >{{ s }}</span>
                            </span>
                            <span v-if="msg.attachments && msg.attachments.length" class="wb-direct-msg__atts">
                              <span
                                v-for="a in msg.attachments"
                                :key="`a-${msg.id}-${a.name}`"
                                class="wb-direct-msg__att-chip"
                                :title="`${a.name} · ${formatDirectFileSize(a.size)} · ${a.status}`"
                              >📎 {{ a.name }}</span>
                            </span>
                          </header>
                          <template v-if="msg.role === 'user' && editingMessageId === msg.id">
                            <div class="wb-direct-edit">
                              <textarea
                                v-model="editingDraft"
                                class="wb-direct-edit__input"
                                rows="3"
                                spellcheck="false"
                              />
                              <div class="wb-direct-edit__ops">
                                <button type="button" class="wb-direct-edit__btn wb-direct-edit__btn--ghost" @click="cancelEditUserMessage">取消</button>
                                <button type="button" class="wb-direct-edit__btn wb-direct-edit__btn--primary" :disabled="!editingDraft.trim() || directLoading" @click="() => void commitEditedUserMessage()">改后重发</button>
                              </div>
                            </div>
                          </template>
                          <template v-else>
                            <MessageBody :content="msg.content" :streaming="!!msg.pending" />
                            <p v-if="msg.error" class="wb-direct-msg__err" role="alert">{{ msg.error }}</p>
                            <div v-if="msg.role === 'assistant' && msg.citations && msg.citations.length" class="wb-direct-cites" aria-label="引用来源">
                              <div class="wb-direct-cites__head">引用资料</div>
                              <details
                                v-for="(cite, ci) in msg.citations"
                                :key="`cite-${msg.id}-${ci}`"
                                class="wb-direct-cite"
                              >
                                <summary class="wb-direct-cite__sum">
                                  <span aria-hidden="true">📄</span>
                                  <span>{{ cite.title }}</span>
                                </summary>
                                <p class="wb-direct-cite__snip">{{ cite.snippet }}</p>
                              </details>
                            </div>
                          </template>
                        </div>
                        <MessageActions
                          :role="msg.role"
                          :content="msg.content"
                          :feedback="msg.feedback"
                          :can-regenerate="msg.role === 'assistant' && !msg.pending && !directLoading"
                          :speaking="speakingMessageId === msg.id"
                          @edit="startEditUserMessage(msg.id)"
                          @regenerate="() => void regenerateAssistant(msg.id)"
                          @speak="speakMessage(msg.id)"
                          @feedback="(v) => setMessageFeedback(msg.id, v)"
                        />
                      </div>
                    </article>
                  </TransitionGroup>

                  <div
                    class="wb-direct-box"
                    :class="{ 'wb-direct-box--drop': directIsDragging }"
                    @paste="onComposerPaste"
                  >
                    <div class="wb-direct-box-main">
                      <input
                        ref="directFileInputRef"
                        type="file"
                        class="wb-direct-file-input"
                        multiple
                        :accept="DIRECT_ATTACHMENT_ACCEPT"
                        @change="onDirectFilesChange"
                      />
                      <button
                        type="button"
                        class="wb-direct-attach"
                        :disabled="directLoading"
                        aria-label="选择本地文件作为附件"
                        title="选择本地文件（图片、PDF、Word、Excel；图片支持粘贴/拖拽进输入框）"
                        @click="openDirectFilePicker"
                      >
                        <svg class="wb-direct-attach__icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M21.44 11.05l-8.49 8.48a5.66 5.66 0 01-8-8l9.19-9.2a3.77 3.77 0 015.33 5.33L8.95 19.07a2.36 2.36 0 01-3.33-3.33l8.49-8.48" />
                        </svg>
                      </button>
                      <textarea
                        v-model="directDraft"
                        class="wb-direct-input"
                        rows="3"
                        placeholder="直接问问题，例如：帮我写一份门店日报自动化方案…粘贴/拖拽图片或文件也可以"
                        spellcheck="false"
                        @keydown="onDirectKeydown"
                      />
                      <div class="wb-llm-inline wb-direct-llm-inline" aria-label="一档模型">
                        <div class="wb-mode-segment" role="radiogroup" aria-label="一档模型模式">
                          <button
                            type="button"
                            class="wb-mode-segment__btn"
                            :class="{ 'wb-mode-segment__btn--on': modelMode === 'auto' }"
                            role="radio"
                            :aria-checked="modelMode === 'auto'"
                            @click="modelMode = 'auto'"
                          >Auto</button>
                          <button
                            type="button"
                            class="wb-mode-segment__btn"
                            :class="{ 'wb-mode-segment__btn--on': modelMode === 'manual' }"
                            role="radio"
                            :aria-checked="modelMode === 'manual'"
                            @click="modelMode = 'manual'"
                          >自选</button>
                        </div>
                        <template v-if="modelMode === 'manual' && llmCatalog && llmCatalog.providers?.length && !llmCatalogError">
                          <div class="wb-llm-dd">
                            <span class="wb-sr-only" id="wb-direct-provider-lbl">厂商</span>
                            <button
                              type="button"
                              class="wb-dd-trigger wb-dd-trigger--compact"
                              :class="{ 'wb-dd-trigger--open': llmDdOpen === 'directProvider' }"
                              aria-haspopup="listbox"
                              :aria-expanded="llmDdOpen === 'directProvider'"
                              aria-labelledby="wb-direct-provider-lbl"
                              title="厂商"
                              @click.stop="toggleLlmDd('directProvider')"
                            >
                              <span class="wb-dd-trigger__text">{{ currentProviderLabel }}</span>
                              <svg class="wb-dd-trigger__icon" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                                <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" />
                              </svg>
                            </button>
                            <ul
                              v-show="llmDdOpen === 'directProvider'"
                              class="wb-dd-panel"
                              role="listbox"
                              aria-labelledby="wb-direct-provider-lbl"
                            >
                              <li
                                v-for="b in llmCatalog.providers"
                                :key="`direct-${b.provider}`"
                                role="option"
                                class="wb-dd-item"
                                :class="{ 'wb-dd-item--on': selectedProvider === b.provider }"
                                :aria-selected="selectedProvider === b.provider"
                                @click.stop="pickProvider(b.provider)"
                              >
                                {{ b.label || b.provider }}
                              </li>
                            </ul>
                          </div>
                          <div class="wb-llm-dd wb-llm-dd--model">
                            <span class="wb-sr-only" id="wb-direct-model-lbl">模型</span>
                            <button
                              type="button"
                              class="wb-dd-trigger wb-dd-trigger--model wb-dd-trigger--compact"
                              :class="{ 'wb-dd-trigger--open': llmDdOpen === 'directModel' }"
                              :disabled="!modelPickerEnabled"
                              aria-haspopup="listbox"
                              :aria-expanded="llmDdOpen === 'directModel'"
                              aria-labelledby="wb-direct-model-lbl"
                              title="模型"
                              @click.stop="modelPickerEnabled && toggleLlmDd('directModel')"
                            >
                              <span class="wb-dd-trigger__text">{{ selectedModel || '选择模型' }}</span>
                              <svg class="wb-dd-trigger__icon" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                                <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" />
                              </svg>
                            </button>
                            <ul
                              v-show="llmDdOpen === 'directModel' && modelPickerEnabled"
                              class="wb-dd-panel wb-dd-panel--tall"
                              role="listbox"
                              aria-labelledby="wb-direct-model-lbl"
                            >
                              <template v-for="cat in LLM_CATEGORY_ORDER" :key="`direct-${cat}`">
                                <template v-if="modelsForWorkbenchCategory(cat).length">
                                  <li class="wb-dd-cat" role="presentation">{{ categoryLabel(cat) }}</li>
                                  <li
                                    v-for="row in modelsForWorkbenchCategory(cat)"
                                    :key="`direct-${row.id}`"
                                    role="option"
                                    class="wb-dd-item"
                                    :class="{ 'wb-dd-item--on': selectedModel === row.id }"
                                    :aria-selected="selectedModel === row.id"
                                    @click.stop="pickModel(row.id)"
                                  >
                                    {{ row.id }}
                                  </li>
                                </template>
                              </template>
                            </ul>
                          </div>
                        </template>
                        <span
                          v-else-if="modelMode === 'manual' && (llmCatalogLoading || llmCatalogError || !llmCatalog?.providers?.length)"
                          class="wb-llm-inline__note"
                          :title="llmCatalogError || ''"
                        >{{ llmCatalogLoading ? '目录…' : '登录配置' }}</span>
                      </div>
                      <button
                        v-if="directLoading"
                        type="button"
                        class="wb-direct-send wb-direct-send--stop"
                        title="停止生成"
                        @click="stopGeneration"
                      >停止</button>
                      <button
                        v-else
                        type="button"
                        class="wb-direct-send"
                        :disabled="directSendDisabled"
                        @click="() => void sendDirectChat()"
                      >发送</button>
                    </div>
                    <TransitionGroup
                      v-if="directAttachedFiles.length"
                      name="wb-direct-file-card"
                      tag="div"
                      class="wb-direct-file-stack"
                      aria-label="已选附件"
                    >
                      <article
                        v-for="(f, i) in directVisibleAttachedFiles"
                        :key="f.id"
                        class="wb-direct-file-card"
                        :class="[
                          `wb-direct-file-card--${f.status}`,
                          `wb-direct-file-card--${directAttachmentKind(f)}`,
                          { 'wb-direct-file-card--ingesting': f.ingesting },
                        ]"
                        :style="{ '--att-index': i }"
                        :title="directFileChipTitle(f)"
                      >
                        <span class="wb-direct-file-card__deck" aria-hidden="true">
                          <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--back"></span>
                          <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--mid"></span>
                          <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--front">
                            <span class="wb-direct-file-card__deck-label">{{ directAttachmentKindLabel(f) }}</span>
                          </span>
                        </span>
                        <span class="wb-direct-file-card__state" aria-hidden="true">
                          <span v-if="f.status === 'uploading' || f.ingesting" class="wb-direct-file-card__spinner" />
                          <span v-else-if="f.status === 'ready' || f.status === 'inline'" class="wb-direct-file-card__check">✓</span>
                          <span v-else class="wb-direct-file-card__warn">!</span>
                        </span>
                        <button
                          type="button"
                          class="wb-direct-file-card__remove"
                          :aria-label="`移除 ${f.name}`"
                          :disabled="directLoading || f.status === 'uploading'"
                          @click="() => void removeDirectAttachedFile(f.id)"
                        >×</button>
                      </article>
                      <div
                        v-if="directHiddenAttachmentCount"
                        key="__more"
                        class="wb-direct-file-card wb-direct-file-card--more"
                        aria-label="更多附件"
                      >
                        <span class="wb-direct-file-card__deck" aria-hidden="true">
                          <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--back"></span>
                          <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--mid"></span>
                          <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--front">
                            <span class="wb-direct-file-card__deck-plus">+{{ directHiddenAttachmentCount }}</span>
                          </span>
                        </span>
                      </div>
                    </TransitionGroup>
                    <div v-if="directAttachmentMentions.length" class="wb-file-mention-row" aria-label="已引用附件">
                      <span
                        v-for="(m, i) in directAttachmentMentions"
                        :key="`direct-ref-${m}`"
                        class="wb-file-mention-token"
                      >@附件{{ i + 1 }} {{ m }}</span>
                    </div>
                    <p v-if="directAttachHint" class="wb-direct-attach-hint" role="status">
                      {{ directAttachHint }}
                    </p>
                  </div>
                  <div class="wb-direct-new-row">
                    <button
                      type="button"
                      class="wb-direct-new-btn"
                      title="新开一档对话：清空输入与附件，并回到初始会话"
                      @click="newConversationHandler"
                    >新建</button>
                  </div>
                  <p v-if="directError" class="wb-direct-error" role="alert">{{ directError }}</p>
                  <p class="wb-direct-prefs-row">
                    <button type="button" class="wb-direct-prefs-btn" @click="personalSettingsOpen = true">
                      个性化与朗读设置
                    </button>
                  </p>
                  <div v-if="hasWorkflow" class="wb-direct-employee-row">
                    <label class="wb-direct-employee-label" for="wb-direct-employee-select">测试员工（一档单选）</label>
                    <select
                      id="wb-direct-employee-select"
                      v-model="directChatEmployeeId"
                      class="wb-direct-employee-select"
                      :disabled="directLoading"
                      aria-describedby="wb-direct-employee-hint"
                    >
                      <option value="">不绑定（通用检索）</option>
                      <option v-for="opt in directEmployeeOptions" :key="opt.id" :value="opt.id">
                        {{ opt.name }} · {{ opt.id }}（{{ opt.sourceLabel }}）
                      </option>
                    </select>
                    <p id="wb-direct-employee-hint" class="wb-direct-employee-hint">
                      仅选一个员工：知识检索优先使用该 id；与人设并存时仍以本选择为准。
                    </p>
                  </div>
                </div>
              </div>

              <AgentMarket
                :open="showAgentMarket"
                :bots="allBots"
                @close="showAgentMarket = false"
                @start="onStartWithAgent"
                @create="onCreateAgent"
                @remove="onRemoveAgent"
                @favorite="onFavoriteAgent"
              />
              <VoicePhoneModal
                :open="showVoicePhone"
                :on-turn="handleVoicePhoneTurn"
                @close="showVoicePhone = false"
              />
              <PersonalSettings
                :open="personalSettingsOpen"
                :model-value="personalSettings"
                @close="personalSettingsOpen = false"
                @update:model-value="onPersonalSettingsUpdate"
              />
              <MediaGenPanel
                :open="showMediaGen"
                :runner="mediaGenRunner"
                @close="showMediaGen = false"
                @insert="insertGeneratedToChat"
              />
            </section>

            <section class="wb-gear-scene wb-make-scene" aria-label="二档制作流程">
      <header class="wb-make-hero">
        <p v-if="greetingLine" class="wb-hero-kicker">{{ greetingLine }}</p>
        <h1 class="wb-hero-title">{{ makeHeroTitle }}</h1>
      </header>
      <section
        v-if="hasWorkflow && planSession"
        ref="planPanelRef"
        class="wb-plan"
        aria-labelledby="wb-plan-title"
      >
        <Transition name="wb-plan-shell" appear>
          <div :key="planSurfaceKey" class="wb-plan-surface">
            <div class="wb-plan-head">
              <h2 id="wb-plan-title" class="wb-plan-title">{{ planPanelTitle }}</h2>
              <button type="button" class="wb-plan-close" aria-label="关闭规划" @click="dismissPlanSession">×</button>
            </div>
            <p class="wb-plan-kicker">
              类型：{{ planSession.intentTitle }} · {{ planSession.phase === 'summary' ? '先确认任务摘要，再进入规划选择。' : '先通过对话澄清需求，再生成执行清单，确认后进入制作与生成。' }}
            </p>
            <div v-if="planSession.loading" class="wb-plan-loading-block" aria-live="polite">
              <div class="wb-plan-loading-track" aria-hidden="true">
                <div class="wb-plan-loading-bar" />
              </div>
              <p class="wb-plan-loading-lead">
                {{ planSession.phase === 'summary' ? '正在生成任务摘要' : '正在请求规划模型' }}
              </p>
              <ol class="wb-plan-loading-steps" aria-label="加载步骤">
                <li
                  v-for="(label, i) in planLoadingStepLabelsForUi"
                  :key="i"
                  class="wb-plan-loading-steps__li"
                  :class="{
                    'wb-plan-loading-steps__li--done': i < planLoadingAdvance,
                    'wb-plan-loading-steps__li--active': i === planLoadingAdvance,
                    'wb-plan-loading-steps__li--pending': i > planLoadingAdvance,
                  }"
                >
                  {{ label }}
                </li>
              </ol>
            </div>
            <TransitionGroup v-if="planSession.phase !== 'summary'" name="wb-plan-msg" tag="ul" class="wb-plan-thread" aria-live="polite">
              <li
                v-for="(m, idx) in planSession.messages"
                :key="`${m.role}-${idx}`"
                class="wb-plan-msg"
                :class="m.role === 'user' ? 'wb-plan-msg--user' : 'wb-plan-msg--assistant'"
              >
                <span class="wb-plan-msg-role">{{ m.role === 'user' ? '你' : '规划助手' }}</span>
                <template v-if="m.role === 'user'">
                  <div class="wb-plan-msg-body">{{ m.content }}</div>
                </template>
                <template v-else>
                  <div class="wb-plan-msg-assistant-grid">
                    <div class="wb-plan-diagram-col">
                      <button
                        v-if="planAssistantParts(m.content).hasDiagram && !planDiagramError[idx]"
                        type="button"
                        class="wb-plan-diagram-preview-open"
                        title="完整查看架构图（可滚动）"
                        @click="() => void openPlanDiagramPreview(idx)"
                      >
                        完整预览
                      </button>
                      <div
                        v-if="!planAssistantParts(m.content).hasDiagram"
                        class="wb-plan-diagram-fallback"
                      >
                        暂无流程图，见详细
                      </div>
                      <div
                        v-else
                        :id="'wb-plan-mer-' + idx"
                        class="wb-plan-diagram-host"
                        :class="{
                          'wb-plan-diagram-host--with-preview':
                            planAssistantParts(m.content).hasDiagram && !planDiagramError[idx],
                        }"
                        aria-hidden="false"
                      />
                      <p v-if="planDiagramError[idx]" class="wb-plan-diagram-err" role="alert">
                        {{ planDiagramError[idx] }}
                      </p>
                    </div>
                    <aside class="wb-plan-aside-col">
                      <details
                        class="wb-plan-details"
                        :open="!planAssistantParts(m.content).hasDiagram"
                      >
                        <summary class="wb-plan-details-summary">详细</summary>
                        <div class="wb-plan-details-expand">
                          <div class="wb-plan-details-expand-inner">
                            <div class="wb-plan-details-body">{{ planAssistantParts(m.content).details }}</div>
                          </div>
                        </div>
                      </details>
                    </aside>
                  </div>
                </template>
              </li>
            </TransitionGroup>
            <p v-if="planSession.planError" class="wb-plan-error" role="alert">{{ planSession.planError }}</p>
            <template v-if="planSession.phase === 'summary'">
              <section v-if="!planSession.loading && planSession.summaryText" class="wb-plan-summary-card" aria-label="任务摘要确认">
                <p class="wb-plan-summary-kicker">任务摘要</p>
                <h3 class="wb-plan-summary-title">{{ planSession.summaryTitle || '请确认任务' }}</h3>
                <p class="wb-plan-summary-body">{{ planSession.summaryText }}</p>
                <p v-if="planSession.displayBrief" class="wb-plan-summary-source">{{ planSession.displayBrief }}</p>
              </section>
              <div class="wb-plan-actions">
                <button
                  type="button"
                  class="wb-plan-secondary"
                  :disabled="planSession.loading || autoPilotRunning"
                  @click="backSummaryToComposer"
                >
                  返回修改
                </button>
                <button
                  type="button"
                  class="wb-plan-primary"
                  :disabled="planSession.loading || autoPilotRunning || !planSession.summaryText"
                  @click="() => void confirmSummaryAndStartPlanning()"
                >
                  确认并开始规划
                </button>
                <button
                  type="button"
                  class="wb-plan-primary wb-plan-autopilot"
                  :disabled="planSession.loading || autoPilotRunning || !planSession.summaryText"
                  :title="autoPilotRunning ? 'AI 正在自主跑完整个流程…' : '跳过澄清与确认，AI 自动跑完规划→清单→制作→生成'"
                  @click="() => void runAutoPilotFromSummary()"
                >
                  {{ autoPilotRunning ? 'AI 自主进行中…' : 'AI 自主全部进行' }}
                </button>
              </div>
              <p v-if="autoPilotError" class="wb-plan-autopilot-error" role="alert">
                AI 自主流程失败：{{ autoPilotError }}
              </p>
            </template>
            <template v-if="planSession.phase === 'chat'">
              <div
                v-if="planQuickOptions.length"
                class="wb-plan-quick"
                :aria-label="planSession.intentKey === 'mod' ? '需求澄清（宿主为 FHD，技术栈已固定）' : '快捷选择'"
              >
                <div class="wb-plan-quick-main">
                  <div v-for="q in planQuickOptions" :key="q.id" class="wb-plan-quick-block">
                  <div class="wb-plan-quick-title">{{ q.title }}</div>
                  <div class="wb-plan-quick-chips" role="group" :aria-label="q.title">
                    <button
                      v-for="c in q.choices"
                      :key="q.id + '-' + c.id"
                      type="button"
                      class="wb-plan-chip"
                      :class="{ 'wb-plan-chip--on': planOptionSelections[q.id] === c.id }"
                      :disabled="planSession.loading"
                      @click="pickPlanOption(q.id, c.id)"
                    >
                      {{ c.label }}
                    </button>
                    <button
                      type="button"
                      class="wb-plan-chip wb-plan-chip--other"
                      :class="{ 'wb-plan-chip--on': planOptionSelections[q.id] === PLAN_OPTION_OTHER_ID }"
                      :disabled="planSession.loading"
                      :aria-pressed="planOptionSelections[q.id] === PLAN_OPTION_OTHER_ID"
                      :aria-label="`${q.title}：其他（自定义输入）`"
                      @click="pickPlanOption(q.id, PLAN_OPTION_OTHER_ID)"
                    >
                      其他
                    </button>
                  </div>
                  <div
                    v-if="planOptionSelections[q.id] === PLAN_OPTION_OTHER_ID"
                    class="wb-plan-other-wrap"
                  >
                    <label class="wb-sr-only" :for="'wb-plan-other-' + q.id">自定义：{{ q.title }}</label>
                    <textarea
                      :id="'wb-plan-other-' + q.id"
                      v-model="planOptionOtherText[q.id]"
                      class="wb-plan-other-input"
                      rows="2"
                      :placeholder="`填写「${q.title}」的自定义说明…`"
                      spellcheck="false"
                      :disabled="planSession.loading"
                    />
                  </div>
                  </div>
                  <button
                    type="button"
                    class="wb-plan-primary wb-plan-quick-send"
                    :disabled="planSession.loading || !canSendPlanQuickPicks"
                    @click="() => void sendPlanReplyFromQuickPicks()"
                  >
                    用以上选择发送
                  </button>
                </div>
                <aside class="wb-plan-quick-aside" aria-label="快捷操作">
                  <button
                    type="button"
                    class="wb-plan-quick-auto"
                    :disabled="planSession.loading"
                    title="为每道题选中第一个选项，可再手动调整"
                    @click="autoPickPlanQuickOptions"
                  >
                    一键自动选择
                  </button>
                </aside>
              </div>
              <p class="wb-plan-reply-hint" role="note">
                文字补充请在下方主输入框输入；Enter 发送，Shift+Enter 换行。
              </p>
              <div class="wb-plan-actions">
                <button
                  type="button"
                  class="wb-plan-secondary"
                  :disabled="planSession.loading || planSession.messages.length < 2"
                  title="至少完成一轮对话后再生成清单"
                  @click="() => void requestExecutionChecklist()"
                >
                  生成执行清单
                </button>
              </div>
            </template>
            <template v-else-if="planSession.phase === 'checklist'">
              <h3 class="wb-plan-checklist-title">执行清单（确认后将写入制作草稿）</h3>
              <div class="wb-plan-checklist-flow">
                <MessageBody :content="planChecklistFlowMarkdown" />
              </div>
              <details class="wb-plan-checklist-details">
                <summary>查看文字清单</summary>
                <ol class="wb-plan-checklist-ol">
                  <li v-for="(line, i) in planSession.checklistLines" :key="i" class="wb-plan-checklist-li">
                    {{ line }}
                  </li>
                </ol>
              </details>
              <div class="wb-plan-actions">
                <button type="button" class="wb-plan-secondary" :disabled="planSession.loading" @click="backPlanToChat">
                  返回修改
                </button>
                <button type="button" class="wb-plan-primary" :disabled="planSession.loading" @click="confirmPlanAndOpenHandoff">
                  确认清单并进入制作
                </button>
              </div>
            </template>
          </div>
        </Transition>
      </section>

      <section
        v-if="
          hasWorkflow &&
          orchestrationSession?.steps?.length &&
          !(finalizeLoading && pendingHandoff)
        "
        class="wb-orch"
        aria-label="制作进度"
      >
        <div class="wb-orch-head">
          <h3 class="wb-orch-title">制作进度</h3>
          <span class="wb-orch-percent">{{ orchestrationProgress.done }}/{{ orchestrationProgress.total }}</span>
        </div>
        <div class="wb-orch-progress" aria-hidden="true">
          <span class="wb-orch-progress__bar" :style="{ width: `${orchestrationProgress.percent}%` }"></span>
        </div>
        <p
          v-if="orchestrationSession?.artifact?.execution_mode === 'script' && orchestrationSession?.status === 'done'"
          class="wb-orch-script-hint"
          role="status"
        >
          本次已按「附件 + Python 脚本」生成脚本工作流，稍后会进入沙箱调试页。
          你可以继续上传同类 Excel 文件，反复验证脚本输出是否正确。
        </p>
        <ol class="wb-steps">
          <li
            v-for="st in orchestrationSession.steps"
            :key="st.id"
            class="wb-step"
            :class="orchStepClass(st)"
          >
            <span class="wb-step-dot" aria-hidden="true" />
            <span class="wb-step-body">
              <span class="wb-step-label">{{ st.label }}</span>
              <span v-if="st.message" class="wb-step-msg">{{ st.message }}</span>
              <span v-if="orchStepRunningSec(st) !== null" class="wb-step-since">已运行 {{ formatWallClockSec(orchStepRunningSec(st)) }}</span>
              <span v-if="orchStepSlowHint(st)" class="wb-step-slow">模型响应较慢，仍在等待…</span>
            </span>
          </li>
        </ol>
        <div v-if="orchestrationSession.script_result?.outputs?.length" class="wb-script-result">
          <h4 class="wb-script-result__title">生成结果</h4>
          <a
            v-for="file in orchestrationSession.script_result.outputs"
            :key="file.filename"
            class="wb-script-download"
            :href="file.download_url"
            target="_blank"
            rel="noopener noreferrer"
          >
            下载 {{ file.filename }}
          </a>
        </div>
        <details v-if="orchestrationSession.script_result" class="wb-script-log">
          <summary>查看脚本日志</summary>
          <pre>{{ orchestrationSession.script_result.stderr || orchestrationSession.script_result.stdout || '暂无日志' }}</pre>
        </details>
        <p
          v-if="orchestrationSession.validate_warnings?.length"
          class="wb-orch-warn"
        >
          Python 语法提示：{{ orchestrationSession.validate_warnings.join('；') }}
        </p>
      </section>

      <section
        v-if="hasWorkflow && workflowLinkOffer"
        class="wb-handoff wb-workflow-link"
        aria-labelledby="wb-wf-link-title"
      >
        <div class="wb-handoff-head">
          <h2 id="wb-wf-link-title" class="wb-handoff-title">Skill 组已就绪</h2>
          <button type="button" class="wb-handoff-close" aria-label="关闭" @click="dismissWorkflowLinkOffer">×</button>
        </div>
        <p class="wb-workflow-link__name">{{ workflowLinkOffer.workflowName }}</p>
        <p v-if="!workflowLinkOffer.sandboxOk && workflowLinkOffer.validationErrors?.length" class="wb-handoff-error" role="alert">
          校验提示：{{ workflowLinkOffer.validationErrors.join('；') }}
        </p>
        <p v-if="workflowLinkOffer.llmWarnings?.length" class="wb-orch-warn">
          生成提示：{{ workflowLinkOffer.llmWarnings.join('；') }}
        </p>
        <label class="wb-handoff-label" for="wb-wf-link-mod">关联到 Mod（写入 manifest.workflow_employees）</label>
        <select
          id="wb-wf-link-mod"
          v-model="linkModId"
          class="wb-handoff-input"
        >
          <option value="">请选择 Mod…</option>
          <option v-for="m in linkMods" :key="m.id" :value="m.id">
            {{ m.id }}{{ m.name ? ` — ${m.name}` : '' }}
          </option>
        </select>
        <p v-if="linkError" class="wb-handoff-error" role="alert">{{ linkError }}</p>
        <div class="wb-handoff-actions wb-workflow-link__actions">
          <button
            type="button"
            class="wb-handoff-primary"
            :disabled="linkBusy || !linkModId"
            @click="() => void confirmWorkflowModLink()"
          >
            {{ linkBusy ? '写入中…' : '关联并打开 Mod' }}
          </button>
          <button type="button" class="wb-handoff-secondary" :disabled="linkBusy" @click="() => void openWorkflowCanvasOnly()">
            仅打开 Skill 组画布
          </button>
        </div>
      </section>

      <section
        v-if="hasWorkflow && pendingHandoff"
        ref="handoffPanelRef"
        class="wb-handoff"
        aria-labelledby="wb-handoff-title"
      >
        <div class="wb-handoff-head">
          <h2 id="wb-handoff-title" class="wb-handoff-title">制作草稿</h2>
          <button type="button" class="wb-handoff-close" aria-label="关闭" @click="dismissPendingHandoff">×</button>
        </div>
        <p class="wb-handoff-intent">类型：{{ pendingHandoff.intentTitle }}</p>
        <div class="wb-handoff-fields">
          <label class="wb-handoff-label" for="wb-handoff-desc">{{ handoffDescLabel }}</label>
          <textarea
            id="wb-handoff-desc"
            v-model="pendingHandoff.description"
            class="wb-handoff-textarea"
            rows="4"
            spellcheck="false"
          />
          <template v-if="isCanvasSkillIntent(pendingHandoff.intentKey)">
            <label class="wb-handoff-label" for="wb-handoff-name">Skill 组名称 <span class="wb-handoff-req">必填</span></label>
            <input
              id="wb-handoff-name"
              v-model="pendingHandoff.workflowName"
              type="text"
              class="wb-handoff-input"
              placeholder="例如：每日出货同步"
              autocomplete="off"
            />
            <label class="wb-handoff-label" for="wb-handoff-plan">框架与排期 <span class="wb-handoff-opt">选填</span></label>
            <textarea
              id="wb-handoff-plan"
              v-model="pendingHandoff.planNotes"
              class="wb-handoff-textarea wb-handoff-textarea--sm"
              rows="3"
              placeholder="例如：先画节点框架、预计本周完成初版…"
              spellcheck="false"
            />
          </template>
          <template v-else-if="pendingHandoff.intentKey === 'mod'">
            <label class="wb-handoff-label" for="wb-handoff-suggest">
              Mod ID（根据用户需求填写，相当于关键词；已预填可改）<span class="wb-handoff-opt">选填</span>
            </label>
            <input
              id="wb-handoff-suggest"
              v-model="pendingHandoff.suggestedModId"
              type="text"
              class="wb-handoff-input"
              placeholder="如 my-qq-watch，或一句便于检索/生成标识的关键词"
              autocomplete="off"
            />
          </template>
          <template v-else-if="pendingHandoff.intentKey === 'employee'">
            <label class="wb-handoff-label" for="wb-handoff-emp-target">员工包模式</label>
            <select id="wb-handoff-emp-target" v-model="pendingHandoff.employeeTarget" class="wb-handoff-input">
              <option value="pack_only">仅员工包（快速）</option>
              <option value="pack_plus_workflow">员工包 + 画布工作流</option>
            </select>
            <label class="wb-handoff-label" for="wb-handoff-emp-wf">
              画布工作流名称 <span class="wb-handoff-opt">选填</span>
            </label>
            <input
              id="wb-handoff-emp-wf"
              v-model="pendingHandoff.employeeWorkflowName"
              type="text"
              class="wb-handoff-input"
              placeholder="留空则使用包目录名"
              autocomplete="off"
            />
            <label class="wb-handoff-label" for="wb-handoff-fhd-url">
              FHD 根 URL（末尾 GET /api/mods/ 探测）<span class="wb-handoff-opt">选填</span>
            </label>
            <input
              id="wb-handoff-fhd-url"
              v-model="pendingHandoff.fhdBaseUrl"
              type="url"
              class="wb-handoff-input"
              placeholder="https://宿主:端口"
              autocomplete="off"
            />
          </template>
        </div>
        <p v-if="finalizeError" class="wb-handoff-error" role="alert">{{ finalizeError }}</p>
        <div
          v-if="finalizeLoading"
          class="wb-handoff-run"
          role="status"
          aria-live="polite"
          aria-busy="true"
        >
          <p class="wb-handoff-run__status">{{ handoffRunStatusLine }}</p>
          <div
            v-if="orchestrationSession?.steps?.length"
            class="wb-handoff-run__bar-wrap"
            aria-hidden="true"
          >
            <span class="wb-handoff-run__bar">
              <span class="wb-handoff-run__fill" :style="{ width: `${orchestrationProgress.percent}%` }"></span>
            </span>
            <span class="wb-handoff-run__counts">{{ orchestrationProgress.done }}/{{ orchestrationProgress.total }}</span>
          </div>
          <p v-else class="wb-handoff-run__boot">正在创建编排会话并拉取步骤，通常数秒内显示进度。</p>
          <ol v-if="orchestrationSession?.steps?.length" class="wb-steps wb-handoff-run__steps">
            <li
              v-for="st in orchestrationSession.steps"
              :key="st.id"
              class="wb-step"
              :class="orchStepClass(st)"
            >
              <span class="wb-step-dot" aria-hidden="true" />
              <span class="wb-step-body">
                <span class="wb-step-label">{{ st.label }}</span>
                <span v-if="st.message" class="wb-step-msg">{{ st.message }}</span>
                <span v-if="orchStepRunningSec(st) !== null" class="wb-step-since">已运行 {{ formatWallClockSec(orchStepRunningSec(st)) }}</span>
                <span v-if="orchStepSlowHint(st)" class="wb-step-slow">模型响应较慢，仍在等待…</span>
              </span>
            </li>
          </ol>
        </div>
        <div class="wb-handoff-actions">
          <button
            type="button"
            class="wb-handoff-primary"
            :disabled="finalizeLoading || !canRunOrchestration"
            @click="() => void runOrchestration()"
          >
            {{ finalizeLoading ? orchestrationButtonPendingLabel : orchestrationButtonLabel }}
          </button>
          <div
            v-if="finalizeLoading"
            class="wb-handoff-actions__timing"
            role="status"
            aria-live="polite"
            :title="orchestrationTimingTooltip"
          >
            <span class="wb-handoff-actions__timing-line">
              <span class="wb-handoff-actions__k">耗时参考</span>
              <span class="wb-handoff-actions__v">{{ orchestrationEtaDisplay }}</span>
            </span>
            <span class="wb-handoff-actions__timing-line">
              <span class="wb-handoff-actions__k">已用</span>
              <span class="wb-handoff-actions__v">{{ orchestrationElapsedDisplay }}</span>
            </span>
          </div>
        </div>
        <p class="wb-handoff-foot">{{ handoffFootNote }}</p>
      </section>

      <div
        v-if="hasWorkflow"
        class="wb-composer-column"
        :class="{ 'wb-composer-column--task-slim': makeHasActiveTask }"
      >
        <div class="wb-composer-panel" @keydown="onComposerKeydown">
          <div class="wb-composer-body">
            <aside
              class="wb-composer-intent"
              :class="{ 'wb-composer-intent--compact': intentRepoPickShow && !showIntentGuide }"
              aria-live="polite"
            >
              <template v-if="showIntentGuide">
                <p class="wb-composer-intent__kicker">将制作</p>
                <p class="wb-composer-intent__title wb-composer-intent__title--dynamic">{{ composerMainTitle }}</p>
                <p class="wb-composer-intent__sub">{{ intentMeta.sub }}</p>
              </template>
              <button
                v-if="intentRepoPickShow"
                type="button"
                class="wb-intent-guide-toggle"
                :aria-expanded="showIntentGuide"
                @click="intentGuideCollapsed = !intentGuideCollapsed"
              >
                {{ showIntentGuide ? '收起说明' : '展开说明' }}
              </button>
              <div
                v-if="intentRepoPickShow"
                class="wb-intent-repo"
                aria-label="从仓库选择已有项以编辑"
              >
                <p class="wb-intent-repo__title">仓库已有（可跳转编辑）</p>
                <template v-if="composerIntent === 'employee'">
                  <select v-model="pickEmployeeKey" class="wb-intent-repo__sel">
                    <option value="">— 选择 Catalog 员工包 —</option>
                    <option v-for="row in catalogEmployeesForPick" :key="row.k" :value="row.k">
                      {{ row.label }}
                    </option>
                  </select>
                  <div v-if="pickedEmployeeRow" class="wb-intent-repo__detail">
                    <p class="wb-intent-repo__detail-kicker">已选包</p>
                    <p class="wb-intent-repo__detail-name">
                      {{ pickedEmployeeRow.displayName }} · {{ pickedEmployeeRow.ver }}
                    </p>
                    <p class="wb-intent-repo__detail-meta">
                      {{ releaseChannelLabel(pickedEmployeeRow.release_channel) }} · {{ pickedEmployeeRow.industry || '行业 —' }}
                      <template v-if="pickedEmployeeRow.probe_mod_id">
                        · 关联 Mod <code class="mono">{{ pickedEmployeeRow.probe_mod_id }}</code>
                      </template>
                    </p>
                    <p class="wb-intent-repo__detail-desc">
                      {{ truncateWorkbenchText(pickedEmployeeRow.description, 280) || '（无描述）' }}
                    </p>
                    <p class="wb-intent-repo__detail-hint">
                      点「去员工制作」打开该版本。在员工页修改后使用「保存测试版」会写入新的
                      <code class="mono">draft-…</code> 记录；正式版请在员工页通过「发布正式」晋升。
                    </p>
                  </div>
                  <button
                    type="button"
                    class="btn wb-intent-repo__go"
                    :disabled="!pickEmployeeKey"
                    title="携带 edit_pkg / edit_ver 打开员工制作页，载入该 Catalog 版本以便编辑与保存测试版"
                    @click="goEditEmployeeFromPick"
                  >
                    去员工制作
                  </button>
                </template>
                <template v-else-if="composerIntent === 'mod'">
                  <select v-model="pickModId" class="wb-intent-repo__sel">
                    <option value="">— 选择 Mod —</option>
                    <option v-for="m in catalogModsForPick" :key="m.id" :value="m.id">
                      {{ m.label }}
                    </option>
                  </select>
                  <div v-if="pickedModRow" class="wb-intent-repo__detail">
                    <p class="wb-intent-repo__detail-kicker">已选 Mod</p>
                    <p class="wb-intent-repo__detail-name">
                      {{ pickedModRow.id }} · v{{ pickedModManifestVersion }}
                    </p>
                    <p v-if="pickedModManifestName" class="wb-intent-repo__detail-meta">{{ pickedModManifestName }}</p>
                    <p class="wb-intent-repo__detail-desc">
                      {{ truncateWorkbenchText(pickedModManifestDescription, 280) || '（无描述）' }}
                    </p>
                    <p class="wb-intent-repo__detail-hint">
                      点「去 Mod 制作」打开制作页，可继续改 manifest、workflow_employees 与文件。
                    </p>
                  </div>
                  <button
                    type="button"
                    class="btn wb-intent-repo__go"
                    :disabled="!pickModId"
                    title="打开 Mod 制作页（编辑模式）"
                    @click="goEditModFromPick"
                  >
                    去 Mod 制作
                  </button>
                </template>
              </div>
            </aside>
            <div
              class="wb-composer-main"
              :class="{ 'wb-composer-main--drag': knowledgeDragActive }"
              @dragenter.prevent="onKnowledgeDragEnter"
              @dragover.prevent="onKnowledgeDragEnter"
              @dragleave.prevent="onKnowledgeDragLeave"
              @drop.prevent="onKnowledgeDrop"
            >
              <label class="wb-sr-only" for="wb-home-input">{{ makeComposerInputLabel }}</label>
              <textarea
                id="wb-home-input"
                ref="inputRef"
                v-model="makeComposerInput"
                class="wb-input"
                :rows="makeComposerRows"
                :placeholder="makeComposerPlaceholder"
                spellcheck="false"
              />
              <input
                ref="knowledgeFileInputRef"
                type="file"
                class="wb-kb-file"
                accept=".txt,.md,.json,.csv,.pdf,.docx,.xlsx"
                multiple
                :disabled="knowledgeUploading || !!planSession"
                @change="onKnowledgeFileChange"
              />
              <p v-if="knowledgeError" class="wb-research-msg wb-research-msg--err" role="status">{{ knowledgeError }}</p>
              <TransitionGroup
                v-if="directAttachedFiles.length"
                name="wb-direct-file-card"
                tag="div"
                class="wb-direct-file-stack wb-composer-file-stack"
                aria-label="二档附件"
              >
                <article
                  v-for="(f, i) in directVisibleAttachedFiles"
                  :key="`composer-${f.id}`"
                  class="wb-direct-file-card"
                  :class="[
                    `wb-direct-file-card--${f.status}`,
                    `wb-direct-file-card--${directAttachmentKind(f)}`,
                    { 'wb-direct-file-card--ingesting': f.ingesting },
                  ]"
                  :style="{ '--att-index': i }"
                  :title="directFileChipTitle(f)"
                >
                  <span class="wb-direct-file-card__deck" aria-hidden="true">
                    <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--back"></span>
                    <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--mid"></span>
                    <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--front">
                      <span class="wb-direct-file-card__deck-label">{{ directAttachmentKindLabel(f) }}</span>
                    </span>
                  </span>
                  <span class="wb-direct-file-card__state" aria-hidden="true">
                    <span v-if="f.status === 'uploading' || f.ingesting" class="wb-direct-file-card__spinner" />
                    <span v-else-if="f.status === 'ready' || f.status === 'inline'" class="wb-direct-file-card__check">✓</span>
                    <span v-else class="wb-direct-file-card__warn">!</span>
                  </span>
                  <button
                    type="button"
                    class="wb-direct-file-card__remove"
                    :aria-label="`移除 ${f.name}`"
                    :disabled="knowledgeUploading || f.status === 'uploading'"
                    @click="() => void removeDirectAttachedFile(f.id)"
                  >×</button>
                </article>
                <div
                  v-if="directHiddenAttachmentCount"
                  key="composer-more"
                  class="wb-direct-file-card wb-direct-file-card--more"
                  aria-label="更多附件"
                >
                  <span class="wb-direct-file-card__deck" aria-hidden="true">
                    <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--back"></span>
                    <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--mid"></span>
                    <span class="wb-direct-file-card__deck-card wb-direct-file-card__deck-card--front">
                      <span class="wb-direct-file-card__deck-plus">+{{ directHiddenAttachmentCount }}</span>
                    </span>
                  </span>
                </div>
              </TransitionGroup>
              <div v-if="directAttachmentMentions.length" class="wb-file-mention-row wb-file-mention-row--composer" aria-label="二档已引用附件">
                <span
                  v-for="(m, i) in directAttachmentMentions"
                  :key="`make-ref-${m}`"
                  class="wb-file-mention-token"
                >@附件{{ i + 1 }} {{ m }}</span>
              </div>
              <div class="wb-input-footer">
                <div
                  class="wb-input-hint"
                  title="Enter 发送 · Shift+Enter 换行"
                >
                  <div class="wb-input-hint__primary">
                    <button
                      type="button"
                      class="wb-direct-new-btn wb-composer-new-btn"
                      title="清空输入与附件，并退出需求规划"
                      :disabled="knowledgeUploading"
                      @click="resetMakeComposer"
                    >新建</button>
                    <span class="wb-input-hint__intent"
                      >当前：{{ composerMainTitle
                      }}<template v-if="planSession?.phase === 'chat'"> · 规划追问</template></span
                    >
                    <button
                      v-if="composerIntent === 'mod'"
                      type="button"
                      class="wb-frontend-toggle"
                      :class="{ 'wb-frontend-toggle--on': modFrontendEnabled }"
                      role="switch"
                      :aria-checked="modFrontendEnabled"
                      title="打开后会为本 Mod 生成可路由 Vue 前端页面；关闭则只生成 Mod 骨架、员工和工作流"
                      @click="modFrontendEnabled = !modFrontendEnabled"
                    >
                      <span class="wb-frontend-toggle__label">制作前端</span>
                      <span class="wb-frontend-toggle__switch" aria-hidden="true">
                        <span class="wb-frontend-toggle__knob"></span>
                      </span>
                    </button>
                    <span class="wb-input-hint__keys">Enter 发送 · Shift+Enter 换行</span>
                  </div>
                </div>
                <div class="wb-footer-trailing">
              <div class="wb-llm-inline" aria-label="模型">
                <!-- 原生 select 下拉由系统绘制，深色主题下常出现白底；Auto/自选 仅两项，用分段按钮替代 -->
                <div class="wb-mode-segment" role="radiogroup" aria-label="模型模式">
                  <button
                    type="button"
                    class="wb-mode-segment__btn"
                    :class="{ 'wb-mode-segment__btn--on': modelMode === 'auto' }"
                    role="radio"
                    :aria-checked="modelMode === 'auto'"
                    @click="modelMode = 'auto'"
                  >
                    Auto
                  </button>
                  <button
                    type="button"
                    class="wb-mode-segment__btn"
                    :class="{ 'wb-mode-segment__btn--on': modelMode === 'manual' }"
                    role="radio"
                    :aria-checked="modelMode === 'manual'"
                    @click="modelMode = 'manual'"
                  >
                    自选
                  </button>
                </div>
                <template v-if="modelMode === 'manual' && llmCatalog && llmCatalog.providers?.length && !llmCatalogError">
                  <div class="wb-llm-dd">
                    <span class="wb-sr-only" id="wb-home-provider-lbl">厂商</span>
                    <button
                      type="button"
                      class="wb-dd-trigger"
                      :class="{ 'wb-dd-trigger--open': llmDdOpen === 'provider' }"
                      aria-haspopup="listbox"
                      :aria-expanded="llmDdOpen === 'provider'"
                      aria-labelledby="wb-home-provider-lbl"
                      title="厂商"
                      @click.stop="toggleLlmDd('provider')"
                    >
                      <span class="wb-dd-trigger__text">{{ currentProviderLabel }}</span>
                      <svg class="wb-dd-trigger__icon" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                        <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" />
                      </svg>
                    </button>
                    <ul
                      v-show="llmDdOpen === 'provider'"
                      class="wb-dd-panel"
                      role="listbox"
                      aria-labelledby="wb-home-provider-lbl"
                    >
                      <li
                        v-for="b in llmCatalog.providers"
                        :key="b.provider"
                        role="option"
                        class="wb-dd-item"
                        :class="{ 'wb-dd-item--on': selectedProvider === b.provider }"
                        :aria-selected="selectedProvider === b.provider"
                        @click.stop="pickProvider(b.provider)"
                      >
                        {{ b.label || b.provider }}
                      </li>
                    </ul>
                  </div>
                  <div class="wb-llm-dd wb-llm-dd--model">
                    <span class="wb-sr-only" id="wb-home-model-lbl">模型</span>
                    <button
                      type="button"
                      class="wb-dd-trigger wb-dd-trigger--model"
                      :class="{ 'wb-dd-trigger--open': llmDdOpen === 'model' }"
                      :disabled="!modelPickerEnabled"
                      aria-haspopup="listbox"
                      :aria-expanded="llmDdOpen === 'model'"
                      aria-labelledby="wb-home-model-lbl"
                      title="模型"
                      @click.stop="modelPickerEnabled && toggleLlmDd('model')"
                    >
                      <span class="wb-dd-trigger__text">{{ selectedModel || '选择模型' }}</span>
                      <svg class="wb-dd-trigger__icon" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                        <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" />
                      </svg>
                    </button>
                    <ul
                      v-show="llmDdOpen === 'model' && modelPickerEnabled"
                      class="wb-dd-panel wb-dd-panel--tall"
                      role="listbox"
                      aria-labelledby="wb-home-model-lbl"
                    >
                      <template v-for="cat in LLM_CATEGORY_ORDER" :key="cat">
                        <template v-if="modelsForWorkbenchCategory(cat).length">
                          <li class="wb-dd-cat" role="presentation">{{ categoryLabel(cat) }}</li>
                          <li
                            v-for="row in modelsForWorkbenchCategory(cat)"
                            :key="row.id"
                            role="option"
                            class="wb-dd-item"
                            :class="{ 'wb-dd-item--on': selectedModel === row.id }"
                            :aria-selected="selectedModel === row.id"
                            @click.stop="pickModel(row.id)"
                          >
                            {{ row.id }}
                          </li>
                        </template>
                      </template>
                    </ul>
                  </div>
                </template>
                <span
                  v-else-if="modelMode === 'manual' && (llmCatalogLoading || llmCatalogError || !llmCatalog?.providers?.length)"
                  class="wb-llm-inline__note"
                  :title="llmCatalogError || ''"
                >{{ llmCatalogLoading ? '目录…' : '登录配置' }}</span>
              </div>
              <button
                type="button"
                class="wb-kb-add-btn"
                :disabled="knowledgeUploading || !!planSession"
                :title="knowledgeUploading ? '上传中' : '上传文件'"
                aria-label="上传文件"
                @click="openKnowledgeFilePicker"
              >
                <span v-if="knowledgeUploading" class="wb-kb-spinner" aria-hidden="true"></span>
                <span v-else class="wb-kb-plus" aria-hidden="true"></span>
              </button>
              <button
                type="button"
                class="wb-input-send"
                :disabled="composerSendDisabled"
                :aria-label="planSession?.phase === 'chat' ? '发送追问' : '发送'"
                @click="() => void onComposerSendClick()"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <p class="wb-composer-note">
          Enter 发送后先进入「需求规划」：多轮澄清并生成执行清单，确认后再打开「制作草稿」启动生成与校验。
          <template v-if="planSession && planSession.phase !== 'chat'">当前请在上方完成摘要或清单。</template>
          <template v-else-if="planSession?.phase === 'chat'">澄清阶段在本框继续输入即可。</template>
          Auto 会按账户默认模型调用；若默认厂商没有可用密钥，会自动改用已配置密钥的厂商与模型（可在钱包页固定默认）。
        </p>
      </div>

      <nav v-if="!makeHasActiveTask" class="wb-starters" aria-label="Skill 组描述快捷提示">
        <button
          v-if="hasRepo"
          type="button"
          class="wb-starter"
          :class="{ 'wb-starter--active': hasWorkflow && composerIntent === 'mod' }"
          @click="applyStarter('mod')"
        >
          <div class="wb-starter-text">
            <span class="wb-starter-title">做 Mod</span>
            <span class="wb-starter-sub">先建仓库 · 行业 JSON · 员工命名（不必一次完善）</span>
          </div>
          <span class="wb-starter-arrow" aria-hidden="true">→</span>
        </button>
        <button
          v-if="hasEmployee"
          type="button"
          class="wb-starter"
          :class="{ 'wb-starter--active': hasWorkflow && composerIntent === 'employee' }"
          @click="applyStarter('employee')"
        >
          <div class="wb-starter-text">
            <span class="wb-starter-title">做员工</span>
            <span class="wb-starter-sub">提示词与工具 · 填入描述</span>
          </div>
          <span class="wb-starter-arrow" aria-hidden="true">→</span>
        </button>
        <button
          v-if="hasWorkflow"
          type="button"
          class="wb-starter"
          :class="{ 'wb-starter--active': hasWorkflow && composerIntent === CANVAS_SKILL_INTENT }"
          @click="applyStarter(CANVAS_SKILL_INTENT)"
        >
          <div class="wb-starter-text">
            <span class="wb-starter-title">生成 Skill 组</span>
            <span class="wb-starter-sub">画布编排（调度图）· 先拆 Skill 再组合；可执行程序见脚本工作流</span>
          </div>
          <span class="wb-starter-arrow" aria-hidden="true">→</span>
        </button>
      </nav>

      <footer class="wb-foot">
        <span v-if="hasWorkflow"
          >选择类型后输入想法：Enter 先进入需求规划（多轮问答与清单），确认后再在制作草稿中启动生成；顶部可查看执行进度。
          <template v-if="hasScriptWorkflowRoute">
            若你要的是<strong>可执行、完成任务的程序</strong>，请用
            <router-link :to="{ name: 'script-workflow-new' }" class="wb-foot-link">新建脚本工作流</router-link>
            （与画布「调度图」并列，脚本即程序本体）。</template>
        </span>
        <span v-else>从顶栏「工作台」进入 Mod 库、员工制作或工作流管理。</span>
        <router-link :to="{ name: 'ai-store' }" class="wb-foot-link">AI 市场</router-link>
        <template v-if="hasPlans">
          <span class="wb-foot-dot" aria-hidden="true">·</span>
          <router-link :to="{ name: 'plans' }" class="wb-foot-link">套餐</router-link>
        </template>
      </footer>
            </section>

            <section class="wb-gear-scene wb-voice-scene" aria-label="三档语音规划">
              <div class="wb-voice-orb-wrap">
                <!-- 轨道旋转时一、二档仍在视窗外挂载会导致大量 CSS 动画持续跑 GPU；仅在三档展示时再挂载 -->
                <template v-if="activeGear === 'voice'">
                  <OrbitRings :mode="voiceState" :lite="voiceState === 'idle'" />
                  <button
                    type="button"
                    class="wb-voice-orb"
                    :class="`wb-voice-orb--${voiceState}`"
                    :disabled="voiceBusy"
                    aria-label="语音输入"
                    @click="toggleVoiceListening"
                  >
                    <JarvisCore
                      :is-speaking="voiceState === 'listening'"
                      :is-work-mode="voiceState === 'thinking'"
                      :is-monitor-mode="voiceState === 'summary'"
                      :reduce-effects="voiceState === 'idle'"
                    />
                  </button>
                </template>
                <button
                  v-else
                  type="button"
                  class="wb-voice-orb wb-voice-orb--placeholder"
                  disabled
                  aria-hidden="true"
                  tabindex="-1"
                ></button>
              </div>
              <div class="wb-voice-copy">
                <h1 class="wb-voice-title">{{ voiceTitle }}</h1>
                <p class="wb-voice-sub">{{ voiceStatusText }}</p>
              </div>
              <p v-if="voiceTranscript" class="wb-voice-transcript">“{{ voiceTranscript }}”</p>
              <div v-if="voiceMessages.length" class="wb-voice-thread" aria-live="polite">
                <article
                  v-for="(msg, i) in voiceMessages"
                  :key="`voice-${i}`"
                  class="wb-voice-msg"
                  :class="msg.role === 'user' ? 'wb-voice-msg--user' : 'wb-voice-msg--assistant'"
                >
                  {{ msg.content }}
                </article>
              </div>
              <div class="wb-voice-actions">
                <button
                  type="button"
                  class="wb-voice-primary"
                  :disabled="voiceBusy"
                  @click="toggleVoiceListening"
                >
                  {{ voiceListening ? '停止聆听' : '开始说话' }}
                </button>
                <button
                  type="button"
                  class="wb-voice-secondary"
                  :disabled="voiceBusy || !voiceDraft.trim()"
                  @click="() => void submitVoiceTurn()"
                >
                  发送文字
                </button>
                <button
                  type="button"
                  class="wb-voice-secondary"
                  :disabled="!voiceMessages.length"
                  @click="confirmVoiceAndOpenHandoff"
                >
                  确认并制作
                </button>
              </div>
              <textarea
                v-model="voiceDraft"
                class="wb-voice-fallback"
                rows="2"
                placeholder="语音不可用时，可以在这里打字补充…"
              />
              <p v-if="voiceError" class="wb-voice-error" role="alert">{{ voiceError }}</p>
            </section>
          </div>
        </div>
      </div>
    </div>
    <Teleport to="body">
      <div
        v-if="showDirectTierFab"
        class="wb-direct-tier-fab"
        role="region"
        aria-label="消费档位悬浮控件"
      >
        <ConsumptionTierControl v-model="consumptionTier" />
      </div>
    </Teleport>
    <Teleport to="body">
      <div
        v-if="planDiagramPreviewIdx !== null"
        class="wb-plan-diagram-preview-backdrop"
        role="presentation"
        @click.self="closePlanDiagramPreview"
      >
        <div
          class="wb-plan-diagram-preview-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="wb-plan-diagram-preview-title"
        >
          <div class="wb-plan-diagram-preview-head">
            <h2 id="wb-plan-diagram-preview-title" class="wb-plan-diagram-preview-title">架构图预览</h2>
            <button
              type="button"
              class="wb-plan-diagram-preview-close"
              aria-label="关闭预览"
              @click="closePlanDiagramPreview"
            >
              ×
            </button>
          </div>
          <div class="wb-plan-diagram-preview-body">
            <div class="wb-plan-diagram-preview-toolbar" @pointerdown.stop>
              <button type="button" class="wb-plan-preview-tool" aria-label="缩小" @click="planDiagramPreviewZoomStep(-1)">−</button>
              <button type="button" class="wb-plan-preview-tool wb-plan-preview-tool--primary" @click="planDiagramPreviewFitView">
                适应窗口
              </button>
              <button type="button" class="wb-plan-preview-tool" aria-label="放大" @click="planDiagramPreviewZoomStep(1)">+</button>
              <span class="wb-plan-preview-hint">滚轮缩放 · 按住左键拖拽平移</span>
            </div>
            <div
              ref="planDiagramPreviewViewportRef"
              class="wb-plan-diagram-preview-viewport"
              @wheel.prevent="onPlanDiagramPreviewWheel"
              @pointerdown="onPlanDiagramPreviewPointerDown"
            >
              <div class="wb-plan-diagram-preview-panlayer" :style="planDiagramPreviewPanStyle">
                <div ref="planDiagramPreviewMountRef" class="wb-plan-diagram-preview-canvas" tabindex="-1" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  computed,
  reactive,
  onMounted,
  onActivated,
  onUnmounted,
  onBeforeUnmount,
  nextTick,
  watch,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ConsumptionTierControl from '../components/workbench/ConsumptionTierControl.vue'
import MessageBody from '../components/workbench/MessageBody.vue'
import MessageActions from '../components/workbench/MessageActions.vue'
import VoicePhoneModal from '../components/workbench/VoicePhoneModal.vue'
import JarvisCore from '../components/workbench/JarvisCore.vue'
import OrbitRings from '../components/workbench/OrbitRings.vue'
import PersonalSettings from '../components/workbench/PersonalSettings.vue'
import AgentMarket from '../components/workbench/AgentMarket.vue'
import MediaGenPanel from '../components/workbench/MediaGenPanel.vue'
import type { AgentBot } from '../utils/agentBots'
import {
  loadAllBots,
  loadMyBots,
  saveMyBots,
  loadFavorites,
  saveFavorites,
  loadActiveBotId,
  saveActiveBotId,
} from '../utils/agentBots'
import type { PersonalSettings as PersonalSettingsValue } from '../utils/personalSettings'
import {
  defaultPersonalSettings,
  loadPersonalSettings,
  savePersonalSettings,
  applyThemeToDocument,
} from '../utils/personalSettings'
import { api } from '../api'
import { getAccessToken } from '../infrastructure/storage/tokenStore'
import type { ChatMessage, Conversation } from '../utils/conversationStore'
import {
  loadConversations,
  saveConversations,
  loadActiveId,
  saveActiveId,
  createConversation,
  makeMessage,
  summarizeForTitle,
  exportConversationAsMarkdown,
} from '../utils/conversationStore'
import { streamLLMChat } from '../utils/llmStream'
import type { StreamHandle } from '../utils/llmStream'
import { stripInternalMarkers } from '../utils/lightMarkdown'
import {
  DIRECT_ATTACHMENT_ACCEPT,
  DIRECT_KB_MAX_BYTES,
  DIRECT_KB_SUPPORTED_EXT,
  DIRECT_KB_SUPPORTED_EXTENSIONS,
  directFileExt,
  directFileKind,
  directFileKindLabel,
  formatDirectFileSize,
  resolveDirectAttachmentOutcome,
} from '../utils/directAttachments'

/** 从需求正文猜一个 Mod ID（与后端 normalize_mod_id 规则对齐，可全中文时回退为 mod-<时间戳>） */
function suggestModIdFromText(raw: string): string {
  const normalize = (x: string) =>
    x
      .toLowerCase()
      .replace(/[^a-z0-9._-]+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-+|-+$/g, '')
  let t = normalize(String(raw || ''))
  if (!t || !/^[a-z0-9]/.test(t)) {
    t = `mod-${Date.now().toString(36)}`
  }
  if (t.length > 48) {
    t = normalize(t.slice(0, 48))
  }
  if (!/^[a-z0-9][a-z0-9._-]*$/.test(t)) {
    t = `mod-${Date.now().toString(36)}`
  }
  return t
}

/** 与后端 llm_model_taxonomy.CATEGORY_ORDER 一致 */
const LLM_CATEGORY_ORDER = ['llm', 'vlm', 'image', 'video', 'other']

const router = useRouter()
const route = useRoute()
const draft = ref('')
const displayName = ref('')
const inputRef = ref(null)
const handoffPanelRef = ref(null)
/** 发送后暂存在页顶；补全并创建成功后才跳转画布 */
const pendingHandoff = ref(null)
const finalizeLoading = ref(false)
const finalizeError = ref('')
/** 编排轮询中的会话快照（含 steps） */
const orchestrationSession = ref(null)
const orchestrationSessionId = ref('')
const pollStop = ref(false)
/** 编排：估算耗时阶段 → 正式执行（估算结束后才开始「已用」计时） */
const orchPhase = ref('idle')
const orchestrationEtaSeconds = ref(null)
const orchestrationEtaReason = ref('')
let orchElapsedTimer = null
const orchTimingStartMs = ref(null)
/** 每 500ms 递增，驱动已用时间的 computed 刷新 */
const orchElapsedTick = ref(0)
/** 工作流编排成功后的「关联 Mod」卡片 */
const workflowLinkOffer = ref(null)
const linkMods = ref([])
const linkModId = ref('')
const linkBusy = ref(false)
const linkError = ref('')

/** 需求规划：多轮澄清 → 执行清单 → 再进入制作草稿 */
const planSession = ref(null)
const planReplyDraft = ref('')
/** 「AI 自主全部进行」：从 summary 一路串到 runOrchestration 结束的互斥锁 */
const autoPilotRunning = ref(false)
const autoPilotError = ref('')
/** 快捷选项：题目 id -> 选中的 choice id（含 UI 专用「其他」） */
const planOptionSelections = ref({})
/** 「其他」在提交与 canSend 中使用的保留 choice id（勿与模型返回的 id 重复） */
const PLAN_OPTION_OTHER_ID = '__plan_ui_other__'
/** 题目 id -> 「其他」时的自定义文案 */
const planOptionOtherText = reactive({})

function clearPlanOptionOtherText() {
  for (const k of Object.keys(planOptionOtherText)) {
    delete planOptionOtherText[k]
  }
}
const planPanelRef = ref(null)
/** 每次打开规划会话递增，用于 Transition 内层 :key 触发动画 */
const planSurfaceKey = ref(0)

const MAKE_PROGRESS_CACHE_KEY = 'workbench_home_make_progress_v1'
const MAKE_PROGRESS_CACHE_TTL_MS = 24 * 60 * 60 * 1000

/** 需求规划加载区：分步提示（定时推进当前步，减少「卡住」感） */
const planLoadingStepsSummary = Object.freeze([
  '校验登录与默认模型',
  '读取任务描述与上传材料',
  '请求模型生成摘要（较慢时可能需数十秒）',
  '写入确认卡片',
])
const planLoadingStepsChat = Object.freeze([
  '校验登录与默认模型',
  '整理本轮对话与隐藏上下文',
  '发起模型上游请求',
  '等待模型输出（长任务可能需数十秒）',
  '解析流程图与快捷选项格式',
  '写入本条助手回复',
])
const planLoadingAdvance = ref(0)
let planLoadingIntervalId = null

const planLoadingStepLabelsForUi = computed(() => {
  if (!planSession.value?.loading) return []
  return planSession.value.phase === 'summary' ? planLoadingStepsSummary : planLoadingStepsChat
})

const knowledgeStatus = ref(null)
const knowledgeDocs = ref([])
const knowledgeLoading = ref(false)
const knowledgeUploading = ref(false)
const knowledgeError = ref('')
const knowledgeFileInputRef = ref(null)
const knowledgeDragActive = ref(false)

/** 调 /api/knowledge/search 之前的预检：未配置 Embedding Key 时直接跳过 RAG，
 *  避免一档对话 / 二档制作发送时连带产生 503 与「未配置可用 Embedding Key」横幅，
 *  这条横幅原本只是提示性的，但放在 catch 里会让用户误以为业务流程失败。 */
function isEmbeddingConfigured(): boolean {
  const st = knowledgeStatus.value as any
  return Boolean(st?.embedding?.configured)
}
/** 与下方 starter 同步：仅标记制作类型，不写入输入框（画布 Skill 组 intent 为 `skill`） */
const CANVAS_SKILL_INTENT = 'skill'
function isCanvasSkillIntent(k: string | undefined | null): boolean {
  return k === CANVAS_SKILL_INTENT || k === 'workflow'
}
const composerIntent = ref(CANVAS_SKILL_INTENT)
const modFrontendEnabled = ref(true)
const activeGear = ref('make')
const gearScenes = [
  { key: 'direct', num: '1', label: '聊' },
  { key: 'make', num: '2', label: '做' },
  { key: 'voice', num: '3', label: '说' },
]
const gearIndex = computed(() => Math.max(0, gearScenes.findIndex((it) => it.key === activeGear.value)))
const activeGearScene = computed(() => gearScenes[gearIndex.value] || gearScenes[1])
const gearDragging = ref(false)
const gearDragOffset = ref(0)
let gearDragStartY = 0
let gearDragTrackHeight = 1
let gearWheelLockedUntil = 0
let gearWheelAccum = 0
let gearWheelResetTimer = null
const gearThumbPercent = computed(() => {
  const last = Math.max(1, gearScenes.length - 1)
  const base = (gearIndex.value / last) * 100
  return Math.min(100, Math.max(0, base + gearDragOffset.value))
})
const directDraft = ref('')
const directFileInputRef = ref(null)
const directThreadRef = ref<HTMLElement | null>(null)
/**
 * 直接聊天待发送的本地附件。每项形如：
 *   { id, name, size, status: 'uploading'|'ready'|'error'|'skipped', docId, error, file }
 * - status='ready' 的文档已上传到当前用户知识库（doc_id），发送时会做向量检索并拼到 system prompt。
 * - status='skipped'/'error' 的文件不上传，只在消息中附带文件名说明。
 */
const directAttachedFiles = ref([])
const directLoading = ref(false)
const directError = ref('')

/** 一档直接聊天：单选绑定员工 id（优先于人设 id 参与知识检索）；sessionStorage 持久化 */
const WB_DIRECT_CHAT_EMPLOYEE_ID_KEY = 'wb_direct_chat_employee_id'
type DirectEmployeeOption = { id: string; name: string; sourceLabel: string }
const directChatEmployeeId = ref('')
const directEmployeeOptions = ref<DirectEmployeeOption[]>([])

// === 一档「直接聊天」会话管理 / 流式 / 多模态 / 工具栏 / 个性化 ===
const conversations = ref<Conversation[]>([])
const activeConversationId = ref<string>('')
const activeConversation = computed<Conversation | null>(
  () => conversations.value.find((c) => c.id === activeConversationId.value) || null,
)
const directMessages = computed<ChatMessage[]>(() => activeConversation.value?.messages || [])
const directIsDragging = ref(false)
let currentStreamHandle: StreamHandle | null = null
const editingMessageId = ref<string>('')
const editingDraft = ref<string>('')
const personalSettings = ref<PersonalSettingsValue>(defaultPersonalSettings())
const personalSettingsOpen = ref(false)

function onPersonalSettingsUpdate(v: PersonalSettingsValue) {
  personalSettings.value = v
  try {
    savePersonalSettings(v)
    applyThemeToDocument(v.theme)
  } catch {
    /* ignore */
  }
}
const showAgentMarket = ref(false)
const showVoicePhone = ref(false)
const showMediaGen = ref(false)
const allBots = ref<AgentBot[]>([])
const activeBotId = ref<string>('')
const activeBot = computed<AgentBot | null>(
  () => allBots.value.find((b) => b.id === activeBotId.value) || null,
)
/** 对话进行中：左上角一行当前主题（会话标题或最近用户提问摘要） */
const directTaskLine = computed(() => {
  const convTitle = String(activeConversation.value?.title || '').trim()
  if (convTitle && convTitle !== '新对话') return convTitle
  const latestUser = [...directMessages.value].reverse().find((m) => m.role === 'user')
  const raw = stripInternalMarkers(latestUser?.content || '').replace(/\s+/g, ' ').trim()
  if (raw) return summarizeForTitle(raw)
  if (activeBot.value?.name) return `${activeBot.value.name} · 对话中`
  return '对话中'
})
const speakingMessageId = ref<string>('')
let phoneSynth: SpeechSynthesis | null = null
let directTtsAudio: HTMLAudioElement | null = null
let directTtsObjectUrl: string | null = null

function stopDirectTtsPlayback() {
  if (directTtsAudio) {
    try {
      directTtsAudio.pause()
      directTtsAudio.removeAttribute('src')
      directTtsAudio.load()
    } catch {
      /* ignore */
    }
  }
  directTtsAudio = null
  if (directTtsObjectUrl) {
    try {
      URL.revokeObjectURL(directTtsObjectUrl)
    } catch {
      /* ignore */
    }
  }
  directTtsObjectUrl = null
}

const directSendDisabled = computed(
  () =>
    directLoading.value ||
    directAttachedFiles.value.some((f) => f.status === 'uploading') ||
    (!String(directDraft.value || '').trim() && directAttachedFiles.value.length === 0),
)

const directAttachHint = computed(() => {
  const list = directAttachedFiles.value
  if (!list.length) return ''
  const ready = list.filter((f) => f.status === 'ready').length
  const uploading = list.filter((f) => f.status === 'uploading').length
  const inlined = list.filter((f) => f.status === 'inline').length
  const skipped = list.filter((f) => f.status === 'skipped').length
  const errored = list.filter((f) => f.status === 'error').length
  const parts: string[] = []
  if (uploading) parts.push(`${uploading} 个读取中`)
  if (ready) parts.push(`${ready} 个已纳入资料库（提问时按相关度自动召回）`)
  if (inlined) parts.push(`${inlined} 个已读取，可直接发送给模型`)
  const embLabels = Array.from(
    new Set(
      list
        .map((f) => formatEmbeddingLabel(f.embedding))
        .filter(Boolean),
    ),
  )
  if (embLabels.length) parts.push(`向量索引：${embLabels.join('、')}`)
  if (skipped) parts.push(`${skipped} 个未受支持，仅附文件名给模型参考`)
  if (errored) parts.push(`${errored} 个上传失败，仅附文件名给模型参考`)
  return parts.join(' · ')
})
const directVisibleAttachedFiles = computed(() => directAttachedFiles.value.slice(0, 3))
const directHiddenAttachmentCount = computed(() => Math.max(0, directAttachedFiles.value.length - 3))
const directAttachmentMentions = computed(() =>
  directAttachedFiles.value
    .map((f) => String(f?.name || '').trim())
    .filter(Boolean),
)
const CONSUMPTION_TIER_STORAGE_KEY = 'workbench_consumption_tier'

function readStoredConsumptionTier(): number {
  try {
    const raw = sessionStorage.getItem(CONSUMPTION_TIER_STORAGE_KEY)
    const n = raw == null ? NaN : parseInt(raw, 10)
    if (Number.isFinite(n) && n >= 1 && n <= 10) return n
  } catch {
    /* ignore */
  }
  return 5
}

/** 直接聊天右上角「消费档位」1–10：占位；与右侧工作台 1/2/3 挡位无关 */
const consumptionTier = ref(readStoredConsumptionTier())

watch(consumptionTier, (v) => {
  try {
    sessionStorage.setItem(CONSUMPTION_TIER_STORAGE_KEY, String(v))
  } catch {
    /* ignore */
  }
})
const voiceDraft = ref('')
const voiceTranscript = ref('')
const voiceMessages = ref([])
const voiceListening = ref(false)
const voiceBusy = ref(false)
const voiceError = ref('')
const voiceState = ref('idle')
let voiceRecognition = null
/** 合并语音识别 interim 回调，避免超大视图每个音素都整页重渲染 */
let voiceTranscriptRaf = 0
let pendingVoiceTranscript = ''

const voiceTitle = computed(() => {
  if (voiceState.value === 'listening') return '我在听'
  if (voiceState.value === 'thinking') return '正在思考'
  if (voiceState.value === 'summary') return '已整理需求'
  return '说出你想制作的东西'
})

const voiceStatusText = computed(() => {
  if (voiceState.value === 'listening') return '直接说需求、场景、限制条件，我会边听边整理。'
  if (voiceState.value === 'thinking') return '正在把语音内容转成可执行的制作思路。'
  if (voiceState.value === 'summary') return '确认后会进入二档制作草稿，也可以继续补充。'
  return '点击呼吸球开始语音规划。浏览器不支持语音时，可用下方文字补充。'
})

function isGearAxisLocked() {
  const hasInput =
    Boolean(String(draft.value || '').trim()) ||
    Boolean(String(directDraft.value || '').trim()) ||
    Boolean(String(voiceDraft.value || '').trim()) ||
    Boolean(String(planReplyDraft.value || '').trim()) ||
    directAttachedFiles.value.length > 0
  const hasTask =
    Boolean(planSession.value) ||
    Boolean(pendingHandoff.value) ||
    Boolean(finalizeLoading.value) ||
    Boolean(linkBusy.value) ||
    Boolean(orchestrationSession.value?.steps?.length)
  return hasInput || hasTask
}

function setGear(key) {
  if (!gearScenes.some((it) => it.key === key)) return
  if (key !== activeGear.value && gearNavHardLocked.value) return
  if (key !== activeGear.value && isGearAxisLocked()) return
  gearDragOffset.value = 0
  gearDragging.value = false
  activeGear.value = key
}

function gearStopPercent(index) {
  const last = Math.max(1, gearScenes.length - 1)
  return (index / last) * 100
}

function onGearWheel(e) {
  if (gearNavHardLocked.value) {
    try {
      e.preventDefault()
    } catch {
      /* ignore */
    }
    gearWheelAccum = 0
    return
  }
  if (isGearAxisLocked()) {
    gearWheelAccum = 0
    return
  }
  const dy = Number(e?.deltaY || 0)
  const now = Date.now()
  if (now < gearWheelLockedUntil) return
  gearWheelAccum += dy
  if (gearWheelResetTimer) clearTimeout(gearWheelResetTimer)
  gearWheelResetTimer = setTimeout(() => {
    gearWheelAccum = 0
    gearWheelResetTimer = null
  }, 220)
  if (Math.abs(gearWheelAccum) < 240) return
  const next = Math.min(gearScenes.length - 1, Math.max(0, gearIndex.value + (gearWheelAccum > 0 ? 1 : -1)))
  if (next === gearIndex.value) return
  activeGear.value = gearScenes[next]?.key || activeGear.value
  gearWheelAccum = 0
  gearWheelLockedUntil = now + 520
}

function onGearPointerDown(e) {
  if (gearNavHardLocked.value) return
  if (isGearAxisLocked()) return
  const el = e.currentTarget
  const rect = el?.getBoundingClientRect?.()
  gearDragTrackHeight = Math.max(1, rect?.height || 1)
  gearDragStartY = Number(e.clientY || 0)
  gearDragOffset.value = 0
  gearDragging.value = true
  el?.setPointerCapture?.(e.pointerId)
}

function onGearPointerMove(e) {
  if (!gearDragging.value) return
  const delta = Number(e.clientY || 0) - gearDragStartY
  gearDragOffset.value = (delta / gearDragTrackHeight) * 100
}

function settleGearDrag() {
  if (!gearDragging.value) return
  if (gearNavHardLocked.value) {
    gearDragging.value = false
    gearDragOffset.value = 0
    return
  }
  if (isGearAxisLocked()) {
    gearDragging.value = false
    gearDragOffset.value = 0
    return
  }
  const step = 100 / Math.max(1, gearScenes.length - 1)
  const threshold = step * 0.64
  let next = gearIndex.value
  if (gearDragOffset.value > threshold) next += 1
  else if (gearDragOffset.value < -threshold) next -= 1
  next = Math.min(gearScenes.length - 1, Math.max(0, next))
  activeGear.value = gearScenes[next]?.key || activeGear.value
  gearDragging.value = false
  gearDragOffset.value = 0
}

function onGearPointerUp(e) {
  e.currentTarget?.releasePointerCapture?.(e.pointerId)
  settleGearDrag()
}

function onGearPointerCancel(e) {
  e.currentTarget?.releasePointerCapture?.(e.pointerId)
  gearDragging.value = false
  gearDragOffset.value = 0
}

function directFileChipTitle(f) {
  if (!f) return ''
  const emb = formatEmbeddingLabel(f.embedding)
  if (f.status === 'uploading') return `${f.name}：正在读取文件内容…`
  if (f.status === 'ready') return `${f.name}：已纳入资料库，提问时会按相关度自动召回片段${emb ? `；向量模型：${emb}` : ''}`
  if (f.status === 'inline') {
    return f.ingestError
      ? `${f.name}：已读取文本，可直接发送；${f.ingestError}`
      : `${f.name}：已读取文本，将直接注入模型上下文${f.ingesting ? '，资料库入库中' : ''}${emb ? `；向量模型：${emb}` : ''}`
  }
  if (f.status === 'skipped') return `${f.name}：${f.error || '该格式暂不解析；将仅附文件名供模型参考'}`
  if (f.status === 'error') return `${f.name}：${f.error || '上传失败'}（仅附文件名给模型参考）`
  return f.name
}

function formatEmbeddingLabel(embedding) {
  if (!embedding || typeof embedding !== 'object') return ''
  const provider = String(embedding.provider || '').trim()
  const model = String(embedding.model || '').trim()
  const dim = Number(embedding.dim || 0) || 0
  if (!provider && !model) return ''
  return `${provider || '默认'} / ${model || '默认模型'}${dim ? ` · ${dim}维` : ''}`
}

function directAttachmentKind(f) {
  return directFileKind(f?.name || '', f?.file?.type || '')
}

function directAttachmentKindLabel(f) {
  return directFileKindLabel(directAttachmentKind(f))
}

function directAttachmentStatusText(f) {
  if (!f) return ''
  if (f.status === 'uploading') return '读取中'
  if (f.status === 'ready') return f.embedding ? '已入库 · 向量' : '已入库'
  if (f.status === 'inline') {
    if (f.ingesting) return '可发送 · 入库中'
    if (f.ingestError) return '可发送 · 入库失败'
    return '可发送'
  }
  if (f.status === 'skipped') return '未支持'
  return '读取失败'
}

function directAttachmentNote(files) {
  const list = Array.isArray(files) ? files : []
  if (!list.length) return ''
  const parts = list.map((f, idx) => {
    const tag =
      f.status === 'ready'
        ? '已入库'
        : f.status === 'uploading'
        ? '读取中'
        : f.status === 'inline'
        ? '已读取'
        : f.status === 'error'
        ? '上传失败'
        : '未解析'
    return `@附件${idx + 1} ${f.name}（${formatDirectFileSize(f.size)}，${tag}）`
  })
  return `[附件顺序：${parts.join('，')}]`
}

function openDirectFilePicker() {
  if (directLoading.value) return
  directFileInputRef.value?.click?.()
}

function makeDirectAttachId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    try {
      return crypto.randomUUID()
    } catch {
      /* fallthrough */
    }
  }
  return `att_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function appendAttachmentMentions(files: File[], target: 'direct' | 'make') {
  const names = (Array.isArray(files) ? files : [])
    .map((file) => String(file?.name || '').trim())
    .filter(Boolean)
  if (!names.length) return
  const startIndex = Math.max(0, directAttachedFiles.value.length - names.length)
  const mentions = names.map((name, idx) => `@附件${startIndex + idx + 1} ${name}`).join(' ')
  const r = target === 'make' ? draft : directDraft
  const current = String(r.value || '')
  const joiner = current.trim() ? (/\s$/.test(current) ? '' : ' ') : ''
  r.value = `${current}${joiner}${mentions} `
}

async function uploadDirectAttachedFile(item) {
  let extractedText = ''
  try {
    const extractRes = await api.knowledgeExtractText(item.file)
    const outcome = resolveDirectAttachmentOutcome({ extractedText: extractRes?.text })
    const idx = directAttachedFiles.value.findIndex((x) => x.id === item.id)
    if (idx < 0) return
    if (!outcome.canSend) throw new Error(outcome.error)
    extractedText = outcome.extractedText
    directAttachedFiles.value[idx] = {
      ...directAttachedFiles.value[idx],
      status: 'inline',
      extractedText,
      docId: '',
      error: '',
      ingesting: true,
      ingestError: '',
    }
  } catch (e) {
    const idx = directAttachedFiles.value.findIndex((x) => x.id === item.id)
    if (idx < 0) return
    const outcome = resolveDirectAttachmentOutcome({ extractError: e })
    directAttachedFiles.value[idx] = {
      ...directAttachedFiles.value[idx],
      status: 'error',
      extractedText: '',
      docId: '',
      error: outcome.error,
      ingesting: false,
      ingestError: '',
    }
    return
  }

  try {
    const embeddingChoice = await resolveChatProviderModel()
    const res = await api.knowledgeUploadDocument(item.file, {
      embeddingProvider: embeddingChoice.provider,
      embeddingModel: embeddingChoice.model,
    })
    const docId = res?.document?.doc_id || res?.document?.docId || ''
    const idx = directAttachedFiles.value.findIndex((x) => x.id === item.id)
    if (idx < 0) {
      // 已被移除：尝试回收资料库中的副本，避免脏数据
      if (docId) {
        try {
          await api.knowledgeDeleteDocument(docId)
        } catch {
          /* ignore cleanup error */
        }
      }
      return
    }
    const outcome = resolveDirectAttachmentOutcome({ extractedText, docId, uploadError: docId ? undefined : '上传未返回文档 ID' })
    directAttachedFiles.value[idx] = {
      ...directAttachedFiles.value[idx],
      status: outcome.status,
      docId: outcome.docId,
      extractedText: outcome.extractedText,
      error: outcome.error,
      ingesting: false,
      ingestError: outcome.ingestError,
      embedding: res?.embedding || null,
    }
  } catch (e) {
    const idx = directAttachedFiles.value.findIndex((x) => x.id === item.id)
    if (idx < 0) return
    const outcome = resolveDirectAttachmentOutcome({ extractedText, uploadError: e })
    directAttachedFiles.value[idx] = {
      ...directAttachedFiles.value[idx],
      status: outcome.status,
      docId: '',
      extractedText: outcome.extractedText,
      error: outcome.error,
      ingesting: false,
      ingestError: outcome.ingestError,
    }
  }
}

function onDirectFilesChange(e) {
  const input = e?.target as HTMLInputElement | null
  if (!input || typeof input.files === 'undefined') return
  const picked: File[] = Array.from(input.files || [])
  input.value = ''
  if (!picked.length) return
  const maxFiles = 12
  const remaining = Math.max(0, maxFiles - directAttachedFiles.value.length)
  const accepted = picked.slice(0, remaining)
  const items = accepted.map((file: File) => {
    const ext = directFileExt(file.name)
    const supported = DIRECT_KB_SUPPORTED_EXT.has(ext)
    const tooBig = Number(file.size || 0) > DIRECT_KB_MAX_BYTES
    if (!supported) {
      return {
        id: makeDirectAttachId(),
        name: file.name,
        size: file.size || 0,
        status: 'skipped',
        docId: '',
        error: `不支持的格式（仅 ${DIRECT_KB_SUPPORTED_EXTENSIONS.join('/')} 入库）`,
        ingesting: false,
        ingestError: '',
        file,
      }
    }
    if (tooBig) {
      return {
        id: makeDirectAttachId(),
        name: file.name,
        size: file.size || 0,
        status: 'skipped',
        docId: '',
        error: `超过 ${formatDirectFileSize(DIRECT_KB_MAX_BYTES)} 上限`,
        ingesting: false,
        ingestError: '',
        file,
      }
    }
    return {
      id: makeDirectAttachId(),
      name: file.name,
      size: file.size || 0,
      status: 'uploading',
      docId: '',
      error: '',
      ingesting: false,
      ingestError: '',
      file,
    }
  })
  directAttachedFiles.value = [...directAttachedFiles.value, ...items]
  appendAttachmentMentions(accepted, 'direct')
  for (const it of items) {
    if (it.status === 'uploading') void uploadDirectAttachedFile(it)
  }
}

async function removeDirectAttachedFile(id) {
  const item = directAttachedFiles.value.find((f) => f.id === id)
  if (!item) return
  if (item.status === 'uploading') return
  directAttachedFiles.value = directAttachedFiles.value.filter((f) => f.id !== id)
  if (item.docId) {
    try {
      await api.knowledgeDeleteDocument(item.docId)
    } catch {
      /* 移除知识库中的副本失败不影响 UI */
    }
  }
}

function persistConversations() {
  saveConversations(conversations.value.slice())
}

function ensureActiveConversation(opts?: { forceNew?: boolean; bot?: AgentBot | null }): Conversation {
  if (!opts?.forceNew && activeConversation.value) return activeConversation.value
  const bot = opts?.bot ?? activeBot.value
  const conv = createConversation({
    title: '新对话',
    agentId: bot?.id,
    agentLabel: bot?.name,
  })
  if (bot?.opener) {
    conv.messages.push(makeMessage('assistant', bot.opener))
  }
  conversations.value = [conv, ...conversations.value]
  activeConversationId.value = conv.id
  saveActiveId(conv.id)
  persistConversations()
  return conv
}

function patchActiveConversation(mutator: (c: Conversation) => void) {
  const id = activeConversationId.value
  if (!id) return
  conversations.value = conversations.value.map((c) => {
    if (c.id !== id) return c
    const next: Conversation = { ...c, messages: c.messages.slice() }
    mutator(next)
    next.updatedAt = Date.now()
    return next
  })
  persistConversations()
}

function appendUserAndAssistant(userMsg: ChatMessage, assistantPlaceholder: ChatMessage) {
  patchActiveConversation((c) => {
    c.messages.push(userMsg)
    c.messages.push(assistantPlaceholder)
    if (!c.title || c.title === '新对话') {
      c.title = summarizeForTitle(userMsg.content)
    }
  })
}

function updateAssistantMessage(id: string, mutator: (m: ChatMessage) => void) {
  patchActiveConversation((c) => {
    const idx = c.messages.findIndex((m) => m.id === id)
    if (idx < 0) return
    const next = { ...c.messages[idx] }
    mutator(next)
    c.messages[idx] = next
  })
}

function buildSystemPrompt(
  activeBotPersona: string,
  knowledgePack: string,
  inlineFiles?: Array<{ name: string; text: string }>,
  directEmployeeHint?: string,
): string {
  const parts: string[] = []
  if (activeBotPersona) {
    parts.push(activeBotPersona)
  } else {
    parts.push('你是一个简洁直接的中文 AI 助手。优先给出可执行答案；如果信息不足，先给合理假设，再列出需要确认的问题。')
  }
  if (directEmployeeHint && directEmployeeHint.trim()) {
    parts.push(directEmployeeHint.trim())
  }
  if (personalSettings.value.memory && personalSettings.value.memory.trim()) {
    parts.push(`关于用户的长期记忆（请在回答中合理利用，但不要每次都重复念出）：\n${personalSettings.value.memory.trim()}`)
  }
  if (inlineFiles && inlineFiles.length > 0) {
    const blocks = inlineFiles
      .map((f, idx) => `### @附件${idx + 1}：${f.name}\n\n${f.text}`)
      .join('\n\n---\n\n')
    parts.push(
      `以下是用户按顺序直接上传的附件全文；用户消息里的 @附件1、@附件2 会对应这里的同序号文件。请按编号理解文件之间的先后逻辑，并优先据此回答：\n\n${blocks}`,
    )
  }
  if (knowledgePack) {
    parts.push(
      `以下是用户当前提问相关的资料库片段（来自其本人上传的文档），优先据此回答；若与提问无关请忽略：\n${knowledgePack}`,
    )
  }
  parts.push('回答时使用 Markdown：标题用 ## / ###，列表用「-」或「1.」，代码用 ``` 包裹并标注语言；公式用 $$ 包裹；如需画图请用 ```mermaid 代码块。')
  return parts.join('\n\n')
}

function rebuildContextMessages(forSendUpToIndex?: number): Array<{ role: string; content: string }> {
  const msgs = directMessages.value
  const sliceEnd = typeof forSendUpToIndex === 'number' ? forSendUpToIndex + 1 : msgs.length
  return msgs.slice(0, sliceEnd).map((m) => ({ role: m.role, content: m.content }))
}

function directEmployeeSystemHint(): string {
  const id = String(directChatEmployeeId.value || '').trim()
  if (!id) return ''
  const picked = directEmployeeOptions.value.find((e) => e.id === id)
  const label = picked ? `${picked.name}（${picked.sourceLabel}）` : id
  return `【一档测试绑定员工（单选）】当前绑定 id：${id}；显示：${label}。回答时请尽量贴合该员工职责与知识边界；若问题明显超出该角色，可简要说明后给出通用建议。`
}

async function runDirectChatTurn(opts: {
  userMsg?: ChatMessage
  assistantId: string
  userText: string
  inlineFiles?: Array<{ name: string; text: string }>
}) {
  directError.value = ''
  directLoading.value = true
  let knowledgePack = ''
  let citations: Array<{ title: string; snippet?: string; url?: string }> = []
  try {
    const { provider, model } = await resolveChatProviderModel()
    if (opts.userText) {
      try {
        const pickedEmp = String(directChatEmployeeId.value || '').trim()
        const botEmp = String(activeBot.value?.id || '').trim()
        const employeeId = pickedEmp || botEmp
        const res: any = await api.knowledgeV2Retrieve({
          query: opts.userText,
          top_k: 6,
          employee_id: employeeId || undefined,
          embedding_provider: provider,
          embedding_model: model,
        })
        const items = Array.isArray(res?.items) ? res.items : []
        if (items.length > 0) {
          knowledgePack = formatKnowledgeContext(items)
          citations = items.slice(0, 6).map((it: any, i: number) => {
            const filename = String(it?.filename || '资料')
            const pageNo = Number(it?.page_no || it?.pageNo || 0) || 0
            const snippet = String(it?.content || '').trim().slice(0, 200)
            return { title: `${i + 1}. ${filename}${pageNo ? ` · 第 ${pageNo} 页` : ''}`, snippet }
          })
        }
      } catch {
        // v2 不可用时回退到 v1（仅当用户有上传附件且 Embedding 已配置时检索）
        try {
          const ready = directAttachedFiles.value.some((f) => f.status === 'ready')
          const hasUserUploads = activeConversation.value?.messages?.some(
            (m) => Array.isArray(m.attachments) && m.attachments.some((a) => a.status === 'ready'),
          )
          if ((ready || hasUserUploads) && isEmbeddingConfigured()) {
            const res: any = await api.knowledgeSearch(opts.userText, 6, {
              embeddingProvider: provider,
              embeddingModel: model,
            })
            const items = Array.isArray(res?.items) ? res.items : []
            knowledgePack = formatKnowledgeContext(items)
            citations = items.slice(0, 6).map((it: any, i: number) => {
              const filename = String(it?.filename || '资料')
              const pageNo = Number(it?.page_no || it?.pageNo || 0) || 0
              const snippet = String(it?.content || '').trim().slice(0, 200)
              return { title: `${i + 1}. ${filename}${pageNo ? ` · 第 ${pageNo} 页` : ''}`, snippet }
            })
          }
        } catch {
          /* 检索失败不阻塞聊天 */
        }
      }
    }
    const sys = buildSystemPrompt(
      activeBot.value?.persona || '',
      knowledgePack,
      opts.inlineFiles,
      directEmployeeSystemHint(),
    )
    const ctx = directMessages.value
      .filter((m) => m.id !== opts.assistantId)
      .map((m) => ({ role: m.role, content: m.content }))
    const msgs = [{ role: 'system', content: sys }, ...ctx]
    const handle = streamLLMChat({
      provider,
      model,
      messages: msgs,
      maxTokens: 2048,
      onToken: (_delta, soFar) => {
        updateAssistantMessage(opts.assistantId, (m) => {
          m.content = soFar
          m.pending = true
        })
      },
      onError: (e) => {
        directError.value = e?.message || String(e)
        updateAssistantMessage(opts.assistantId, (m) => {
          m.pending = false
          m.error = e?.message || String(e)
          if (!m.content) m.content = `（生成失败：${m.error}）`
        })
      },
      onDone: (full, aborted) => {
        updateAssistantMessage(opts.assistantId, (m) => {
          m.pending = false
          if (aborted) {
            m.content = m.content ? `${m.content}\n\n_（已中断）_` : '_（已中断）_'
          } else if (full) {
            m.content = full
          }
          if (citations.length) m.citations = citations
        })
      },
    })
    currentStreamHandle = handle
    await handle.done
  } catch (e: any) {
    directError.value = e?.message || String(e)
    updateAssistantMessage(opts.assistantId, (m) => {
      m.pending = false
      m.error = e?.message || String(e)
      if (!m.content) m.content = `（生成失败：${m.error}）`
    })
  } finally {
    currentStreamHandle = null
    directLoading.value = false
  }
}

async function sendDirectChat(text = '') {
  if (directAttachedFiles.value.some((f) => f.status === 'uploading')) {
    directError.value = '附件仍在上传中，请稍候'
    return
  }
  const userText = String(text || directDraft.value || '').trim()
  const filesSnapshot = [...directAttachedFiles.value]
  const note = directAttachmentNote(filesSnapshot)
  let userContent = userText
  if (note) userContent = userContent ? `${userContent}\n\n${note}` : note
  if (!userContent || directLoading.value) return
  if (!requireLoginForWorkbenchUse()) return

  ensureActiveConversation()
  directDraft.value = ''
  directError.value = ''

  const userMsg = makeMessage('user', userContent, {
    skills: [],
    attachments: filesSnapshot.map((f) => ({ name: f.name, size: f.size, status: f.status, docId: f.docId })),
  })
  const inlineFiles = filesSnapshot
    .filter((f: any) => (f.status === 'inline' || f.status === 'ready') && f.extractedText)
    .map((f: any) => ({ name: f.name, text: f.extractedText as string }))

  const placeholder = makeMessage('assistant', '', { pending: true })
  appendUserAndAssistant(userMsg, placeholder)
  directAttachedFiles.value = []

  await runDirectChatTurn({ userMsg, assistantId: placeholder.id, userText, inlineFiles })
}

function stopGeneration() {
  if (currentStreamHandle) {
    currentStreamHandle.abort()
  }
}

async function regenerateAssistant(messageId: string) {
  if (directLoading.value) return
  const msgs = directMessages.value
  const idx = msgs.findIndex((m) => m.id === messageId)
  if (idx <= 0) return
  let userIdx = -1
  for (let i = idx - 1; i >= 0; i -= 1) {
    if (msgs[i].role === 'user') {
      userIdx = i
      break
    }
  }
  if (userIdx < 0) return
  const userText = msgs[userIdx].content
  patchActiveConversation((c) => {
    c.messages.splice(idx, 1)
  })
  const placeholder = makeMessage('assistant', '', { pending: true })
  patchActiveConversation((c) => {
    c.messages.push(placeholder)
  })
  await runDirectChatTurn({ assistantId: placeholder.id, userText })
}

function startEditUserMessage(messageId: string) {
  const m = directMessages.value.find((x) => x.id === messageId)
  if (!m || m.role !== 'user') return
  editingMessageId.value = messageId
  editingDraft.value = m.content
}

async function commitEditedUserMessage() {
  const id = editingMessageId.value
  const draft = String(editingDraft.value || '').trim()
  if (!id || !draft) {
    editingMessageId.value = ''
    editingDraft.value = ''
    return
  }
  const idx = directMessages.value.findIndex((m) => m.id === id)
  if (idx < 0) {
    editingMessageId.value = ''
    return
  }
  patchActiveConversation((c) => {
    c.messages[idx] = { ...c.messages[idx], content: draft }
    c.messages.splice(idx + 1)
  })
  editingMessageId.value = ''
  editingDraft.value = ''
  const placeholder = makeMessage('assistant', '', { pending: true })
  patchActiveConversation((c) => {
    c.messages.push(placeholder)
  })
  await runDirectChatTurn({ assistantId: placeholder.id, userText: draft })
}

function cancelEditUserMessage() {
  editingMessageId.value = ''
  editingDraft.value = ''
}

function setMessageFeedback(messageId: string, fb: 'up' | 'down' | null) {
  patchActiveConversation((c) => {
    const idx = c.messages.findIndex((m) => m.id === messageId)
    if (idx < 0) return
    c.messages[idx] = { ...c.messages[idx], feedback: fb }
  })
}

function getPhoneSynth(): SpeechSynthesis | null {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null
  if (!phoneSynth) phoneSynth = window.speechSynthesis
  return phoneSynth
}

function pickDirectSpeakVoice(synth: SpeechSynthesis): SpeechSynthesisVoice | null {
  const voices = synth.getVoices()
  const want = String(personalSettings.value.ttsVoiceName || '').trim()
  if (want) {
    const named = voices.find((v) => v.name === want)
    if (named) return named
  }
  return voices.find((v) => /^zh/i.test(v.lang)) || voices[0] || null
}

function speakMessageBrowser(messageId: string, text: string) {
  const synth = getPhoneSynth()
  if (!synth) {
    directError.value = '当前浏览器不支持语音合成。'
    return
  }
  synth.cancel()
  const u = new SpeechSynthesisUtterance(text)
  const voice = pickDirectSpeakVoice(synth)
  if (voice) u.voice = voice
  const rr = Number(personalSettings.value.ttsRate)
  u.rate = Number.isFinite(rr) ? Math.max(0.6, Math.min(1.6, rr)) : 1
  u.onend = () => {
    if (speakingMessageId.value === messageId) speakingMessageId.value = ''
  }
  u.onerror = () => {
    if (speakingMessageId.value === messageId) speakingMessageId.value = ''
  }
  speakingMessageId.value = messageId
  synth.speak(u)
}

async function speakMessage(messageId: string) {
  if (speakingMessageId.value === messageId) {
    stopDirectTtsPlayback()
    getPhoneSynth()?.cancel()
    speakingMessageId.value = ''
    return
  }
  const m = directMessages.value.find((x) => x.id === messageId)
  if (!m?.content) return

  stopDirectTtsPlayback()
  getPhoneSynth()?.cancel()

  const text = stripInternalMarkers(m.content).slice(0, 1500)

  if (personalSettings.value.ttsEngine === 'edge-online') {
    speakingMessageId.value = messageId
    try {
      const blob = await api.workbenchEdgeTts(
        text,
        personalSettings.value.ttsEdgeVoice || undefined,
        personalSettings.value.ttsRate,
      )
      const url = URL.createObjectURL(blob)
      directTtsObjectUrl = url
      const audio = new Audio(url)
      directTtsAudio = audio
      const done = () => {
        if (speakingMessageId.value === messageId) speakingMessageId.value = ''
        stopDirectTtsPlayback()
      }
      audio.addEventListener('ended', done, { once: true })
      audio.addEventListener(
        'error',
        () => {
          directError.value = '云端朗读播放失败，已尝试本机朗读。'
          done()
          speakMessageBrowser(messageId, text)
        },
        { once: true },
      )
      await audio.play()
    } catch {
      speakingMessageId.value = ''
      stopDirectTtsPlayback()
      directError.value = '云端朗读不可用（需登录且服务端安装 edge-tts），已尝试本机朗读。'
      speakMessageBrowser(messageId, text)
    }
    return
  }

  speakMessageBrowser(messageId, text)
}

function copyConversationLink(c: Conversation) {
  const md = exportConversationAsMarkdown(c)
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${c.title || '对话'}-${c.id.slice(0, 8)}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function newConversationHandler() {
  if (currentStreamHandle) {
    currentStreamHandle.abort()
    currentStreamHandle = null
  }
  directLoading.value = false
  stopDirectTtsPlayback()
  speakingMessageId.value = ''
  editingMessageId.value = ''
  editingDraft.value = ''
  directDraft.value = ''
  directError.value = ''
  directIsDragging.value = false
  directDragDepth.value = 0
  llmDdOpen.value = null
  const files = directAttachedFiles.value.slice()
  directAttachedFiles.value = []
  for (const item of files as Array<{ docId?: string }>) {
    if (item.docId) {
      void api.knowledgeDeleteDocument(item.docId).catch(() => {
        /* 与移除单附件一致：删库失败不阻塞新建 */
      })
    }
  }
  ensureActiveConversation({ forceNew: true })
}

function pickConversation(id: string) {
  if (id === activeConversationId.value) return
  if (currentStreamHandle) currentStreamHandle.abort()
  activeConversationId.value = id
  saveActiveId(id)
}

function pinConversation(id: string) {
  conversations.value = conversations.value.map((c) =>
    c.id === id ? { ...c, pinned: !c.pinned, updatedAt: Date.now() } : c,
  )
  persistConversations()
}

function renameConversation(id: string, title: string) {
  conversations.value = conversations.value.map((c) =>
    c.id === id ? { ...c, title: title.slice(0, 60), updatedAt: Date.now() } : c,
  )
  persistConversations()
}

function exportConversation(id: string) {
  const c = conversations.value.find((x) => x.id === id)
  if (!c) return
  copyConversationLink(c)
}

function removeConversation(id: string) {
  if (!window.confirm('确定删除这个对话？删除后无法恢复。')) return
  conversations.value = conversations.value.filter((c) => c.id !== id)
  if (activeConversationId.value === id) {
    activeConversationId.value = conversations.value[0]?.id || ''
    saveActiveId(activeConversationId.value)
  }
  persistConversations()
}

function clearAllConversations() {
  if (!window.confirm('清空全部对话？此操作不可恢复。')) return
  conversations.value = []
  activeConversationId.value = ''
  saveActiveId('')
  persistConversations()
}

function onComposerPaste(e: ClipboardEvent) {
  const items = e.clipboardData?.items
  if (!items?.length) return
  const images: File[] = []
  for (const it of Array.from(items)) {
    if (it.kind === 'file') {
      const f = it.getAsFile()
      if (f && f.type.startsWith('image/')) images.push(f)
    }
  }
  if (!images.length) return
  e.preventDefault()
  void ingestComposerFiles(images)
}

/** 拖入计数：dragenter/leave 在子元素切换时会成对触发，单纯靠 dragleave 关闭遮罩会闪烁，
 *  改用计数器在所有子元素都 leave 完成后再清零。 */
const directDragDepth = ref(0)

function dragHasFiles(e: DragEvent): boolean {
  const types = e.dataTransfer?.types
  if (!types) return false
  for (let i = 0; i < types.length; i += 1) {
    if (types[i] === 'Files') return true
  }
  return false
}

function onSurfaceDragEnter(e: DragEvent) {
  if (!dragHasFiles(e)) return
  e.preventDefault()
  directDragDepth.value += 1
  directIsDragging.value = true
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
}

function onSurfaceDragOver(e: DragEvent) {
  if (!dragHasFiles(e)) return
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
}

function onSurfaceDragLeave(e: DragEvent) {
  if (!dragHasFiles(e)) return
  directDragDepth.value = Math.max(0, directDragDepth.value - 1)
  if (directDragDepth.value === 0) directIsDragging.value = false
}

function onSurfaceDrop(e: DragEvent) {
  directDragDepth.value = 0
  directIsDragging.value = false
  const list = e.dataTransfer?.files
  if (!list?.length) return
  e.preventDefault()
  void ingestComposerFiles(Array.from(list))
}

async function ingestComposerFiles(files: File[], target: 'direct' | 'make' = 'direct') {
  const remaining = Math.max(0, 12 - directAttachedFiles.value.length)
  const accepted = files.slice(0, remaining)
  const items = accepted.map((file) => {
    const ext = directFileExt(file.name)
    const supported = DIRECT_KB_SUPPORTED_EXT.has(ext)
    const isImage = file.type.startsWith('image/')
    const tooBig = Number(file.size || 0) > DIRECT_KB_MAX_BYTES
    if (isImage) {
      return {
        id: makeDirectAttachId(),
        name: file.name,
        size: file.size || 0,
        status: 'skipped',
        docId: '',
        error: '图片暂以「文件名 + 简短描述」形式给模型；接入视觉模型后会改为 base64 上送。',
        ingesting: false,
        ingestError: '',
        file,
      }
    }
    if (!supported || tooBig) {
      return {
        id: makeDirectAttachId(),
        name: file.name,
        size: file.size || 0,
        status: 'skipped',
        docId: '',
        error: tooBig
          ? `超过 ${formatDirectFileSize(DIRECT_KB_MAX_BYTES)} 上限`
          : `不支持的格式（仅 ${DIRECT_KB_SUPPORTED_EXTENSIONS.join('/')} 入库）`,
        ingesting: false,
        ingestError: '',
        file,
      }
    }
    return {
      id: makeDirectAttachId(),
      name: file.name,
      size: file.size || 0,
      status: 'uploading',
      docId: '',
      error: '',
      ingesting: false,
      ingestError: '',
      file,
    }
  })
  directAttachedFiles.value = [...directAttachedFiles.value, ...items]
  appendAttachmentMentions(accepted, target)
  for (const it of items) {
    if (it.status === 'uploading') void uploadDirectAttachedFile(it)
  }
}

function refreshAllBots() {
  allBots.value = loadAllBots()
}

function onCreateAgent(bot: AgentBot) {
  const my = loadMyBots()
  const next = [{ ...bot, mine: true }, ...my.filter((b) => b.id !== bot.id)]
  saveMyBots(next)
  const fav = loadFavorites()
  fav.add(bot.id)
  saveFavorites(fav)
  refreshAllBots()
}

function onRemoveAgent(bot: AgentBot) {
  if (!bot.mine) return
  if (!window.confirm(`删除我的 Bot「${bot.name}」？`)) return
  const my = loadMyBots().filter((b) => b.id !== bot.id)
  saveMyBots(my)
  const fav = loadFavorites()
  fav.delete(bot.id)
  saveFavorites(fav)
  if (activeBotId.value === bot.id) {
    activeBotId.value = ''
    saveActiveBotId('')
  }
  refreshAllBots()
}

function onFavoriteAgent(bot: AgentBot) {
  const fav = loadFavorites()
  if (fav.has(bot.id)) fav.delete(bot.id)
  else fav.add(bot.id)
  saveFavorites(fav)
  refreshAllBots()
}

function onStartWithAgent(bot: AgentBot) {
  activeBotId.value = bot.id
  saveActiveBotId(bot.id)
  showAgentMarket.value = false
  ensureActiveConversation({ forceNew: true, bot })
}

function clearActiveBot() {
  activeBotId.value = ''
  saveActiveBotId('')
}

function customerServiceQueryContext(): string {
  const q = route.query || {}
  if (String(q.assistant || '') !== 'customer-service') return ''
  const scene = String(q.scene || 'general')
  const parts = [
    '我从市场或导航进入 AI 客服，需要处理以下问题：',
    `场景：${scene}`,
  ]
  const catalogId = String(q.catalog_id || '').trim()
  const pkgId = String(q.pkg_id || '').trim()
  const itemName = String(q.item_name || '').trim()
  const materialCategory = String(q.material_category || '').trim()
  const orderNo = String(q.order_no || '').trim()
  const complaintType = String(q.complaint_type || '').trim()
  if (catalogId) parts.push(`商品 ID：${catalogId}`)
  if (pkgId) parts.push(`包名：${pkgId}`)
  if (itemName) parts.push(`商品名称：${itemName}`)
  if (materialCategory) parts.push(`市场类目：${materialCategory}`)
  if (orderNo) parts.push(`订单号：${orderNo}`)
  if (complaintType) parts.push(`问题类型：${complaintType}`)
  parts.push('请先告诉我还需要补充哪些证据材料，并给出下一步处理路径。')
  return parts.join('\n')
}

function stripCustomerServiceEntryQueryFromUrl() {
  const q = { ...(route.query as Record<string, string | string[] | undefined>) }
  const keys = [
    'assistant',
    'scene',
    'catalog_id',
    'pkg_id',
    'item_name',
    'material_category',
    'order_no',
    'complaint_type',
  ]
  let changed = false
  for (const k of keys) {
    if (Object.prototype.hasOwnProperty.call(q, k)) {
      delete q[k]
      changed = true
    }
  }
  if (!changed) return
  void router.replace({ path: route.path, query: q })
}

/** 避免 keep-alive 下 onMounted 与 onActivated 同一帧各跑一次，重复 forceNew 会话 */
let lastAppliedCustomerServiceQueryKey = ''

function applyCustomerServiceRouteContext() {
  if (String(route.query?.assistant || '') !== 'customer-service') return
  const bot = allBots.value.find((b) => b.id === 'customer-service')
  if (!bot) return
  const dedupeKey = JSON.stringify(route.query)
  if (dedupeKey === lastAppliedCustomerServiceQueryKey) return
  lastAppliedCustomerServiceQueryKey = dedupeKey
  activeBotId.value = bot.id
  saveActiveBotId(bot.id)
  const ctx = customerServiceQueryContext()
  const conv = ensureActiveConversation({ forceNew: true, bot })
  if (ctx) {
    conv.messages.push(makeMessage('user', ctx, { agentLabel: bot.name }))
    conv.messages.push(makeMessage('assistant', '我已收到这些上下文。请继续补充证据截图、链接、订单号或你希望平台采取的处理结果；如果信息已完整，我会帮你整理成可提交给管理员的工单摘要。', { agentLabel: bot.name }))
    persistConversations()
  }
  stripCustomerServiceEntryQueryFromUrl()
}

const directFontPxStyle = computed(() => ({
  '--wb-direct-font-px': `${personalSettings.value.fontPx}px`,
}))

const mediaGenRunner = {
  async generateImages(prompt: string, opts: { size: string; style: string; count: number }) {
    const safePrompt = prompt.slice(0, 240)
    const styled = opts.style && opts.style !== 'default' ? `${opts.style} 风格，` : ''
    try {
      const { provider, model } = await resolveChatProviderModel()
      const imageModel = /image|dall|gpt-image|sdxl|flux|wanx|jimeng|seedream/i.test(model)
        ? model
        : provider === 'openai'
        ? 'gpt-image-1'
        : model
      const res = await api.llmGenerateImage(provider, imageModel, `${styled}${safePrompt}`, {
        size: opts.size,
        count: opts.count,
      })
      const urls = Array.isArray(res?.images) ? res.images.filter(Boolean) : []
      if (urls.length) return urls
    } catch {
      // 未配置真实生图模型时保留占位图回退，避免打断创作流程。
    }
    const items: string[] = []
    for (let i = 0; i < Math.max(1, Math.min(4, opts.count)); i += 1) {
      const seed = `${safePrompt}-${opts.size}-${i}`
      const url = `https://picsum.photos/seed/${encodeURIComponent(seed)}/${opts.size.replace('x', '/')}`
      items.push(url)
    }
    return items
  },
  async generatePptOutline(topic: string, audience: string, pages: number) {
    const { provider, model } = await resolveChatProviderModel()
    const sys = '你是高级 PPT 大纲编写者。为给定主题生成精炼的 markdown 大纲：每页用 ## 标题，下方 3-5 个要点（- 开头），并附 1 行口播说明。控制在指定页数内。'
    const usr = `主题：${topic}\n受众/风格：${audience || '通用商务'}\n页数：${pages}\n请直接输出 markdown 大纲。`
    const res = await api.llmChat(provider, model, [
      { role: 'system', content: sys },
      { role: 'user', content: usr },
    ], 1800)
    return String(res?.content || '').trim() || '（无输出）'
  },
  async generatePptx(topic: string, markdown: string) {
    return await api.llmGeneratePptxBlob(topic, markdown, `${topic.slice(0, 32) || 'ai-presentation'}.pptx`)
  },
  async generateDocument(kind: string, inputs: string) {
    const { provider, model } = await resolveChatProviderModel()
    const kindMap: Record<string, string> = {
      weekly: '周报',
      proposal: '商业方案/提案',
      article: '公众号文章',
      redbook: '小红书种草文案',
      email: '商务邮件',
    }
    const sys = `你是擅长写「${kindMap[kind] || kind}」的中文写手。结构清晰、节奏流畅、有重点；输出 markdown，必要时用列表与小标题。不要套话，先抓重点。`
    const usr = `信息素材：${inputs}\n请直接输出成稿。`
    const res = await api.llmChat(provider, model, [
      { role: 'system', content: sys },
      { role: 'user', content: usr },
    ], 2200)
    return String(res?.content || '').trim() || '（无输出）'
  },
}

function insertGeneratedToChat(text: string) {
  if (!text) return
  ensureActiveConversation()
  const m = makeMessage('assistant', text, {
    agentLabel: 'AI 创作',
  })
  patchActiveConversation((c) => c.messages.push(m))
  showMediaGen.value = false
}

async function handleVoicePhoneTurn(userText: string): Promise<string> {
  ensureActiveConversation()
  const userMsg = makeMessage('user', userText, { agentLabel: '语音电话' })
  const placeholder = makeMessage('assistant', '', { pending: true })
  appendUserAndAssistant(userMsg, placeholder)
  await runDirectChatTurn({ assistantId: placeholder.id, userText })
  const m = directMessages.value.find((x) => x.id === placeholder.id)
  return stripInternalMarkers(m?.content || '')
}

function onDirectKeydown(e) {
  if (e.key !== 'Enter' || e.shiftKey) return
  e.preventDefault()
  void sendDirectChat()
}

function createSpeechRecognition() {
  const w = window as any
  const Ctor = w?.SpeechRecognition || w?.webkitSpeechRecognition
  if (!Ctor) return null
  const rec = new Ctor()
  rec.lang = 'zh-CN'
  rec.interimResults = true
  rec.continuous = false
  return rec
}

function toggleVoiceListening() {
  if (voiceListening.value) {
    stopVoiceRecognition()
    return
  }
  startVoiceRecognition()
}

function startVoiceRecognition() {
  voiceError.value = ''
  const rec = createSpeechRecognition()
  if (!rec) {
    voiceError.value = '当前浏览器不支持语音输入，可用下方文字补充。'
    return
  }
  voiceRecognition = rec
  pendingVoiceTranscript = ''
  voiceTranscript.value = ''
  voiceListening.value = true
  voiceState.value = 'listening'
  rec.onresult = (event) => {
    let text = ''
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      text += event.results[i][0]?.transcript || ''
    }
    const trimmed = text.trim()
    const finalSeg = event.results[event.results.length - 1]
    if (finalSeg?.isFinal) {
      if (voiceTranscriptRaf) {
        cancelAnimationFrame(voiceTranscriptRaf)
        voiceTranscriptRaf = 0
      }
      voiceTranscript.value = trimmed
      if (voiceTranscript.value) voiceDraft.value = voiceTranscript.value
      return
    }
    pendingVoiceTranscript = trimmed
    if (voiceTranscriptRaf) return
    voiceTranscriptRaf = requestAnimationFrame(() => {
      voiceTranscriptRaf = 0
      voiceTranscript.value = pendingVoiceTranscript
    })
  }
  rec.onerror = (event) => {
    if (voiceTranscriptRaf) {
      cancelAnimationFrame(voiceTranscriptRaf)
      voiceTranscriptRaf = 0
    }
    voiceError.value = event?.error ? `语音识别失败：${event.error}` : '语音识别失败'
    voiceListening.value = false
    voiceState.value = 'idle'
  }
  rec.onend = () => {
    voiceListening.value = false
    if (voiceDraft.value.trim()) {
      void submitVoiceTurn()
    } else if (voiceState.value === 'listening') {
      voiceState.value = 'idle'
    }
  }
  try {
    rec.start()
  } catch (e) {
    voiceError.value = e?.message || String(e)
    voiceListening.value = false
    voiceState.value = 'idle'
  }
}

function stopVoiceRecognition() {
  if (voiceTranscriptRaf) {
    cancelAnimationFrame(voiceTranscriptRaf)
    voiceTranscriptRaf = 0
  }
  try {
    voiceRecognition?.stop?.()
  } catch {
    /* ignore */
  }
  voiceListening.value = false
}

async function submitVoiceTurn() {
  const content = voiceDraft.value.trim()
  if (!content || voiceBusy.value) return
  if (!requireLoginForWorkbenchUse()) return
  voiceDraft.value = ''
  voiceError.value = ''
  voiceBusy.value = true
  voiceState.value = 'thinking'
  voiceMessages.value = [...voiceMessages.value, { role: 'user', content }]
  try {
    const { provider, model } = await resolveChatProviderModel()
    const msgs = [
      {
        role: 'system',
        content:
          '你是 Jarvis 风格的中文语音需求规划助手。你的目标是通过追问、整理和总结，把用户口述内容变成可制作 Mod、员工或工作流的需求。回复要短，先总结已知，再问 1-2 个最关键问题；如果足够清楚，给出“可确认制作”的摘要。',
      },
      ...voiceMessages.value.map((m) => ({ role: m.role, content: m.content })),
    ]
    const res = await api.llmChat(provider, model, msgs, 2048)
    const reply = String(res?.content || '').trim() || '我已记录，请继续补充。'
    voiceMessages.value = [...voiceMessages.value, { role: 'assistant', content: reply }]
    voiceState.value = 'summary'
  } catch (e) {
    voiceError.value = e?.message || String(e)
    voiceState.value = 'idle'
  } finally {
    voiceBusy.value = false
  }
}

function confirmVoiceAndOpenHandoff() {
  if (!voiceMessages.value.length) return
  const text = formatPlanMessagesForBrief(voiceMessages.value)
  const intentKey = composerIntent.value
  pendingHandoff.value = {
    description: `【语音规划记录】\n${text}`,
    intentTitle: intentMeta.value.title,
    intentKey,
    workflowName: '',
    planNotes: isCanvasSkillIntent(intentKey) ? text : '',
    suggestedModId: intentKey === 'mod' ? suggestModIdFromText(text) : '',
    generateFrontend: intentKey === 'mod' ? modFrontendEnabled.value : false,
    employeeTarget: intentKey === 'employee' ? 'pack_plus_workflow' : 'pack_only',
    employeeWorkflowName: '',
    fhdBaseUrl: '',
  }
  activeGear.value = 'make'
  nextTick(() => {
    const el = handoffPanelRef.value
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}

function requireLoginForWorkbenchUse() {
  if (getAccessToken()) return true
  const text = draft.value.trim()
  try {
    if (text) sessionStorage.setItem('workbench_home_pending_draft', text)
    sessionStorage.setItem('workbench_home_pending_intent', composerIntent.value)
  } catch {
    /* ignore */
  }
  void router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath || '/' } })
  return false
}

const llmCatalog = ref(null)
const llmCatalogLoading = ref(false)
const llmCatalogError = ref('')
const selectedProvider = ref('openai')
const selectedModel = ref('')
/** auto：发送时用账户 preferences；manual：用下方自选并写回 preferences */
const modelMode = ref('auto')
/** 自选时厂商/模型自定义下拉：'provider' | 'model' | null（避免原生 select 白底弹层） */
const llmDdOpen = ref(null)

const _canvasSkillMeta = {
  title: '生成 Skill 组',
  sub: '按描述生成可复用 Skill，并在画布上编排成 Skill 组（调度图）。要「可运行程序本体」请走脚本工作流。',
}
const INTENT_META = {
  mod: {
    title: '做 Mod',
    sub: '可先生成仓库与名片骨架，也可以继续补齐员工包登记、工作流绑定和真实执行验证。只有名片不等于可工作的员工。',
  },
  employee: {
    title: '做员工',
    sub: '提示词与工具 · 在下方用自然语言描述岗位与流程',
  },
  skill: _canvasSkillMeta,
  /** @deprecated 会话缓存旧键，等同于 skill */
  workflow: _canvasSkillMeta,
}

const intentMeta = computed(() => INTENT_META[composerIntent.value] || INTENT_META.skill)

const intentRepoPickShow = computed(() => {
  if (!hasWorkflow.value || planSession.value) return false
  return composerIntent.value === 'employee' || composerIntent.value === 'mod'
})

/** Mod/employee：可收起侧栏说明，仅保留仓库跳转区 */
const intentGuideCollapsed = ref(true)

const showIntentGuide = computed(() => !intentRepoPickShow.value || !intentGuideCollapsed.value)

const catalogEmployeeRows = ref([])
const catalogModRows = ref([])
const pickEmployeeKey = ref('')
const pickModId = ref('')

const catalogEmployeesForPick = computed(() => catalogEmployeeRows.value)

const catalogModsForPick = computed(() =>
  (catalogModRows.value || []).map((r) => ({
    id: r.id,
    label: `${r.id}${r.manifest?.name ? ` · ${r.manifest.name}` : ''}`,
  })),
)

const pickedEmployeeRow = computed(() => {
  const k = (pickEmployeeKey.value || '').trim()
  if (!k) return null
  return catalogEmployeeRows.value.find((r) => r.k === k) || null
})

const pickedModRow = computed(() => {
  const id = (pickModId.value || '').trim()
  if (!id) return null
  return (catalogModRows.value || []).find((r) => String(r.id) === id) || null
})

const pickedModManifestVersion = computed(() => {
  const v = pickedModRow.value?.manifest?.version
  return typeof v === 'string' && v.trim() ? v.trim() : '?'
})

const pickedModManifestName = computed(() => {
  const n = pickedModRow.value?.manifest?.name
  return typeof n === 'string' && n.trim() ? n.trim() : ''
})

const pickedModManifestDescription = computed(() => {
  const d = pickedModRow.value?.manifest?.description
  return typeof d === 'string' ? d : ''
})

function truncateWorkbenchText(text, max = 280) {
  const s = typeof text === 'string' ? text.replace(/\s+/g, ' ').trim() : ''
  if (!s) return ''
  return s.length <= max ? s : `${s.slice(0, max)}…`
}

function releaseChannelLabel(ch) {
  const x = String(ch || 'stable').toLowerCase()
  return x === 'draft' ? '测试通道' : '正式通道'
}

async function loadDirectEmployeeOptions() {
  directEmployeeOptions.value = []
  if (!localStorage.getItem('modstore_token')) return
  const merged = new Map<string, DirectEmployeeOption>()
  try {
    const sqlRows = await api.listEmployees()
    for (const e of Array.isArray(sqlRows) ? sqlRows : []) {
      const id = String((e as { id?: unknown })?.id ?? '').trim()
      if (!id) continue
      const name = String((e as { name?: unknown })?.name ?? id).trim() || id
      merged.set(id, { id, name, sourceLabel: '执行器' })
    }
  } catch {
    /* ignore */
  }
  try {
    const r = await api.listV1Packages('employee_pack', '', 120, 0)
    for (const p of r?.packages || []) {
      const id = String((p as { id?: unknown })?.id ?? '').trim()
      if (!id) continue
      const pkgName = String((p as { name?: unknown })?.name ?? id).trim() || id
      const existing = merged.get(id)
      if (existing) {
        const sl = existing.sourceLabel
        existing.sourceLabel = sl.includes('目录') ? sl : `${sl}·目录`
        if (pkgName && pkgName !== existing.name) existing.name = `${existing.name}（${pkgName}）`
        continue
      }
      merged.set(id, { id, name: pkgName, sourceLabel: '本地包' })
    }
  } catch {
    /* ignore */
  }
  directEmployeeOptions.value = [...merged.values()].sort((a, b) =>
    String(a.name).localeCompare(String(b.name), 'zh-CN'),
  )
  const cur = String(directChatEmployeeId.value || '').trim()
  if (cur && !merged.has(cur)) {
    directChatEmployeeId.value = ''
    try {
      sessionStorage.removeItem(WB_DIRECT_CHAT_EMPLOYEE_ID_KEY)
    } catch {
      /* ignore */
    }
  }
}

async function loadWorkbenchRepoPicks() {
  catalogEmployeeRows.value = []
  catalogModRows.value = []
  if (!localStorage.getItem('modstore_token')) return
  try {
    const r = await api.listV1Packages('employee_pack', '', 80, 0)
    const rows = []
    for (const p of r.packages || []) {
      const id = String(p.id || '').trim()
      const ver = String(p.version || '').trim()
      if (!id || !ver) continue
      const ch = String(p.release_channel || 'stable').toLowerCase()
      const displayName = String(p.name || id).trim() || id
      const description = typeof p.description === 'string' ? p.description : ''
      const industry = typeof p.industry === 'string' && p.industry.trim() ? p.industry.trim() : ''
      const artifact = String(p.artifact || 'employee_pack').toLowerCase()
      const probe = typeof p.probe_mod_id === 'string' && p.probe_mod_id.trim() ? p.probe_mod_id.trim() : ''
      rows.push({
        k: `${id}@${ver}`,
        id,
        ver,
        displayName,
        label: `${p.name || id} · ${ver}${ch === 'draft' ? '（测试）' : ''}`,
        description,
        industry,
        artifact,
        release_channel: ch,
        probe_mod_id: probe,
      })
    }
    catalogEmployeeRows.value = rows
  } catch {
    catalogEmployeeRows.value = []
  }
  try {
    const m = await api.listMods()
    catalogModRows.value = Array.isArray(m?.data) ? m.data : []
  } catch {
    catalogModRows.value = []
  }
  await loadDirectEmployeeOptions()
}

function goEditEmployeeFromPick() {
  if (!requireLoginForWorkbenchUse()) return
  const v = pickEmployeeKey.value
  if (!v) return
  const at = v.lastIndexOf('@')
  if (at <= 0) return
  const id = v.slice(0, at)
  const ver = v.slice(at + 1)
  router.push({ name: 'workbench-employee', query: { edit_pkg: id, edit_ver: ver } })
}

function goEditModFromPick() {
  if (!requireLoginForWorkbenchUse()) return
  const id = (pickModId.value || '').trim()
  if (!id) return
  router.push({ name: 'mod-authoring', params: { modId: id }, query: { mode: 'edit' } })
}

watch(composerIntent, () => {
  pickEmployeeKey.value = ''
  pickModId.value = ''
})

/** 侧栏与输入脚「当前」主标题：{name} Skill 组 / Mod / AI 员工 */
const composerMainTitle = computed(() => {
  if (workflowLinkOffer.value?.workflowName) {
    return `${workflowLinkOffer.value.workflowName} Skill 组`
  }
  const ph = pendingHandoff.value
  if (isCanvasSkillIntent(ph?.intentKey)) {
    const n = (ph.workflowName || '').trim()
    if (n) return `${n} Skill 组`
  }
  if (ph?.intentKey === 'mod') {
    const n = (ph.suggestedModId || '').trim()
    if (n) return `${n} Mod`
  }
  if (ph?.intentKey === 'employee') {
    const d = (ph.description || '').trim().split('\n')[0].trim().slice(0, 36)
    if (d) return `${d} AI 员工`
  }
  const k = composerIntent.value
  if (k === 'mod') return '做 Mod'
  if (k === 'employee') return '做员工'
  return '生成 Skill 组'
})

const handoffDescLabel = computed(() => {
  const k = pendingHandoff.value?.intentKey
  if (k === 'mod') return 'Mod 需求描述'
  if (k === 'employee') return '员工能力描述'
  return 'Skill 组描述'
})

const orchestrationButtonLabel = computed(() => {
  const k = pendingHandoff.value?.intentKey
  if (k === 'mod') return '开始生成 Mod'
  if (k === 'employee') return '开始生成员工包'
  const files = pendingHandoff.value?.files
  if (isCanvasSkillIntent(k) && Array.isArray(files) && files.length > 0) {
    return '开始处理附件（AI 生成 Python 脚本）'
  }
  if (isCanvasSkillIntent(k)) return '开始生成 Skill 组并校验'
  return '开始创建并校验'
})

const orchestrationButtonPendingLabel = computed(() => {
  if (!finalizeLoading.value) return orchestrationButtonLabel.value
  if (orchPhase.value === 'estimating') return '估算用时…'
  return '执行中…'
})

const makeHasActiveTask = computed(() =>
  Boolean(
    planSession.value ||
      pendingHandoff.value ||
      workflowLinkOffer.value ||
      finalizeLoading.value ||
      orchestrationSession.value?.steps?.length,
  ),
)

const makeComposerRows = computed(() => {
  if (planSession.value?.phase === 'chat') return 2
  return makeHasActiveTask.value ? 1 : 4
})

const orchestrationProgress = computed(() => {
  const steps = Array.isArray(orchestrationSession.value?.steps) ? orchestrationSession.value.steps : []
  const total = Math.max(steps.length, 1)
  const done = steps.filter((s) => s.status === 'done').length
  const running = steps.some((s) => s.status === 'running') ? 0.45 : 0
  const percent = Math.min(100, Math.max(0, ((done + running) / total) * 100))
  return { total: steps.length, done, percent }
})

/** 制作草稿执行中：紧邻按钮的可读状态，避免只看到「执行中…」误以为卡住 */
const handoffRunStatusLine = computed(() => {
  if (!finalizeLoading.value) return ''
  const s = orchestrationSession.value
  const steps = Array.isArray(s?.steps) ? s.steps : []
  const running = steps.find((x: { status?: string }) => x.status === 'running')
  if (running) {
    const lab = String(running.label || '编排').trim() || '编排'
    const msg = typeof running.message === 'string' && running.message.trim() ? ` — ${running.message.trim()}` : ''
    const sec = orchStepRunningSec(running)
    const elapsed = sec !== null && sec >= 5 ? `（已运行 ${formatWallClockSec(sec)}）` : ''
    return `进行中：${lab}${msg}${elapsed}`
  }
  if (steps.length) {
    const done = steps.filter((x: { status?: string }) => x.status === 'done').length
    const next = steps.find((x: { status?: string }) => x.status === 'pending')
    if (next && done < steps.length) {
      const nl = String(next.label || '下一步').trim() || '下一步'
      return `排队中：${nl}（已完成 ${done}/${steps.length}）`
    }
    return `编排进度：${done}/${steps.length} 步`
  }
  const st = typeof s?.status === 'string' ? s.status.trim() : ''
  if (st && st !== 'done' && st !== 'error') return `编排状态：${st}`
  return '已提交，正在连接编排服务并拉取步骤…'
})

function formatWallClockSec(sec) {
  const s = Math.max(0, Math.floor(Number(sec) || 0))
  const m = Math.floor(s / 60)
  const r = s % 60
  if (m >= 60) {
    const h = Math.floor(m / 60)
    const mm = m % 60
    return `${h}:${String(mm).padStart(2, '0')}:${String(r).padStart(2, '0')}`
  }
  if (m === 0) return `${r}秒`
  return `${m}分${String(r).padStart(2, '0')}秒`
}

function stopOrchestrationElapsedTicker() {
  if (orchElapsedTimer != null) {
    clearInterval(orchElapsedTimer)
    orchElapsedTimer = null
  }
}

function startOrchestrationElapsedTicker() {
  stopOrchestrationElapsedTicker()
  orchElapsedTick.value = 0
  orchElapsedTimer = setInterval(() => {
    orchElapsedTick.value += 1
  }, 500)
}

const ORCH_ESTIMATE_SYSTEM = [
  '你是「工作台异步编排」的 wall-clock 耗时估算助手。用户即将启动一次服务端多步任务（可能含多次 LLM、写盘、工作流/沙箱等）。',
  '请只根据 intent、需求摘要与清单规模，推断从「开始执行」到「全部完成」的总秒数；不得照抄示例数字，须结合复杂度自行推理。',
  '只输出一个 JSON 对象，不要用 markdown 代码围栏，不要其它文字。',
  '字段：estimated_seconds（整数，通常 120～3600，极端不超过 7200），confidence（"low"|"medium"|"high"），one_line_reason（一句中文，≤80 字）。',
].join('')

function parseOrchestrationEtaFromLlmText(text) {
  let s = String(text || '').trim()
  if (!s) return { seconds: null, reason: '' }
  if (s.startsWith('```')) {
    s = s.replace(/^```(?:json)?\s*/i, '').replace(/\s*```\s*$/i, '').trim()
  }
  const start = s.indexOf('{')
  const end = s.lastIndexOf('}')
  if (start < 0 || end <= start) return { seconds: null, reason: '' }
  try {
    const o = JSON.parse(s.slice(start, end + 1))
    const n = Number(o.estimated_seconds)
    if (!Number.isFinite(n)) return { seconds: null, reason: String(o.one_line_reason || '').trim().slice(0, 120) }
    const sec = Math.round(Math.max(30, Math.min(n, 7200)))
    return {
      seconds: sec,
      reason: String(o.one_line_reason || '').trim().slice(0, 120),
    }
  } catch {
    return { seconds: null, reason: '' }
  }
}

/** 模型未返回 estimated_seconds 时，用清单规模与意图粗估总秒数，避免「预计 —」不可读 */
function fallbackOrchestrationSecondsEstimate(ctx: {
  intent: string
  checklistLen: number
  generateFrontend?: boolean
  employeeTarget?: string
  scriptFileCount?: number
}): number {
  let n = 150
  const cl = Math.max(0, Math.floor(Number(ctx.checklistLen) || 0))
  n += cl * 95
  const intent = String(ctx.intent || CANVAS_SKILL_INTENT)
  if (intent === 'mod') {
    n += 260
    if (ctx.generateFrontend) n += 480
  } else if (intent === 'employee') {
    n += 320
    if (String(ctx.employeeTarget || '').includes('pack_plus')) n += 260
  } else {
    n += 200
  }
  const sf = Math.max(0, Math.floor(Number(ctx.scriptFileCount) || 0))
  n += sf * 160
  return Math.round(Math.min(7200, Math.max(120, n)))
}

async function estimateOrchestrationSeconds(ctx) {
  try {
    const { provider, model } = await resolveChatProviderModel()
    const lines = [
      `intent=${ctx.intent}`,
      `execution_checklist 条数=${ctx.checklistLen}`,
      ctx.intent === 'mod' ? `generate_frontend=${ctx.generateFrontend}` : '',
      ctx.intent === 'employee' ? `employee_target=${ctx.employeeTarget || ''}` : '',
      typeof ctx.scriptFileCount === 'number' && ctx.scriptFileCount > 0
        ? `script_workflow 附件数=${ctx.scriptFileCount}`
        : '',
      '--- 需求摘要（截断） ---',
      ctx.brief.slice(0, 3500),
    ].filter(Boolean)
    const res = await api.llmChat(provider, model, [
      { role: 'system', content: ORCH_ESTIMATE_SYSTEM },
      { role: 'user', content: lines.join('\n') },
    ], 256)
    return parseOrchestrationEtaFromLlmText(res?.content)
  } catch {
    return { seconds: null, reason: '' }
  }
}

const orchestrationEtaDisplay = computed(() => {
  if (!finalizeLoading.value) return '—'
  if (orchPhase.value === 'estimating') return '模型推算中…'
  orchElapsedTick.value
  let sec = orchestrationEtaSeconds.value
  const h = pendingHandoff.value
  if ((sec == null || !Number.isFinite(sec)) && orchPhase.value === 'running' && h) {
    const scriptFiles = isCanvasSkillIntent(h.intentKey) && Array.isArray(h.files) ? h.files : []
    sec = fallbackOrchestrationSecondsEstimate({
      intent: String(h.intentKey || CANVAS_SKILL_INTENT),
      checklistLen: Array.isArray(h.executionChecklist) ? h.executionChecklist.length : 0,
      generateFrontend: h.intentKey === 'mod' ? modFrontendEnabled.value : false,
      employeeTarget: h.intentKey === 'employee' ? String(h.employeeTarget || '').trim() : '',
      scriptFileCount: scriptFiles.length,
    })
  }
  if (sec == null || !Number.isFinite(sec)) {
    return orchestrationEtaReason.value
      ? `未算出数值（${orchestrationEtaReason.value}）`
      : '未算出数值'
  }
  const totalLabel = `总估约 ${formatWallClockSec(sec)}`
  const t0 = orchTimingStartMs.value
  if (t0 == null) return `${totalLabel}（即将计时）`
  const elapsed = (Date.now() - t0) / 1000
  const rem = sec - elapsed
  if (rem >= 20) return `${totalLabel} · 剩余约 ${formatWallClockSec(rem)}`
  if (rem >= 0) return `${totalLabel} · 收尾中`
  return `${totalLabel} · 已超过估算，仍在执行`
})

const orchestrationTimingTooltip = computed(() => {
  if (!finalizeLoading.value) return ''
  const r = String(orchestrationEtaReason.value || '').trim()
  return r || '总时长为模型推算或按步骤量粗估；剩余时间按总估与已用时间相减。'
})

const orchestrationElapsedDisplay = computed(() => {
  orchElapsedTick.value
  if (!finalizeLoading.value) return '—'
  if (orchPhase.value === 'estimating') return '—'
  const t0 = orchTimingStartMs.value
  if (t0 == null) return '—'
  return formatWallClockSec((Date.now() - t0) / 1000)
})

const canRunOrchestration = computed(() => {
  const h = pendingHandoff.value
  if (!h?.description?.trim()) return false
  if (isCanvasSkillIntent(h.intentKey)) return Boolean(h.workflowName?.trim())
  return true
})

const handoffFootNote = computed(() => {
  const k = pendingHandoff.value?.intentKey
  if (k === 'mod') {
    return '生成成功后进入 Mod 制作页。页面会区分“名片已生成”和“员工可工作”：未登记员工包、未绑定工作流或未真实执行都会列为缺口。'
  }
  if (k === 'employee') {
    return '员工包写入你的本地库；上架请到「员工制作」上传。商店执行器以已上架包为准。'
  }
  if (Array.isArray(pendingHandoff.value?.files) && pendingHandoff.value.files.length > 0) {
    return '已选择附件：将生成可复用的「脚本工作流」，成功后自动进入沙箱调试页；你可以继续上传同类 Excel 文件验证脚本输出。若要生成节点与连线的流程图，请先移除附件再提交。'
  }
  return '创建并校验成功后进入画布编辑 Skill 组；尚无节点时跳过拓扑沙盒。'
})

const hasRepo = computed(() => router.hasRoute('workbench-repository'))
const hasWorkflow = computed(() => router.hasRoute('workbench-workflow'))
/** Teleport 到 body；keep-alive 下切到统一工作台等路由时首页仍缓存，需按当前路由隐藏 FAB */
const showDirectTierFab = computed(() => {
  if (!hasWorkflow.value) return false
  const n = String(route.name || '')
  return n === 'home' || n === 'workbench-home'
})
const hasScriptWorkflowRoute = computed(() => router.hasRoute('script-workflow-new'))
const hasEmployee = computed(() => router.hasRoute('workbench-employee'))
const hasPlans = computed(() => router.hasRoute('plans'))

/** 一档有聊天记录时默认锁定挡位切换，需用户显式解锁（同一会话内保持） */
const gearNavUserUnlocked = ref(false)
const gearNavHardLocked = computed(
  () => Boolean(hasWorkflow.value && directMessages.value.length && !gearNavUserUnlocked.value),
)

function unlockGearNav() {
  gearNavUserUnlocked.value = true
}

watch(activeConversationId, () => {
  gearNavUserUnlocked.value = false
})

watch(
  () => directMessages.value.length,
  (len, prev) => {
    if (!len) {
      gearNavUserUnlocked.value = false
      return
    }
    /* 从「无消息」到「有消息」时强制重新解锁；避免空会话里提前点解锁绕过 */
    if (!prev) gearNavUserUnlocked.value = false
  },
)

const greetingLine = computed(() => {
  const n = displayName.value.trim()
  if (!n) return ''
  return `你好，${n}`
})

const placeholder = computed(() => {
  if (composerIntent.value === 'mod') {
    return '例如：行业「物流」、新建仓库 my-track；先生成 Mod 骨架，再把「路由调度员」登记成 employee_pack，绑定工作流，并用非 Mock 沙盒跑通一次…'
  }
  if (composerIntent.value === 'employee') {
    return '例如：岗位负责核对发票金额与税号，输出结构化结果给财务系统…'
  }
  return '例如：每天把 Excel 出货单里的品名和数量同步到仓库表…'
})

/** 「做」模式主输入：无规划或与助手对话时合并到底栏，避免双文本框 */
const makeComposerInput = computed({
  get() {
    if (planSession.value?.phase === 'chat') return planReplyDraft.value
    return draft.value
  },
  set(v: string) {
    if (planSession.value?.phase === 'chat') {
      planReplyDraft.value = v
    } else {
      draft.value = v
    }
  },
})

const makeComposerInputLabel = computed(() =>
  planSession.value?.phase === 'chat' ? '补充或追问' : '描述想法',
)

const makeComposerPlaceholder = computed(() =>
  planSession.value?.phase === 'chat'
    ? '自由补充…（Enter 发送，Shift+Enter 换行）'
    : placeholder.value,
)

const composerSendDisabled = computed(() => {
  if (knowledgeUploading.value) return true
  const ps = planSession.value
  if (ps?.phase === 'chat') {
    return ps.loading || !String(planReplyDraft.value || '').trim()
  }
  if (ps) return true
  if (!hasWorkflow.value) return true
  const text = String(draft.value || '').trim()
  const uploading = directAttachedFiles.value.some((f: any) => f.status === 'uploading')
  if (uploading) return true
  return !text && !directAttachedFiles.value.length
})

const currentLlmBlock = computed(() => {
  if (!llmCatalog.value?.providers) return null
  return llmCatalog.value.providers.find((p) => p.provider === selectedProvider.value) || null
})

const currentProviderLabel = computed(() => {
  const list = llmCatalog.value?.providers
  if (!Array.isArray(list)) return '厂商'
  const b = list.find((p) => p.provider === selectedProvider.value)
  const lab = typeof b?.label === 'string' ? b.label.trim() : ''
  const id = typeof b?.provider === 'string' ? b.provider.trim() : ''
  return lab || id || '厂商'
})

const modelPickerEnabled = computed(() => {
  const block = currentLlmBlock.value
  return Boolean(block && Array.isArray(block.models) && block.models.length)
})

function categoryLabel(cat) {
  return llmCatalog.value?.category_labels?.[cat] || cat
}

function modelsForWorkbenchCategory(cat) {
  const block = currentLlmBlock.value
  const detailed = block?.models_detailed
  if (detailed && detailed.length) {
    return detailed.filter((r) => r.category === cat)
  }
  if (cat === 'llm' && block?.models?.length) {
    return block.models.map((id) => ({ id, category: 'llm' }))
  }
  return []
}

function syncManualSelectionFromPreferences() {
  const res = llmCatalog.value
  if (!res?.providers?.length) return
  const pref = res.preferences || {}
  let p = pref.provider || 'openai'
  if (!res.providers.some((x) => x.provider === p)) {
    p = res.providers[0]?.provider || 'openai'
  }
  selectedProvider.value = p
  const block = res.providers.find((x) => x.provider === p)
  const mids = block?.models || []
  let m = pref.model || ''
  if (!m || !mids.includes(m)) m = mids[0] || ''
  selectedModel.value = m
}

async function loadLlmCatalogForWorkbench() {
  if (!localStorage.getItem('modstore_token')) return
  llmCatalogLoading.value = true
  llmCatalogError.value = ''
  try {
    const res = await api.llmCatalog(false)
    llmCatalog.value = res
    syncManualSelectionFromPreferences()
  } catch (e) {
    llmCatalog.value = null
    llmCatalogError.value = e.message || String(e)
  } finally {
    llmCatalogLoading.value = false
  }
}

watch(modelMode, (mode) => {
  llmDdOpen.value = null
  if (mode === 'manual') syncManualSelectionFromPreferences()
})

function onWorkbenchProviderChange() {
  const block = currentLlmBlock.value
  const mids = block?.models || []
  selectedModel.value = mids[0] || ''
}

function toggleLlmDd(which) {
  llmDdOpen.value = llmDdOpen.value === which ? null : which
}

function pickProvider(p) {
  if (typeof p !== 'string' || !p) return
  selectedProvider.value = p
  onWorkbenchProviderChange()
  llmDdOpen.value = null
}

function pickModel(id) {
  if (typeof id !== 'string' || !id) return
  selectedModel.value = id
  llmDdOpen.value = null
}

function onLlmDocPointerDown(ev) {
  if (!llmDdOpen.value) return
  const t = ev.target
  if (t && typeof t.closest === 'function' && t.closest('.wb-llm-dd')) return
  llmDdOpen.value = null
}

function onLlmEscape(ev) {
  if (ev.key === 'Escape') llmDdOpen.value = null
}

function orchStepClass(st) {
  return {
    'wb-step--done': st.status === 'done',
    'wb-step--running': st.status === 'running',
    'wb-step--error': st.status === 'error',
    'wb-step--pending': st.status === 'pending',
  }
}

/** 返回某步骤已运行的秒数（仅 running 状态 + 有 started_at 时），null 表示不展示。
 *  orchElapsedTick 作为响应式依赖使其每 0.5 秒刷新一次。*/
function orchStepRunningSec(st) {
  orchElapsedTick.value // 依赖订阅，使每次 tick 重新计算
  if (st.status !== 'running' || !st.started_at) return null
  const t0 = new Date(st.started_at).getTime()
  if (!Number.isFinite(t0)) return null
  return Math.max(0, Math.floor((Date.now() - t0) / 1000))
}

/** 跟踪各步骤最近一次 message 变化时间，用于「响应较慢」提示（B3）。*/
const _stepLastMsgChange: Record<string, { msg: string; ts: number }> = {}

function orchStepSlowHint(st) {
  orchElapsedTick.value // 响应式订阅
  if (st.status !== 'running') return false
  const sec = orchStepRunningSec(st)
  if (sec === null || sec < 60) return false
  const tracked = _stepLastMsgChange[st.id]
  if (!tracked) return true // 从未记录过，说明消息一直没来
  return (Date.now() - tracked.ts) >= 30000
}

/** 每次轮询后调用，更新 message 变化时间戳。 */
function _trackStepMessages(steps: Array<{ id: string; message?: string | null }>) {
  for (const st of steps || []) {
    const cur = String(st.message || '')
    const prev = _stepLastMsgChange[st.id]
    if (!prev || prev.msg !== cur) {
      _stepLastMsgChange[st.id] = { msg: cur, ts: Date.now() }
    }
  }
}

function serializablePlanSession(ps) {
  if (!ps || typeof ps !== 'object') return null
  return {
    ...ps,
    files: Array.isArray(ps.files)
      ? ps.files.map((f) => ({
          name: String(f?.name || ''),
          size: Number(f?.size || 0),
          type: String(f?.type || ''),
          cachedOnly: true,
        }))
      : [],
  }
}

function restorePlanSession(ps) {
  if (!ps || typeof ps !== 'object') return null
  const out = {
    ...ps,
    files: Array.isArray(ps.files) ? ps.files : [],
    messages: Array.isArray(ps.messages) ? ps.messages : [],
    checklistLines: Array.isArray(ps.checklistLines) ? ps.checklistLines : [],
  }
  if (out.loading) {
    out.loading = false
    out.planError =
      out.planError ||
      '页面切换前的规划请求已中断；已恢复当前进度，你可以继续补充或重新触发本步骤。'
  }
  return out
}

function serializablePendingHandoff(h) {
  if (!h || typeof h !== 'object') return null
  return {
    ...h,
    files: Array.isArray(h.files)
      ? h.files.map((f) => ({
          name: String(f?.name || ''),
          size: Number(f?.size || 0),
          type: String(f?.type || ''),
          cachedOnly: true,
        }))
      : [],
    planningMessages: Array.isArray(h.planningMessages)
      ? h.planningMessages.map((m) => ({ role: m.role, content: m.content }))
      : [],
    executionChecklist: Array.isArray(h.executionChecklist) ? [...h.executionChecklist] : [],
    sourceDocuments: Array.isArray(h.sourceDocuments) ? [...h.sourceDocuments] : [],
  }
}

function restorePendingHandoff(h) {
  if (!h || typeof h !== 'object') return null
  return {
    ...h,
    files: Array.isArray(h.files) ? h.files : [],
    planningMessages: Array.isArray(h.planningMessages) ? h.planningMessages : [],
    executionChecklist: Array.isArray(h.executionChecklist) ? h.executionChecklist : [],
    sourceDocuments: Array.isArray(h.sourceDocuments) ? h.sourceDocuments : [],
  }
}

function makeHasCachedProgress() {
  return Boolean(
    planSession.value ||
      pendingHandoff.value ||
      workflowLinkOffer.value ||
      finalizeLoading.value ||
      finalizeError.value ||
      orchestrationSession.value?.steps?.length ||
      orchestrationSessionId.value,
  )
}

function cacheMakeProgress() {
  try {
    if (!makeHasCachedProgress()) {
      sessionStorage.removeItem(MAKE_PROGRESS_CACHE_KEY)
      return
    }
    sessionStorage.setItem(
      MAKE_PROGRESS_CACHE_KEY,
      JSON.stringify({
        savedAt: Date.now(),
        activeGear: activeGear.value,
        draft: draft.value,
        composerIntent: composerIntent.value,
        modFrontendEnabled: modFrontendEnabled.value,
        planSession: serializablePlanSession(planSession.value),
        planReplyDraft: planReplyDraft.value,
        planOptionSelections: planOptionSelections.value,
        planOptionOtherText: { ...planOptionOtherText },
        pendingHandoff: serializablePendingHandoff(pendingHandoff.value),
        finalizeLoading: finalizeLoading.value,
        finalizeError: finalizeError.value,
        orchestrationSession: orchestrationSession.value,
        orchestrationSessionId: orchestrationSessionId.value,
        orchPhase: orchPhase.value,
        orchestrationEtaSeconds: orchestrationEtaSeconds.value,
        orchestrationEtaReason: orchestrationEtaReason.value,
        orchTimingStartMs: orchTimingStartMs.value,
        workflowLinkOffer: workflowLinkOffer.value,
      }),
    )
  } catch {
    /* ignore */
  }
}

function clearMakeProgressCache() {
  try {
    sessionStorage.removeItem(MAKE_PROGRESS_CACHE_KEY)
  } catch {
    /* ignore */
  }
}

function restoreMakeProgressCache() {
  try {
    const raw = sessionStorage.getItem(MAKE_PROGRESS_CACHE_KEY)
    if (!raw) return
    const cached = JSON.parse(raw)
    if (!cached || Date.now() - Number(cached.savedAt || 0) > MAKE_PROGRESS_CACHE_TTL_MS) {
      clearMakeProgressCache()
      return
    }
    if (cached.activeGear && gearScenes.some((it) => it.key === cached.activeGear)) {
      activeGear.value = cached.activeGear
    }
    if (typeof cached.draft === 'string' && !draft.value.trim()) draft.value = cached.draft
    if (cached.composerIntent === 'workflow') {
      composerIntent.value = CANVAS_SKILL_INTENT
    } else if (INTENT_META[cached.composerIntent]) {
      composerIntent.value = cached.composerIntent
    }
    if (typeof cached.modFrontendEnabled === 'boolean') {
      modFrontendEnabled.value = cached.modFrontendEnabled
    }
    planSession.value = restorePlanSession(cached.planSession)
    planReplyDraft.value = typeof cached.planReplyDraft === 'string' ? cached.planReplyDraft : ''
    planOptionSelections.value =
      cached.planOptionSelections && typeof cached.planOptionSelections === 'object'
        ? cached.planOptionSelections
        : {}
    clearPlanOptionOtherText()
    if (cached.planOptionOtherText && typeof cached.planOptionOtherText === 'object') {
      for (const [k, v] of Object.entries(cached.planOptionOtherText)) {
        planOptionOtherText[k] = String(v || '')
      }
    }
    pendingHandoff.value = restorePendingHandoff(cached.pendingHandoff)
    finalizeLoading.value = Boolean(cached.finalizeLoading)
    finalizeError.value = typeof cached.finalizeError === 'string' ? cached.finalizeError : ''
    orchestrationSession.value = cached.orchestrationSession || null
    orchestrationSessionId.value = String(cached.orchestrationSessionId || '').trim()
    orchPhase.value = cached.orchPhase || (finalizeLoading.value ? 'running' : 'idle')
    orchestrationEtaSeconds.value =
      cached.orchestrationEtaSeconds == null ? null : Number(cached.orchestrationEtaSeconds)
    orchestrationEtaReason.value =
      typeof cached.orchestrationEtaReason === 'string' ? cached.orchestrationEtaReason : ''
    orchTimingStartMs.value =
      cached.orchTimingStartMs == null ? null : Number(cached.orchTimingStartMs)
    workflowLinkOffer.value = cached.workflowLinkOffer || null
  } catch {
    clearMakeProgressCache()
  }
}

watch(
  () => directMessages.value.map((m) => `${m.id}:${m.content.length}:${m.pending ? 1 : 0}`).join('|'),
  async () => {
    await nextTick()
    const raw = directThreadRef.value as any
    const el: HTMLElement | null = raw?.$el || raw
    if (!el) return
    el.scrollTop = el.scrollHeight
  },
)

onMounted(async () => {
  document.addEventListener('pointerdown', onLlmDocPointerDown, true)
  window.addEventListener('keydown', onLlmEscape)
  try {
    const pendingDraft = sessionStorage.getItem('workbench_home_pending_draft')
    const pendingIntent = sessionStorage.getItem('workbench_home_pending_intent')
    if (pendingDraft && !draft.value.trim()) draft.value = pendingDraft
    if (pendingIntent && INTENT_META[pendingIntent]) {
      composerIntent.value = pendingIntent === 'workflow' ? CANVAS_SKILL_INTENT : pendingIntent
    }
    sessionStorage.removeItem('workbench_home_pending_draft')
    sessionStorage.removeItem('workbench_home_pending_intent')
  } catch {
    /* ignore */
  }
  restoreMakeProgressCache()
  try {
    const emp = sessionStorage.getItem(WB_DIRECT_CHAT_EMPLOYEE_ID_KEY)
    if (emp && emp.trim()) directChatEmployeeId.value = emp.trim()
  } catch {
    /* ignore */
  }
  /* 须在首个 await 之前完成：否则 keep-alive 下 onActivated 可能先于 bots/会话加载执行，客服深链会漏处理 */
  try {
    refreshAllBots()
    activeBotId.value = loadActiveBotId() || ''
  } catch {
    /* ignore */
  }
  try {
    conversations.value = loadConversations()
    const storedActive = loadActiveId()
    if (storedActive && conversations.value.some((c) => c.id === storedActive)) {
      activeConversationId.value = storedActive
    } else if (conversations.value.length) {
      activeConversationId.value = conversations.value[0].id
      saveActiveId(activeConversationId.value)
    }
  } catch {
    /* ignore */
  }
  try {
    applyCustomerServiceRouteContext()
  } catch {
    /* ignore */
  }

  try {
    const me = await api.me()
    const u = typeof me.username === 'string' ? me.username.trim() : ''
    const e = typeof me.email === 'string' ? me.email.trim() : ''
    displayName.value = u || (e ? e.split('@')[0] || e : '')
  } catch {
    displayName.value = ''
  }
  await loadLlmCatalogForWorkbench()
  await loadWorkbenchRepoPicks()
  await loadKnowledgeDocuments()

  try {
    personalSettings.value = loadPersonalSettings()
    applyThemeToDocument(personalSettings.value.theme)
  } catch {
    /* ignore */
  }
  void resumeCachedOrchestration()
})

onActivated(() => {
  try {
    applyCustomerServiceRouteContext()
  } catch {
    /* ignore */
  }
})

watch(directChatEmployeeId, (v) => {
  try {
    const s = String(v || '').trim()
    if (s) sessionStorage.setItem(WB_DIRECT_CHAT_EMPLOYEE_ID_KEY, s)
    else sessionStorage.removeItem(WB_DIRECT_CHAT_EMPLOYEE_ID_KEY)
  } catch {
    /* ignore */
  }
})

watch(
  () => Boolean(planSession.value?.loading),
  (loading) => {
    if (planLoadingIntervalId !== null) {
      clearInterval(planLoadingIntervalId)
      planLoadingIntervalId = null
    }
    planLoadingAdvance.value = 0
    if (!loading) return
    const step = () => {
      const ps = planSession.value
      const list = ps?.phase === 'summary' ? planLoadingStepsSummary : planLoadingStepsChat
      const max = Math.max(0, list.length - 1)
      if (planLoadingAdvance.value < max) planLoadingAdvance.value += 1
    }
    planLoadingIntervalId = window.setInterval(step, 2000)
  },
)

watch(
  [
    planSession,
    planReplyDraft,
    planOptionSelections,
    pendingHandoff,
    workflowLinkOffer,
    finalizeLoading,
    finalizeError,
    orchestrationSession,
    orchestrationSessionId,
    orchPhase,
    orchestrationEtaSeconds,
    orchestrationEtaReason,
    orchTimingStartMs,
    composerIntent,
    draft,
    modFrontendEnabled,
    activeGear,
  ],
  cacheMakeProgress,
  { deep: true },
)

watch(
  () => ({ ...planOptionOtherText }),
  cacheMakeProgress,
  { deep: true },
)

onBeforeUnmount(() => {
  pollStop.value = true
  stopOrchestrationElapsedTicker()
  closePlanDiagramPreview()
  if (planLoadingIntervalId !== null) {
    clearInterval(planLoadingIntervalId)
    planLoadingIntervalId = null
  }
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onLlmDocPointerDown, true)
  window.removeEventListener('keydown', onLlmEscape)
  stopDirectTtsPlayback()
})

function clearWorkbenchHandoffSession() {
  try {
    sessionStorage.removeItem('workbench_home_draft')
    sessionStorage.removeItem('workbench_home_intent')
    sessionStorage.removeItem('workbench_home_llm')
    sessionStorage.removeItem('workbench_home_llm_mode')
  } catch {
    /* ignore */
  }
  clearMakeProgressCache()
}

/** 做 Mod 时屏蔽「选语言 / 选 API 风格 / 选 UI 库」等通用脚手架题（旧回复或误遵指令时兜底） */
function isModHostStackSurveyQuestion(q) {
  const t = String(q?.title || '').trim()
  if (!t) return false
  if (/员工包.*语言|后端.*语言|^语言$/i.test(t)) return true
  if (/API\s*(设计|风格)|RESTful|RPC\s*风格|统一前缀/i.test(t)) return true
  if (/前端\s*UI|UI\s*框架|Element\s*Plus|Ant\s*Design|Vant/i.test(t)) return true
  return false
}

function normalizePlanOptions(raw) {
  const out = []
  if (!Array.isArray(raw)) return out
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const qid = String(item.id || '').trim().slice(0, 48)
    const title = String(item.title || item.question || '').trim().slice(0, 120)
    const choicesIn = item.choices
    if (!qid || !title || !Array.isArray(choicesIn)) continue
    const choices = []
    for (const c of choicesIn) {
      if (!c || typeof c !== 'object') continue
      const cid = String(c.id || '').trim().slice(0, 48)
      const label = String(c.label || c.text || '').trim().slice(0, 160)
      if (!cid || !label) continue
      choices.push({ id: cid, label })
    }
    if (choices.length < 2) continue
    if (choices.length > 5) choices.length = 5
    out.push({ id: qid, title, choices })
  }
  return out.slice(0, 6)
}

/** 解析规划助手回复：Mermaid + <<<PLAN_DETAILS>>> + <<<PLAN_OPTIONS>>> JSON（与 buildPlanSystemPrompt 约定一致） */
function parsePlanAssistantContent(raw) {
  const s = String(raw || '')
  const mer = s.match(/```mermaid\s*([\s\S]*?)```/i)
  const diagram = mer ? mer[1].trim() : ''
  const det = s.match(/<<<PLAN_DETAILS>>>([\s\S]*?)<<<END_PLAN_DETAILS>>>/i)
  const opt = s.match(/<<<PLAN_OPTIONS>>>([\s\S]*?)<<<END_PLAN_OPTIONS>>>/i)
  let options = []
  if (opt) {
    const rawJson = opt[1].trim()
    try {
      options = normalizePlanOptions(JSON.parse(rawJson))
    } catch {
      options = []
    }
  }
  let details = det ? det[1].trim() : ''
  if (!details) {
    let rest = s
    if (mer) rest = rest.replace(mer[0], '')
    if (det) rest = rest.replace(det[0], '')
    if (opt) rest = rest.replace(opt[0], '')
    details = rest.replace(/^\s*\n+|\n+\s*$/g, '').trim()
  }
  if (!details && diagram) details = '（仅流程图，无补充说明）'
  const hasDiagram = diagram.length > 0
  return { diagram, details, hasDiagram, options }
}

const planQuickOptions = computed(() => {
  const ps = planSession.value
  if (!ps?.messages?.length) return []
  for (let i = ps.messages.length - 1; i >= 0; i--) {
    if (ps.messages[i].role === 'assistant') {
      let o = parsePlanAssistantContent(ps.messages[i].content).options
      if (!Array.isArray(o)) return []
      if (ps.intentKey === 'mod') {
        o = o.filter((q) => !isModHostStackSurveyQuestion(q))
      }
      return o
    }
  }
  return []
})

const planPanelTitle = computed(() => {
  const ps = planSession.value
  if (!ps) return '需求规划'
  if (ps.phase === 'summary') return ps.summaryTitle || '确认任务摘要'
  return ps.summaryTitle || '需求规划'
})

const planChecklistFlowMarkdown = computed(() => {
  const lines = Array.isArray(planSession.value?.checklistLines) ? planSession.value.checklistLines : []
  return buildChecklistFlowMarkdown(lines)
})

function mermaidChecklistLabel(text, max = 30) {
  const s = String(text || '')
    .replace(/^\s*\d+[\.)、]\s*/, '')
    .replace(/[<>]/g, '')
    .replace(/["[\]{}]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!s) return '步骤'
  return s.length > max ? `${s.slice(0, max)}…` : s
}

function buildChecklistFlowMarkdown(lines) {
  const list = Array.isArray(lines) ? lines.filter((x) => String(x || '').trim()).slice(0, 18) : []
  if (!list.length) {
    return '```mermaid\nflowchart TD\n  start["开始"] --> done["完成"]\n```'
  }
  const out = ['```mermaid', 'flowchart TD', '  start["开始"]']
  list.forEach((line, idx) => {
    out.push(`  S${idx + 1}["${idx + 1}. ${mermaidChecklistLabel(line)}"]`)
  })
  out.push('  done["完成"]')
  out.push('  start --> S1')
  for (let i = 1; i < list.length; i += 1) {
    out.push(`  S${i} --> S${i + 1}`)
  }
  out.push(`  S${list.length} --> done`)
  out.push('```')
  return out.join('\n')
}

function compactPlanVisibleText(text, max = 260) {
  const s = String(text || '')
    .replace(/【本次上传附件全文】[\s\S]*?(?=\n\n---\n|$)/g, '【本次上传附件全文已读取，界面不展开】')
    .replace(/【我的文件资料库命中片段】[\s\S]*?(?=\n\n---\n|$)/g, '【资料库片段已读取，界面不展开】')
    .replace(/\s+/g, ' ')
    .trim()
  if (!s) return '请根据上传内容和输入描述进行规划'
  return s.length > max ? `${s.slice(0, max)}…` : s
}

/** 制作区大标题：从交接描述里优先取「初始想法」段，否则整段压缩 */
function extractInitialIdeaFromHandoff(description) {
  const s = String(description || '')
  const m = s.match(/【初始想法】\s*\n+([\s\S]*?)(?=\n\n---|\n【|$)/)
  const chunk = m?.[1]?.trim() ? m[1].trim() : s.trim()
  if (!chunk) return ''
  return compactPlanVisibleText(chunk, 900)
}

const MAKE_HERO_TITLE_MAX = 64

const makeHeroTitle = computed(() => {
  if (!makeHasActiveTask.value) return '今天有什么安排？'
  const ps = planSession.value
  if (ps) {
    const title = String(ps.summaryTitle || '').trim()
    if (title) return truncateWorkbenchText(title, MAKE_HERO_TITLE_MAX)
    if (ps.phase === 'summary') {
      const body = String(ps.summaryText || '').replace(/\s+/g, ' ').trim()
      if (body) return truncateWorkbenchText(body, MAKE_HERO_TITLE_MAX)
    }
    const firstUser = ps.messages?.find((m) => m.role === 'user')
    if (firstUser?.content) {
      return truncateWorkbenchText(compactPlanVisibleText(String(firstUser.content), 800), MAKE_HERO_TITLE_MAX)
    }
    return truncateWorkbenchText(planPanelTitle.value, MAKE_HERO_TITLE_MAX)
  }
  if (finalizeLoading.value) {
    const h = pendingHandoff.value
    const nm = h?.workflowName?.trim()
    if (nm) return truncateWorkbenchText(nm, MAKE_HERO_TITLE_MAX)
    return '正在启动制作…'
  }
  const h = pendingHandoff.value
  if (h) {
    if (isCanvasSkillIntent(h.intentKey) && h.workflowName?.trim()) {
      return truncateWorkbenchText(h.workflowName.trim(), MAKE_HERO_TITLE_MAX)
    }
    const idea = extractInitialIdeaFromHandoff(h.description)
    if (idea) return truncateWorkbenchText(idea, MAKE_HERO_TITLE_MAX)
    return truncateWorkbenchText(h.intentTitle || '制作草稿', MAKE_HERO_TITLE_MAX)
  }
  const orch = orchestrationSession.value
  if (orch?.steps?.length) {
    const art = orch.artifact || {}
    const nm = String(art.workflow_name || art.workflowName || art.name || orch.workflow_name || '').trim()
    if (nm) return truncateWorkbenchText(nm, MAKE_HERO_TITLE_MAX)
    const st = orch.steps.find((s) => s.status === 'running') || orch.steps[0]
    if (st?.label) return truncateWorkbenchText(String(st.label), MAKE_HERO_TITLE_MAX)
    return '制作进行中'
  }
  const wf = workflowLinkOffer.value
  if (wf?.workflowName) return truncateWorkbenchText(String(wf.workflowName), MAKE_HERO_TITLE_MAX)
  return '进行中的任务'
})

function buildPlanSummarySystemPrompt(intentTitle) {
  return [
    '你是需求摘要助手。你只负责把用户上传文件和输入内容总结成一个简短、准确的任务摘要，供用户确认。',
    `当前制作类型：${intentTitle || '未指定'}`,
    '输出格式必须严格为：',
    'TITLE: 一句话任务标题，不超过22个中文字符',
    'SUMMARY: 2到3句话说明任务目标、输入文件、期望产出',
    '不要输出流程图，不要输出选项，不要输出执行清单，不要泄露附件全文。',
  ].join('\n')
}

function parsePlanSummary(raw, fallback) {
  const text = String(raw || '').trim()
  const titleMatch = text.match(/^TITLE:\s*(.+)$/im)
  const summaryMatch = text.match(/^SUMMARY:\s*([\s\S]+)$/im)
  const lines = text.split(/\r?\n/).map((x) => x.trim()).filter(Boolean)
  const fallbackText = compactPlanVisibleText(fallback, 180)
  const title = (titleMatch?.[1] || lines[0] || fallbackText || '确认任务').replace(/^#+\s*/, '').trim().slice(0, 36)
  const summary = (summaryMatch?.[1] || lines.slice(1).join(' ') || fallbackText || title).trim()
  return { title, summary }
}

const canSendPlanQuickPicks = computed(() => {
  const opts = planQuickOptions.value
  if (!opts.length) return false
  const sel = planOptionSelections.value
  return opts.every((q) => {
    const cid = sel[q.id]
    if (!cid) return false
    if (cid === PLAN_OPTION_OTHER_ID) {
      return Boolean(String(planOptionOtherText[q.id] || '').trim())
    }
    return true
  })
})

watch(
  () => {
    const ps = planSession.value
    if (!ps?.messages?.length) return ''
    for (let i = ps.messages.length - 1; i >= 0; i--) {
      if (ps.messages[i].role === 'assistant') return ps.messages[i].content
    }
    return ''
  },
  () => {
    planOptionSelections.value = {}
    clearPlanOptionOtherText()
  },
)

function planAssistantParts(raw) {
  return parsePlanAssistantContent(raw)
}

function sanitizeMermaidLabel(label) {
  return String(label || '')
    .replace(/[()[\]{}<>]/g, ' ')
    .replace(/[*/\\=+\-]/g, ' ')
    .replace(/[|:;，,。]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 24) || '步骤'
}

function sanitizeMermaidSource(src) {
  return String(src || '')
    .split(/\r?\n/)
    .map((line) =>
      line.replace(/\[([^\]]*)\]/g, (_m, label) => `["${sanitizeMermaidLabel(label)}"]`),
    )
    .join('\n')
}

/** 助手气泡 Mermaid 渲染错误（按消息下标） */
const planDiagramError = ref({})

/** 规划流程图：完整预览浮层（消息下标，null 为关闭） */
const planDiagramPreviewIdx = ref(null)
const planDiagramPreviewMountRef = ref(null)
const planDiagramPreviewViewportRef = ref(null)
const planPreviewScale = ref(1)
const planPreviewTx = ref(0)
const planPreviewTy = ref(0)
let planDiagramPreviewEscUnlisten = null
let planDiagramPreviewPointerCleanup = null

const planDiagramPreviewPanStyle = computed(() => ({
  transform: `translate(${planPreviewTx.value}px, ${planPreviewTy.value}px) scale(${planPreviewScale.value})`,
  transformOrigin: '0 0',
}))

function clearPlanDiagramPreviewPointerListeners() {
  if (planDiagramPreviewPointerCleanup) {
    planDiagramPreviewPointerCleanup()
    planDiagramPreviewPointerCleanup = null
  }
  planDiagramPreviewViewportRef.value?.classList.remove('wb-plan-diagram-preview-viewport--drag')
}

function onPlanDiagramPreviewWheel(e: WheelEvent) {
  const vp = planDiagramPreviewViewportRef.value
  if (!vp) return
  const rect = vp.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  const oldS = planPreviewScale.value
  const factor = e.deltaY > 0 ? 0.9 : 1.1
  const newS = Math.min(6, Math.max(0.06, oldS * factor))
  if (Math.abs(newS - oldS) < 1e-6) return
  planPreviewTx.value = mx - ((mx - planPreviewTx.value) * newS) / oldS
  planPreviewTy.value = my - ((my - planPreviewTy.value) * newS) / oldS
  planPreviewScale.value = newS
}

function onPlanDiagramPreviewPointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  const vp = planDiagramPreviewViewportRef.value
  if (!vp || !planDiagramPreviewMountRef.value) return
  clearPlanDiagramPreviewPointerListeners()
  const sx = e.clientX
  const sy = e.clientY
  const stx = planPreviewTx.value
  const sty = planPreviewTy.value
  vp.classList.add('wb-plan-diagram-preview-viewport--drag')
  const move = (ev: PointerEvent) => {
    planPreviewTx.value = stx + (ev.clientX - sx)
    planPreviewTy.value = sty + (ev.clientY - sy)
  }
  const end = () => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', end)
    window.removeEventListener('pointercancel', end)
    vp.classList.remove('wb-plan-diagram-preview-viewport--drag')
    planDiagramPreviewPointerCleanup = null
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', end)
  window.addEventListener('pointercancel', end)
  planDiagramPreviewPointerCleanup = () => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', end)
    window.removeEventListener('pointercancel', end)
    vp.classList.remove('wb-plan-diagram-preview-viewport--drag')
  }
}

function planDiagramPreviewZoomStep(dir: number) {
  const vp = planDiagramPreviewViewportRef.value
  if (!vp) return
  const mx = vp.clientWidth / 2
  const my = vp.clientHeight / 2
  const oldS = planPreviewScale.value
  const factor = dir < 0 ? 1 / 1.22 : 1.22
  const newS = Math.min(6, Math.max(0.06, oldS * factor))
  planPreviewTx.value = mx - ((mx - planPreviewTx.value) * newS) / oldS
  planPreviewTy.value = my - ((my - planPreviewTy.value) * newS) / oldS
  planPreviewScale.value = newS
}

async function planDiagramPreviewFitView() {
  await nextTick()
  const vp = planDiagramPreviewViewportRef.value
  const mount = planDiagramPreviewMountRef.value
  const svg = mount?.querySelector('svg')
  if (!vp || !svg) return
  planPreviewScale.value = 1
  planPreviewTx.value = 0
  planPreviewTy.value = 0
  await nextTick()
  await new Promise<void>((r) => requestAnimationFrame(() => r()))
  let nw = 0
  let nh = 0
  try {
    const bb = svg.getBBox()
    nw = bb.width
    nh = bb.height
  } catch {
    /* ignore */
  }
  if (!nw || !nh) {
    const r = svg.getBoundingClientRect()
    nw = r.width || 1
    nh = r.height || 1
  }
  const pad = 36
  const vw = Math.max(64, vp.clientWidth - pad * 2)
  const vh = Math.max(64, vp.clientHeight - pad * 2)
  const s = Math.min(vw / nw, vh / nh, 3)
  const fit = Number.isFinite(s) && s > 0 ? s : 1
  planPreviewScale.value = fit
  const bw = nw * fit
  const bh = nh * fit
  planPreviewTx.value = (vp.clientWidth - bw) / 2
  planPreviewTy.value = (vp.clientHeight - bh) / 2
}

async function openPlanDiagramPreview(idx) {
  planDiagramPreviewIdx.value = idx
  planPreviewScale.value = 1
  planPreviewTx.value = 0
  planPreviewTy.value = 0
  if (planDiagramPreviewEscUnlisten) {
    planDiagramPreviewEscUnlisten()
    planDiagramPreviewEscUnlisten = null
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') closePlanDiagramPreview()
  }
  window.addEventListener('keydown', onKey)
  planDiagramPreviewEscUnlisten = () => window.removeEventListener('keydown', onKey)
  await nextTick()
  await nextTick()
  const host = document.getElementById(`wb-plan-mer-${idx}`)
  const svg = host?.querySelector('svg')
  const target = planDiagramPreviewMountRef.value
  if (!target) return
  target.innerHTML = ''
  if (svg) {
    const clone = svg.cloneNode(true) as SVGElement
    clone.style.maxWidth = 'none'
    clone.style.width = 'auto'
    clone.style.height = 'auto'
    target.appendChild(clone)
  } else {
    const p = document.createElement('p')
    p.className = 'wb-plan-diagram-preview-empty'
    p.textContent = '流程图尚未渲染完成，请稍后再次点击「完整预览」。'
    target.appendChild(p)
  }
  await nextTick()
  await planDiagramPreviewFitView()
  target.focus()
}

function closePlanDiagramPreview() {
  clearPlanDiagramPreviewPointerListeners()
  if (planDiagramPreviewEscUnlisten) {
    planDiagramPreviewEscUnlisten()
    planDiagramPreviewEscUnlisten = null
  }
  planDiagramPreviewIdx.value = null
}

let mermaidApi = null
let mermaidInitDone = false

async function getMermaidSingleton() {
  if (!mermaidApi) {
    const mod = await import('mermaid')
    mermaidApi = mod.default
  }
  if (!mermaidInitDone) {
    mermaidApi.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: 'dark',
      fontFamily: 'ui-sans-serif, system-ui, sans-serif',
    })
    mermaidInitDone = true
  }
  return mermaidApi
}

async function flushPlanMermaidDiagrams() {
  const ps = planSession.value
  if (!ps?.messages?.length) {
    planDiagramError.value = {}
    return
  }
  const nextErr = {}
  let mer
  try {
    mer = await getMermaidSingleton()
  } catch {
    planDiagramError.value = { _: '无法加载流程图组件' }
    return
  }
  for (const [idx, m] of ps.messages.entries()) {
    if (m.role !== 'assistant') continue
    const { diagram, hasDiagram } = parsePlanAssistantContent(m.content)
    const host = document.getElementById(`wb-plan-mer-${idx}`)
    if (!host) continue
    host.innerHTML = ''
    if (!hasDiagram) continue
    const graphEl = document.createElement('div')
    graphEl.className = 'mermaid'
    graphEl.textContent = diagram
    host.appendChild(graphEl)
    try {
      await mer.run({ nodes: [graphEl] })
    } catch (e) {
      const cleaned = sanitizeMermaidSource(diagram)
      host.innerHTML = ''
      const retryEl = document.createElement('div')
      retryEl.className = 'mermaid'
      retryEl.textContent = cleaned
      host.appendChild(retryEl)
      try {
        await mer.run({ nodes: [retryEl] })
      } catch (retryError) {
        nextErr[idx] = (retryError && retryError.message) || String(retryError) || '流程图解析失败'
        host.innerHTML = ''
      }
    }
  }
  planDiagramError.value = nextErr
}

watch(
  () => {
    const ps = planSession.value
    if (!ps?.messages) return ''
    return ps.messages.map((m) => `${m.role}\t${m.content}`).join('\n')
  },
  async () => {
    await nextTick()
    if (!planSession.value) {
      planDiagramError.value = {}
      return
    }
    await flushPlanMermaidDiagrams()
  },
)

function dismissPlanSession() {
  closePlanDiagramPreview()
  planSession.value = null
  planReplyDraft.value = ''
  planOptionSelections.value = {}
  clearPlanOptionOtherText()
  planDiagramError.value = {}
}

/** 二档制作主输入：开启全新任务，清空草稿、附件、规划与执行态。 */
function resetMakeComposer() {
  if (knowledgeUploading.value) return
  dismissPendingHandoff()
  draft.value = ''
  knowledgeError.value = ''
  const files = directAttachedFiles.value.slice()
  directAttachedFiles.value = []
  for (const item of files as Array<{ docId?: string }>) {
    if (item.docId) {
      void api.knowledgeDeleteDocument(item.docId).catch(() => {
        /* 与移除单附件一致 */
      })
    }
  }
  clearMakeProgressCache()
  nextTick(() => {
    const el = inputRef.value
    if (el && typeof el.focus === 'function') el.focus()
  })
}

async function loadKnowledgeDocuments(requireLogin = false) {
  if (!getAccessToken()) {
    if (requireLogin) requireLoginForWorkbenchUse()
    knowledgeStatus.value = null
    knowledgeDocs.value = []
    knowledgeError.value = ''
    return
  }
  knowledgeLoading.value = true
  knowledgeError.value = ''
  try {
    const [st, docs] = await Promise.all([
      api.knowledgeStatus(),
      api.knowledgeListDocuments(),
    ])
    knowledgeStatus.value = st
    knowledgeDocs.value = Array.isArray(docs?.documents) ? docs.documents : []
  } catch (e) {
    knowledgeError.value = e?.message || String(e)
    knowledgeDocs.value = []
  } finally {
    knowledgeLoading.value = false
  }
}

function openKnowledgeFilePicker() {
  if (knowledgeUploading.value || planSession.value) return
  if (!requireLoginForWorkbenchUse()) return
  knowledgeFileInputRef.value?.click?.()
}

async function uploadKnowledgeFiles(files) {
  const list = Array.from(files || []).filter(Boolean)
  if (!list.length || knowledgeUploading.value) return
  if (!requireLoginForWorkbenchUse()) return
  knowledgeError.value = ''
  try {
    await ingestComposerFiles(list as File[], 'make')
  } catch (err) {
    knowledgeError.value = err?.message || String(err)
  } finally {
    if (knowledgeFileInputRef.value) knowledgeFileInputRef.value.value = ''
  }
}

async function onKnowledgeFileChange(e) {
  await uploadKnowledgeFiles(e?.target?.files)
}

function onKnowledgeDragEnter() {
  if (knowledgeUploading.value || planSession.value) return
  knowledgeDragActive.value = true
}

function onKnowledgeDragLeave(e) {
  const current = e?.currentTarget
  const related = e?.relatedTarget
  if (current && related && current.contains?.(related)) return
  knowledgeDragActive.value = false
}

async function onKnowledgeDrop(e) {
  knowledgeDragActive.value = false
  if (knowledgeUploading.value || planSession.value) return
  if (!requireLoginForWorkbenchUse()) return
  await uploadKnowledgeFiles(e?.dataTransfer?.files)
}

function fileExtension(filename) {
  const ext = String(filename || '').split('.').pop()?.toLowerCase() || 'file'
  return ext.length > 5 ? ext.slice(0, 5) : ext
}

function fileKind(doc) {
  const ext = fileExtension(doc?.filename)
  if (ext === 'pdf') return 'pdf'
  if (ext === 'docx') return 'doc'
  if (ext === 'xlsx' || ext === 'csv') return 'sheet'
  if (ext === 'json') return 'json'
  if (ext === 'md') return 'md'
  return 'text'
}

function fileKindClass(doc) {
  return `wb-kb-card--${fileKind(doc)}`
}

function fileKindLabel(doc) {
  const m = {
    pdf: 'PDF 文档',
    doc: 'Word 文档',
    sheet: '表格数据',
    json: 'JSON 配置',
    md: 'Markdown',
    text: '文本资料',
  }
  return m[fileKind(doc)] || '文件'
}

function formatBytes(value) {
  const n = Number(value || 0)
  if (!Number.isFinite(n) || n <= 0) return '0 B'
  if (n < 1024) return `${Math.round(n)} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function deleteKnowledgeDocument(docId) {
  if (!docId) return
  if (!requireLoginForWorkbenchUse()) return
  try {
    await api.knowledgeDeleteDocument(docId)
    await loadKnowledgeDocuments()
  } catch (e) {
    knowledgeError.value = e?.message || String(e)
  }
}

function formatKnowledgeContext(items) {
  const rows = Array.isArray(items) ? items : []
  if (!rows.length) return ''
  return rows
    .slice(0, 6)
    .map((it, i) => {
      const filename = it?.filename || '资料'
      const pageNo = Number(it?.page_no || it?.pageNo || 0) || 0
      const content = String(it?.content || '').trim()
      return `### ${i + 1}. ${filename}${pageNo ? `（第 ${pageNo} 页）` : ''}\n${content}`
    })
    .join('\n\n---\n\n')
}

function dismissWorkflowLinkOffer() {
  workflowLinkOffer.value = null
  linkMods.value = []
  linkModId.value = ''
  linkError.value = ''
  linkBusy.value = false
}

async function loadLinkMods() {
  try {
    const res = await api.listMods()
    linkMods.value = Array.isArray(res?.data) ? res.data : []
  } catch {
    linkMods.value = []
  }
}

async function openWorkflowCanvasOnly() {
  const o = workflowLinkOffer.value
  if (!o) return
  const wid = o.workflowId
  dismissWorkflowLinkOffer()
  await router.push({ name: 'workbench-workflow', query: { edit: String(wid) } })
}

async function confirmWorkflowModLink() {
  const o = workflowLinkOffer.value
  if (!o || !linkModId.value) return
  linkBusy.value = true
  linkError.value = ''
  try {
    await api.modWorkflowLink(String(linkModId.value), {
      workflow_id: o.workflowId,
      label: o.workflowName,
    })
    const mid = linkModId.value
    dismissWorkflowLinkOffer()
    await router.push({ name: 'mod-authoring', params: { modId: mid } })
  } catch (e) {
    linkError.value = e.message || String(e)
  } finally {
    linkBusy.value = false
  }
}

function dismissPendingHandoff() {
  pendingHandoff.value = null
  finalizeError.value = ''
  orchestrationSession.value = null
  orchestrationSessionId.value = ''
  pollStop.value = true
  stopOrchestrationElapsedTicker()
  orchPhase.value = 'idle'
  orchTimingStartMs.value = null
  orchestrationEtaSeconds.value = null
  orchestrationEtaReason.value = ''
  finalizeLoading.value = false
  dismissWorkflowLinkOffer()
  dismissPlanSession()
  clearWorkbenchHandoffSession()
}

async function persistManualLlmIfNeeded() {
  if (modelMode.value !== 'manual' || !selectedModel.value || !selectedProvider.value) return
  try {
    await api.llmSavePreferences(selectedProvider.value, selectedModel.value)
  } catch {
    /* 仍尝试创建工作流 */
  }
}

async function pollWorkbenchSession(sessionId) {
  const delay = (ms) => new Promise((r) => setTimeout(r, ms))
  /**
   * 轮询策略：基础 1500ms（约 40 次/分钟），落在后端 RateLimiterMiddleware
   * 默认 60 次/60 秒的限额内，避免「开始生成员工包」长时间运行被 429 截断。
   * 后端同时为 GET /api/workbench/sessions/{id} 单独抬高了上限作为兜底。
   */
  const baseIntervalMs = 1500
  /** 总等待预算约 10 分钟，使用墙钟时间而非轮询次数（应对动态退避）。 */
  const deadline = Date.now() + 10 * 60 * 1000
  let backoffMs = 0
  while (!pollStop.value) {
    try {
      const s = await api.workbenchGetSession(sessionId)
      orchestrationSession.value = s
      _trackStepMessages(s.steps)
      if (s.status === 'done' || s.status === 'error') {
        // 后端守卫确保 status=done 时所有步骤已是终态；但在极端竞态下
        // 可能还有 pending/running 步骤——此处额外做最多 3 次补充轮询
        // 以等待守卫写完，保证前端渲染完整的 N/N 步完成状态。
        if (s.status === 'done') {
          const nonTerminal = (s.steps || []).filter(
            (x: { status?: string }) => x.status !== 'done' && x.status !== 'error',
          )
          if (nonTerminal.length > 0) {
            for (let i = 0; i < 3 && !pollStop.value; i++) {
              await delay(800)
              try {
                const s2 = await api.workbenchGetSession(sessionId)
                orchestrationSession.value = s2
                _trackStepMessages(s2.steps)
                const stillPending = (s2.steps || []).filter(
                  (x: { status?: string }) => x.status !== 'done' && x.status !== 'error',
                )
                if (stillPending.length === 0) break
              } catch {
                break
              }
            }
          }
        }
        return orchestrationSession.value as typeof s
      }
      backoffMs = 0
    } catch (e) {
      const status = e && typeof e === 'object' && typeof (e as any).status === 'number' ? (e as any).status : 0
      // 429（限流）/ 503（短暂不可用）属于可恢复抖动：指数退避后继续轮询，
      // 而非把整个编排会话标记为失败。其余错误按原行为向上抛出。
      if (status === 429 || status === 503) {
        backoffMs = backoffMs ? Math.min(backoffMs * 2, 30000) : 5000
      } else {
        throw e
      }
    }
    if (Date.now() >= deadline) {
      const steps = Array.isArray(orchestrationSession.value?.steps) ? orchestrationSession.value.steps : []
      const stuckStep = steps.find((x) => x.status === 'running') || steps.slice().reverse().find((x) => x.status === 'done')
      const stuckLabel = stuckStep ? `「${String(stuckStep.label || stuckStep.id)}」` : ''
      throw new Error(`在${stuckLabel}步骤等待超时（约 10 分钟）。后端已自动标记失败，可立即重试。请检查后端日志、网络或 LLM 配置。`)
    }
    await delay(backoffMs || baseIntervalMs)
  }
  return null
}

async function resumeCachedOrchestration() {
  const sid = String(orchestrationSessionId.value || '').trim()
  if (!sid || !finalizeLoading.value) return
  pollStop.value = false
  if (orchPhase.value !== 'estimating') {
    orchPhase.value = 'running'
    if (!orchTimingStartMs.value) orchTimingStartMs.value = Date.now()
    startOrchestrationElapsedTicker()
  }
  try {
    const final = await pollWorkbenchSession(sid)
    if (!final || pollStop.value) return
    orchestrationSession.value = final
    if (final.status === 'error') {
      finalizeError.value = final.error || '编排失败'
    }
  } catch (e: any) {
    const m = e?.message || String(e)
    finalizeError.value = m
  } finally {
    stopOrchestrationElapsedTicker()
    finalizeLoading.value = false
    orchPhase.value = 'idle'
    orchTimingStartMs.value = null
  }
}

async function runOrchestration() {
  const h = pendingHandoff.value
  if (!h || !hasWorkflow.value || finalizeLoading.value) return
  if (!requireLoginForWorkbenchUse()) return
  if (!canRunOrchestration.value) {
    if (isCanvasSkillIntent(h.intentKey)) finalizeError.value = '请填写 Skill 组名称与描述'
    else finalizeError.value = '请填写描述'
    return
  }
  finalizeError.value = ''
  finalizeLoading.value = true
  pollStop.value = false
  orchestrationSession.value = null
  orchestrationSessionId.value = ''
  orchPhase.value = 'estimating'
  orchestrationEtaSeconds.value = null
  orchestrationEtaReason.value = ''
  orchTimingStartMs.value = null
  stopOrchestrationElapsedTicker()
  try {
    await persistManualLlmIfNeeded()
    const intent = h.intentKey || CANVAS_SKILL_INTENT
    const checklist = Array.isArray(h.executionChecklist) ? h.executionChecklist : []
    const scriptFiles = isCanvasSkillIntent(intent) && Array.isArray(h.files) ? h.files : []
    const eta = await estimateOrchestrationSeconds({
      intent,
      brief: String(h.description || '').trim(),
      checklistLen: checklist.length,
      generateFrontend: intent === 'mod' ? modFrontendEnabled.value : false,
      employeeTarget: intent === 'employee' ? String(h.employeeTarget || '').trim() : '',
      scriptFileCount: scriptFiles.length,
    })
    let etaSec = eta.seconds
    let etaReason = String(eta.reason || '').trim()
    if (etaSec == null || !Number.isFinite(etaSec)) {
      etaSec = fallbackOrchestrationSecondsEstimate({
        intent,
        checklistLen: checklist.length,
        generateFrontend: intent === 'mod' ? modFrontendEnabled.value : false,
        employeeTarget: intent === 'employee' ? String(h.employeeTarget || '').trim() : '',
        scriptFileCount: scriptFiles.length,
      })
      if (!etaReason) etaReason = '按步骤量粗估（模型未返回数值）'
    }
    orchestrationEtaSeconds.value = etaSec
    orchestrationEtaReason.value = etaReason
    orchPhase.value = 'running'
    orchTimingStartMs.value = Date.now()
    startOrchestrationElapsedTicker()

    const body: Record<string, unknown> = {
      intent,
      brief: (h.description || '').trim(),
      workflow_name:
        isCanvasSkillIntent(intent) ? (h.workflowName || '').trim() : undefined,
      plan_notes: isCanvasSkillIntent(intent) ? (h.planNotes || '').trim() : '',
      suggested_mod_id:
        intent === 'mod' ? (h.suggestedModId || '').trim() || undefined : undefined,
      replace: true,
      planning_messages: Array.isArray(h.planningMessages) ? h.planningMessages : [],
      execution_checklist: checklist,
      source_documents: Array.isArray(h.sourceDocuments) ? h.sourceDocuments : [],
      // 以当前「制作前端」开关为准，避免交接对象上缺失或陈旧的 generateFrontend
      generate_frontend: intent === 'mod' ? modFrontendEnabled.value : false,
    }
    if (intent === 'employee') {
      const et = String(h.employeeTarget || 'pack_plus_workflow').trim()
      body.employee_target = et === 'pack_only' ? 'pack_only' : 'pack_plus_workflow'
      const wfn = String(h.employeeWorkflowName || '').trim()
      if (wfn) body.employee_workflow_name = wfn
      const fhd = String(h.fhdBaseUrl || '').trim()
      if (fhd) body.fhd_base_url = fhd
    }
    if (modelMode.value === 'manual' && selectedProvider.value && selectedModel.value) {
      body.provider = selectedProvider.value
      body.model = selectedModel.value
    } else {
      // Auto：与需求规划相同逻辑——默认厂商无密钥时换到已配置密钥的厂商，并显式传给编排接口
      const { provider, model } = await resolveChatProviderModel()
      body.provider = provider
      body.model = model
    }
    const useScriptMode = isCanvasSkillIntent(intent) && scriptFiles.length > 0
    const started = useScriptMode
      ? await api.workbenchStartScriptSession(
          {
            brief: body.brief,
            workflow_name: body.workflow_name,
            provider: body.provider,
            model: body.model,
          },
          scriptFiles,
        )
      : await api.workbenchStartSession(body)
    const sid = started?.session_id
    if (!sid) throw new Error('未返回 session_id')
    orchestrationSessionId.value = String(sid)
    const final = await pollWorkbenchSession(sid)
    if (pollStop.value) return
    if (!final) throw new Error('轮询已取消')
    if (final.status === 'error') {
      finalizeError.value = final.error || '编排失败'
      return
    }
    const art = final.artifact || {}
    const finIntent = final.intent || intent
    clearWorkbenchHandoffSession()
    try {
      if (modelMode.value === 'manual' && selectedProvider.value && selectedModel.value) {
        sessionStorage.setItem(
          'workbench_home_llm',
          JSON.stringify({
            provider: selectedProvider.value,
            model: selectedModel.value,
          }),
        )
        sessionStorage.setItem('workbench_home_llm_mode', 'manual')
      }
      sessionStorage.setItem('workbench_home_intent', finIntent)
    } catch {
      /* ignore */
    }
    if (art.execution_mode === 'script') {
      pendingHandoff.value = null
      const scriptWorkflowId = Number(art.script_workflow_id || 0)
      if (Number.isFinite(scriptWorkflowId) && scriptWorkflowId > 0) {
        // 让用户先看到完成状态，再跳转
        await nextTick()
        await new Promise((r) => setTimeout(r, 1200))
        orchestrationSession.value = null
        orchestrationSessionId.value = ''
        await router.push({ path: `/script-workflows/${scriptWorkflowId}/edit`, query: { tab: 'sandbox' } })
        return
      }
      nextTick(() => {
        const el = document.querySelector('.wb-script-result')
        if (el && typeof el.scrollIntoView === 'function') {
          el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        }
      })
      return
    }
    const gid = art.skill_group_id ?? art.workflow_id
    if (isCanvasSkillIntent(finIntent) && gid != null) {
      workflowLinkOffer.value = {
        workflowId: gid,
        workflowName: String(
          art.skill_group_name ||
            art.workflow_name ||
            (h.workflowName || '').trim() ||
            `Skill 组 ${gid}`,
        ),
        validationErrors: Array.isArray(art.validation_errors) ? art.validation_errors : [],
        llmWarnings: Array.isArray(art.llm_warnings) ? art.llm_warnings : [],
        sandboxOk: art.sandbox_ok !== false,
      }
      linkModId.value = ''
      linkError.value = ''
      void loadLinkMods()
      // 先渲染一次完成状态，再切换到 workflowLinkOffer 面板
      await nextTick()
      pendingHandoff.value = null
      orchestrationSession.value = null
      orchestrationSessionId.value = ''
      return
    }
    if (finIntent === 'mod' && art.mod_id) {
      // 让用户先看到完成状态，再跳转
      await nextTick()
      await new Promise((r) => setTimeout(r, 1200))
      pendingHandoff.value = null
      orchestrationSession.value = null
      orchestrationSessionId.value = ''
      await router.push({
        name: 'mod-authoring',
        params: { modId: String(art.mod_id) },
      })
      return
    }
    if (finIntent === 'employee') {
      const q: Record<string, string> = {
        fromAi: '1',
        packId: art.pack_id != null ? String(art.pack_id) : '',
        name: art.name != null ? String(art.name) : '',
        desc: art.description != null ? String(art.description) : '',
      }
      const wfId = art.workflow_id ?? art.workflow_attachment?.workflow_id
      if (wfId != null && Number(wfId) > 0) q.wfId = String(wfId)
      // 让用户先看到 8/8 完成状态，再跳转到员工页
      await nextTick()
      await new Promise((r) => setTimeout(r, 1200))
      await router.push({ name: 'workbench-employee', query: q })
      return
    }
    pendingHandoff.value = null
    orchestrationSession.value = null
    orchestrationSessionId.value = ''
  } catch (e: any) {
    const m = e?.message || String(e)
    const low = m.toLowerCase()
    if (
      low.includes('not found') ||
      low.includes('404') ||
      m.includes('会话不存在') ||
      m.includes('已过期')
    ) {
      finalizeError.value =
        '无法查询编排会话（可能命中了另一台后端进程）。请部署并重启带「工作台会话落盘」的版本后重试；若已更新仍失败，请再点一次「开始生成 Mod」。'
    } else {
      finalizeError.value = m
    }
  } finally {
    stopOrchestrationElapsedTicker()
    orchPhase.value = 'idle'
    orchTimingStartMs.value = null
    orchestrationEtaSeconds.value = null
    orchestrationEtaReason.value = ''
    finalizeLoading.value = false
  }
}

function applyStarter(kind) {
  if (hasWorkflow.value) {
    if (!INTENT_META[kind]) return
    dismissPlanSession()
    composerIntent.value = kind
    nextTick(() => {
      const el = inputRef.value
      if (el && typeof el.focus === 'function') el.focus()
    })
    return
  }
  const fallback = {
    mod: hasRepo.value ? 'workbench-repository' : null,
    employee: hasEmployee.value ? 'workbench-employee' : null,
    skill: hasWorkflow.value ? 'workbench-workflow' : null,
    workflow: hasWorkflow.value ? 'workbench-workflow' : null,
  }[kind]
  if (fallback && router.hasRoute(fallback)) {
    router.push({ name: fallback })
  }
}

function buildPlanSystemPrompt(intentKey, intentTitle) {
  const typeHint =
    isCanvasSkillIntent(intentKey)
      ? '区分两类产物：（1）Skill 组合工作流＝先把需求拆成可复用 ESkill/Skill，再把这些 Skill 组合成画布工作流；（2）脚本工作流＝可运行程序、直接完成任务。规划时若用户要「程序本体」，引导其需求规划结束后去「脚本工作流」新建；此处必须先识别业务能力边界，拆出多个 Skill，说明每个 Skill 的输入、输出、质量门和触发策略，再描述 Skill 之间的顺序、条件与失败重试。流程图用 flowchart LR 或 TD，主干应体现 SkillA --> SkillB --> SkillC，节点用简短中文，避免括号、引号、特殊符号破坏 Mermaid 语法。'
      : intentKey === 'mod'
        ? [
            '用户目标可能有两档：（1）Mod 草稿骨架：仓库、manifest、行业 JSON、workflow_employees 名片；（2）可执行员工：在骨架基础上生成/登记 employee_pack，绑定 workflow_id，让工作流 employee 节点使用可执行包 id，并完成非 Mock 真实执行验证。',
            '【宿主软件 FHD / XCAGI 已定型，禁止「技术栈问卷」】宿主主程序为 Vue 3 + Vite + Element Plus（FHD/frontend）；本 Mod 前端作为专业版切换（侧栏 proModeToggle 等入口）后的「第二套前端」，挂在现有 /mods/<id>/frontend 路由体系，UI 语汇与宿主一致，不要引导用户再选「Node/Python/Go 员工包语言」「REST/RPC」「Element Plus / Ant Design / Vant」等通用栈。',
            '宿主与平台服务侧为 Python + FastAPI 等，不要提议用 Express/Gin 替换宿主 API。澄清时围绕：行业与场景、仓库与数据、员工职责与工具、工作流绑定、外部系统（微信/电话/合同等）、合规与脱敏、是否需要额外宿主路由/页面；不要把这些写成「选语言/选框架」的多选题。',
            'Mermaid 须用 flowchart 画出「建仓库 → 员工名片 → 员工包登记 → 工作流绑定 → 真实验证」的主线，节点名两到六字中文，不用括号。',
            '<<<PLAN_OPTIONS>>>：若需要点选澄清，只能出与业务/交付相关的题；若当前轮没有合适的二选一/多选一，必须输出 []。严禁出现「后端语言」「前端 UI 框架」「API 风格 REST/RPC」类标题或选项。',
          ].join(' ')
        : '关注员工角色、可用工具/能力标识、输入输出与行业场景。Mermaid 用 flowchart 表示角色、工具、输出关系即可。'
  const diagramParity =
    intentKey === 'mod'
      ? '【与做员工对齐】每条回复的流程图要求与「做员工」完全相同：不得以「暂无图」「略」或纯文字代替拓扑；必须在 fenced Mermaid 中给出 flowchart。信息不足时仍输出极简示例，例如：flowchart LR 建仓库 --> 写JSON骨架 --> 员工命名。'
      : intentKey === 'employee'
        ? '【流程图】每条回复须含 fenced Mermaid flowchart，不得以纯文字代替；信息不足时用 3～5 个短中文节点概括角色与产出。'
        : ''
  return [
    `你是 XCAGI 工作台的「需求规划」助手。用户当前制作类型：「${intentTitle}」。`,
    `${typeHint}`,
    ...(diagramParity ? [diagramParity] : []),
    '流程：先根据用户的初步想法提出 2～4 个高价值澄清问题（用数字编号列出）；用户补充后，可继续追问直到需求足够具体。',
    '不要生成最终代码、manifest JSON 或工作流节点配置；不要代替用户直接写执行清单（清单由用户点击「生成执行清单」触发）。',
    '用语简洁，中文。',
    '',
    '【输出格式必须严格遵守，便于界面展示】',
    '1) 回复开头必须先输出且仅输出一段 fenced Mermaid（主视图流程草图），例如：',
    '```mermaid',
    'flowchart LR',
    '  A[开始] --> B[步骤]',
    '  B --> C[结束]',
    '```',
    '2) 紧接着输出澄清与说明文字，且必须用以下标记包裹（界面默认折叠在「详细」中）：',
    '<<<PLAN_DETAILS>>>',
    '（此处写编号问题与补充，可多段）',
    '<<<END_PLAN_DETAILS>>>',
    '3) 再输出快捷选项：单行 JSON 数组，用以下标记包裹（供界面点选；不需要选项时输出 []）：',
    '<<<PLAN_OPTIONS>>>',
    intentKey === 'mod'
      ? '[{"id":"q_scope","title":"交付档位","choices":[{"id":"skeleton","label":"先骨架（manifest/行业 JSON/名片）"},{"id":"full","label":"骨架 + 可执行员工包 + 工作流绑定"}]}]'
      : '[{"id":"q1","title":"短标题","choices":[{"id":"c1","label":"选项甲"},{"id":"c2","label":"选项乙"}]}]',
    '<<<END_PLAN_OPTIONS>>>',
    'JSON 须为单行；每项含 id、title、choices（2～5 项，每项 id 与 label）；label 内勿用英文双引号。',
    '除上述各段外不要输出其它前言或后记。',
  ].join('\n')
}

/** 仅用于「生成执行清单」单次请求：不得沿用对话里的 Mermaid/PLAN_* 格式，否则模型会拒写 <<<CHECKLIST>>> */
function buildChecklistGenerationSystemPrompt(intentKey, intentTitle) {
  const scope =
    isCanvasSkillIntent(intentKey)
      ? '每条任务应可执行、可验证。若用户要「程序本体」，清单中应出现脚本工作流（编写/运行/沙箱）相关条目；否则必须围绕 Skill 生成闭环：拆分 Skill 蓝图、定义每个 Skill 的输入输出契约、静态逻辑、质量门、动态触发策略、固化策略、Skill 间数据映射、组合工作流与沙盒校验。普通画布节点只作为 start/end/condition 等控制节点。'
      : intentKey === 'mod'
        ? '每条任务应可落到 Mod 仓库与真实可用闭环：仓库、manifest、行业 JSON、员工名片、employee_pack 登记、workflow_id 绑定、employee 节点 id 匹配、Mock 结构沙盒与非 Mock 真实执行验证。若用户只要草稿骨架，也必须在清单中标明后续成为可执行员工还缺哪些步骤。'
        : '每条任务应可落到员工能力、工具配置与交付物。'
  return [
    `你是 XCAGI 工作台的「执行清单」生成助手。当前制作类型：「${intentTitle}」。`,
    `${scope}`,
    '用户与助手的前文是对话历史；你的**整段回复只允许**输出下面这一块，不要写任何其它字符（不要写「好的」、不要写 mermaid、不要写 <<<PLAN_DETAILS>>>、不要写 <<<PLAN_OPTIONS>>>、不要用 ``` 代码围栏）。',
    '',
    '【必须严格按行输出】',
    '<<<CHECKLIST>>>',
    '1. …',
    '2. …',
    '<<<END>>>',
    '',
    '至少 4 条、建议 6～12 条；中文短句；行首编号必须为「数字 + 英文句点 + 空格」。',
  ].join('\n')
}

function formatPlanMessagesForBrief(msgs) {
  if (!Array.isArray(msgs) || !msgs.length) return ''
  return msgs
    .map((m) => `${m.role === 'user' ? '用户' : '助手'}：${m.content}`)
    .join('\n\n')
}

/** 规划面板：把 nginx 504 HTML 等转成可读中文，避免整页 HTML 贴在 planError 里 */
function friendlyPlanPanelApiError(err) {
  const raw = err && typeof err === 'object' && 'message' in err ? String(err.message) : String(err || '')
  const s = raw.trim()
  if (!s) return '请求失败，请稍后重试。'
  if (/504|Gateway Time-out|网关超时/i.test(s) || /<title>\s*504/i.test(s)) {
    return '网关超时（504）：最前面的 nginx 在超时时间内没等到后端返回就断开了连接。需求规划调用模型往往较慢，请在对外提供站点的那台 nginx 里为 /api/ 增大 proxy_read_timeout、proxy_send_timeout（建议 3600s），nginx -t 后 reload；若直连本机 API 正常而域名访问 504，说明问题在这一层反代。仓库示例见 market/nginx.conf、docs/nginx-https-example.conf。'
  }
  if (/<\s*html[\s>]/i.test(s)) {
    return '服务器返回了 HTML 错误页（多为反代或网关层），请在浏览器网络面板查看该请求的 HTTP 状态码，并检查 nginx 与 modstore 服务日志。'
  }
  return s.length > 900 ? `${s.slice(0, 900)}…` : s
}

function _checklistBodyToResult(body) {
  const lines = String(body || '')
    .split(/\r?\n/)
    .map((l) => l.replace(/^\s*\d+[\.)]\s*/, '').trim())
    .filter((l) => l && !/^<<<[\s\S]*>>>$/.test(l))
  if (!lines.length) return null
  const text = lines.map((l, i) => `${i + 1}. ${l}`).join('\n')
  return { text, lines }
}

/** 模型漏写结束标签时：取文末连续「数字. 」行作为清单（仅当正文含 <<<CHECKLIST>>> 时由上层调用） */
function parseChecklistNumberedTail(raw) {
  const lines = String(raw || '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
  while (lines.length && /^```/.test(lines[lines.length - 1])) {
    lines.pop()
  }
  const collected = []
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const l = lines[i]
    if (/^\d+[\.)]\s+\S/.test(l)) {
      collected.unshift(l.replace(/^\d+[\.)]\s+/, '').trim())
    } else if (collected.length) {
      break
    }
  }
  if (collected.length < 2) return null
  return _checklistBodyToResult(collected.join('\n'))
}

function parseChecklistBlock(raw) {
  let s = String(raw || '').trim()
  const fullFence = s.match(/^```(?:\w*)?\s*\n([\s\S]*?)\n```\s*$/m)
  if (fullFence) s = fullFence[1].trim()
  const mer = s.match(/```mermaid\s*[\s\S]*?```/i)
  if (mer) s = s.replace(mer[0], '')
  const pd = s.match(/<<<PLAN_DETAILS>>>([\s\S]*?)<<<END_PLAN_DETAILS>>>/i)
  if (pd) s = s.replace(pd[0], '')
  const po = s.match(/<<<PLAN_OPTIONS>>>([\s\S]*?)<<<END_PLAN_OPTIONS>>>/i)
  if (po) s = s.replace(po[0], '')
  s = s.replace(/<<<\s*CHECKLIST\s*>>>/gi, '<<<CHECKLIST>>>')
  s = s.replace(/<<<\s*END\s*CHECKLIST\s*>>>/gi, '<<<END>>>')
  s = s.replace(/<<<\s*END_CHECKLIST\s*>>>/gi, '<<<END>>>')
  s = s.replace(/<<<\s*END\s*>>>/gi, '<<<END>>>')
  const tryBodies = []
  let m = s.match(/<<<CHECKLIST>>>([\s\S]*?)<<<END>>>/i)
  if (m) tryBodies.push(m[1])
  if (!tryBodies.length) {
    m = s.match(/<<<CHECKLIST>>>([\s\S]*?)$/im)
    if (m) tryBodies.push(m[1])
  }
  for (const body of tryBodies) {
    const r = _checklistBodyToResult(body)
    if (r) return r
  }
  if (/<<<CHECKLIST>>>/i.test(s)) {
    const t = parseChecklistNumberedTail(s)
    if (t) return t
  }
  return null
}

function _providerRowHasUsableKey(row, fernetOk) {
  if (!row) return false
  if (row.provider === 'xiaomi' && row.has_platform_key) return true
  if (row.has_user_override && fernetOk) return true
  return false
}

/**
 * Auto 模式：优先请求服务端 /resolve-chat-default（与 /chat 共用 resolve_api_key），
 * 避免前端 /status + 目录推断与后端不一致；失败时再回退到本地推断。
 */
async function resolveChatProviderModel() {
  if (modelMode.value === 'manual') {
    if (!selectedProvider.value || !selectedModel.value) {
      throw new Error('自选模式下请选择厂商与模型')
    }
    return { provider: selectedProvider.value, model: selectedModel.value }
  }
  if (localStorage.getItem('modstore_token')) {
    try {
      const resolved = await api.llmResolveChatDefault()
      const rp = typeof resolved?.provider === 'string' ? resolved.provider.trim() : ''
      const rm = typeof resolved?.model === 'string' ? resolved.model.trim() : ''
      if (rp && rm) {
        return { provider: rp, model: rm }
      }
    } catch (e) {
      const msg = e?.message || String(e)
      if (/404|Not Found/i.test(msg)) {
        /* 旧服务端无此路由时回退到下方本地推断 */
      } else {
        throw e
      }
    }
  }
  if (!llmCatalog.value && localStorage.getItem('modstore_token')) {
    await loadLlmCatalogForWorkbench()
  }
  const pref = llmCatalog.value?.preferences || {}
  let p = typeof pref.provider === 'string' ? pref.provider.trim() : ''
  let m = typeof pref.model === 'string' ? pref.model.trim() : ''
  if (!p || !m) {
    throw new Error('请先在 LLM 设置中选择默认模型，或切换到「自选」')
  }

  let statusPayload
  try {
    statusPayload = await api.llmStatus()
  } catch {
    statusPayload = null
  }
  const fernetOk = Boolean(statusPayload?.fernet_configured)
  const rows = Array.isArray(statusPayload?.providers) ? statusPayload.providers : []
  const rowP = rows.find((r) => r.provider === p)

  if (!_providerRowHasUsableKey(rowP, fernetOk)) {
    const withModels = rows.filter((r) => {
      if (!_providerRowHasUsableKey(r, fernetOk)) return false
      const b = llmCatalog.value?.providers?.find((x) => x.provider === r.provider)
      return b && Array.isArray(b.models) && b.models.length
    })
    const fallback = withModels[0] || rows.find((r) => _providerRowHasUsableKey(r, fernetOk))
    if (!fallback) {
      if (!fernetOk && rows.some((r) => r.has_user_override)) {
        throw new Error(
          '已保存 BYOK，但服务端未配置 MODSTORE_LLM_MASTER_KEY，无法解密使用。请在部署环境设置主密钥，或改用平台环境变量密钥。',
        )
      }
      throw new Error(
        `当前默认厂商「${p}」没有可用的平台或 BYOK 密钥。请在钱包页 LLM 中为该厂商配置密钥，或切换到「自选」选择已有密钥的厂商与模型。`,
      )
    }
    const newP = fallback.provider
    const block = llmCatalog.value?.providers?.find((b) => b.provider === newP)
    const models = block?.models
    const newM = Array.isArray(models) && models.length ? models[0] : ''
    if (!newM) {
      throw new Error(
        `检测到 ${newP} 具备密钥，但模型列表不可用。请刷新页面或到钱包页确认该厂商模型目录已加载，再试需求规划。`,
      )
    }
    p = newP
    m = newM
  }

  return { provider: p, model: m }
}

function scrollPlanIntoView() {
  nextTick(() => {
    const el = planPanelRef.value
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  })
}

async function appendUserAndAssistantPlanTurn(userText, displayText = userText) {
  const ps = planSession.value
  if (!ps) return
  ps.messages.push({ role: 'user', content: displayText })
  ps.planError = ''
  const { provider, model } = await resolveChatProviderModel()
  const sys = buildPlanSystemPrompt(ps.intentKey, ps.intentTitle)
  const mappedMessages = ps.messages.map((m, idx) => {
    if (idx === ps.messages.length - 1 && m.role === 'user') {
      return { role: 'user', content: String(userText || displayText || '') }
    }
    return { role: m.role, content: m.content }
  })
  const apiMsgs = [
    { role: 'system', content: sys },
    ...(ps.fullBrief ? [{ role: 'user', content: `【完整隐藏上下文，供理解任务使用；不要原样输出】\n${ps.fullBrief}` }] : []),
    ...mappedMessages,
  ]
  const res = await api.llmChat(provider, model, apiMsgs, 2048)
  const c = typeof res?.content === 'string' ? res.content : ''
  ps.messages.push({ role: 'assistant', content: (c || '').trim() || '（无回复）' })
}

async function summarizePlanSession() {
  const ps = planSession.value
  if (!ps) return
  const { provider, model } = await resolveChatProviderModel()
  const sys = buildPlanSummarySystemPrompt(ps.intentTitle)
  const res = await api.llmChat(provider, model, [
    { role: 'system', content: sys },
    { role: 'user', content: ps.fullBrief || ps.displayBrief || ps.initialBrief },
  ], 700)
  const parsed = parsePlanSummary(res?.content, ps.displayBrief || ps.fullBrief)
  ps.summaryTitle = parsed.title
  ps.summaryText = parsed.summary
  ps.initialBrief = `${parsed.title}\n${parsed.summary}`
}

async function openPlanSession(input) {
  planSurfaceKey.value += 1
  const meta = INTENT_META[composerIntent.value] || INTENT_META.workflow
  const fullBrief = typeof input === 'object' && input ? String(input.fullBrief || '') : String(input || '')
  const displayBrief = typeof input === 'object' && input ? String(input.displayBrief || '') : compactPlanVisibleText(fullBrief)
  planSession.value = {
    intentKey: composerIntent.value,
    intentTitle: meta.title,
    phase: 'summary',
    initialBrief: displayBrief,
    fullBrief,
    displayBrief,
    generateFrontend: composerIntent.value === 'mod' ? input?.generateFrontend !== false : false,
    summaryTitle: '',
    summaryText: '',
    files: Array.isArray(input?.files) ? input.files : [],
    messages: [],
    checklistText: '',
    checklistLines: [],
    planError: '',
    loading: true,
  }
  draft.value = ''
  planReplyDraft.value = ''
  planOptionSelections.value = {}
  clearPlanOptionOtherText()
  finalizeError.value = ''
  await nextTick()
  scrollPlanIntoView()
  try {
    await summarizePlanSession()
  } catch (e) {
    if (planSession.value) {
      const fallback = parsePlanSummary('', displayBrief || fullBrief)
      planSession.value.summaryTitle = fallback.title
      planSession.value.summaryText = fallback.summary
      planSession.value.initialBrief = `${fallback.title}\n${fallback.summary}`
      planSession.value.planError = `摘要生成失败，已使用输入内容兜底：${friendlyPlanPanelApiError(e)}`
    }
  } finally {
    if (planSession.value) planSession.value.loading = false
  }
}

function backSummaryToComposer() {
  const ps = planSession.value
  if (ps?.displayBrief) draft.value = ps.displayBrief
  dismissPlanSession()
  nextTick(() => {
    const el = inputRef.value
    if (el && typeof el.focus === 'function') el.focus()
  })
}

async function confirmSummaryAndStartPlanning() {
  const ps = planSession.value
  if (!ps || ps.phase !== 'summary' || ps.loading) return
  ps.phase = 'chat'
  ps.messages = []
  ps.planError = ''
  ps.loading = true
  directAttachedFiles.value = []
  planOptionSelections.value = {}
  clearPlanOptionOtherText()
  const visible = `已确认任务：${ps.summaryTitle || '任务摘要'}\n${ps.summaryText || ps.displayBrief || ''}`
  try {
    await appendUserAndAssistantPlanTurn(ps.fullBrief || ps.displayBrief || ps.summaryText, visible)
  } catch (e) {
    ps.planError = friendlyPlanPanelApiError(e)
    ps.messages = []
  } finally {
    ps.loading = false
    scrollPlanIntoView()
  }
}

/**
 * 「AI 自主全部进行」：从 summary 阶段一路串到后端编排完成。
 * 流程：confirmSummaryAndStartPlanning → 自动答快捷题（如有） →
 * requestExecutionChecklist → confirmPlanAndOpenHandoff → runOrchestration。
 * 任一步失败：把可读错误写入 autoPilotError，停在当前阶段，让用户手动接管。
 */
async function runAutoPilotFromSummary() {
  const ps0 = planSession.value
  if (!ps0 || ps0.phase !== 'summary' || ps0.loading) return
  if (autoPilotRunning.value) return
  if (!ps0.summaryText) return
  autoPilotRunning.value = true
  autoPilotError.value = ''
  try {
    await confirmSummaryAndStartPlanning()
    let ps = planSession.value
    if (!ps || ps.phase !== 'chat') {
      throw new Error('未能进入澄清阶段')
    }
    if (ps.planError) throw new Error(ps.planError)

    await nextTick()
    if (planQuickOptions.value.length) {
      autoPickPlanQuickOptions()
      await nextTick()
      if (canSendPlanQuickPicks.value) {
        await sendPlanReplyFromQuickPicks()
      }
      ps = planSession.value
      if (ps?.planError) throw new Error(ps.planError)
    }

    ps = planSession.value
    if (!ps || ps.phase !== 'chat') {
      throw new Error('澄清阶段已被打断')
    }
    if ((ps.messages?.length || 0) < 2) {
      throw new Error('澄清回合不足，无法生成执行清单')
    }

    await requestExecutionChecklist()
    ps = planSession.value
    if (!ps) throw new Error('规划会话已丢失')
    if (ps.planError) throw new Error(ps.planError)
    if (ps.phase !== 'checklist') throw new Error('未能生成执行清单')

    confirmPlanAndOpenHandoff()
    await nextTick()
    if (!pendingHandoff.value) throw new Error('未能生成制作草稿')

    await runOrchestration()
    if (finalizeError.value) throw new Error(finalizeError.value)
  } catch (e) {
    autoPilotError.value = friendlyPlanPanelApiError(e)
  } finally {
    autoPilotRunning.value = false
  }
}

function pickPlanOption(qid, cid) {
  planOptionSelections.value = { ...planOptionSelections.value, [qid]: cid }
}

/** 每道快捷题选中第一个选项（非「其他」），便于快速填表后再微调 */
function autoPickPlanQuickOptions() {
  const ps = planSession.value
  if (!ps || ps.loading || ps.phase !== 'chat') return
  const opts = planQuickOptions.value
  if (!opts.length) return
  clearPlanOptionOtherText()
  const sel = { ...planOptionSelections.value }
  for (const q of opts) {
    const first = q.choices?.[0]
    if (first?.id) sel[q.id] = first.id
  }
  planOptionSelections.value = sel
}

async function submitPlanUserMessage(userText) {
  const ps = planSession.value
  const t = String(userText || '').trim()
  if (!t || !ps || ps.loading || ps.phase !== 'chat') return
  planOptionSelections.value = {}
  clearPlanOptionOtherText()
  ps.loading = true
  ps.planError = ''
  try {
    await appendUserAndAssistantPlanTurn(t)
  } catch (e) {
    ps.planError = friendlyPlanPanelApiError(e)
    if (ps.messages.length && ps.messages[ps.messages.length - 1].role === 'user') {
      ps.messages.pop()
    }
  } finally {
    ps.loading = false
    scrollPlanIntoView()
  }
}

async function sendPlanReply() {
  const t = planReplyDraft.value.trim()
  if (!t) return
  planReplyDraft.value = ''
  await submitPlanUserMessage(t)
}

async function sendPlanReplyFromQuickPicks() {
  const opts = planQuickOptions.value
  if (!opts.length || !canSendPlanQuickPicks.value) return
  const sel = planOptionSelections.value
  const lines = []
  for (const q of opts) {
    const cid = sel[q.id]
    if (cid === PLAN_OPTION_OTHER_ID) {
      lines.push(`【${q.title}】${String(planOptionOtherText[q.id] || '').trim()}`)
    } else {
      const c = (q.choices || []).find((x) => x.id === cid)
      lines.push(`【${q.title}】${c ? c.label : cid}`)
    }
  }
  await submitPlanUserMessage(lines.join('\n'))
}

async function requestExecutionChecklist() {
  const ps = planSession.value
  if (!ps || ps.loading || ps.phase !== 'chat') return
  if (ps.messages.length < 2) {
    ps.planError = '请先与助手完成至少一轮问答，再生成执行清单。'
    return
  }
  ps.loading = true
  ps.planError = ''
  try {
    const { provider, model } = await resolveChatProviderModel()
    const sys = buildChecklistGenerationSystemPrompt(ps.intentKey, ps.intentTitle)
    const tail = {
      role: 'user',
      content: [
        '请根据以上整段对话，输出一份可直接照着实现的「执行清单」。',
        '',
        '只输出下面这一块，不要前言、不要后记；不要用 markdown 代码围栏（不要用 ```）包住整块；不要输出 mermaid；不要输出 <<<PLAN_DETAILS>>> / <<<PLAN_OPTIONS>>>。',
        '',
        '必须严格使用这三行作为头尾标记（尖括号与单词一致）：',
        '<<<CHECKLIST>>>',
        '1. 第一条任务（一行一条，行首为数字+英文句点+空格）',
        '2. 第二条任务',
        '（按需继续编号）',
        '<<<END>>>',
        '',
        '注意：结束标记必须是单独的 <<<END>>>（与需求规划里其它 <<<END_…>>> 不同），否则系统无法解析。',
      ].join('\n'),
    }
    const apiMsgs = [
      { role: 'system', content: sys },
      ...(ps.fullBrief ? [{ role: 'user', content: `【完整隐藏上下文，供生成清单使用；不要原样输出】\n${ps.fullBrief}` }] : []),
      ...ps.messages.map((m) => ({ role: m.role, content: m.content })),
      tail,
    ]
    const res = await api.llmChat(provider, model, apiMsgs, 6144)
    const raw = typeof res?.content === 'string' ? res.content : ''
    const parsed = parseChecklistBlock(raw)
    if (!parsed) {
      ps.planError =
        '未能解析清单：请确认模型输出含 <<<CHECKLIST>>> 与 <<<END>>>（勿用 ``` 包裹），且至少两条编号任务；仍失败可把清单要点再发一轮对话后重试「生成执行清单」。'
      return
    }
    ps.checklistText = parsed.text
    ps.checklistLines = parsed.lines
    ps.phase = 'checklist'
  } catch (e) {
    ps.planError = friendlyPlanPanelApiError(e)
  } finally {
    ps.loading = false
    scrollPlanIntoView()
  }
}

function backPlanToChat() {
  const ps = planSession.value
  if (!ps) return
  ps.phase = 'chat'
  ps.checklistText = ''
  ps.checklistLines = []
  ps.planError = ''
}

function confirmPlanAndOpenHandoff() {
  const ps = planSession.value
  if (!ps || ps.phase !== 'checklist') return
  const qaText = formatPlanMessagesForBrief(ps.messages)
  const descChunks = [`【初始想法】\n${ps.initialBrief}`]
  if (qaText) descChunks.push(`【澄清对话】\n${qaText}`)
  descChunks.push(`【执行清单】\n${ps.checklistText}`)
  const description = descChunks.join('\n\n---\n\n')
  const ik = ps.intentKey
  pendingHandoff.value = {
    description,
    intentTitle: ps.intentTitle,
    intentKey: ik,
    workflowName: '',
    planNotes: isCanvasSkillIntent(ik) ? ps.checklistText : '',
    suggestedModId: ik === 'mod' ? suggestModIdFromText(`${ps.initialBrief}\n${ps.checklistText}`) : '',
    files: Array.isArray(ps.files) ? ps.files : [],
    generateFrontend: ik === 'mod' ? modFrontendEnabled.value : false,
    planningMessages: Array.isArray(ps.messages) ? ps.messages.map((m) => ({ role: m.role, content: m.content })) : [],
    executionChecklist: Array.isArray(ps.checklistLines) ? [...ps.checklistLines] : [],
    sourceDocuments: Array.isArray(ps.files)
      ? ps.files.map((f) => ({ name: String(f?.name || ''), size: Number(f?.size || 0), type: String(f?.type || '') }))
      : [],
    employeeTarget: ik === 'employee' ? 'pack_plus_workflow' : 'pack_only',
    employeeWorkflowName: '',
    fhdBaseUrl: '',
  }
  dismissPlanSession()
  nextTick(() => {
    const el = handoffPanelRef.value
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}

async function submitDraft() {
  const text = draft.value.trim()
  if ((!text && directAttachedFiles.value.length === 0) || !hasWorkflow.value) return
  if (!requireLoginForWorkbenchUse()) return
  if (directAttachedFiles.value.some((f) => f.status === 'uploading')) {
    knowledgeError.value = '附件仍在读取中，请稍候'
    return
  }
  if (planSession.value?.phase === 'chat') return
  if (planSession.value) {
    finalizeError.value = '请先完成或关闭上方的「需求规划」面板。'
    return
  }
  finalizeError.value = ''
  const filesSnapshot = [...directAttachedFiles.value]
  const note = directAttachmentNote(filesSnapshot)
  const inlineBlocks = filesSnapshot
    .filter((f: any) => (f.status === 'inline' || f.status === 'ready') && f.extractedText)
    .map((f: any, idx: number) => `### @附件${idx + 1}：${f.name}\n\n${f.extractedText}`)
    .join('\n\n---\n\n')
  let knowledgePack = ''
  if (text && isEmbeddingConfigured()) {
    try {
      const embeddingChoice = await resolveChatProviderModel()
      const res = await api.knowledgeSearch(text, 6, {
        embeddingProvider: embeddingChoice.provider,
        embeddingModel: embeddingChoice.model,
      })
      knowledgePack = formatKnowledgeContext(res?.items)
    } catch (e) {
      knowledgeError.value = e?.message || String(e)
    }
  }
  const payloadParts = [text]
  const wantsModFrontend = composerIntent.value === 'mod' && modFrontendEnabled.value
  if (composerIntent.value === 'mod') {
    payloadParts.push(
      wantsModFrontend
        ? '【制作选项】本次需要为 Mod 生成可路由的定制 Vue 前端页面，并在 manifest.frontend.menu 中暴露入口。'
        : '【制作选项】本次暂不生成定制前端，只保留 Mod 骨架、员工和工作流能力。',
    )
  }
  if (note) payloadParts.push(note)
  if (inlineBlocks) {
    payloadParts.push(`【本次上传附件全文】\n用户按上传顺序提供了以下文件；@附件1、@附件2 等编号与上方附件顺序一致，请按编号理解文件之间的先后逻辑。\n\n${inlineBlocks}`)
  }
  if (knowledgePack) payloadParts.push(`【我的文件资料库命中片段】\n${knowledgePack}`)
  const payload = payloadParts.filter(Boolean).join('\n\n---\n')
  const displayPayload = [text, note].filter(Boolean).join('\n\n')
  await openPlanSession({
    fullBrief: payload,
    displayBrief: displayPayload,
    files: filesSnapshot.map((f: any) => f.file).filter(Boolean),
    generateFrontend: wantsModFrontend,
  })
}

async function onComposerSendClick() {
  if (planSession.value?.phase === 'chat') {
    await sendPlanReply()
    return
  }
  await submitDraft()
}

function onComposerKeydown(e) {
  if (e.key !== 'Enter' || e.shiftKey) return
  const ps = planSession.value
  if (ps?.phase === 'chat') {
    e.preventDefault()
    void sendPlanReply()
    return
  }
  if (ps) return
  e.preventDefault()
  void submitDraft()
}
</script>

<style scoped>
.wb-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* 与主布局窗口等高、不产生页面级滚动；纵向仅在三联场景内滚动 */
.wb-home {
  flex: 1 1 0%;
  min-height: 0;
  max-height: 100%;
  height: 100%;
  width: 100%;
  max-width: 100%;
  padding: clamp(0.5rem, 1.5vw, 1rem) var(--layout-pad-x, 1rem) clamp(0.5rem, 1.2vw, 0.9rem);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  overflow: hidden;
}

.wb-home-inner {
  width: 100%;
  min-height: 0;
  max-height: 100%;
  /* 窄屏贴边留白、宽屏随屏变宽，上限约 56rem 避免一行过长 */
  max-width: min(56rem, calc(100vw - 2 * var(--layout-pad-x, 16px)));
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: clamp(1rem, 2.5vw, 1.5rem);
  overflow: hidden;
}
.wb-home-inner--gears {
  max-width: min(76rem, calc(100vw - 2 * var(--layout-pad-x, 16px)));
  flex: 1 1 0%;
  min-height: 0;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  gap: clamp(0.45rem, 1.1vw, 0.85rem);
  overflow: hidden;
}

.wb-home-inner--make {
  padding-top: 0;
}

.wb-home-inner--no-workflow {
  flex: 0 1 auto;
  gap: 1.25rem;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.wb-hero {
  text-align: center;
  /* 顶部留白：避免「你好，xx」与「今天有什么安排？」紧贴页面顶端，
     兼顾首页态（hasWorkflow=false）与二档场景（activeGear === 'make'） */
  padding-top: clamp(0.8rem, 2.6vw, 1.8rem);
  margin-bottom: 0;
}

.wb-hero-kicker {
  margin: 0 0 0.5rem;
  font-size: clamp(0.95rem, 0.9rem + 0.2vw, 1.05rem);
  color: rgba(255, 255, 255, 0.45);
}

.wb-hero-title {
  margin: 0;
  font-size: clamp(1.85rem, 4vw + 1rem, 2.75rem);
  font-weight: 600;
  letter-spacing: -0.035em;
  line-height: 1.15;
  color: #f4f4f5;
}

.wb-gear-layout {
  position: relative;
  width: 100%;
  flex: 1 1 0%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-right: clamp(3.25rem, 4.5vw, 4rem);
}

.wb-gear-layout--nav-locked .wb-gear-slider {
  opacity: 0.42;
  pointer-events: none;
  cursor: not-allowed;
}

.wb-gear-layout--nav-locked .wb-gear-stop {
  pointer-events: none;
  cursor: not-allowed;
  opacity: 0.55;
}

.wb-gear-rail {
  position: absolute;
  top: 50%;
  right: 0;
  z-index: 5;
  transform: translateY(-50%);
}

.wb-gear-slider {
  position: relative;
  width: 1.82rem;
  height: clamp(18rem, 46vh, 25rem);
  border-radius: 999px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.052), rgba(255, 255, 255, 0.018)),
    rgba(0, 0, 0, 0.26);
  border: 1px solid rgba(255, 255, 255, 0.075);
  box-shadow:
    0 14px 34px rgba(0, 0, 0, 0.24),
    inset 0 0 0 1px rgba(255, 255, 255, 0.025);
  touch-action: none;
  user-select: none;
  cursor: grab;
}

.wb-gear-slider--dragging {
  cursor: grabbing;
}

.wb-gear-slider__track {
  position: absolute;
  top: 1.05rem;
  bottom: 1.05rem;
  left: 50%;
  width: 1.5px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.11);
  transform: translateX(-50%);
}

.wb-gear-slider__fill {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(165, 180, 252, 0.95), rgba(56, 189, 248, 0.62));
  transition: height 0.28s ease;
}

.wb-gear-slider--dragging .wb-gear-slider__fill {
  transition: none;
}

.wb-gear-stop {
  position: absolute;
  left: 50%;
  z-index: 2;
  width: 1.45rem;
  height: 1.45rem;
  display: grid;
  place-items: center;
  gap: 0.04rem;
  padding: 0.18rem;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(255, 255, 255, 0.38);
  font: inherit;
  cursor: pointer;
  transform: translate(-50%, -50%);
  transition: color 0.18s ease, background 0.18s ease, opacity 0.18s ease;
}

.wb-gear-stop:hover {
  color: rgba(255, 255, 255, 0.78);
  background: rgba(255, 255, 255, 0.11);
}

.wb-gear-stop--active {
  opacity: 0;
  pointer-events: none;
}

.wb-gear-stop__num,
.wb-gear-thumb__num {
  font-size: 0.58rem;
  font-weight: 800;
  line-height: 1;
}

.wb-gear-stop__label,
.wb-gear-thumb__label {
  font-size: 0.56rem;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0;
}

.wb-gear-thumb {
  position: absolute;
  left: 50%;
  z-index: 3;
  width: 1.82rem;
  height: 1.82rem;
  display: grid;
  place-items: center;
  gap: 0.04rem;
  border-radius: 999px;
  border: 1px solid rgba(165, 180, 252, 0.58);
  background:
    radial-gradient(circle at 35% 25%, rgba(255, 255, 255, 0.18), transparent 36%),
    rgba(55, 62, 101, 0.94);
  color: #fff;
  box-shadow:
    0 0 0 3px rgba(129, 140, 248, 0.065),
    0 10px 22px rgba(0, 0, 0, 0.3);
  transform: translate(-50%, -50%);
  transition: top 0.3s cubic-bezier(0.22, 1, 0.36, 1), transform 0.18s ease;
  pointer-events: none;
}

.wb-gear-slider--dragging .wb-gear-thumb {
  transition: transform 0.18s ease;
  transform: translate(-50%, -50%) scale(1.06);
}

.wb-gear-viewport {
  position: relative;
  width: 100%;
  flex: 1 1 0%;
  min-height: 0;
  overflow: hidden;
}

.wb-gear-nav-lock {
  position: absolute;
  top: 0.35rem;
  left: 0.35rem;
  right: clamp(3.6rem, 5vw, 4.6rem);
  z-index: 12;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  padding: 0.38rem 0.55rem 0.38rem 0.65rem;
  border-radius: 0.65rem;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(2, 6, 23, 0.55);
  color: rgba(226, 232, 240, 0.86);
  font-size: 0.72rem;
  line-height: 1.35;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.wb-gear-nav-lock__text {
  flex: 1;
  min-width: 0;
  color: rgba(203, 213, 225, 0.82);
}

.wb-gear-nav-lock__btn {
  flex: 0 0 auto;
  padding: 0.22rem 0.62rem;
  border-radius: 999px;
  border: 1px solid rgba(165, 180, 252, 0.35);
  background: rgba(99, 102, 241, 0.18);
  color: #e0e7ff;
  font: inherit;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition:
    background 0.14s ease,
    border-color 0.14s ease,
    color 0.14s ease;
}

.wb-gear-nav-lock__btn:hover {
  background: rgba(99, 102, 241, 0.28);
  border-color: rgba(165, 180, 252, 0.5);
  color: #fff;
}

.wb-gear-track {
  height: 300%;
  transition: transform 0.55s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: transform;
}

.wb-gear-scene {
  height: calc(100% / 3);
  padding: clamp(0.75rem, 1.8vw, 1.25rem);
  box-sizing: border-box;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.28) transparent;
}

.wb-voice-scene {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(0.8rem, 1.8vw, 1.25rem);
  text-align: center;
  /* 隔离语音轨道的绘制与布局，减轻与纵向档位切换、一档聊天的交叉重绘 */
  contain: layout paint;
  isolation: isolate;
}

.wb-direct-scene {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(0.85rem, 2vh, 1.35rem);
  text-align: left;
  font-size: var(--wb-direct-font-px, 15px);
}

.wb-direct-shell {
  display: flex;
  flex: 1;
  min-height: 0;
  align-items: stretch;
  width: 100%;
  max-width: min(78rem, 100%);
  margin: 0 auto;
  border-radius: 0;
  background: transparent;
  border: 0;
  overflow: visible;
  position: relative;
}

.wb-direct-shell--empty {
  flex: 0 0 auto;
}

.wb-direct-main {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 0.85rem clamp(0.75rem, 1.5vw, 1.25rem) 1rem;
  gap: 0.55rem;
  overflow: hidden;
}

.wb-direct-main--empty {
  align-items: center;
  justify-content: flex-start;
  padding-top: 0;
  padding-bottom: 0;
}

.wb-direct-main--chatting {
  align-items: stretch;
  justify-content: flex-start;
  padding-top: clamp(0.85rem, 1.7vw, 1.25rem);
  animation: wb-direct-chat-surface-in 0.42s cubic-bezier(0.22, 1, 0.36, 1);
}

.wb-direct-main--drop {
  box-shadow: inset 0 0 0 2px rgba(165, 180, 252, 0.55);
  background: rgba(99, 102, 241, 0.05);
  transition: background 0.18s ease, box-shadow 0.18s ease;
}

.wb-direct-dropzone {
  position: absolute;
  inset: 0;
  z-index: 30;
  display: grid;
  place-items: center;
  padding: clamp(1rem, 4vh, 2rem);
  background: radial-gradient(120% 80% at 50% 40%, rgba(99, 102, 241, 0.22), rgba(2, 6, 23, 0.78) 70%);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  pointer-events: none;
  animation: wb-direct-dropzone-in 0.18s ease-out;
}

.wb-direct-dropzone__panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.55rem;
  padding: 1.1rem 1.5rem;
  border-radius: 1rem;
  border: 2px dashed rgba(165, 180, 252, 0.7);
  background: rgba(15, 23, 42, 0.55);
  color: #e2e8f0;
  text-align: center;
  box-shadow: 0 18px 40px -20px rgba(15, 23, 42, 0.6);
}

.wb-direct-dropzone__icon {
  width: 2.4rem;
  height: 2.4rem;
  display: grid;
  place-items: center;
  color: #c7d2fe;
}

.wb-direct-dropzone__icon > svg {
  width: 100%;
  height: 100%;
}

.wb-direct-dropzone__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.wb-direct-dropzone__sub {
  margin: 0;
  font-size: 0.82rem;
  color: rgba(226, 232, 240, 0.75);
}

@keyframes wb-direct-dropzone-in {
  from {
    opacity: 0;
    transform: scale(0.985);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes wb-direct-chat-surface-in {
  from {
    opacity: 0.84;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.wb-direct-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-wrap: wrap;
  transition:
    opacity 0.24s ease,
    transform 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}

.wb-direct-main--empty .wb-direct-topbar {
  position: absolute;
  top: 0.85rem;
  left: clamp(0.75rem, 1.5vw, 1.25rem);
  right: clamp(0.75rem, 1.5vw, 1.25rem);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-8px);
  border-bottom: 0;
}

.wb-direct-main--empty:hover .wb-direct-topbar,
.wb-direct-main--empty:focus-within .wb-direct-topbar {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

.wb-direct-main--chatting .wb-direct-topbar {
  opacity: 1;
  transform: translateY(0);
}

.wb-direct-topbar__l,
.wb-direct-topbar__r {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.wb-direct-topbtn {
  display: inline-flex;
  align-items: center;
  gap: 0.32rem;
  padding: 0.32rem 0.7rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(226, 232, 240, 0.86);
  cursor: pointer;
  font-size: 0.78rem;
  white-space: nowrap;
  transition: background 140ms ease, color 140ms ease;
}

.wb-direct-topbtn:hover {
  background: rgba(99, 102, 241, 0.18);
  color: #fff;
}

.wb-direct-bot-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(244, 114, 182, 0.32), rgba(168, 85, 247, 0.42));
  border: 1px solid rgba(244, 114, 182, 0.45);
  color: #fff;
  font-size: 0.78rem;
  font-weight: 600;
}

.wb-direct-bot-chip__name {
  max-width: 9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-direct-bot-chip__x {
  width: 1.05rem;
  height: 1.05rem;
  border-radius: 999px;
  border: none;
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
  cursor: pointer;
  font-size: 0.78rem;
  line-height: 1;
  padding: 0;
}

.wb-direct-msg__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.25rem;
}

.wb-direct-msg__skills,
.wb-direct-msg__atts {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.2rem;
}

.wb-direct-msg__skill-chip,
.wb-direct-msg__att-chip {
  font-size: 0.62rem;
  padding: 0.05rem 0.32rem;
  border-radius: 0.32rem;
  background: rgba(99, 102, 241, 0.22);
  color: rgba(199, 210, 254, 0.98);
  border: 1px solid rgba(165, 180, 252, 0.32);
}

.wb-direct-msg__att-chip {
  background: rgba(45, 212, 191, 0.18);
  color: #5eead4;
  border-color: rgba(45, 212, 191, 0.32);
}

.wb-direct-msg__err {
  margin: 0.35rem 0 0;
  color: rgba(252, 165, 165, 0.95);
  font-size: 0.78rem;
}

.wb-direct-cites {
  margin: 0.55rem 0 0;
  padding: 0.5rem 0.65rem;
  border-radius: 0.5rem;
  background: rgba(45, 212, 191, 0.07);
  border: 1px dashed rgba(45, 212, 191, 0.32);
}

.wb-direct-cites__head {
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  color: rgba(94, 234, 212, 0.95);
  font-weight: 700;
  margin-bottom: 0.3rem;
  text-transform: uppercase;
}

.wb-direct-cite {
  font-size: 0.78rem;
  color: rgba(226, 232, 240, 0.85);
}

.wb-direct-cite + .wb-direct-cite {
  margin-top: 0.15rem;
}

.wb-direct-cite__sum {
  display: inline-flex;
  align-items: center;
  gap: 0.32rem;
  cursor: pointer;
  padding: 0.18rem 0;
  list-style: none;
}

.wb-direct-cite__sum::-webkit-details-marker {
  display: none;
}

.wb-direct-cite__snip {
  margin: 0.2rem 0 0.4rem 1.3rem;
  padding: 0.32rem 0.55rem;
  border-left: 2px solid rgba(94, 234, 212, 0.45);
  background: rgba(2, 6, 23, 0.32);
  border-radius: 0.32rem;
  font-size: 0.74rem;
  color: rgba(203, 213, 225, 0.78);
  line-height: 1.45;
  white-space: pre-wrap;
}

.wb-direct-edit {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.wb-direct-edit__input {
  width: 100%;
  padding: 0.5rem 0.65rem;
  border-radius: 0.5rem;
  background: rgba(2, 6, 23, 0.7);
  border: 1px solid rgba(165, 180, 252, 0.45);
  color: #e2e8f0;
  font-family: inherit;
  font-size: inherit;
  resize: vertical;
  min-height: 4rem;
}

.wb-direct-edit__ops {
  display: flex;
  gap: 0.4rem;
  justify-content: flex-end;
}

.wb-direct-edit__btn {
  padding: 0.32rem 0.85rem;
  border-radius: 0.4rem;
  border: 1px solid transparent;
  cursor: pointer;
  font-size: 0.78rem;
}

.wb-direct-edit__btn--primary {
  background: linear-gradient(135deg, rgba(129, 140, 248, 0.55), rgba(99, 102, 241, 0.75));
  color: #fff;
  border-color: rgba(165, 180, 252, 0.55);
}

.wb-direct-edit__btn--ghost {
  background: rgba(255, 255, 255, 0.05);
  color: rgba(226, 232, 240, 0.85);
  border-color: rgba(255, 255, 255, 0.1);
}

.wb-direct-edit__btn--primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.wb-direct-box--drop {
  outline: 2px dashed rgba(165, 180, 252, 0.55);
  outline-offset: 4px;
  background: rgba(99, 102, 241, 0.1);
}

.wb-direct-send--stop {
  background: rgba(248, 113, 113, 0.32) !important;
  color: #fff !important;
  border: 1px solid rgba(248, 113, 113, 0.45) !important;
}

.wb-direct-tier-fab {
  position: fixed;
  left: clamp(0.85rem, 2.2vw, 1.35rem);
  bottom: clamp(0.85rem, 2.2vw, 1.35rem);
  z-index: 50;
  width: min(22rem, calc(100vw - 2rem));
  background: transparent;
  border: 0;
  box-shadow: none;
  padding: 0;
  animation: wb-direct-tier-fab-in 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes wb-direct-tier-fab-in {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 720px) {
  .wb-direct-tier-fab {
    left: 0.75rem;
    right: auto;
    bottom: 0.75rem;
    width: min(21rem, calc(100vw - 1.5rem));
  }
}

.wb-make-scene {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(0.72rem, 1.4vw, 1rem);
  padding-inline: clamp(1rem, 3vw, 3rem);
}

.wb-gear-layout--make .wb-make-scene {
  justify-content: center;
}

.wb-make-scene > .wb-plan,
.wb-make-scene > .wb-orch,
.wb-make-scene > .wb-handoff,
.wb-make-scene > .wb-composer-column,
.wb-make-scene > .wb-starters,
.wb-make-scene > .wb-foot,
.wb-make-scene > .wb-make-hero {
  width: min(100%, 64rem);
}

.wb-make-hero {
  margin: 0 0 clamp(0.6rem, 1.6vw, 1.2rem);
  text-align: center;
}

.wb-direct-hero,
.wb-voice-copy {
  max-width: 42rem;
}

.wb-direct-hero {
  position: relative;
  z-index: 1;
  width: min(42rem, 100%);
  text-align: center;
  transform-origin: left top;
  transition:
    width 0.46s cubic-bezier(0.22, 1, 0.36, 1),
    max-width 0.46s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.46s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.3s ease,
    margin 0.46s cubic-bezier(0.22, 1, 0.36, 1);
  animation: wb-direct-hero-enter 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

.wb-direct-empty-title {
  position: relative;
  z-index: 2;
  width: min(42rem, 100%);
  flex: 0 0 auto;
  margin-top: 0;
  text-align: center;
}

.wb-direct-main--empty .wb-direct-hero {
  flex: 0 0 auto;
  margin-bottom: clamp(0.9rem, 2.4vh, 1.4rem);
  opacity: 1;
  visibility: visible;
}

.wb-direct-main--empty .wb-direct-title {
  color: #f8fafc;
  text-shadow: 0 14px 42px rgba(15, 23, 42, 0.72);
}

.wb-direct-main--empty .wb-direct-sub {
  color: rgba(226, 232, 240, 0.68);
}

.wb-direct-hero--compact {
  width: auto;
  max-width: min(32rem, calc(100% - 0.5rem));
  align-self: flex-start;
  margin: 0.05rem 0 0.35rem clamp(0.2rem, 0.9vw, 0.7rem);
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  text-align: left;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: 0.01em;
  color: rgba(203, 213, 225, 0.78);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transform: translate3d(0, 0, 0);
  animation: wb-direct-hero-collapse 0.46s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes wb-direct-hero-enter {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.985);
    filter: blur(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
    filter: blur(0);
  }
}

@keyframes wb-direct-hero-collapse {
  from {
    opacity: 0.94;
    transform: translate3d(12%, 36%, 0) scale(1.35);
    filter: blur(2px);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0) scale(1);
    filter: blur(0);
  }
}

.wb-direct-kicker,
.wb-voice-kicker {
  margin: 0 0 0.45rem;
  color: rgba(165, 180, 252, 0.75);
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.wb-direct-title,
.wb-voice-title {
  margin: 0;
  color: #f8fafc;
  font-size: clamp(2rem, 5vw, 3.2rem);
  line-height: 1.08;
  letter-spacing: -0.05em;
  transition:
    font-size 0.46s cubic-bezier(0.22, 1, 0.36, 1),
    letter-spacing 0.46s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.3s ease;
}

.wb-direct-sub,
.wb-voice-sub {
  margin: 0.65rem 0 0;
  color: rgba(226, 232, 240, 0.58);
  font-size: clamp(0.95rem, 0.9rem + 0.22vw, 1.1rem);
  transition:
    opacity 0.28s ease,
    transform 0.36s cubic-bezier(0.22, 1, 0.36, 1),
    font-size 0.36s cubic-bezier(0.22, 1, 0.36, 1),
    margin 0.36s cubic-bezier(0.22, 1, 0.36, 1);
}

.wb-direct-box {
  position: relative;
  width: min(50rem, 100%);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  border-radius: 1.35rem;
  background: rgba(255, 255, 255, 0.075);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition:
    width 0.46s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.46s cubic-bezier(0.22, 1, 0.36, 1),
    margin 0.46s cubic-bezier(0.22, 1, 0.36, 1),
    border-radius 0.32s ease,
    background 0.32s ease,
    box-shadow 0.32s ease;
  animation: wb-direct-composer-enter 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

.wb-direct-main--empty .wb-direct-box {
  margin-top: 0.55rem;
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.24);
}

.wb-direct-main--chatting .wb-direct-box {
  width: min(54rem, 100%);
  margin-top: auto;
  transform: translateY(0);
  border-radius: 1.1rem;
  background: rgba(255, 255, 255, 0.062);
  animation: wb-direct-composer-drop 0.48s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes wb-direct-composer-enter {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes wb-direct-composer-drop {
  from {
    transform: translateY(-18px) scale(1.015);
    opacity: 0.82;
  }
  to {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
}

.wb-direct-box-main {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: end;
  gap: 0.55rem 0.65rem;
}

.wb-file-mention-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  min-height: 1.4rem;
}

.wb-file-mention-row--composer {
  margin: 0.35rem 1rem 0;
}

.wb-file-mention-token {
  display: inline-flex;
  align-items: center;
  max-width: min(22rem, 100%);
  padding: 0.16rem 0.48rem;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.13);
  border: 1px solid rgba(165, 180, 252, 0.18);
  color: #c4b5fd;
  font-size: 0.72rem;
  font-weight: 750;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-direct-llm-inline {
  justify-content: flex-end;
  align-self: end;
  margin-right: 0;
  max-width: min(42vw, 23rem);
}

.wb-direct-llm-inline .wb-mode-segment__btn {
  min-width: 2.85rem;
  padding-inline: 0.62rem;
}

.wb-dd-trigger--compact {
  max-width: 8.5rem;
  min-height: 1.92rem;
  padding-inline: 0.62rem;
}

.wb-direct-file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.wb-direct-attach {
  display: grid;
  place-items: center;
  width: 2.35rem;
  height: 2.35rem;
  flex-shrink: 0;
  margin-bottom: 0.12rem;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(226, 232, 240, 0.72);
  cursor: pointer;
  transition:
    color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.wb-direct-attach:hover:not(:disabled) {
  color: #f8fafc;
  background: rgba(255, 255, 255, 0.12);
}

.wb-direct-attach:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.wb-direct-attach__icon {
  width: 1.1rem;
  height: 1.1rem;
}

.wb-direct-attach:focus-visible {
  outline: 2px solid rgba(129, 140, 248, 0.65);
  outline-offset: 2px;
}

.wb-direct-file-stack {
  --att-overlap: 0.62rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0;
  min-height: 4.05rem;
  padding: 0.25rem 0.1rem 0.18rem 0.55rem;
}

.wb-direct-file-card {
  position: relative;
  display: grid;
  place-items: center;
  width: 3.15rem;
  height: 4.35rem;
  min-height: 0;
  margin-left: calc(var(--att-index, 0) * -1 * var(--att-overlap));
  padding: 0;
  border: 0;
  border-radius: 0.58rem;
  background: transparent;
  box-shadow: none;
  color: rgba(226, 232, 240, 0.92);
  transform: translateY(calc(var(--att-index, 0) * -0.12rem)) rotate(calc((var(--att-index, 0) - 1) * -6deg));
  transition:
    transform 0.22s ease,
    filter 0.22s ease;
  z-index: calc(20 + var(--att-index, 0));
}

.wb-direct-file-card:hover {
  transform: translateY(calc(var(--att-index, 0) * -0.12rem - 0.25rem)) rotate(calc((var(--att-index, 0) - 1) * -7deg));
  filter: brightness(1.08);
}

.wb-direct-file-card--ready {
  background: transparent;
}

.wb-direct-file-card--uploading {
  background: transparent;
}

.wb-direct-file-card--inline {
  background: transparent;
}

.wb-direct-file-card--error,
.wb-direct-file-card--skipped {
  background: transparent;
}

.wb-direct-file-card--more {
  opacity: 0.82;
  margin-left: -0.62rem;
  transform: translateY(-0.18rem) scale(0.96) rotate(6deg);
  z-index: 26;
}

.wb-direct-file-card__deck {
  position: relative;
  width: 3.05rem;
  height: 4.2rem;
  flex: 0 0 auto;
  transform: translateZ(0);
}

.wb-direct-file-card__deck-card {
  position: absolute;
  inset: 0;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 0.54rem;
  background: linear-gradient(145deg, #30333d, #22252d);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.22);
  transition: transform 0.22s ease, background 0.22s ease, border-color 0.22s ease;
}

.wb-direct-file-card__deck-card--back {
  display: none;
}

.wb-direct-file-card__deck-card--mid {
  display: none;
}

.wb-direct-file-card__deck-card--front {
  display: grid;
  place-items: center;
  transform: none;
  color: #aeb4c2;
}

.wb-direct-file-card:hover .wb-direct-file-card__deck-card--back {
  transform: translate(-0.28rem, 0.3rem) rotate(-11deg);
}

.wb-direct-file-card:hover .wb-direct-file-card__deck-card--mid {
  transform: translate(0.02rem, 0.08rem) rotate(-5deg);
}

.wb-direct-file-card:hover .wb-direct-file-card__deck-card--front {
  transform: none;
}

.wb-direct-file-card__deck-label,
.wb-direct-file-card__deck-plus {
  display: inline-grid;
  place-items: center;
  max-width: 2.2rem;
  transform: none;
  font-size: 0.54rem;
  font-weight: 850;
  letter-spacing: 0.04em;
  line-height: 1;
  text-transform: uppercase;
}

.wb-direct-file-card__deck-plus {
  color: #b9bfcc;
  font-size: 0.8rem;
  font-weight: 700;
}

.wb-direct-file-card--excel .wb-direct-file-card__deck-card--front {
  border-color: rgba(74, 222, 128, 0.18);
  background: linear-gradient(145deg, rgba(30, 82, 52, 0.9), rgba(31, 41, 55, 0.96));
  color: #a7f3d0;
}

.wb-direct-file-card--pdf .wb-direct-file-card__deck-card--front {
  border-color: rgba(248, 113, 113, 0.2);
  background: linear-gradient(145deg, rgba(91, 33, 33, 0.92), rgba(31, 41, 55, 0.96));
  color: #fecaca;
}

.wb-direct-file-card--word .wb-direct-file-card__deck-card--front {
  border-color: rgba(96, 165, 250, 0.22);
  background: linear-gradient(145deg, rgba(30, 58, 138, 0.84), rgba(31, 41, 55, 0.96));
  color: #bfdbfe;
}

.wb-direct-file-card--csv .wb-direct-file-card__deck-card--front,
.wb-direct-file-card--json .wb-direct-file-card__deck-card--front,
.wb-direct-file-card--text .wb-direct-file-card__deck-card--front {
  border-color: rgba(251, 191, 36, 0.2);
  background: linear-gradient(145deg, rgba(113, 63, 18, 0.88), rgba(31, 41, 55, 0.96));
  color: #fde68a;
}

.wb-direct-file-card__body {
  display: grid;
  min-width: 0;
  gap: 0.12rem;
}

.wb-direct-file-card__name {
  overflow: hidden;
  color: #f8fafc;
  font-size: 0.75rem;
  font-weight: 720;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-direct-file-card__order {
  display: inline-flex;
  margin-right: 0.32rem;
  color: rgba(165, 180, 252, 0.98);
  font-weight: 850;
}

.wb-direct-file-card__meta {
  overflow: hidden;
  font-size: 0.66rem;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-direct-file-card__meta {
  color: rgba(148, 163, 184, 0.88);
  font-variant-numeric: tabular-nums;
}

.wb-direct-file-card__state {
  position: absolute;
  right: 0.1rem;
  bottom: 0.1rem;
  display: grid;
  place-items: center;
  width: 1.05rem;
  height: 1.05rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.76);
  box-shadow: 0 5px 14px rgba(0, 0, 0, 0.24);
  font-size: 0.72rem;
  font-weight: 850;
  z-index: 3;
}

.wb-direct-file-card__check {
  color: #5eead4;
}

.wb-direct-file-card__warn {
  color: #fca5a5;
}

.wb-direct-file-card__spinner {
  width: 0.8rem;
  height: 0.8rem;
  border-radius: 999px;
  border: 1.5px solid rgba(165, 180, 252, 0.35);
  border-top-color: rgba(199, 210, 254, 0.95);
  animation: wb-direct-file-card-spin 0.85s linear infinite;
}

@keyframes wb-direct-file-card-spin {
  to {
    transform: rotate(360deg);
  }
}

.wb-direct-file-card-enter-active,
.wb-direct-file-card-leave-active {
  transition: opacity 0.24s ease, transform 0.34s cubic-bezier(0.18, 1.05, 0.28, 1);
}

.wb-direct-file-card-enter-from,
.wb-direct-file-card-leave-to {
  opacity: 0;
  transform: translateY(-1.8rem) rotate(-14deg) scale(0.9);
}

.wb-direct-file-card-move {
  transition: transform 0.28s cubic-bezier(0.18, 1.05, 0.28, 1);
}

.wb-direct-attach-hint {
  margin: 0;
  padding: 0 0.15rem;
  font-size: 0.7rem;
  line-height: 1.35;
  color: rgba(148, 163, 184, 0.85);
  text-align: left;
}

.wb-direct-file-card__remove {
  position: absolute;
  right: -0.18rem;
  top: -0.18rem;
  display: grid;
  place-items: center;
  width: 1.18rem;
  height: 1.18rem;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: rgba(31, 41, 55, 0.92);
  color: rgba(248, 250, 252, 0.58);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  z-index: 4;
}

.wb-direct-file-card__remove:hover:not(:disabled) {
  color: #fecaca;
  background: rgba(248, 113, 113, 0.14);
}

.wb-direct-file-card__remove:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.wb-composer-file-stack {
  margin: 0.45rem 0 0.2rem;
}

.wb-direct-input {
  width: 100%;
  min-height: 4.5rem;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: #f8fafc;
  font: inherit;
  font-size: 1rem;
  line-height: 1.5;
}

.wb-direct-input::placeholder {
  color: rgba(255, 255, 255, 0.34);
}

.wb-direct-send,
.wb-voice-primary,
.wb-voice-secondary {
  border: none;
  border-radius: 999px;
  padding: 0.65rem 1rem;
  background: #f8fafc;
  color: #0f172a;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
}

.wb-direct-send:disabled,
.wb-voice-primary:disabled,
.wb-voice-secondary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.wb-direct-suggestions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.55rem;
  animation: wb-direct-suggestions-in 0.55s cubic-bezier(0.22, 1, 0.36, 1) 0.08s both;
}

.wb-direct-suggestion {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 999px;
  padding: 0.45rem 0.8rem;
  background: rgba(255, 255, 255, 0.045);
  color: rgba(255, 255, 255, 0.68);
  cursor: pointer;
  font: inherit;
  font-size: 0.8rem;
  transition:
    transform 0.18s ease,
    background 0.18s ease,
    color 0.18s ease,
    border-color 0.18s ease;
}

.wb-direct-suggestion:hover {
  transform: translateY(-2px);
  background: rgba(255, 255, 255, 0.075);
  color: rgba(255, 255, 255, 0.9);
  border-color: rgba(255, 255, 255, 0.18);
}

@keyframes wb-direct-suggestions-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.wb-voice-thread {
  width: min(50rem, 100%);
  max-height: 12rem;
  overflow-y: auto;
  display: grid;
  gap: 0.5rem;
  text-align: left;
}

.wb-direct-thread {
  flex: 1;
  width: min(58rem, 100%);
  align-self: center;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  gap: 1.05rem;
  text-align: left;
  padding: 0.45rem clamp(0.2rem, 0.8vw, 0.7rem) 1rem;
  align-content: start;
  scroll-behavior: smooth;
  animation: wb-direct-thread-rise 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes wb-direct-thread-rise {
  from {
    opacity: 0;
    transform: translateY(20px);
    filter: blur(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
    filter: blur(0);
  }
}

.wb-voice-msg {
  padding: 0.65rem 0.8rem;
  border-radius: 0.85rem;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(248, 250, 252, 0.9);
}

.wb-direct-msg {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: start;
  gap: 0.78rem;
  padding: 0;
  color: rgba(248, 250, 252, 0.92);
  max-width: 100%;
  transform-origin: left top;
}

.wb-direct-msg--user,
.wb-voice-msg--user {
  justify-self: end;
  grid-template-columns: minmax(0, 1fr) auto;
  max-width: min(84%, 42rem);
  transform-origin: right top;
}

.wb-direct-msg--assistant {
  justify-self: start;
  max-width: min(90%, 49rem);
}

.wb-direct-msg__persona {
  display: grid;
  justify-items: center;
  gap: 0.34rem;
  min-width: 3.25rem;
  padding-top: 0.04rem;
}

.wb-direct-msg--user .wb-direct-msg__persona {
  grid-column: 2;
  grid-row: 1;
}

.wb-direct-msg__avatar {
  display: grid;
  place-items: center;
  width: 2.45rem;
  height: 2.45rem;
  border-radius: 0.55rem;
  background: rgba(51, 65, 85, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.22);
  color: rgba(248, 250, 252, 0.92);
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.02em;
  box-shadow: none;
}

.wb-direct-msg--user .wb-direct-msg__avatar {
  background: rgba(79, 70, 229, 0.88);
  border-color: rgba(199, 210, 254, 0.22);
}

.wb-direct-msg__name {
  max-width: 4.2rem;
  color: rgba(203, 213, 225, 0.58);
  font-size: 0.62rem;
  font-weight: 700;
  line-height: 1.15;
  text-align: center;
  letter-spacing: 0.045em;
}

.wb-direct-msg__stack {
  display: grid;
  justify-items: start;
  gap: 0.38rem;
  min-width: 0;
}

.wb-direct-msg--user .wb-direct-msg__stack {
  grid-column: 1;
  grid-row: 1;
  justify-items: end;
}

.wb-direct-msg__bubble {
  position: relative;
  min-width: min(8rem, 100%);
  padding: 0.86rem 1rem;
  border-radius: 0.54rem 1.22rem 1.22rem;
  background:
    linear-gradient(150deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.68)),
    rgba(2, 6, 23, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.09),
    0 18px 44px rgba(2, 6, 23, 0.22);
  overflow: hidden;
  backdrop-filter: blur(16px) saturate(126%);
}

.wb-direct-msg__bubble::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent 38%);
  pointer-events: none;
}

.wb-direct-msg--user .wb-direct-msg__bubble {
  border-radius: 1.22rem 0.54rem 1.22rem 1.22rem;
  background:
    linear-gradient(150deg, rgba(99, 102, 241, 0.5), rgba(37, 99, 235, 0.26)),
    rgba(30, 41, 59, 0.72);
  border-color: rgba(199, 210, 254, 0.28);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    0 18px 44px rgba(37, 99, 235, 0.18);
}

.wb-direct-msg--user .wb-direct-msg__bubble::before {
  background:
    radial-gradient(circle at 88% 0%, rgba(255, 255, 255, 0.14), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), transparent 44%);
}

.wb-direct-msg-flow-enter-active,
.wb-direct-msg-flow-leave-active {
  transition:
    opacity 0.36s ease,
    transform 0.42s cubic-bezier(0.22, 1, 0.36, 1),
    filter 0.32s ease;
}

.wb-direct-msg-flow-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.985);
  filter: blur(4px);
}

.wb-direct-msg-flow-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.99);
  filter: blur(3px);
}

.wb-direct-msg-flow-move {
  transition: transform 0.36s cubic-bezier(0.22, 1, 0.36, 1);
}

.wb-direct-msg--assistant:first-child,
.wb-direct-msg--assistant:nth-child(2) {
  animation: wb-direct-ai-stream-card 0.55s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes wb-direct-ai-stream-card {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.98);
    box-shadow: 0 0 0 rgba(99, 102, 241, 0);
  }
  45% {
    opacity: 1;
    box-shadow: 0 0 34px rgba(99, 102, 241, 0.18);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
    box-shadow: 0 12px 34px rgba(0, 0, 0, 0.12);
  }
}

.wb-direct-msg__role {
  display: inline-flex;
  align-items: center;
  gap: 0.32rem;
  color: rgba(226, 232, 240, 0.74);
  font-size: 0.66rem;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.wb-direct-msg__role::before {
  content: "";
  width: 0.34rem;
  height: 0.34rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.8);
  box-shadow: 0 0 12px rgba(148, 163, 184, 0.35);
}

.wb-direct-msg--user .wb-direct-msg__role {
  color: rgba(224, 231, 255, 0.86);
}

.wb-direct-msg--user .wb-direct-msg__role::before {
  background: #c7d2fe;
  box-shadow: 0 0 14px rgba(199, 210, 254, 0.55);
}

.wb-direct-msg--assistant .wb-direct-msg__role::before {
  background: #5eead4;
  box-shadow: 0 0 14px rgba(94, 234, 212, 0.45);
}

.wb-direct-msg__body {
  margin: 0;
  white-space: pre-wrap;
  color: rgba(248, 250, 252, 0.94);
  line-height: 1.72;
}

.wb-direct-error,
.wb-voice-error {
  margin: 0;
  color: rgba(252, 165, 165, 0.95);
  font-size: 0.82rem;
}

.wb-direct-new-row {
  margin: 0.35rem 0 0;
  display: flex;
  justify-content: flex-start;
}

.wb-direct-new-btn {
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(15, 23, 42, 0.4);
  color: rgba(226, 232, 240, 0.9);
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 140ms ease,
    color 140ms ease,
    border-color 140ms ease;
}

.wb-direct-new-btn:hover {
  background: rgba(51, 65, 85, 0.45);
  color: #f8fafc;
  border-color: rgba(148, 163, 184, 0.35);
}

.wb-direct-prefs-row {
  margin: 0.4rem 0 0;
  display: flex;
  justify-content: flex-end;
}

.wb-direct-prefs-btn {
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(15, 23, 42, 0.35);
  color: rgba(165, 180, 252, 0.88);
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 140ms ease,
    color 140ms ease,
    border-color 140ms ease;
}

.wb-direct-prefs-btn:hover {
  background: rgba(99, 102, 241, 0.2);
  color: #e0e7ff;
  border-color: rgba(165, 180, 252, 0.35);
}

.wb-direct-employee-row {
  margin: 0.55rem 0 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem 0.65rem;
}

.wb-direct-employee-label {
  margin: 0;
  font-size: 0.72rem;
  font-weight: 600;
  color: rgba(226, 232, 240, 0.82);
  flex: 0 0 auto;
}

.wb-direct-employee-select {
  min-width: 12rem;
  max-width: 100%;
  flex: 1 1 14rem;
  padding: 0.28rem 0.5rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(15, 23, 42, 0.55);
  color: rgba(248, 250, 252, 0.92);
  font-size: 0.75rem;
  cursor: pointer;
}

.wb-direct-employee-select:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.wb-direct-employee-hint {
  margin: 0;
  flex: 1 0 100%;
  font-size: 0.65rem;
  line-height: 1.45;
  color: rgba(148, 163, 184, 0.88);
}

.wb-voice-orb-wrap {
  position: relative;
  display: grid;
  place-items: center;
  width: min(18rem, 48vw);
  aspect-ratio: 1;
  overflow: visible;
  isolation: isolate;
}

.wb-voice-orb {
  position: relative;
  z-index: 1;
  width: 72%;
  aspect-ratio: 1;
  border: none;
  background: transparent;
  cursor: pointer;
  display: grid;
  place-items: center;
  padding: 0;
}

.wb-voice-orb:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.wb-voice-orb.wb-voice-orb--placeholder:disabled {
  visibility: hidden;
  opacity: 0;
  pointer-events: none;
}

.wb-voice-orb--listening {
  filter: drop-shadow(0 0 24px rgba(45, 212, 191, 0.45));
}

.wb-voice-orb--thinking {
  filter: drop-shadow(0 0 24px rgba(255, 80, 80, 0.45));
}

.wb-voice-orb--summary {
  filter: drop-shadow(0 0 28px rgba(255, 215, 0, 0.5));
}

.wb-voice-transcript {
  width: min(38rem, 100%);
  margin: 0;
  padding: 0.75rem 1rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(226, 232, 240, 0.82);
}

.wb-voice-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.55rem;
}

.wb-voice-secondary {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(248, 250, 252, 0.88);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.wb-voice-fallback {
  width: min(34rem, 100%);
  resize: none;
  border-radius: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.045);
  color: #f8fafc;
  font: inherit;
  padding: 0.75rem 0.9rem;
  outline: none;
}

@media (min-width: 920px) {
  .wb-voice-scene {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
  }

  .wb-voice-orb-wrap {
    width: min(17rem, 28vw);
  }

  .wb-voice-copy,
  .wb-voice-transcript,
  .wb-voice-thread,
  .wb-voice-actions,
  .wb-voice-fallback,
  .wb-voice-error {
    width: min(42rem, 100%);
  }

  .wb-voice-actions {
    justify-content: center;
  }

  .wb-direct-scene {
    justify-content: center;
    padding-inline: clamp(2rem, 5vw, 5rem);
  }
}

.wb-plan {
  width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
  border-radius: 1.6rem;
}

.wb-plan-surface {
  position: relative;
  border-radius: 1.75rem;
  padding: 1.25rem 1.5rem 1.35rem;
  border: none;
  background:
    radial-gradient(120% 90% at 12% 0%, rgba(99, 102, 241, 0.14), transparent 52%),
    radial-gradient(90% 70% at 88% 12%, rgba(56, 189, 248, 0.08), transparent 48%),
    rgba(15, 23, 42, 0.38);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow:
    0 28px 56px -24px rgba(0, 0, 0, 0.45),
    0 0 1px rgba(255, 255, 255, 0.04) inset;
}

.wb-plan-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
  padding-bottom: 0.85rem;
  border-bottom: none;
}

.wb-plan-title {
  margin: 0;
  font-size: clamp(1rem, 0.95rem + 0.2vw, 1.12rem);
  font-weight: 600;
  color: #f4f4f5;
}

.wb-plan-close {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.45);
  font-size: 1.35rem;
  line-height: 1;
  cursor: pointer;
  padding: 0.15rem 0.35rem;
  border-radius: 0.35rem;
}

.wb-plan-close:hover {
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.06);
}

.wb-plan-kicker {
  margin: 0 0 0.95rem;
  font-size: clamp(0.8rem, 0.76rem + 0.12vw, 0.88rem);
  line-height: 1.45;
  color: rgba(191, 219, 254, 0.72);
}

.wb-plan-loading-block {
  margin: 0 0 0.75rem;
}

.wb-plan-loading-track {
  height: 3px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
  margin-bottom: 0.4rem;
}

.wb-plan-loading-bar {
  height: 100%;
  width: 42%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    rgba(99, 102, 241, 0.15),
    rgba(129, 140, 248, 0.95),
    rgba(56, 189, 248, 0.85),
    rgba(99, 102, 241, 0.15)
  );
  background-size: 200% 100%;
  animation: wb-plan-loading-shimmer 1.15s ease-in-out infinite;
}

@keyframes wb-plan-loading-shimmer {
  0% {
    transform: translateX(-100%);
    background-position: 0% 50%;
  }
  100% {
    transform: translateX(240%);
    background-position: 100% 50%;
  }
}

.wb-plan-thread {
  list-style: none;
  margin: 0 0 1rem;
  padding: 0.5rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  max-height: min(44vh, 24rem);
  overflow-y: auto;
  border-top: none;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.35) transparent;
}

.wb-plan-thread::-webkit-scrollbar {
  width: 6px;
}

.wb-plan-thread::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.28);
  border-radius: 999px;
}

.wb-plan-msg {
  border-radius: 1rem;
  padding: 0.65rem 0.9rem;
  border: none;
  transition: box-shadow 0.22s ease;
}

.wb-plan-msg--user {
  margin-right: 1.35rem;
  background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 12px 32px -18px rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.wb-plan-msg--assistant {
  margin-left: 0.35rem;
  background: rgba(30, 41, 59, 0.42);
  box-shadow: 0 16px 40px -22px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.wb-plan-msg-assistant-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.65rem 0.75rem;
  align-items: start;
}

@media (max-width: 720px) {
  .wb-plan-msg-assistant-grid {
    grid-template-columns: 1fr;
  }
}

.wb-plan-diagram-col {
  position: relative;
  min-width: 0;
  min-height: 5rem;
  border-radius: 0.9rem;
  border: none;
  background: rgba(30, 41, 59, 0.5);
  padding: 0.55rem 0.6rem;
  overflow: auto;
  max-height: min(40vh, 22rem);
  box-shadow: 0 12px 28px -16px rgba(0, 0, 0, 0.35);
}

.wb-plan-diagram-fallback {
  margin: 0;
  padding: 0.5rem 0.35rem;
  font-size: 0.82rem;
  line-height: 1.45;
  color: rgba(191, 219, 254, 0.65);
}

.wb-plan-diagram-preview-open {
  position: absolute;
  top: 0.4rem;
  left: 0.45rem;
  z-index: 2;
  margin: 0;
  padding: 0.22rem 0.5rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(15, 23, 42, 0.88);
  color: rgba(226, 232, 240, 0.95);
  font: inherit;
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.wb-plan-diagram-preview-open:hover,
.wb-plan-diagram-preview-open:focus-visible {
  border-color: rgba(165, 180, 252, 0.55);
  background: rgba(30, 27, 75, 0.92);
  color: #fff;
  outline: none;
}

.wb-plan-diagram-host {
  min-height: 3rem;
  display: block;
  max-width: 100%;
  overflow: auto;
  padding-bottom: 0.25rem;
}

.wb-plan-diagram-host--with-preview {
  padding-top: 1.85rem;
}

.wb-plan-diagram-host :deep(svg) {
  max-width: none;
  min-width: min(34rem, 100%);
  height: auto;
}

.wb-plan-diagram-err {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  line-height: 1.35;
  color: #fecaca;
}

.wb-plan-diagram-preview-backdrop {
  position: fixed;
  inset: 0;
  z-index: 11020;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(0.65rem, 2vw, 1.25rem);
  background: rgba(2, 6, 23, 0.78);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.wb-plan-diagram-preview-dialog {
  display: flex;
  flex-direction: column;
  width: min(96vw, 112rem);
  max-height: min(92vh, 120rem);
  border-radius: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: #0b1220;
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.35),
    0 24px 64px rgba(0, 0, 0, 0.55);
  overflow: hidden;
}

.wb-plan-diagram-preview-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 0.65rem 0.5rem 0.85rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(15, 23, 42, 0.65);
}

.wb-plan-diagram-preview-title {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 600;
  color: rgba(248, 250, 252, 0.95);
}

.wb-plan-diagram-preview-close {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(248, 250, 252, 0.92);
  font: inherit;
  font-size: 1.35rem;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}

.wb-plan-diagram-preview-close:hover,
.wb-plan-diagram-preview-close:focus-visible {
  background: rgba(255, 255, 255, 0.16);
  outline: none;
  transform: scale(1.04);
}

.wb-plan-diagram-preview-body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.wb-plan-diagram-preview-toolbar {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.65rem;
  padding: 0.35rem 0.65rem 0.45rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(15, 23, 42, 0.45);
}

.wb-plan-preview-tool {
  margin: 0;
  padding: 0.28rem 0.55rem;
  border-radius: 0.45rem;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(30, 41, 59, 0.75);
  color: rgba(226, 232, 240, 0.95);
  font: inherit;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.14s ease,
    border-color 0.14s ease;
}

.wb-plan-preview-tool:hover,
.wb-plan-preview-tool:focus-visible {
  border-color: rgba(165, 180, 252, 0.5);
  background: rgba(51, 65, 85, 0.85);
  outline: none;
}

.wb-plan-preview-tool--primary {
  border-color: rgba(129, 140, 248, 0.45);
  background: rgba(67, 56, 202, 0.35);
}

.wb-plan-preview-hint {
  font-size: 0.72rem;
  color: rgba(148, 163, 184, 0.88);
  margin-left: auto;
}

@media (max-width: 640px) {
  .wb-plan-preview-hint {
    width: 100%;
    margin-left: 0;
  }
}

.wb-plan-diagram-preview-viewport {
  flex: 1 1 auto;
  min-height: min(72vh, 52rem);
  overflow: hidden;
  position: relative;
  touch-action: none;
  user-select: none;
  cursor: grab;
}

.wb-plan-diagram-preview-viewport--drag {
  cursor: grabbing;
}

.wb-plan-diagram-preview-panlayer {
  display: inline-block;
  vertical-align: top;
  will-change: transform;
}

.wb-plan-diagram-preview-canvas {
  padding: clamp(0.5rem, 1vw, 1rem);
  outline: none;
}

.wb-plan-diagram-preview-canvas svg {
  display: block;
  max-width: none;
  width: auto;
  height: auto;
}

.wb-plan-diagram-preview-empty {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.5;
  color: rgba(226, 232, 240, 0.72);
}

.wb-plan-aside-col {
  flex-shrink: 0;
  width: 4.5rem;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 720px) {
  .wb-plan-aside-col {
    width: 100%;
    justify-content: flex-start;
  }
}

.wb-plan-details {
  width: 100%;
  max-width: 12rem;
  border-radius: 0.75rem;
  border: none;
  background: rgba(15, 23, 42, 0.35);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  overflow: hidden;
  box-shadow: 0 8px 24px -14px rgba(0, 0, 0, 0.35);
}

@media (max-width: 720px) {
  .wb-plan-details {
    max-width: none;
  }
}

.wb-plan-details-summary {
  cursor: pointer;
  list-style: none;
  padding: 0.45rem 0.6rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: rgba(191, 219, 254, 0.95);
  user-select: none;
  transition: color 0.2s ease, background 0.2s ease;
  border-radius: 0.5rem;
}

.wb-plan-details-summary:hover {
  color: #f8fafc;
  background: rgba(255, 255, 255, 0.06);
}

.wb-plan-details-summary::-webkit-details-marker {
  display: none;
}

.wb-plan-details-expand {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.32s cubic-bezier(0.4, 0, 0.2, 1);
}

.wb-plan-details[open] .wb-plan-details-expand {
  grid-template-rows: 1fr;
}

.wb-plan-details-expand-inner {
  min-height: 0;
  overflow: hidden;
}

.wb-plan-details-body {
  padding: 0 0.55rem 0.55rem;
  font-size: clamp(0.82rem, 0.78rem + 0.1vw, 0.9rem);
  line-height: 1.5;
  color: rgba(248, 250, 252, 0.9);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: min(38vh, 18rem);
  overflow-y: auto;
  opacity: 0.92;
  transition: opacity 0.25s ease;
}

.wb-plan-details[open] .wb-plan-details-body {
  opacity: 1;
}

.wb-plan-msg-role {
  display: block;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.35);
  margin-bottom: 0.25rem;
}

.wb-plan-msg-body {
  font-size: clamp(0.86rem, 0.82rem + 0.1vw, 0.95rem);
  line-height: 1.5;
  color: rgba(248, 250, 252, 0.92);
  white-space: pre-wrap;
  word-break: break-word;
}

.wb-plan-error {
  margin: 0 0 0.65rem;
  font-size: 0.86rem;
  color: #fecaca;
}

.wb-plan-quick {
  margin: 0 0 0.75rem;
  padding: 0.5rem 0;
  border-radius: 0;
  border: none;
  background: transparent;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  box-shadow: none;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 1rem 1.35rem;
}

.wb-plan-quick-main {
  flex: 1 1 auto;
  min-width: min(100%, 18rem);
}

.wb-plan-quick-aside {
  flex: 0 0 auto;
  align-self: flex-start;
  padding-top: 0.1rem;
}

.wb-plan-quick-auto {
  padding: 0.48rem 0.95rem;
  border-radius: 0.55rem;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(248, 250, 252, 0.95);
  font: inherit;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.2s ease, box-shadow 0.2s ease;
}

.wb-plan-quick-auto:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.16);
  box-shadow: 0 8px 22px -12px rgba(0, 0, 0, 0.35);
}

.wb-plan-quick-auto:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .wb-plan-quick {
    flex-direction: column;
  }

  .wb-plan-quick-aside {
    width: 100%;
    padding-top: 0;
  }

  .wb-plan-quick-auto {
    width: 100%;
  }
}

.wb-plan-quick-block {
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: none;
}

.wb-plan-quick-block:last-of-type {
  margin-bottom: 0.35rem;
  padding-bottom: 0;
}

.wb-plan-quick-title {
  font-size: 0.78rem;
  font-weight: 600;
  color: rgba(191, 219, 254, 0.92);
  margin-bottom: 0.35rem;
}

.wb-plan-quick-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.wb-plan-other-wrap {
  margin-top: 0.45rem;
  width: 100%;
}

.wb-plan-other-input {
  display: block;
  width: 100%;
  box-sizing: border-box;
  margin: 0;
  padding: 0.5rem 0.65rem;
  border-radius: 0.65rem;
  border: none;
  background: rgba(0, 0, 0, 0.2);
  color: #ececec;
  font: inherit;
  font-size: 0.84rem;
  line-height: 1.45;
  resize: vertical;
  min-height: 2.5rem;
  max-height: 5.5rem;
  box-shadow: 0 8px 20px -12px rgba(0, 0, 0, 0.35);
}

.wb-plan-other-input::placeholder {
  color: rgba(148, 163, 184, 0.65);
}

.wb-plan-other-input:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.22), 0 8px 20px -12px rgba(0, 0, 0, 0.35);
}

.wb-plan-chip {
  padding: 0.32rem 0.65rem;
  border-radius: 999px;
  border: none;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(248, 250, 252, 0.9);
  font: inherit;
  font-size: 0.8rem;
  cursor: pointer;
  transition:
    background 0.22s ease,
    box-shadow 0.22s ease,
    transform 0.2s cubic-bezier(0.34, 1.2, 0.64, 1);
}

.wb-plan-chip:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.13);
}

.wb-plan-chip--on {
  background: rgba(99, 102, 241, 0.35);
  box-shadow: 0 8px 20px -10px rgba(99, 102, 241, 0.55);
  transform: scale(1.02);
}

.wb-plan-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.wb-plan-summary-card {
  margin: 0 0 0.85rem;
  padding: 0.9rem 1rem;
  border-radius: 0.9rem;
  border: 1px solid rgba(129, 140, 248, 0.2);
  background:
    radial-gradient(circle at 18% 0%, rgba(129, 140, 248, 0.16), transparent 16rem),
    rgba(15, 23, 42, 0.46);
  box-shadow: 0 16px 34px -24px rgba(0, 0, 0, 0.58);
}

.wb-plan-summary-kicker {
  margin: 0 0 0.4rem;
  color: rgba(165, 180, 252, 0.9);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.wb-plan-summary-title {
  margin: 0 0 0.45rem;
  color: #f8fafc;
  font-size: clamp(1rem, 0.94rem + 0.22vw, 1.18rem);
  line-height: 1.35;
}

.wb-plan-summary-body,
.wb-plan-summary-source {
  margin: 0;
  color: rgba(226, 232, 240, 0.84);
  font-size: 0.88rem;
  line-height: 1.55;
  white-space: pre-wrap;
}

.wb-plan-summary-source {
  margin-top: 0.65rem;
  padding-top: 0.55rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(148, 163, 184, 0.78);
  font-size: 0.78rem;
}

.wb-plan-quick-send {
  width: 100%;
  margin-top: 0.15rem;
  padding: 0.42rem 0.85rem;
  font-size: 0.86rem;
}

.wb-plan-reply-hint {
  margin: 0.35rem 0 0.65rem;
  font-size: 0.78rem;
  line-height: 1.45;
  color: rgba(148, 163, 184, 0.85);
}

.wb-plan-reply-fold {
  margin: 0 0 0.75rem;
  border-radius: 0.85rem;
  border: none;
  background: rgba(15, 23, 42, 0.28);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  overflow: hidden;
  box-shadow: 0 12px 28px -18px rgba(0, 0, 0, 0.35);
}

.wb-plan-reply-fold__summary {
  cursor: pointer;
  list-style: none;
  padding: 0.45rem 0.7rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: rgba(191, 219, 254, 0.75);
  user-select: none;
  transition: color 0.2s ease, background 0.2s ease;
  border-radius: 0.5rem;
}

.wb-plan-reply-fold__summary:hover {
  color: rgba(248, 250, 252, 0.92);
  background: rgba(255, 255, 255, 0.05);
}

.wb-plan-reply-fold__summary::-webkit-details-marker {
  display: none;
}

.wb-plan-reply-expand {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.32s cubic-bezier(0.4, 0, 0.2, 1);
}

.wb-plan-reply-fold[open] .wb-plan-reply-expand {
  grid-template-rows: 1fr;
}

.wb-plan-reply-expand-inner {
  min-height: 0;
  overflow: hidden;
}

.wb-plan-reply {
  display: block;
  width: 100%;
  box-sizing: border-box;
  margin: 0;
  padding: 0.5rem 0.65rem;
  border-radius: 0 0 0.75rem 0.75rem;
  border: none;
  border-top: none;
  background: rgba(0, 0, 0, 0.18);
  color: #ececec;
  font: inherit;
  font-size: 0.88rem;
  line-height: 1.45;
  resize: vertical;
  min-height: 2.75rem;
  max-height: 6rem;
}

.wb-plan-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.wb-plan-secondary {
  padding: 0.45rem 0.95rem;
  border-radius: 0.55rem;
  border: none;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.88);
  font: inherit;
  font-size: 0.88rem;
  cursor: pointer;
}

.wb-plan-secondary:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
}

.wb-plan-secondary:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.wb-plan-primary {
  padding: 0.45rem 1rem;
  border-radius: 0.5rem;
  border: none;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
}

.wb-plan-primary:hover:not(:disabled) {
  filter: brightness(1.06);
}

.wb-plan-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.wb-plan-autopilot {
  background: linear-gradient(135deg, #10b981, #059669);
}

.wb-plan-autopilot-error {
  margin: 0.4rem 0 0;
  font-size: 0.78rem;
  color: #fca5a5;
}

.wb-plan-checklist-title {
  margin: 0 0 0.5rem;
  font-size: 0.92rem;
  font-weight: 600;
  color: rgba(224, 231, 255, 0.95);
}

.wb-plan-checklist-flow {
  margin: 0 0 0.85rem;
  padding: 0.5rem;
  border: 1px solid rgba(129, 140, 248, 0.18);
  border-radius: 0.75rem;
  background: rgba(15, 23, 42, 0.42);
  overflow-x: auto;
  max-width: 100%;
}

.wb-plan-checklist-flow :deep(svg) {
  max-width: none;
  min-width: min(38rem, 100%);
  height: auto;
}

.wb-plan-checklist-details {
  margin: 0 0 0.85rem;
  color: rgba(203, 213, 225, 0.9);
}

.wb-plan-checklist-details > summary {
  cursor: pointer;
  width: fit-content;
  margin-bottom: 0.45rem;
  color: rgba(165, 180, 252, 0.95);
  font-size: 0.82rem;
}

.wb-plan-checklist-ol {
  margin: 0 0 0.85rem;
  padding-left: 1.25rem;
  color: rgba(248, 250, 252, 0.9);
  font-size: 0.9rem;
  line-height: 1.55;
}

.wb-plan-checklist-li {
  margin-bottom: 0.35rem;
}

.wb-plan-loading-lead {
  margin: 0 0 0.45rem;
  font-size: 0.84rem;
  font-weight: 600;
  color: rgba(226, 232, 240, 0.92);
}

.wb-plan-loading-steps {
  margin: 0;
  padding: 0 0 0 1.15rem;
  display: flex;
  flex-direction: column;
  gap: 0.28rem;
  font-size: 0.78rem;
  line-height: 1.45;
  color: rgba(148, 163, 184, 0.88);
  list-style: decimal;
}

.wb-plan-loading-steps__li {
  padding-left: 0.15rem;
  transition: color 0.2s ease, opacity 0.2s ease;
}

.wb-plan-loading-steps__li--pending {
  opacity: 0.55;
}

.wb-plan-loading-steps__li--active {
  color: rgba(147, 197, 253, 0.98);
  font-weight: 600;
  opacity: 1;
  list-style-type: decimal;
}

.wb-plan-loading-steps__li--active::marker {
  color: rgba(129, 140, 248, 0.95);
}

.wb-plan-loading-steps__li--done {
  color: rgba(148, 163, 184, 0.72);
  opacity: 0.85;
}

.wb-plan-loading {
  margin: 0;
  font-size: 0.82rem;
  color: rgba(147, 197, 253, 0.88);
}

/* 面板入场 */
.wb-plan-shell-enter-active {
  transition:
    opacity 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.wb-plan-shell-enter-from {
  opacity: 0;
  transform: translateY(10px) scale(0.99);
}

.wb-plan-shell-enter-to {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.wb-plan-shell-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.wb-plan-shell-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

/* 消息列表 */
.wb-plan-msg-enter-active {
  transition:
    opacity 0.28s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.wb-plan-msg-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.wb-plan-msg-move {
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

@media (prefers-reduced-motion: reduce) {
  .wb-plan-shell-enter-active,
  .wb-plan-shell-leave-active,
  .wb-plan-msg-enter-active,
  .wb-plan-msg-move,
  .wb-plan-details-expand,
  .wb-plan-reply-expand,
  .wb-plan-msg,
  .wb-plan-chip,
  .wb-plan-details-summary,
  .wb-plan-reply-fold__summary,
  .wb-plan-details-body {
    transition: none !important;
  }

  .wb-plan-loading-bar {
    animation: none !important;
    transform: none !important;
    width: 100%;
    opacity: 0.65;
  }

  .wb-plan-loading-steps__li--pending,
  .wb-plan-loading-steps__li--active {
    opacity: 1;
    font-weight: 500;
    color: rgba(148, 163, 184, 0.88);
  }

  .wb-plan-shell-enter-from,
  .wb-plan-shell-leave-to,
  .wb-plan-msg-enter-from {
    opacity: 1;
    transform: none;
  }

  .wb-plan-details[open] .wb-plan-details-expand,
  .wb-plan-reply-fold[open] .wb-plan-reply-expand {
    transition: none;
  }

  .wb-plan-chip--on {
    transform: none;
  }
}

.wb-orch {
  width: 100%;
  border-radius: 0.95rem;
  border: 1px solid rgba(52, 211, 153, 0.28);
  background: linear-gradient(180deg, rgba(16, 185, 129, 0.1), rgba(15, 23, 42, 0.22));
  padding: 0.85rem 1rem 0.9rem;
}

.wb-orch-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.wb-orch-title {
  margin: 0;
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(167, 243, 208, 0.85);
}

.wb-orch-percent {
  color: rgba(167, 243, 208, 0.78);
  font-size: 0.76rem;
  font-variant-numeric: tabular-nums;
}

.wb-orch-progress {
  position: relative;
  height: 0.42rem;
  margin-bottom: 0.75rem;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
}

.wb-orch-progress__bar {
  position: absolute;
  inset: 0 auto 0 0;
  width: 0%;
  border-radius: inherit;
  background: linear-gradient(90deg, #34d399, #a7f3d0);
  transition: width 0.35s ease;
}

.wb-orch-script-hint {
  margin: 0 0 0.65rem;
  padding: 0.55rem 0.65rem;
  border-radius: 0.55rem;
  font-size: 0.8rem;
  line-height: 1.45;
  color: rgba(226, 232, 240, 0.88);
  background: rgba(2, 6, 23, 0.35);
  border: 1px solid rgba(94, 234, 212, 0.22);
}

.wb-steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  align-items: flex-start;
}

.wb-step {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  min-width: 0;
  max-width: 100%;
  font-size: clamp(0.82rem, 0.78rem + 0.12vw, 0.9rem);
  color: rgba(255, 255, 255, 0.45);
}

.wb-step-dot {
  flex-shrink: 0;
  width: 0.55rem;
  height: 0.55rem;
  margin-top: 0.32rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.22);
}

.wb-step-body {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.wb-step-label {
  font-weight: 600;
  color: rgba(255, 255, 255, 0.55);
}

.wb-step-msg {
  font-size: 0.78rem;
  line-height: 1.35;
  color: rgba(255, 255, 255, 0.38);
  word-break: break-word;
}

.wb-step-since {
  font-size: 0.72rem;
  color: rgba(251, 191, 36, 0.6);
  font-variant-numeric: tabular-nums;
}

.wb-step-slow {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.3);
  font-style: italic;
}

.wb-step--pending .wb-step-dot {
  background: rgba(255, 255, 255, 0.18);
}

.wb-step--running .wb-step-dot {
  background: #fbbf24;
  box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.25);
}

.wb-step--running .wb-step-label {
  color: #fde68a;
}

.wb-step--done .wb-step-dot {
  background: #34d399;
}

.wb-step--done .wb-step-label {
  color: rgba(167, 243, 208, 0.95);
}

.wb-step--error .wb-step-dot {
  background: #f87171;
}

.wb-step--error .wb-step-label {
  color: #fecaca;
}

.wb-orch-warn {
  margin: 0.65rem 0 0;
  font-size: 0.78rem;
  line-height: 1.4;
  color: rgba(253, 224, 71, 0.88);
}

.wb-script-result {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  margin-top: 0.75rem;
  padding-top: 0.65rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.wb-script-result__title {
  margin: 0 0.35rem 0 0;
  color: rgba(226, 232, 240, 0.9);
  font-size: 0.82rem;
}

.wb-script-download {
  display: inline-flex;
  align-items: center;
  padding: 0.32rem 0.7rem;
  border-radius: 999px;
  color: #ccfbf1;
  background: rgba(20, 184, 166, 0.18);
  text-decoration: none;
  font-size: 0.8rem;
  font-weight: 700;
}

.wb-script-log {
  margin-top: 0.55rem;
  color: rgba(203, 213, 225, 0.82);
  font-size: 0.78rem;
}

.wb-script-log summary {
  cursor: pointer;
  width: fit-content;
}

.wb-script-log pre {
  max-height: 9rem;
  overflow: auto;
  margin: 0.45rem 0 0;
  padding: 0.6rem 0.7rem;
  border-radius: 0.65rem;
  background: rgba(0, 0, 0, 0.28);
  white-space: pre-wrap;
}

.wb-handoff {
  border-radius: 0;
  border: 0;
  border-left: 2px solid rgba(129, 140, 248, 0.5);
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.12), rgba(15, 23, 42, 0.08));
  padding: 0.85rem 0 0.9rem 1rem;
  box-shadow: none;
}

.wb-handoff-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.wb-handoff-title {
  margin: 0;
  font-size: clamp(1rem, 0.95rem + 0.2vw, 1.12rem);
  font-weight: 600;
  color: #f4f4f5;
}

.wb-handoff-close {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 999px;
  font-size: 1.25rem;
  line-height: 1;
  color: rgba(255, 255, 255, 0.55);
  background: rgba(255, 255, 255, 0.06);
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.wb-handoff-close:hover {
  color: rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.1);
}

.wb-handoff-intent {
  margin: 0 0 0.65rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: rgba(199, 210, 254, 0.95);
}

.wb-handoff-fields {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.65rem;
  min-width: 0;
}

.wb-handoff-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.55);
  margin-top: 0.35rem;
}

.wb-handoff-label:first-of-type {
  margin-top: 0;
}

.wb-handoff-req {
  font-weight: 500;
  color: rgba(252, 165, 165, 0.95);
}

.wb-handoff-opt {
  font-weight: 500;
  color: rgba(255, 255, 255, 0.35);
}

.wb-handoff-input,
.wb-handoff-textarea {
  box-sizing: border-box;
  width: 100%;
  margin: 0;
  padding: 0.55rem 0.7rem;
  border-radius: 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.25);
  color: #f4f4f5;
  font: inherit;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  max-width: 100%;
}

.wb-handoff-textarea {
  line-height: 1.5;
  resize: vertical;
  min-height: 4.5rem;
  max-height: 7rem;
  overflow: auto;
}

.wb-handoff-textarea--sm {
  min-height: 3.25rem;
  max-height: 5.5rem;
}

.wb-handoff-input::placeholder,
.wb-handoff-textarea::placeholder {
  color: rgba(255, 255, 255, 0.28);
}

.wb-handoff-input:focus,
.wb-handoff-textarea:focus {
  border-color: rgba(165, 180, 252, 0.45);
  box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.2);
}

.wb-handoff-error {
  margin: 0 0 0.5rem;
  font-size: 0.82rem;
  line-height: 1.4;
  color: #fca5a5;
}

.wb-handoff-run {
  margin: 0 0 0.75rem;
  padding: 0.65rem 0.75rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(129, 140, 248, 0.22);
  background: rgba(15, 23, 42, 0.45);
}

.wb-handoff-run__status {
  margin: 0 0 0.5rem;
  font-size: 0.84rem;
  line-height: 1.45;
  color: rgba(226, 232, 240, 0.92);
}

.wb-handoff-run__boot {
  margin: 0;
  font-size: 0.78rem;
  line-height: 1.45;
  color: rgba(148, 163, 184, 0.9);
}

.wb-handoff-run__bar-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.45rem;
}

.wb-handoff-run__bar {
  flex: 1 1 auto;
  display: block;
  height: 0.35rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.wb-handoff-run__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(129, 140, 248, 0.85), rgba(56, 189, 248, 0.75));
  transition: width 0.35s ease;
}

.wb-handoff-run__counts {
  flex: 0 0 auto;
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
  color: rgba(186, 230, 253, 0.85);
}

.wb-handoff-run__steps {
  margin: 0.35rem 0 0;
  padding-left: 0;
}

.wb-handoff-foot {
  margin: 0.65rem 0 0;
  font-size: 0.75rem;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.38);
}

.wb-handoff-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1rem;
  justify-content: flex-start;
}

.wb-handoff-actions__timing {
  margin-left: auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.15rem;
  font-size: 0.78rem;
  line-height: 1.35;
  color: rgba(255, 255, 255, 0.48);
  min-width: 0;
}

.wb-handoff-actions__timing-line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: baseline;
  justify-content: flex-end;
}

.wb-handoff-actions__k {
  flex-shrink: 0;
  color: rgba(255, 255, 255, 0.36);
}

.wb-handoff-actions__v {
  font-variant-numeric: tabular-nums;
  color: rgba(226, 232, 240, 0.9);
  max-width: min(100%, 28rem);
  text-align: right;
  word-break: break-word;
}

.wb-handoff-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.55rem 1.15rem;
  border: none;
  border-radius: 999px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  color: #121212;
  background: #fff;
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.wb-handoff-primary:hover:not(:disabled) {
  opacity: 0.92;
  transform: scale(1.02);
}

.wb-handoff-primary:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  transform: none;
}

.wb-handoff-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.55rem 1.15rem;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 999px;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.88);
  background: transparent;
  cursor: pointer;
  transition: opacity 0.15s ease, border-color 0.15s ease;
}

.wb-handoff-secondary:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.4);
}

.wb-handoff-secondary:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.wb-workflow-link__name {
  margin: 0 0 0.65rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.88);
  overflow-wrap: anywhere;
}

.wb-workflow-link__actions {
  margin-top: 0.5rem;
}

.wb-composer-column {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.5rem;
}

/* 主输入：近似 ChatGPT 输入条 — 深底、大圆角、轻边 */
.wb-composer-panel {
  border-radius: 1.625rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: #2f2f2f;
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.2),
    0 10px 40px rgba(0, 0, 0, 0.35);
  /* visible：自选厂商/模型下拉在 footer 内向上展开，hidden 会裁切面板 */
  overflow: visible;
}

.wb-composer-body {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  min-width: 0;
}

@media (min-width: 640px) {
  .wb-composer-body {
    flex-direction: row;
    align-items: stretch;
  }
}

.wb-composer-intent {
  flex-shrink: 0;
  padding: 1rem 1.15rem 0.85rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
}

@media (min-width: 640px) {
  .wb-composer-intent {
    width: 11.75rem;
    padding: 1.1rem 1.1rem 1rem;
    border-bottom: none;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
  }
}

.wb-composer-intent--compact {
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
}

@media (min-width: 640px) {
  .wb-composer-intent--compact {
    padding-top: 0.85rem;
    padding-bottom: 0.85rem;
  }
}

.wb-composer-intent--compact .wb-intent-repo {
  margin-top: 0.4rem;
  padding-top: 0;
  border-top: none;
}

.wb-intent-guide-toggle {
  width: 100%;
  box-sizing: border-box;
  margin: 0;
  padding: 0.3rem 0.45rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(0, 0, 0, 0.22);
  color: rgba(255, 255, 255, 0.72);
  font: inherit;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  text-align: center;
  transition: background 0.15s ease, color 0.15s ease;
}

.wb-intent-guide-toggle:hover {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.88);
}

.wb-intent-guide-toggle:not(:first-child) {
  margin-top: 0.65rem;
}

.wb-composer-intent__kicker {
  margin: 0 0 0.35rem;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.38);
}

.wb-composer-intent__title {
  margin: 0 0 0.4rem;
  font-size: clamp(1rem, 0.95rem + 0.2vw, 1.12rem);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
  line-height: 1.25;
}

.wb-composer-intent__title--dynamic {
  overflow-wrap: anywhere;
  word-break: break-word;
}

.wb-composer-intent__sub {
  margin: 0;
  font-size: clamp(0.78rem, 0.74rem + 0.12vw, 0.86rem);
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.42);
}

.wb-intent-repo {
  margin-top: 0.65rem;
  padding-top: 0.65rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.wb-intent-repo__title {
  margin: 0 0 0.45rem;
  font-size: 0.68rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.4);
}

.wb-intent-repo__sel {
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 0.45rem;
  padding: 0.35rem 0.5rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(0, 0, 0, 0.25);
  color: rgba(255, 255, 255, 0.88);
  font-size: 0.75rem;
}

.wb-intent-repo__go {
  width: 100%;
  margin-top: 0.35rem;
  font-size: 0.78rem;
}

.wb-intent-repo__detail {
  margin: 0.35rem 0 0.5rem;
  padding: 0.5rem 0.55rem;
  border-radius: 8px;
  border: 1px solid rgba(96, 165, 250, 0.22);
  background: rgba(96, 165, 250, 0.06);
}

.wb-intent-repo__detail-kicker {
  margin: 0 0 0.2rem;
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(147, 197, 253, 0.85);
}

.wb-intent-repo__detail-name {
  margin: 0 0 0.2rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.wb-intent-repo__detail-meta {
  margin: 0 0 0.25rem;
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.45);
}

.wb-intent-repo__detail-desc {
  margin: 0 0 0.35rem;
  font-size: 0.72rem;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.62);
  overflow-wrap: anywhere;
}

.wb-intent-repo__detail-hint {
  margin: 0;
  font-size: 0.65rem;
  line-height: 1.4;
  color: rgba(255, 255, 255, 0.4);
}

.wb-intent-repo__detail .mono,
.wb-intent-repo__detail code.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.68rem;
}

.wb-composer-main {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  transition: background 0.16s ease, box-shadow 0.16s ease;
}

.wb-composer-main--drag {
  background: rgba(129, 140, 248, 0.08);
  box-shadow: inset 0 0 0 1px rgba(129, 140, 248, 0.55);
}

.wb-input {
  display: block;
  width: 100%;
  box-sizing: border-box;
  margin: 0;
  min-height: 6rem;
  padding: 1.1rem 1.2rem 0.55rem;
  border: none;
  resize: none;
  font: inherit;
  font-size: clamp(1.05rem, 1rem + 0.25vw, 1.2rem);
  line-height: 1.55;
  color: #ececec;
  background: transparent;
  outline: none;
}

.wb-input::placeholder {
  color: rgba(255, 255, 255, 0.32);
}

.wb-research-msg {
  margin: 0 1rem 0.25rem;
  font-size: 0.76rem;
  line-height: 1.4;
}

.wb-research-msg--err {
  color: rgba(252, 165, 165, 0.95);
}

.wb-kb-panel {
  margin-top: 0;
}

.wb-kb-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  font-weight: 600;
  color: rgba(191, 219, 254, 0.9);
}

.wb-kb-heading small {
  color: rgba(148, 163, 184, 0.88);
  font-size: 0.7rem;
  font-weight: 500;
}

.wb-kb-upload-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.65rem;
  margin: 0.45rem 0 0.5rem;
  padding: 0.5rem;
  border: 1px dashed rgba(148, 163, 184, 0.32);
  border-radius: 0.75rem;
  background: rgba(15, 23, 42, 0.46);
  color: rgba(226, 232, 240, 0.9);
  transition: border-color 0.16s ease, background 0.16s ease;
}

.wb-kb-upload-row:hover,
.wb-kb-upload-row--drag {
  border-color: rgba(129, 140, 248, 0.9);
  background: rgba(67, 56, 202, 0.16);
}

.wb-kb-upload-row--busy {
  opacity: 0.78;
}

.wb-kb-add-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  place-items: center;
  width: clamp(2.6rem, 2.4rem + 0.5vw, 3rem);
  height: clamp(2.6rem, 2.4rem + 0.5vw, 3rem);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.075);
  color: rgba(248, 250, 252, 0.94);
  cursor: pointer;
  font: inherit;
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1;
  transform: translateZ(0);
  transition: transform 0.15s ease, background 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
}

.wb-kb-add-btn:hover:not(:disabled),
.wb-kb-add-btn:focus-visible {
  border-color: rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.13);
  outline: none;
  transform: scale(1.03);
}

.wb-kb-add-btn:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.wb-kb-plus {
  position: relative;
  display: block;
  width: 1rem;
  height: 1rem;
}

.wb-kb-plus::before,
.wb-kb-plus::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  width: 1rem;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
  transform: translate(-50%, -50%);
}

.wb-kb-plus::after {
  transform: translate(-50%, -50%) rotate(90deg);
}

.wb-kb-spinner {
  width: 1rem;
  height: 1rem;
  border: 2px solid rgba(224, 231, 255, 0.38);
  border-top-color: rgba(224, 231, 255, 0.95);
  border-radius: 999px;
  animation: wb-kb-spin 0.8s linear infinite;
}

@keyframes wb-kb-spin {
  to {
    transform: rotate(360deg);
  }
}

.wb-kb-upload-copy {
  display: grid;
  gap: 0.08rem;
  min-width: 0;
}

.wb-kb-upload-copy strong {
  color: rgba(248, 250, 252, 0.98);
  font-size: 0.8rem;
}

.wb-kb-upload-copy span {
  color: rgba(148, 163, 184, 0.92);
  font-size: 0.7rem;
  line-height: 1.35;
}

.wb-kb-refresh {
  border: none;
  border-radius: 999px;
  padding: 0.28rem 0.55rem;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(203, 213, 225, 0.9);
  cursor: pointer;
  font: inherit;
  font-size: 0.7rem;
  line-height: 1;
}

.wb-kb-refresh:hover:not(:disabled),
.wb-kb-refresh:focus-visible {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(248, 250, 252, 0.96);
  outline: none;
}

.wb-kb-refresh:disabled {
  cursor: not-allowed;
  opacity: 0.56;
}

.wb-kb-file {
  display: none;
}

.wb-kb-list {
  display: grid;
  gap: 0.4rem;
  margin-top: 0.55rem;
}

.wb-kb-file-pill {
  text-transform: uppercase;
  letter-spacing: 0.03em;
  display: inline-grid;
  place-items: center;
  min-width: 2.2rem;
  height: 1.45rem;
  padding: 0 0.36rem;
  border-radius: 999px;
  color: rgba(248, 250, 252, 0.96);
  font-size: 0.62rem;
  font-weight: 750;
  background: rgba(100, 116, 139, 0.78);
}

.wb-kb-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
  padding: 0.42rem 0.48rem;
  border-radius: 0.58rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.035);
  animation: wb-kb-card-in 0.24s ease both;
}

@keyframes wb-kb-card-in {
  from {
    opacity: 0;
    transform: translateY(0.35rem);
  }
}

.wb-kb-card-body {
  min-width: 0;
}

.wb-kb-card-body strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgba(248, 250, 252, 0.94);
  font-size: 0.78rem;
}

.wb-kb-card-body small,
.wb-kb-empty {
  color: rgba(148, 163, 184, 0.86);
  font-size: 0.72rem;
}

.wb-kb-card-remove {
  border: none;
  background: transparent;
  color: rgba(148, 163, 184, 0.9);
  cursor: pointer;
  font: inherit;
  font-size: 0.7rem;
  text-decoration: underline;
  text-underline-offset: 0.12em;
}

.wb-kb-card-remove:hover {
  color: #e2e8f0;
}

.wb-kb-card--pdf .wb-kb-file-pill {
  background: rgba(239, 68, 68, 0.76);
}

.wb-kb-card--doc .wb-kb-file-pill {
  background: rgba(59, 130, 246, 0.76);
}

.wb-kb-card--sheet .wb-kb-file-pill {
  background: rgba(34, 197, 94, 0.7);
}

.wb-kb-card--json .wb-kb-file-pill {
  background: rgba(245, 158, 11, 0.74);
}

.wb-kb-card--md .wb-kb-file-pill {
  background: rgba(168, 85, 247, 0.72);
}

@media (max-width: 640px) {
  .wb-kb-upload-row {
    grid-template-columns: 1fr;
  }

  .wb-kb-add-btn,
  .wb-kb-refresh {
    justify-self: start;
  }
}

.wb-input-footer {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: flex-start;
  gap: 0.5rem 0.65rem;
  padding: 0.42rem 0.75rem 0.42rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

@media (max-width: 720px) {
  .wb-input-footer {
    flex-wrap: wrap;
    row-gap: 0.35rem;
  }
}

.wb-input-hint {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
}

.wb-input-hint__primary {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.55rem;
  width: 100%;
  min-width: 0;
}

.wb-input-hint__primary .wb-input-hint__intent {
  flex: 1 1 6.5rem;
  min-width: 0;
}

.wb-input-hint__intent {
  font-size: clamp(0.8rem, 0.75rem + 0.15vw, 0.875rem);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.52);
  line-height: 1.25;
}

.wb-input-hint__keys {
  margin-left: auto;
  flex: 0 0 auto;
  padding-left: 0.35rem;
  font-size: clamp(0.72rem, 0.7rem + 0.08vw, 0.8rem);
  color: rgba(255, 255, 255, 0.28);
  line-height: 1.25;
  white-space: nowrap;
}

.wb-footer-trailing {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
  margin-left: auto;
  align-self: center;
}

.wb-frontend-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  flex-shrink: 0;
  align-self: center;
  line-height: 1;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 999px;
  padding: 0.28rem 0.34rem 0.28rem 0.62rem;
  background: rgba(0, 0, 0, 0.2);
  color: rgba(255, 255, 255, 0.48);
  font: inherit;
  font-size: 0.74rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background-color 0.16s ease,
    color 0.16s ease;
}

.wb-frontend-toggle:hover,
.wb-frontend-toggle:focus-visible {
  color: rgba(255, 255, 255, 0.84);
  border-color: rgba(125, 211, 252, 0.34);
  outline: none;
}

.wb-frontend-toggle--on {
  color: #ecfeff;
  border-color: rgba(34, 211, 238, 0.38);
  background: rgba(8, 145, 178, 0.2);
}

.wb-frontend-toggle__switch {
  width: 1.9rem;
  height: 1.05rem;
  border-radius: 999px;
  padding: 0.14rem;
  background: rgba(255, 255, 255, 0.12);
  transition: background-color 0.16s ease;
}

.wb-frontend-toggle--on .wb-frontend-toggle__switch {
  background: rgba(34, 211, 238, 0.68);
}

.wb-frontend-toggle__knob {
  display: block;
  width: 0.77rem;
  height: 0.77rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
  transition: transform 0.16s ease;
}

.wb-frontend-toggle--on .wb-frontend-toggle__knob {
  transform: translateX(0.82rem);
  background: #fff;
}

.wb-llm-inline {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-right: 0.1rem;
  max-width: min(100%, 26rem);
  /* 原生下拉在部分浏览器上会跟浅色系统菜单；声明暗色控件族 */
  color-scheme: dark;
}

.wb-llm-inline__note {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.35);
  white-space: nowrap;
}

.wb-mode-segment {
  display: inline-flex;
  flex-shrink: 0;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
  background: rgba(0, 0, 0, 0.22);
}

.wb-mode-segment__btn {
  margin: 0;
  padding: 0.38rem 0.72rem;
  min-width: 3.1rem;
  border: none;
  border-radius: 0;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.42);
  background: transparent;
  cursor: pointer;
  transition:
    color 0.15s ease,
    background-color 0.15s ease;
}

.wb-mode-segment__btn:hover {
  color: rgba(255, 255, 255, 0.75);
  background: rgba(255, 255, 255, 0.05);
}

.wb-mode-segment__btn:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 2px rgba(129, 140, 248, 0.45);
  z-index: 1;
}

.wb-mode-segment__btn--on {
  color: #f4f4f5;
  background: rgba(255, 255, 255, 0.12);
}

/* 自选：厂商 / 模型自定义下拉（非原生 select，避免白底系统菜单） */
.wb-llm-dd {
  position: relative;
  flex-shrink: 0;
  max-width: 100%;
}

.wb-dd-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
  box-sizing: border-box;
  max-width: 11rem;
  min-height: 2rem;
  padding: 0.35rem 0.65rem 0.35rem 0.75rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background-color: rgba(255, 255, 255, 0.06);
  color: rgba(250, 250, 250, 0.95);
  font: inherit;
  font-size: 0.75rem;
  line-height: 1.25;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease,
    box-shadow 0.15s ease;
}

.wb-dd-trigger__text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.wb-dd-trigger__icon {
  flex-shrink: 0;
  color: rgba(255, 255, 255, 0.45);
  transition: transform 0.15s ease;
}

.wb-dd-trigger--open .wb-dd-trigger__icon {
  transform: rotate(180deg);
}

.wb-dd-trigger:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.16);
  background-color: rgba(255, 255, 255, 0.09);
}

.wb-dd-trigger:focus-visible {
  outline: none;
  border-color: rgba(165, 180, 252, 0.45);
  box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.22);
}

.wb-dd-trigger:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.wb-dd-trigger--model {
  max-width: 13rem;
}

.wb-dd-panel {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  z-index: 50;
  min-width: 100%;
  width: max-content;
  max-width: min(20rem, calc(100vw - 2rem));
  max-height: 14rem;
  margin: 0;
  padding: 0.35rem 0;
  list-style: none;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: #1f1f23;
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.35),
    0 12px 36px rgba(0, 0, 0, 0.55);
  overflow-y: auto;
}

.wb-dd-panel--tall {
  max-height: 18rem;
}

.wb-dd-cat {
  padding: 0.35rem 0.75rem 0.2rem;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.38);
  pointer-events: none;
}

.wb-dd-item {
  padding: 0.45rem 0.85rem;
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.82);
  cursor: pointer;
  transition: background 0.1s ease;
}

.wb-dd-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

.wb-dd-item--on {
  background: rgba(129, 140, 248, 0.18);
  color: #e0e7ff;
}

/* 与发送区胶囊风格统一：圆角条、去原生箭头、柔和 focus（避免系统蓝框） */
.wb-inline-select {
  color-scheme: dark;
  box-sizing: border-box;
  max-width: 11rem;
  min-height: 2rem;
  padding: 0.35rem 1.35rem 0.35rem 0.75rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background-color: rgba(255, 255, 255, 0.06);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12' fill='none'%3E%3Cpath d='M3 4.5L6 7.5L9 4.5' stroke='rgba(255,255,255,0.45)' stroke-width='1.35' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.55rem center;
  background-size: 0.65rem;
  color: rgba(250, 250, 250, 0.95);
  font-size: 0.75rem;
  line-height: 1.25;
  outline: none;
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease,
    box-shadow 0.15s ease;
}

.wb-inline-select:hover {
  border-color: rgba(255, 255, 255, 0.16);
  background-color: rgba(255, 255, 255, 0.09);
}

.wb-inline-select:focus,
.wb-inline-select:focus-visible {
  outline: none;
  border-color: rgba(165, 180, 252, 0.45);
  box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.22);
}

.wb-inline-select--model {
  max-width: 13rem;
}

.wb-inline-select:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* 下拉列表：与 WalletView .llm-select 对齐，避免白底系统菜单「像没做样式」 */
.wb-inline-select option,
.wb-inline-select optgroup {
  background: #1a1a1f;
  color: #e2e8f0;
}

.wb-input-send {
  flex-shrink: 0;
  width: clamp(2.6rem, 2.4rem + 0.5vw, 3rem);
  height: clamp(2.6rem, 2.4rem + 0.5vw, 3rem);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 999px;
  cursor: pointer;
  color: #121212;
  background: #fff;
  transform: translateZ(0);
  transition: opacity 0.15s ease, transform 0.15s ease, background 0.15s ease;
}

.wb-input-send:hover:not(:disabled) {
  opacity: 0.92;
  transform: scale(1.03);
}

.wb-input-send:disabled {
  opacity: 0.25;
  cursor: not-allowed;
}

.wb-composer-note {
  width: min(100%, 60rem);
  margin: 0 auto;
  text-align: center;
  font-size: clamp(0.78rem, 0.74rem + 0.12vw, 0.86rem);
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.32);
}

/* 制作场景：已进入任务（规划/交接/编排等）时，主输入压缩为底栏式窄框 */
.wb-make-scene .wb-composer-column.wb-composer-column--task-slim {
  gap: 0.35rem;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-panel {
  border-radius: 1.125rem;
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.18),
    0 6px 22px rgba(0, 0, 0, 0.28);
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-body {
  flex-direction: row;
  align-items: stretch;
}

@media (max-width: 639px) {
  .wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-body {
    flex-direction: column;
  }
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-intent {
  width: clamp(5.25rem, 16vw, 7.25rem);
  max-width: 8rem;
  padding: 0.45rem 0.55rem 0.45rem 0.65rem;
  border-bottom: none;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

@media (max-width: 639px) {
  .wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-intent {
    width: 100%;
    max-width: none;
    border-right: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-intent__kicker {
  display: none;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-intent__title {
  margin: 0 0 0.2rem;
  font-size: 0.72rem;
  line-height: 1.2;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-intent__sub {
  display: none;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-intent-guide-toggle {
  margin-top: 0.35rem;
  padding: 0.22rem 0.35rem;
  font-size: 0.62rem;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-intent-repo {
  margin-top: 0.35rem;
  padding-top: 0.35rem;
  max-height: 5.5rem;
  overflow-y: auto;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-intent-repo__title {
  margin-bottom: 0.3rem;
  font-size: 0.62rem;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-input {
  min-height: 2.45rem;
  max-height: 9rem;
  padding: 0.5rem 0.75rem 0.4rem;
  font-size: 0.92rem;
  line-height: 1.42;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-panel:focus-within .wb-input {
  min-height: 2.75rem;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-research-msg {
  margin: 0 0.65rem 0.15rem;
  font-size: 0.68rem;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-input-footer {
  padding: 0.28rem 0.45rem 0.32rem 0.55rem;
  gap: 0.35rem 0.5rem;
  flex-wrap: nowrap;
  align-items: center;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-input-hint {
  min-width: 0;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-input-hint__primary {
  flex-wrap: nowrap;
  gap: 0.35rem 0.45rem;
  flex: 1 1 auto;
  min-width: 0;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-new-btn {
  flex-shrink: 0;
  padding: 0.16rem 0.42rem;
  font-size: 0.65rem;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-input-hint__intent {
  font-size: 0.68rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1 1 auto;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-input-hint__keys {
  display: none;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-footer-trailing {
  gap: 0.35rem;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-mode-segment__btn {
  padding: 0.28rem 0.55rem;
  min-width: 2.6rem;
  font-size: 0.7rem;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-dd-trigger {
  min-height: 1.75rem;
  padding: 0.22rem 0.5rem 0.22rem 0.55rem;
  font-size: 0.68rem;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-kb-add-btn,
.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-input-send {
  width: 2.25rem;
  height: 2.25rem;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-input-send svg {
  width: 17px;
  height: 17px;
}

.wb-make-scene .wb-composer-column.wb-composer-column--task-slim .wb-composer-note {
  font-size: 0.68rem;
  line-height: 1.35;
  max-width: min(42rem, 100%);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 下方建议块：类似 ChatGPT 起始建议 — 横条卡片 + 箭头 */
.wb-starters {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: clamp(0.65rem, 1.3vw, 0.9rem);
  width: 100%;
}

.wb-starter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
  min-height: 5.35rem;
  padding: clamp(0.9rem, 0.8rem + 0.32vw, 1.05rem) clamp(1rem, 0.9rem + 0.3vw, 1.2rem);
  border-radius: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  font: inherit;
  text-align: left;
  text-decoration: none;
  color: inherit;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.wb-starter:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.14);
}

.wb-starter:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.45);
  outline-offset: 2px;
}

.wb-starter-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  min-width: 0;
  text-align: left;
}

.wb-starter-title {
  font-size: clamp(0.95rem, 0.9rem + 0.2vw, 1.05rem);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
}

.wb-starter-sub {
  font-size: clamp(0.8rem, 0.75rem + 0.15vw, 0.9rem);
  line-height: 1.35;
  color: rgba(255, 255, 255, 0.4);
}

.wb-starter-arrow {
  flex-shrink: 0;
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.35);
}

.wb-starter:hover .wb-starter-arrow {
  color: rgba(255, 255, 255, 0.55);
}

.wb-starter--active {
  border-color: rgba(165, 180, 252, 0.45);
  background: rgba(129, 140, 248, 0.12);
  box-shadow: 0 0 0 1px rgba(129, 140, 248, 0.15);
}

.wb-starter--active .wb-starter-arrow {
  color: rgba(199, 210, 254, 0.85);
}

.wb-foot {
  display: none;
}

@media (max-width: 760px) {
  .wb-starters {
    grid-template-columns: 1fr;
  }
}

.wb-foot-dot {
  margin: 0 0.2rem;
}

.wb-foot-link {
  color: rgba(255, 255, 255, 0.5);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.wb-foot-link:hover {
  color: rgba(255, 255, 255, 0.78);
}
</style>
