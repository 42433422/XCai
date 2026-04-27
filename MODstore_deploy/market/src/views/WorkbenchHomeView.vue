<template>
  <div class="wb-home">
    <div
      class="wb-home-inner"
      :class="{ 'wb-home-inner--no-workflow': !hasWorkflow, 'wb-home-inner--gears': hasWorkflow }"
    >
      <header v-if="!hasWorkflow || activeGear === 'make'" class="wb-hero">
        <p v-if="greetingLine" class="wb-hero-kicker">{{ greetingLine }}</p>
        <h1 class="wb-hero-title">今天有什么安排？</h1>
      </header>

      <div
        v-if="hasWorkflow"
        class="wb-gear-layout"
        @wheel.passive="onGearWheel"
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
          <div class="wb-gear-track" :style="{ transform: `translateY(-${gearIndex * (100 / gearScenes.length)}%)` }">
            <section class="wb-gear-scene wb-direct-scene" aria-label="一档直接聊天">
              <div class="wb-direct-tier-anchor">
                <ConsumptionTierControl v-model="consumptionTier" />
              </div>
              <div class="wb-direct-hero">
                <h1 class="wb-direct-title">有什么想问的？</h1>
                <p class="wb-direct-sub">像聊天一样提问，我直接帮你分析、总结和给出可执行答案。</p>
              </div>
              <div v-if="directMessages.length" class="wb-direct-thread" aria-live="polite">
                <article
                  v-for="(msg, i) in directMessages"
                  :key="`direct-${i}`"
                  class="wb-direct-msg"
                  :class="msg.role === 'user' ? 'wb-direct-msg--user' : 'wb-direct-msg--assistant'"
                >
                  <span class="wb-direct-msg__role">{{ msg.role === 'user' ? '你' : 'AI' }}</span>
                  <p class="wb-direct-msg__body">{{ msg.content }}</p>
                </article>
              </div>
              <div class="wb-direct-box">
                <div class="wb-direct-box-main">
                  <input
                    ref="directFileInputRef"
                    type="file"
                    class="wb-direct-file-input"
                    multiple
                    @change="onDirectFilesChange"
                  />
                  <button
                    type="button"
                    class="wb-direct-attach"
                    :disabled="directLoading"
                    aria-label="选择本地文件作为附件"
                    title="选择本地文件（发送时在消息中附带文件名与大小；后续可接实际上传）"
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
                    placeholder="直接问问题，例如：帮我写一份门店日报自动化方案…"
                    spellcheck="false"
                    @keydown="onDirectKeydown"
                  />
                  <button
                    type="button"
                    class="wb-direct-send"
                    :disabled="directSendDisabled"
                    @click="() => void sendDirectChat()"
                  >
                    {{ directLoading ? '思考中…' : '发送' }}
                  </button>
                </div>
                <div v-if="directAttachedFiles.length" class="wb-direct-file-chips" aria-label="已选附件">
                  <span
                    v-for="f in directAttachedFiles"
                    :key="f.id"
                    class="wb-direct-file-chip"
                    :class="`wb-direct-file-chip--${f.status}`"
                    :title="directFileChipTitle(f)"
                  >
                    <span class="wb-direct-file-chip__dot" aria-hidden="true">
                      <span v-if="f.status === 'uploading'" class="wb-direct-file-chip__spinner" />
                      <span v-else-if="f.status === 'ready'" class="wb-direct-file-chip__check">✓</span>
                      <span v-else-if="f.status === 'error' || f.status === 'skipped'" class="wb-direct-file-chip__warn">!</span>
                    </span>
                    <span class="wb-direct-file-chip__name">{{ f.name }}</span>
                    <span class="wb-direct-file-chip__meta">{{ formatDirectFileSize(f.size) }}</span>
                    <button
                      type="button"
                      class="wb-direct-file-chip__remove"
                      :aria-label="`移除 ${f.name}`"
                      :disabled="directLoading || f.status === 'uploading'"
                      @click="() => void removeDirectAttachedFile(f.id)"
                    >
                      ×
                    </button>
                  </span>
                </div>
                <p v-if="directAttachHint" class="wb-direct-attach-hint" role="status">
                  {{ directAttachHint }}
                </p>
              </div>
              <p v-if="directError" class="wb-direct-error" role="alert">{{ directError }}</p>
              <div class="wb-direct-suggestions" aria-label="建议问题">
                <button
                  v-for="item in directSuggestions"
                  :key="item"
                  type="button"
                  class="wb-direct-suggestion"
                  @click="() => void sendDirectChat(item)"
                >
                  {{ item }}
                </button>
              </div>
            </section>

            <section class="wb-gear-scene wb-make-scene" aria-label="二档制作流程">
      <section
        v-if="hasWorkflow && planSession"
        ref="planPanelRef"
        class="wb-plan"
        aria-labelledby="wb-plan-title"
      >
        <Transition name="wb-plan-shell" appear>
          <div :key="planSurfaceKey" class="wb-plan-surface">
            <div class="wb-plan-head">
              <h2 id="wb-plan-title" class="wb-plan-title">需求规划</h2>
              <button type="button" class="wb-plan-close" aria-label="关闭规划" @click="dismissPlanSession">×</button>
            </div>
            <p class="wb-plan-kicker">
              类型：{{ planSession.intentTitle }} · 类似 Cursor Plan：先多轮澄清，再生成执行清单，最后进入制作与生成。
            </p>
            <div v-if="planSession.loading" class="wb-plan-loading-block" aria-live="polite">
              <div class="wb-plan-loading-track" aria-hidden="true">
                <div class="wb-plan-loading-bar" />
              </div>
              <p class="wb-plan-loading">正在请求模型…</p>
            </div>
            <TransitionGroup name="wb-plan-msg" tag="ul" class="wb-plan-thread" aria-live="polite">
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
            <template v-if="planSession.phase === 'chat'">
              <div v-if="planQuickOptions.length" class="wb-plan-quick" aria-label="快捷选择">
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
              <details class="wb-plan-reply-fold">
                <summary class="wb-plan-reply-fold__summary">其他说明（可选）</summary>
                <div class="wb-plan-reply-expand">
                  <div class="wb-plan-reply-expand-inner">
                    <label class="wb-sr-only" for="wb-plan-reply">补充或回答</label>
                    <textarea
                      id="wb-plan-reply"
                      v-model="planReplyDraft"
                      class="wb-plan-reply"
                      rows="2"
                      placeholder="自由补充…（Enter 发送，Shift+Enter 换行）"
                      spellcheck="false"
                      @keydown="onPlanReplyKeydown"
                    />
                  </div>
                </div>
              </details>
              <div class="wb-plan-actions">
                <button
                  type="button"
                  class="wb-plan-secondary"
                  :disabled="planSession.loading || !planReplyDraft.trim()"
                  @click="() => void sendPlanReply()"
                >
                  发送补充
                </button>
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
              <ol class="wb-plan-checklist-ol">
                <li v-for="(line, i) in planSession.checklistLines" :key="i" class="wb-plan-checklist-li">
                  {{ line }}
                </li>
              </ol>
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
        v-if="hasWorkflow && orchestrationSession?.steps?.length"
        class="wb-orch"
        aria-label="制作进度"
      >
        <h3 class="wb-orch-title">制作进度</h3>
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
            </span>
          </li>
        </ol>
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
          <h2 id="wb-wf-link-title" class="wb-handoff-title">工作流已就绪</h2>
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
            仅打开工作流画布
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
          <template v-if="pendingHandoff.intentKey === 'workflow'">
            <label class="wb-handoff-label" for="wb-handoff-name">工作流名称 <span class="wb-handoff-req">必填</span></label>
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
            <label class="wb-handoff-label" for="wb-handoff-suggest">建议 Mod ID <span class="wb-handoff-opt">选填</span></label>
            <input
              id="wb-handoff-suggest"
              v-model="pendingHandoff.suggestedModId"
              type="text"
              class="wb-handoff-input"
              placeholder="小写字母数字点线，如 my-qq-watch"
              autocomplete="off"
            />
          </template>
        </div>
        <p v-if="finalizeError" class="wb-handoff-error" role="alert">{{ finalizeError }}</p>
        <div class="wb-handoff-actions">
          <button
            type="button"
            class="wb-handoff-primary"
            :disabled="finalizeLoading || !canRunOrchestration"
            @click="() => void runOrchestration()"
          >
            {{ finalizeLoading ? orchestrationButtonPendingLabel : orchestrationButtonLabel }}
          </button>
        </div>
        <p class="wb-handoff-foot">{{ handoffFootNote }}</p>
      </section>

      <div v-if="hasWorkflow" class="wb-composer-column">
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
              <label class="wb-sr-only" for="wb-home-input">描述想法</label>
              <textarea
                id="wb-home-input"
                ref="inputRef"
                v-model="draft"
                class="wb-input"
                rows="4"
                :placeholder="placeholder"
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
              <div class="wb-input-footer">
                <div class="wb-input-hint">
                  <span class="wb-input-hint__intent">当前：{{ composerMainTitle }}</span>
                  <span class="wb-input-hint__keys">Enter 发送 · Shift+Enter 换行</span>
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
                :disabled="!draft.trim() || !!planSession"
                aria-label="发送"
                @click="() => void submitDraft()"
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
          <template v-if="planSession">当前请在上方面板继续对话。</template>
          Auto 会按账户默认模型调用；若默认厂商没有可用密钥，会自动改用已配置密钥的厂商与模型（可在钱包页固定默认）。
        </p>
      </div>

      <nav class="wb-starters" aria-label="工作流描述快捷提示">
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
          :class="{ 'wb-starter--active': hasWorkflow && composerIntent === 'workflow' }"
          @click="applyStarter('workflow')"
        >
          <div class="wb-starter-text">
            <span class="wb-starter-title">做工作流</span>
            <span class="wb-starter-sub">节点与自动化 · 填入描述</span>
          </div>
          <span class="wb-starter-arrow" aria-hidden="true">→</span>
        </button>
      </nav>

      <footer class="wb-foot">
        <span v-if="hasWorkflow">选择类型后输入想法：Enter 先进入需求规划（多轮问答与清单），确认后再在制作草稿中启动生成；顶部可查看执行进度。</span>
        <span v-else>从顶栏「工作台」进入 Mod 库、员工制作或工作流管理。</span>
        <router-link :to="{ name: 'ai-store' }" class="wb-foot-link">AI 员工商店</router-link>
        <template v-if="hasPlans">
          <span class="wb-foot-dot" aria-hidden="true">·</span>
          <router-link :to="{ name: 'plans' }" class="wb-foot-link">套餐</router-link>
        </template>
      </footer>
            </section>

            <section class="wb-gear-scene wb-voice-scene" aria-label="三档语音规划">
              <div class="wb-voice-orb-wrap">
                <button
                  type="button"
                  class="wb-voice-orb"
                  :class="`wb-voice-orb--${voiceState}`"
                  :disabled="voiceBusy"
                  aria-label="语音输入"
                  @click="toggleVoiceListening"
                >
                  <span class="wb-voice-orb__ring"></span>
                  <span class="wb-voice-orb__core"></span>
                </button>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, onUnmounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import ConsumptionTierControl from '../components/workbench/ConsumptionTierControl.vue'
import { api } from '../api'
import { getAccessToken } from '../infrastructure/storage/tokenStore'

/** 与后端 llm_model_taxonomy.CATEGORY_ORDER 一致 */
const LLM_CATEGORY_ORDER = ['llm', 'vlm', 'image', 'video', 'other']

const router = useRouter()
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
const pollStop = ref(false)
/** 工作流编排成功后的「关联 Mod」卡片 */
const workflowLinkOffer = ref(null)
const linkMods = ref([])
const linkModId = ref('')
const linkBusy = ref(false)
const linkError = ref('')

/** Cursor Plan 式：多轮澄清 → 执行清单 → 再进入制作草稿 */
const planSession = ref(null)
const planReplyDraft = ref('')
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
const knowledgeStatus = ref(null)
const knowledgeDocs = ref([])
const knowledgeLoading = ref(false)
const knowledgeUploading = ref(false)
const knowledgeError = ref('')
const knowledgeFileInputRef = ref(null)
const knowledgeDragActive = ref(false)
/** 与下方 starter 同步：仅标记制作类型，不写入输入框 */
const composerIntent = ref('workflow')
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
/**
 * 直接聊天待发送的本地附件。每项形如：
 *   { id, name, size, status: 'uploading'|'ready'|'error'|'skipped', docId, error, file }
 * - status='ready' 的文档已上传到当前用户知识库（doc_id），发送时会做向量检索并拼到 system prompt。
 * - status='skipped'/'error' 的文件不上传，只在消息中附带文件名说明。
 */
const directAttachedFiles = ref([])
const directMessages = ref([])
const directLoading = ref(false)
const directError = ref('')

/** 与后端 knowledge_ingest.SUPPORTED_EXTENSIONS / MAX_UPLOAD_BYTES 保持一致 */
const DIRECT_KB_SUPPORTED_EXT = new Set(['txt', 'md', 'json', 'csv', 'pdf', 'docx', 'xlsx'])
const DIRECT_KB_MAX_BYTES = 20 * 1024 * 1024

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
  const skipped = list.filter((f) => f.status === 'skipped').length
  const errored = list.filter((f) => f.status === 'error').length
  const parts = []
  if (uploading) parts.push(`${uploading} 个上传中`)
  if (ready) parts.push(`${ready} 个已纳入资料库（提问时按相关度自动召回）`)
  if (skipped) parts.push(`${skipped} 个未受支持，仅附文件名给模型参考`)
  if (errored) parts.push(`${errored} 个上传失败，仅附文件名给模型参考`)
  return parts.join(' · ')
})
const directSuggestions = [
  '帮我把今天的工作拆成步骤',
  '帮我分析一个自动化流程',
  '帮我写一段客户沟通话术',
]

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

function setGear(key) {
  if (!gearScenes.some((it) => it.key === key)) return
  gearDragOffset.value = 0
  gearDragging.value = false
  activeGear.value = key
}

function gearStopPercent(index) {
  const last = Math.max(1, gearScenes.length - 1)
  return (index / last) * 100
}

function onGearWheel(e) {
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

function formatDirectFileSize(bytes) {
  const n = Number(bytes) || 0
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function directFileExt(filename) {
  const s = String(filename || '')
  const i = s.lastIndexOf('.')
  if (i < 0 || i >= s.length - 1) return ''
  return s.slice(i + 1).toLowerCase()
}

function directFileChipTitle(f) {
  if (!f) return ''
  if (f.status === 'uploading') return `${f.name}：上传中…`
  if (f.status === 'ready') return `${f.name}：已纳入资料库，提问时会按相关度自动召回片段`
  if (f.status === 'skipped') return `${f.name}：${f.error || '该格式暂不解析；将仅附文件名供模型参考'}`
  if (f.status === 'error') return `${f.name}：${f.error || '上传失败'}（仅附文件名给模型参考）`
  return f.name
}

function directAttachmentNote(files) {
  const list = Array.isArray(files) ? files : []
  if (!list.length) return ''
  const parts = list.map((f) => {
    const tag =
      f.status === 'ready'
        ? '已入库'
        : f.status === 'uploading'
        ? '上传中'
        : f.status === 'error'
        ? '上传失败'
        : '未解析'
    return `${f.name}（${formatDirectFileSize(f.size)}，${tag}）`
  })
  return `[附件：${parts.join('，')}]`
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

async function uploadDirectAttachedFile(item) {
  try {
    const res = await api.knowledgeUploadDocument(item.file)
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
    if (docId) {
      directAttachedFiles.value[idx] = {
        ...directAttachedFiles.value[idx],
        status: 'ready',
        docId,
        error: '',
      }
    } else {
      directAttachedFiles.value[idx] = {
        ...directAttachedFiles.value[idx],
        status: 'error',
        error: '上传未返回文档 ID',
      }
    }
  } catch (e) {
    const idx = directAttachedFiles.value.findIndex((x) => x.id === item.id)
    if (idx < 0) return
    directAttachedFiles.value[idx] = {
      ...directAttachedFiles.value[idx],
      status: 'error',
      error: e?.message || String(e),
    }
  }
}

function onDirectFilesChange(e) {
  const input = e?.target
  if (!input || typeof input.files === 'undefined') return
  const picked = Array.from(input.files || [])
  input.value = ''
  if (!picked.length) return
  const maxFiles = 12
  const remaining = Math.max(0, maxFiles - directAttachedFiles.value.length)
  const accepted = picked.slice(0, remaining)
  const items = accepted.map((file) => {
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
        error: `不支持的格式（仅 ${[...DIRECT_KB_SUPPORTED_EXT].join('/')} 入库）`,
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
      file,
    }
  })
  directAttachedFiles.value = [...directAttachedFiles.value, ...items]
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
  // consumptionTier（1–10）当前仅占位；后续可映射 max_tokens、独立 intensity 或与实时榜单选模后再传入 llmChat / 后端。
  directDraft.value = ''
  directError.value = ''
  directLoading.value = true
  directMessages.value = [...directMessages.value, { role: 'user', content: userContent }]
  // 立刻清空附件，避免失败后重复点发送时再次叠加同一段说明；ready 文档仍留在用户知识库中。
  directAttachedFiles.value = []
  try {
    let knowledgePack = ''
    const hasReadyDocs = filesSnapshot.some((f) => f.status === 'ready')
    if (hasReadyDocs && userText) {
      try {
        const res = await api.knowledgeSearch(userText, 6)
        knowledgePack = formatKnowledgeContext(res?.items)
      } catch {
        // 检索失败不阻塞对话，模型仍能看到附件文件名说明
      }
    }
    const { provider, model } = await resolveChatProviderModel()
    const sysParts = [
      '你是一个简洁直接的中文 AI 助手。优先给出可执行答案；如果信息不足，先给合理假设，再列出需要确认的问题。',
    ]
    if (knowledgePack) {
      sysParts.push(
        `以下是用户当前提问相关的资料库片段（来自其本人上传的文档），优先据此回答；若与提问无关请忽略：\n${knowledgePack}`,
      )
    }
    const msgs = [
      { role: 'system', content: sysParts.join('\n\n') },
      ...directMessages.value.map((m) => ({ role: m.role, content: m.content })),
    ]
    const res = await api.llmChat(provider, model, msgs, 2048)
    const reply = String(res?.content || '').trim() || '（无回复）'
    directMessages.value = [...directMessages.value, { role: 'assistant', content: reply }]
  } catch (e) {
    directError.value = e?.message || String(e)
  } finally {
    directLoading.value = false
  }
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
  voiceTranscript.value = ''
  voiceListening.value = true
  voiceState.value = 'listening'
  rec.onresult = (event) => {
    let text = ''
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      text += event.results[i][0]?.transcript || ''
    }
    voiceTranscript.value = text.trim()
    if (event.results[event.results.length - 1]?.isFinal && voiceTranscript.value) {
      voiceDraft.value = voiceTranscript.value
    }
  }
  rec.onerror = (event) => {
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
  pendingHandoff.value = {
    description: `【语音规划记录】\n${text}`,
    intentTitle: intentMeta.value.title,
    intentKey: composerIntent.value,
    workflowName: '',
    planNotes: composerIntent.value === 'workflow' ? text : '',
    suggestedModId: '',
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

const INTENT_META = {
  mod: {
    title: '做 Mod',
    sub: '先建 Mod 库仓库，按行业写好 manifest/JSON 骨架，把需要的员工在 workflow_employees 里命名占位即可；表结构、规则与接口可后续迭代。',
  },
  employee: {
    title: '做员工',
    sub: '提示词与工具 · 在下方用自然语言描述岗位与流程',
  },
  workflow: {
    title: '做工作流',
    sub: '节点与自动化 · 在下方用自然语言描述触发与步骤',
  },
}

const intentMeta = computed(() => INTENT_META[composerIntent.value] || INTENT_META.workflow)

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

/** 侧栏与输入脚「当前」主标题：{name} 工作流 / Mod / AI 员工 */
const composerMainTitle = computed(() => {
  if (workflowLinkOffer.value?.workflowName) {
    return `${workflowLinkOffer.value.workflowName} 工作流`
  }
  const ph = pendingHandoff.value
  if (ph?.intentKey === 'workflow') {
    const n = (ph.workflowName || '').trim()
    if (n) return `${n} 工作流`
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
  return '做工作流'
})

const handoffDescLabel = computed(() => {
  const k = pendingHandoff.value?.intentKey
  if (k === 'mod') return 'Mod 需求描述'
  if (k === 'employee') return '员工能力描述'
  return '工作流描述'
})

const orchestrationButtonLabel = computed(() => {
  const k = pendingHandoff.value?.intentKey
  if (k === 'mod') return '开始生成 Mod'
  if (k === 'employee') return '开始生成员工包'
  return '开始创建并校验'
})

const orchestrationButtonPendingLabel = computed(() =>
  finalizeLoading.value ? '执行中…' : orchestrationButtonLabel.value,
)

const canRunOrchestration = computed(() => {
  const h = pendingHandoff.value
  if (!h?.description?.trim()) return false
  if (h.intentKey === 'workflow') return Boolean(h.workflowName?.trim())
  return true
})

const handoffFootNote = computed(() => {
  const k = pendingHandoff.value?.intentKey
  if (k === 'mod') {
    return '生成成功后进入 Mod 制作页。首期只需仓库 + 行业相关 JSON + 员工命名即可落库，校验与 Python 扫描的警告不阻塞继续迭代。'
  }
  if (k === 'employee') {
    return '员工包写入你的本地库；上架请到「员工制作」上传。商店执行器以已上架包为准。'
  }
  return '创建并校验成功后进入工作流画布；尚无节点时跳过拓扑沙盒。'
})

const hasRepo = computed(() => router.hasRoute('workbench-repository'))
const hasWorkflow = computed(() => router.hasRoute('workbench-workflow'))
const hasEmployee = computed(() => router.hasRoute('workbench-employee'))
const hasPlans = computed(() => router.hasRoute('plans'))

const greetingLine = computed(() => {
  const n = displayName.value.trim()
  if (!n) return ''
  return `你好，${n}`
})

const placeholder = computed(() => {
  if (composerIntent.value === 'mod') {
    return '例如：行业「物流」、新建仓库 my-track；manifest 里 industry/library 等 JSON 字段先填齐骨架；workflow_employees 里命名「路由调度员」「异常件跟进员」各一条，接口与规则写「待补充」即可…'
  }
  if (composerIntent.value === 'employee') {
    return '例如：岗位负责核对发票金额与税号，输出结构化结果给财务系统…'
  }
  return '例如：每天把 Excel 出货单里的品名和数量同步到仓库表…'
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

onMounted(async () => {
  document.addEventListener('pointerdown', onLlmDocPointerDown, true)
  window.addEventListener('keydown', onLlmEscape)
  try {
    const pendingDraft = sessionStorage.getItem('workbench_home_pending_draft')
    const pendingIntent = sessionStorage.getItem('workbench_home_pending_intent')
    if (pendingDraft && !draft.value.trim()) draft.value = pendingDraft
    if (pendingIntent && INTENT_META[pendingIntent]) composerIntent.value = pendingIntent
    sessionStorage.removeItem('workbench_home_pending_draft')
    sessionStorage.removeItem('workbench_home_pending_intent')
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
})

onBeforeUnmount(() => {
  pollStop.value = true
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onLlmDocPointerDown, true)
  window.removeEventListener('keydown', onLlmEscape)
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
      const o = parsePlanAssistantContent(ps.messages[i].content).options
      return Array.isArray(o) ? o : []
    }
  }
  return []
})

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

/** 助手气泡 Mermaid 渲染错误（按消息下标） */
const planDiagramError = ref({})

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
      nextErr[idx] = (e && e.message) || String(e) || '流程图解析失败'
      host.innerHTML = ''
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
  planSession.value = null
  planReplyDraft.value = ''
  planOptionSelections.value = {}
  clearPlanOptionOtherText()
  planDiagramError.value = {}
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
  knowledgeUploading.value = true
  knowledgeError.value = ''
  try {
    for (const file of list) {
      await api.knowledgeUploadDocument(file)
    }
    await loadKnowledgeDocuments()
  } catch (err) {
    knowledgeError.value = err?.message || String(err)
  } finally {
    knowledgeUploading.value = false
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
      const content = String(it?.content || '').trim()
      return `### ${i + 1}. ${filename}\n${content}`
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
  pollStop.value = true
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
  while (!pollStop.value) {
    const s = await api.workbenchGetSession(sessionId)
    orchestrationSession.value = s
    if (s.status === 'done' || s.status === 'error') return s
    await delay(450)
  }
  return null
}

async function runOrchestration() {
  const h = pendingHandoff.value
  if (!h || !hasWorkflow.value || finalizeLoading.value) return
  if (!requireLoginForWorkbenchUse()) return
  if (!canRunOrchestration.value) {
    if (h.intentKey === 'workflow') finalizeError.value = '请填写工作流名称与描述'
    else finalizeError.value = '请填写描述'
    return
  }
  finalizeError.value = ''
  finalizeLoading.value = true
  pollStop.value = false
  orchestrationSession.value = null
  try {
    await persistManualLlmIfNeeded()
    const intent = h.intentKey || 'workflow'
    const body: Record<string, unknown> = {
      intent,
      brief: (h.description || '').trim(),
      workflow_name:
        intent === 'workflow' ? (h.workflowName || '').trim() : undefined,
      plan_notes: intent === 'workflow' ? (h.planNotes || '').trim() : '',
      suggested_mod_id:
        intent === 'mod' ? (h.suggestedModId || '').trim() || undefined : undefined,
      replace: true,
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
    const started = await api.workbenchStartSession(body)
    const sid = started?.session_id
    if (!sid) throw new Error('未返回 session_id')
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
    if (finIntent === 'workflow' && art.workflow_id != null) {
      workflowLinkOffer.value = {
        workflowId: art.workflow_id,
        workflowName: String(
          art.workflow_name || (h.workflowName || '').trim() || `工作流 ${art.workflow_id}`,
        ),
        validationErrors: Array.isArray(art.validation_errors) ? art.validation_errors : [],
        llmWarnings: Array.isArray(art.llm_warnings) ? art.llm_warnings : [],
        sandboxOk: art.sandbox_ok !== false,
      }
      linkModId.value = ''
      linkError.value = ''
      void loadLinkMods()
      pendingHandoff.value = null
      orchestrationSession.value = null
      return
    }
    pendingHandoff.value = null
    orchestrationSession.value = null
    if (finIntent === 'mod' && art.mod_id) {
      await router.push({
        name: 'mod-authoring',
        params: { modId: String(art.mod_id) },
      })
      return
    }
    if (finIntent === 'employee') {
      const q = {
        fromAi: '1',
        packId: art.pack_id != null ? String(art.pack_id) : '',
        name: art.name != null ? String(art.name) : '',
        desc: art.description != null ? String(art.description) : '',
      }
      await router.push({ name: 'workbench-employee', query: q })
      return
    }
  } catch (e) {
    finalizeError.value = e.message || String(e)
  } finally {
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
    workflow: hasWorkflow.value ? 'workbench-workflow' : null,
  }[kind]
  if (fallback && router.hasRoute(fallback)) {
    router.push({ name: fallback })
  }
}

function buildPlanSystemPrompt(intentKey, intentTitle) {
  const typeHint =
    intentKey === 'workflow'
      ? '关注触发条件、数据来源、节点顺序、失败重试与人工介入点。流程图用 flowchart LR 或 TD，节点用简短中文，避免括号、引号、特殊符号破坏 Mermaid 语法。'
      : intentKey === 'mod'
        ? '用户目标通常是：先在 Mod 库建仓库，再按行业在 manifest（JSON）里落好字段骨架，并在 workflow_employees 中为需要的员工命名与占位（不必一次写全表结构、规则与接口实现）。澄清时优先确认：行业/场景、仓库 id、要几名员工及各字职责一句话。Mermaid 须用 flowchart 画出「建仓库 → 行业JSON骨架 → 员工命名 →（可选）表规则接口迭代」的主线，节点名两到六字中文，不用括号。'
        : '关注员工角色、可用工具/能力标识、输入输出与行业场景。Mermaid 用 flowchart 表示角色、工具、输出关系即可。'
  const diagramParity =
    intentKey === 'mod'
      ? '【与做员工对齐】每条回复的流程图要求与「做员工」完全相同：不得以「暂无图」「略」或纯文字代替拓扑；必须在 fenced Mermaid 中给出 flowchart。信息不足时仍输出极简示例，例如：flowchart LR 建仓库 --> 写JSON骨架 --> 员工命名。'
      : intentKey === 'employee'
        ? '【流程图】每条回复须含 fenced Mermaid flowchart，不得以纯文字代替；信息不足时用 3～5 个短中文节点概括角色与产出。'
        : ''
  return [
    `你是 XCAGI 工作台的「需求规划」助手（风格接近 Cursor 的 Plan）。用户当前制作类型：「${intentTitle}」。`,
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
    '[{"id":"q1","title":"短标题","choices":[{"id":"c1","label":"选项甲"},{"id":"c2","label":"选项乙"}]}]',
    '<<<END_PLAN_OPTIONS>>>',
    'JSON 须为单行；每项含 id、title、choices（2～5 项，每项 id 与 label）；label 内勿用英文双引号。',
    '除上述各段外不要输出其它前言或后记。',
  ].join('\n')
}

function formatPlanMessagesForBrief(msgs) {
  if (!Array.isArray(msgs) || !msgs.length) return ''
  return msgs
    .map((m) => `${m.role === 'user' ? '用户' : '助手'}：${m.content}`)
    .join('\n\n')
}

function parseChecklistBlock(raw) {
  let s = String(raw || '')
  const mer = s.match(/```mermaid\s*[\s\S]*?```/i)
  if (mer) s = s.replace(mer[0], '')
  const pd = s.match(/<<<PLAN_DETAILS>>>([\s\S]*?)<<<END_PLAN_DETAILS>>>/i)
  if (pd) s = s.replace(pd[0], '')
  const po = s.match(/<<<PLAN_OPTIONS>>>([\s\S]*?)<<<END_PLAN_OPTIONS>>>/i)
  if (po) s = s.replace(po[0], '')
  const m = s.match(/<<<CHECKLIST>>>([\s\S]*?)<<<END>>>/i)
  if (!m) return null
  const body = m[1].trim()
  const lines = body
    .split(/\r?\n/)
    .map((l) => l.replace(/^\s*\d+[\.)]\s*/, '').trim())
    .filter(Boolean)
  if (!lines.length) return null
  const text = lines.map((l, i) => `${i + 1}. ${l}`).join('\n')
  return { text, lines }
}

function _providerRowHasUsableKey(row, fernetOk) {
  if (!row) return false
  if (row.has_platform_key) return true
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

async function appendUserAndAssistantPlanTurn(userText) {
  const ps = planSession.value
  if (!ps) return
  ps.messages.push({ role: 'user', content: userText })
  ps.planError = ''
  const { provider, model } = await resolveChatProviderModel()
  const sys = buildPlanSystemPrompt(ps.intentKey, ps.intentTitle)
  const apiMsgs = [
    { role: 'system', content: sys },
    ...ps.messages.map((m) => ({ role: m.role, content: m.content })),
  ]
  const res = await api.llmChat(provider, model, apiMsgs, 2048)
  const c = typeof res?.content === 'string' ? res.content : ''
  ps.messages.push({ role: 'assistant', content: (c || '').trim() || '（无回复）' })
}

async function openPlanSession(initialText) {
  planSurfaceKey.value += 1
  const meta = INTENT_META[composerIntent.value] || INTENT_META.workflow
  planSession.value = {
    intentKey: composerIntent.value,
    intentTitle: meta.title,
    phase: 'chat',
    initialBrief: initialText,
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
    await appendUserAndAssistantPlanTurn(initialText)
  } catch (e) {
    if (planSession.value) {
      planSession.value.planError = e.message || String(e)
      planSession.value.messages = []
    }
  } finally {
    if (planSession.value) planSession.value.loading = false
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
    ps.planError = e.message || String(e)
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
    const sys = buildPlanSystemPrompt(ps.intentKey, ps.intentTitle)
    const tail = {
      role: 'user',
      content:
        '请根据以上整段对话，输出一份可直接照着实现的「执行清单」。不要输出 ```mermaid 代码块，也不要输出 <<<PLAN_DETAILS>>> 或 <<<PLAN_OPTIONS>>> 段；只输出 <<<CHECKLIST>>> 与 <<<END>>> 包裹的清单。严格使用格式：第一行仅为 <<<CHECKLIST>>>，接着每行一条任务（以「1.」「2.」编号），最后一行仅为 <<<END>>>。不要写其它说明文字。',
    }
    const apiMsgs = [
      { role: 'system', content: sys },
      ...ps.messages.map((m) => ({ role: m.role, content: m.content })),
      tail,
    ]
    const res = await api.llmChat(provider, model, apiMsgs, 2048)
    const raw = typeof res?.content === 'string' ? res.content : ''
    const parsed = parseChecklistBlock(raw)
    if (!parsed) {
      ps.planError =
        '未能解析清单（需要 <<<CHECKLIST>>> … <<<END>>> 包裹）。可补充说明后重试「生成执行清单」。'
      return
    }
    ps.checklistText = parsed.text
    ps.checklistLines = parsed.lines
    ps.phase = 'checklist'
  } catch (e) {
    ps.planError = e.message || String(e)
  } finally {
    ps.loading = false
    scrollPlanIntoView()
  }
}

function onPlanReplyKeydown(e) {
  if (e.key !== 'Enter' || e.shiftKey) return
  e.preventDefault()
  void sendPlanReply()
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
  pendingHandoff.value = {
    description,
    intentTitle: ps.intentTitle,
    intentKey: ps.intentKey,
    workflowName: '',
    planNotes: ps.intentKey === 'workflow' ? ps.checklistText : '',
    suggestedModId: '',
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
  if (!text || !hasWorkflow.value) return
  if (!requireLoginForWorkbenchUse()) return
  if (planSession.value) {
    finalizeError.value = '请先完成或关闭上方的「需求规划」面板。'
    return
  }
  finalizeError.value = ''
  let knowledgePack = ''
  try {
    const res = await api.knowledgeSearch(text, 6)
    knowledgePack = formatKnowledgeContext(res?.items)
  } catch (e) {
    knowledgeError.value = e?.message || String(e)
  }
  const payload = knowledgePack
    ? `${text}\n\n---\n【我的文件资料库命中片段】\n${knowledgePack}`
    : text
  await openPlanSession(payload)
}

function onComposerKeydown(e) {
  if (planSession.value) return
  if (e.key !== 'Enter' || e.shiftKey) return
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
  overflow: hidden;
}

.wb-home-inner--no-workflow {
  flex: 0 1 auto;
  gap: 1.25rem;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.wb-hero {
  text-align: center;
}

.wb-hero-kicker {
  margin: 0 0 0.35rem;
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
  font-size: 0.45rem;
  font-weight: 700;
  line-height: 1;
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

.wb-direct-scene,
.wb-voice-scene {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(0.8rem, 1.8vw, 1.25rem);
  text-align: center;
}

.wb-direct-scene {
  position: relative;
  /* 为右上角绝对定位的消费档位留出顶栏空间，避免与标题叠压 */
  padding-top: clamp(2.5rem, 4.5vw, 3.1rem);
}

.wb-direct-tier-anchor {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 4;
  max-width: min(calc(100% - 0.5rem), 22rem);
  padding-left: 0.75rem;
}

.wb-make-scene {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(0.72rem, 1.4vw, 1rem);
  padding-inline: clamp(1rem, 3vw, 3rem);
}

.wb-make-scene > .wb-plan,
.wb-make-scene > .wb-orch,
.wb-make-scene > .wb-handoff,
.wb-make-scene > .wb-composer-column,
.wb-make-scene > .wb-starters,
.wb-make-scene > .wb-foot {
  width: min(100%, 64rem);
}

.wb-direct-hero,
.wb-voice-copy {
  max-width: 42rem;
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
}

.wb-direct-sub,
.wb-voice-sub {
  margin: 0.65rem 0 0;
  color: rgba(226, 232, 240, 0.58);
  font-size: clamp(0.95rem, 0.9rem + 0.22vw, 1.1rem);
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
}

.wb-direct-box-main {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: end;
  gap: 0.55rem 0.65rem;
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

.wb-direct-file-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0 0.1rem 0.15rem;
}

.wb-direct-file-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  max-width: 100%;
  padding: 0.22rem 0.35rem 0.22rem 0.45rem;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.28);
  border: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 0.72rem;
  color: rgba(226, 232, 240, 0.88);
  transition: border-color 0.18s ease, background 0.18s ease;
}

.wb-direct-file-chip--ready {
  border-color: rgba(94, 234, 212, 0.45);
  background: rgba(13, 148, 136, 0.18);
}

.wb-direct-file-chip--uploading {
  border-color: rgba(165, 180, 252, 0.45);
  background: rgba(79, 70, 229, 0.18);
}

.wb-direct-file-chip--error,
.wb-direct-file-chip--skipped {
  border-color: rgba(248, 113, 113, 0.4);
  background: rgba(127, 29, 29, 0.22);
}

.wb-direct-file-chip__dot {
  display: grid;
  place-items: center;
  width: 0.95rem;
  height: 0.95rem;
  flex-shrink: 0;
  font-size: 0.65rem;
  font-weight: 800;
  line-height: 1;
}

.wb-direct-file-chip__check {
  color: #5eead4;
}

.wb-direct-file-chip__warn {
  color: #fca5a5;
}

.wb-direct-file-chip__spinner {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 999px;
  border: 1.5px solid rgba(165, 180, 252, 0.35);
  border-top-color: rgba(199, 210, 254, 0.95);
  animation: wb-direct-file-chip-spin 0.85s linear infinite;
}

@keyframes wb-direct-file-chip-spin {
  to {
    transform: rotate(360deg);
  }
}

.wb-direct-attach-hint {
  margin: 0;
  padding: 0 0.15rem;
  font-size: 0.7rem;
  line-height: 1.35;
  color: rgba(148, 163, 184, 0.85);
  text-align: left;
}

.wb-direct-file-chip__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 12rem;
}

.wb-direct-file-chip__meta {
  flex-shrink: 0;
  color: rgba(148, 163, 184, 0.85);
  font-variant-numeric: tabular-nums;
}

.wb-direct-file-chip__remove {
  display: grid;
  place-items: center;
  width: 1.25rem;
  height: 1.25rem;
  margin: -0.1rem -0.15rem -0.1rem 0;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: rgba(248, 250, 252, 0.55);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
}

.wb-direct-file-chip__remove:hover:not(:disabled) {
  color: #fecaca;
  background: rgba(248, 113, 113, 0.12);
}

.wb-direct-file-chip__remove:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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
}

.wb-direct-thread,
.wb-voice-thread {
  width: min(50rem, 100%);
  max-height: 12rem;
  overflow-y: auto;
  display: grid;
  gap: 0.5rem;
  text-align: left;
}

.wb-direct-msg,
.wb-voice-msg {
  padding: 0.65rem 0.8rem;
  border-radius: 0.85rem;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(248, 250, 252, 0.9);
}

.wb-direct-msg--user,
.wb-voice-msg--user {
  justify-self: end;
  max-width: 82%;
  background: rgba(129, 140, 248, 0.22);
}

.wb-direct-msg__role {
  display: block;
  margin-bottom: 0.2rem;
  color: rgba(255, 255, 255, 0.48);
  font-size: 0.68rem;
  font-weight: 700;
}

.wb-direct-msg__body {
  margin: 0;
  white-space: pre-wrap;
}

.wb-direct-error,
.wb-voice-error {
  margin: 0;
  color: rgba(252, 165, 165, 0.95);
  font-size: 0.82rem;
}

.wb-voice-orb-wrap {
  position: relative;
  display: grid;
  place-items: center;
  width: min(18rem, 48vw);
  aspect-ratio: 1;
}

.wb-voice-orb {
  position: relative;
  width: 72%;
  aspect-ratio: 1;
  border: none;
  border-radius: 999px;
  background:
    radial-gradient(circle at 35% 28%, rgba(255, 255, 255, 0.9), transparent 11%),
    radial-gradient(circle, rgba(125, 211, 252, 0.9), rgba(59, 130, 246, 0.36) 45%, rgba(15, 23, 42, 0.1) 70%);
  box-shadow:
    0 0 36px rgba(56, 189, 248, 0.32),
    0 0 90px rgba(99, 102, 241, 0.2);
  cursor: pointer;
  animation: wb-orb-breathe 3.2s ease-in-out infinite;
}

.wb-voice-orb__ring,
.wb-voice-orb__core {
  position: absolute;
  inset: -12%;
  border-radius: inherit;
  border: 1px solid rgba(125, 211, 252, 0.35);
  animation: wb-orb-ring 4s linear infinite;
}

.wb-voice-orb__core {
  inset: 24%;
  border: none;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.75), rgba(125, 211, 252, 0.16));
  animation: none;
}

.wb-voice-orb--listening {
  animation-duration: 1.25s;
  box-shadow:
    0 0 44px rgba(45, 212, 191, 0.48),
    0 0 120px rgba(56, 189, 248, 0.35);
}

.wb-voice-orb--thinking .wb-voice-orb__ring {
  animation-duration: 1.2s;
  border-style: dashed;
}

.wb-voice-orb--summary {
  box-shadow:
    0 0 52px rgba(196, 181, 253, 0.52),
    0 0 130px rgba(129, 140, 248, 0.36);
}

@keyframes wb-orb-breathe {
  0%, 100% {
    transform: scale(0.96);
  }
  50% {
    transform: scale(1.03);
  }
}

@keyframes wb-orb-ring {
  to {
    transform: rotate(360deg);
  }
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
  min-width: 0;
  min-height: 5rem;
  border-radius: 0.9rem;
  border: none;
  background: rgba(30, 41, 59, 0.5);
  padding: 0.55rem 0.6rem;
  overflow: auto;
  max-height: min(32vh, 16rem);
  box-shadow: 0 12px 28px -16px rgba(0, 0, 0, 0.35);
}

.wb-plan-diagram-fallback {
  margin: 0;
  padding: 0.5rem 0.35rem;
  font-size: 0.82rem;
  line-height: 1.45;
  color: rgba(191, 219, 254, 0.65);
}

.wb-plan-diagram-host {
  min-height: 3rem;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.wb-plan-diagram-host :deep(svg) {
  max-width: 100%;
  height: auto;
}

.wb-plan-diagram-err {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  line-height: 1.35;
  color: #fecaca;
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

.wb-plan-quick-send {
  width: 100%;
  margin-top: 0.15rem;
  padding: 0.42rem 0.85rem;
  font-size: 0.86rem;
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

.wb-plan-checklist-title {
  margin: 0 0 0.5rem;
  font-size: 0.92rem;
  font-weight: 600;
  color: rgba(224, 231, 255, 0.95);
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
  border-radius: 1.125rem;
  border: 1px solid rgba(52, 211, 153, 0.28);
  background: rgba(16, 185, 129, 0.08);
  padding: 1rem 1.15rem 1.05rem;
}

.wb-orch-title {
  margin: 0 0 0.65rem;
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(167, 243, 208, 0.85);
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

.wb-handoff {
  border-radius: 1.125rem;
  border: 1px solid rgba(129, 140, 248, 0.28);
  background: rgba(99, 102, 241, 0.1);
  padding: 1rem 1.15rem 1.1rem;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.15);
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
}

.wb-handoff-textarea {
  line-height: 1.5;
  resize: vertical;
  min-height: 4.5rem;
}

.wb-handoff-textarea--sm {
  min-height: 3.25rem;
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

.wb-handoff-foot {
  margin: 0.65rem 0 0;
  font-size: 0.75rem;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.38);
}

.wb-handoff-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
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
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 0.5rem 0.75rem;
  padding: 0.45rem 0.75rem 0.65rem 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.wb-input-hint {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
}

.wb-input-hint__intent {
  font-size: clamp(0.8rem, 0.75rem + 0.15vw, 0.875rem);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.52);
}

.wb-input-hint__keys {
  font-size: clamp(0.72rem, 0.7rem + 0.08vw, 0.8rem);
  color: rgba(255, 255, 255, 0.28);
}

.wb-footer-trailing {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
  margin-left: auto;
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
