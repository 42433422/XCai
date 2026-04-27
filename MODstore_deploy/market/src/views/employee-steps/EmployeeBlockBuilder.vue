<template>
  <section :class="['builder', immersive ? 'builder--immersive' : '']">
    <div class="canvas-toolbar">
      <div class="tool-group">
        <button type="button" class="btn btn-sm btn-tool" @click="resetView">重置视图</button>
        <button type="button" class="btn btn-sm btn-tool" @click="fitToNodes">适配全图</button>
        <button type="button" class="btn btn-sm btn-tool" @click="autoLayout">自动布局</button>
      </div>
      <div class="tool-group">
        <button type="button" class="btn btn-sm btn-tool" @click="viewport.scale = Math.max(0.55, viewport.scale - 0.1)">-</button>
        <button type="button" class="btn btn-sm btn-tool" @click="viewport.scale = Math.min(1.8, viewport.scale + 0.1)">+</button>
      </div>
      <span class="zoom-chip">{{ Math.round(viewport.scale * 100) }}%</span>
    </div>
    <div v-if="!immersive || showLibraryDrawer" :class="['col','library', immersive ? 'drawer-floating drawer-floating--left' : '', guideTarget === 'library' ? 'spotlight' : '']">
      <h3>模板与模块库</h3>
      <select class="input" :class="{ spotlight: guideTarget === 'library' }" :value="templateId" @change="$emit('template-change', $event.target.value)">
        <option value="workflow">workflow</option>
        <option value="dialog">dialog</option>
        <option value="phone">phone</option>
        <option value="data">data</option>
        <option value="full">full</option>
        <option value="blank">blank</option>
      </select>
      <button type="button" class="btn btn-primary btn-sm" :class="{ spotlight: guideTarget === 'library' }" @click="loadSampleEmployee">样板员工</button>
      <button v-for="m in moduleDefs" :key="m.key" type="button" class="btn btn-sm lib-item" :disabled="isInCanvas(m.key)" @click="addModule(m.key)">
        <span class="dot"></span>{{ m.label }}
      </button>
      <button type="button" class="btn btn-sm" :class="{ spotlight: guideTarget === 'library' }" @click="$emit('export-zip')">导出 employee_pack zip</button>
      <div v-if="isEmptyWorkbench" class="empty-helper">
        <p>空状态：先载入示例模板，1 分钟即可跑通</p>
        <div class="ops">
          <button type="button" class="btn btn-sm btn-primary" @click="loadSampleEmployee">客服协作示例</button>
          <button type="button" class="btn btn-sm" @click="loadDataAnalystSample">数据分析示例</button>
        </div>
      </div>
    </div>

    <div class="col canvas board-grid" :class="{ spotlight: guideTarget === 'canvas' }">
      <h3>画布（白板）</h3>
      <div class="whiteboard" @mousedown="startPan" @wheel.prevent="onWheel">
        <div v-if="immersive" class="canvas-fab-group">
          <button type="button" class="btn btn-sm" @click="showLibraryDrawer = !showLibraryDrawer">{{ showLibraryDrawer ? '收起模块' : '模块库' }}</button>
          <button type="button" class="btn btn-sm" @click="showConfigDrawer = !showConfigDrawer">{{ showConfigDrawer ? '收起属性' : '属性面板' }}</button>
          <button type="button" class="btn btn-sm" @click="showEdgeDrawer = !showEdgeDrawer">{{ showEdgeDrawer ? '收起连线' : '模块连线' }}</button>
        </div>
        <svg class="wb-edges">
          <defs>
            <linearGradient id="edgeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="rgba(99,102,241,.95)" />
              <stop offset="100%" stop-color="rgba(56,189,248,.95)" />
            </linearGradient>
          </defs>
          <path
            v-for="(edge, idx) in renderedEdges"
            :key="`edge-glow-${idx}`"
            :d="edge.d"
            stroke="rgba(56,189,248,.20)"
            stroke-width="8"
            fill="none"
            stroke-linecap="round"
          />
          <line
            v-for="(edge, idx) in renderedEdges"
            :key="`edge-${idx}`"
            :x1="edge.lx1"
            :y1="edge.ly1"
            :x2="edge.lx2"
            :y2="edge.ly2"
            stroke="url(#edgeGradient)"
            stroke-width="2"
          />
          <path
            v-for="(edge, idx) in renderedEdges"
            :key="`edge-main-${idx}`"
            :d="edge.d"
            stroke="url(#edgeGradient)"
            stroke-width="2.5"
            fill="none"
            stroke-linecap="round"
            :stroke-dasharray="edge.condition ? '6 5' : ''"
            @click.stop="openEdgeConfig(edge.index)"
          />
        </svg>
        <div class="wb-title">AI Employee Workbench</div>
        <div
          v-for="(key, idx) in canvasModules"
          :key="key"
          class="wb-node"
          :class="{ active: selectedModule === key }"
          :style="nodeStyle(key)"
          @mousedown.stop="startNodeDrag($event, key)"
          @click.stop="selectedModule = key"
        >
          <div class="node-title">{{ labelOf(key) }}</div>
          <div class="node-meta">{{ moduleMeta(key) || '未配置' }}</div>
          <div class="ops">
            <button type="button" class="btn btn-sm" :disabled="idx === 0" @click.stop="moveUp(idx)">↑</button>
            <button type="button" class="btn btn-sm" :disabled="idx === canvasModules.length - 1" @click.stop="moveDown(idx)">↓</button>
            <button type="button" class="btn btn-sm" :disabled="key === 'collaboration'" @click.stop="removeModule(key)">移除</button>
          </div>
        </div>
      </div>
      <p v-if="!immersive" class="hint">画布操作：滚轮缩放（按鼠标位置缩放）、空白拖动画布、拖拽节点调整布局。</p>
      <p v-if="!immersive" class="hint">心脏模块「协作」已锁定必选，不能移除。</p>
      <div v-if="!immersive || showEdgeDrawer" :class="['edge-drawer', immersive ? 'edge-drawer--floating' : '']">
        <h4 class="sub">模块连线</h4>
        <div class="row">
          <select class="input" v-model="edgeFrom"><option v-for="k in canvasModules" :key="`f-${k}`" :value="k">{{ labelOf(k) }}</option></select>
          <select class="input" v-model="edgeTo"><option v-for="k in canvasModules" :key="`t-${k}`" :value="k">{{ labelOf(k) }}</option></select>
          <button type="button" class="btn btn-sm" @click="addEdge">添加连线</button>
        </div>
        <input class="input" :value="edgeCondition" placeholder="条件表达式（可选）" @input="edgeCondition = $event.target.value" />
        <div v-for="(e, i) in edgeEntries" :key="`e-${i}`" class="edge-item">
          <span>{{ labelOf(e.from) }} -> {{ labelOf(e.to) }} <em v-if="e.condition">[条件]</em></span>
          <button type="button" class="btn btn-sm" @click="removeEdge(i)">删除</button>
        </div>
        <div v-if="editingEdgeIndex >= 0" class="cfg-card">
          <h4 class="sub">连线配置</h4>
          <input class="input" :value="editingEdgeCondition" placeholder="condition" @input="editingEdgeCondition = $event.target.value" />
          <div class="ops">
            <button type="button" class="btn btn-sm" @click="saveEdgeConfig">保存条件</button>
            <button type="button" class="btn btn-sm" @click="removeEdge(editingEdgeIndex)">删除连线</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!immersive || showConfigDrawer" :class="['col','config','right-drawer', immersive ? 'drawer-floating drawer-floating--right' : '', guideTarget === 'config' ? 'spotlight' : '']">
      <h3>配置面板</h3>
      <label class="hint"><input type="checkbox" :checked="showAllConfigs" @change="showAllConfigs = $event.target.checked"> 同时展开全部模块卡片</label>

      <div v-if="showAllConfigs || selectedModule === 'identity'" class="cfg-card">
        <div class="cfg-head">
          <h4 class="cfg-title">身份</h4>
          <span class="cfg-badge ok">{{ moduleStatusLabel('identity') }}</span>
          <span class="cfg-meta">{{ moduleMeta('identity') }}</span>
          <button type="button" class="btn btn-sm" @click="toggleCollapse('identity')">{{ isCollapsed('identity') ? '展开' : '折叠' }}</button>
        </div>
        <div v-show="!isCollapsed('identity')" class="cfg-body">
        <input class="input" :value="local.identity.id" placeholder="identity.id" @input="patchIdentity('id', $event.target.value)" />
        <input class="input" :value="local.identity.version" placeholder="identity.version" @input="patchIdentity('version', $event.target.value)" />
        <input class="input" :value="local.identity.name" placeholder="identity.name" @input="patchIdentity('name', $event.target.value)" />
        <textarea class="input" :value="local.identity.description" placeholder="identity.description" @input="patchIdentity('description', $event.target.value)" />
        <input class="input" :value="local.identity.icon || ''" placeholder="identity.icon" @input="patchIdentity('icon', $event.target.value)" />
        <input class="input" :value="(local.identity.tags || []).join(',')" placeholder="identity.tags (a,b,c)" @input="patchIdentityTags($event.target.value)" />
        <input class="input" :value="local.identity.author || ''" placeholder="identity.author" @input="patchIdentity('author', $event.target.value)" />
        </div>
      </div>

      <div v-if="showAllConfigs || selectedModule === 'perception'" class="cfg-card">
        <div class="cfg-head">
          <h4 class="cfg-title">感知</h4>
          <span :class="['cfg-badge', isModuleEnabled('perception') ? 'ok' : 'off']">{{ moduleStatusLabel('perception') }}</span>
          <span class="cfg-meta">{{ moduleMeta('perception') }}</span>
          <button type="button" class="btn btn-sm" @click="toggleModuleEnabled('perception')">{{ isModuleEnabled('perception') ? '停用' : '启用' }}</button>
          <button type="button" class="btn btn-sm" @click="toggleCollapse('perception')">{{ isCollapsed('perception') ? '展开' : '折叠' }}</button>
        </div>
        <div v-show="!isCollapsed('perception') && isModuleEnabled('perception')" class="cfg-body">
        <label><input type="checkbox" :checked="Boolean(local.perception?.vision?.enabled)" @change="togglePath('perception.vision', $event.target.checked, { enabled: true, supported_formats: ['png', 'jpg'] })" /> 视觉</label>
        <label><input type="checkbox" :checked="Boolean(local.perception?.audio?.enabled)" @change="togglePath('perception.audio', $event.target.checked, { enabled: true, asr: { enabled: false, languages: ['zh-CN'] } })" /> 听觉</label>
        <label><input type="checkbox" :checked="Boolean(local.perception?.document?.enabled)" @change="togglePath('perception.document', $event.target.checked, { enabled: true, supported_formats: ['pdf', 'docx'] })" /> 文档</label>
        <label><input type="checkbox" :checked="Boolean(local.perception?.data_input?.enabled)" @change="togglePath('perception.data_input', $event.target.checked, { enabled: true, api_sources: [] })" /> 数据</label>
        <label><input type="checkbox" :checked="Boolean(local.perception?.event_listener?.enabled)" @change="togglePath('perception.event_listener', $event.target.checked, { enabled: true, topics: [] })" /> 事件</label>
        </div>
      </div>

      <div v-if="showAllConfigs || selectedModule === 'memory'" class="cfg-card">
        <div class="cfg-head">
          <h4 class="cfg-title">记忆</h4>
          <span :class="['cfg-badge', isModuleEnabled('memory') ? 'ok' : 'off']">{{ moduleStatusLabel('memory') }}</span>
          <span class="cfg-meta">{{ moduleMeta('memory') }}</span>
          <button type="button" class="btn btn-sm" @click="toggleModuleEnabled('memory')">{{ isModuleEnabled('memory') ? '停用' : '启用' }}</button>
          <button type="button" class="btn btn-sm" @click="toggleCollapse('memory')">{{ isCollapsed('memory') ? '展开' : '折叠' }}</button>
        </div>
        <div v-show="!isCollapsed('memory') && isModuleEnabled('memory')" class="cfg-body">
        <input class="input" type="number" min="1024" :value="Number(local.memory?.short_term?.context_window || 8000)" placeholder="short_term.context_window" @input="setPath('memory.short_term.context_window', Number($event.target.value || 8000))" />
        <input class="input" type="number" min="60" :value="Number(local.memory?.short_term?.session_timeout || 1800)" placeholder="short_term.session_timeout" @input="setPath('memory.short_term.session_timeout', Number($event.target.value || 1800))" />
        <label><input type="checkbox" :checked="Boolean(local.memory?.long_term?.enabled)" @change="togglePath('memory.long_term', $event.target.checked, { enabled: true, sources: [], retrieval: { strategy: 'hybrid', top_k: 5, similarity_threshold: 0.75, rerank_enabled: true }, chunk_size: 800, chunk_overlap: 100 })" /> 长期记忆</label>
        <div v-if="local.memory?.long_term?.enabled" class="cfg-card">
          <h5 class="sub">知识来源</h5>
          <div v-for="(source, idx) in memorySources" :key="`ms-${idx}`" class="cfg-body">
            <input class="input" :value="source.name || ''" placeholder="来源名称" @input="patchMemorySource(idx, 'name', $event.target.value)" />
            <select class="input" :value="source.type || 'document'" @change="patchMemorySource(idx, 'type', $event.target.value)">
              <option value="document">文件</option><option value="url">URL</option><option value="database">数据库</option><option value="api">API</option>
            </select>
            <textarea class="input" :value="(source.paths || []).join('\n')" placeholder="路径/URL（每行一个）" @input="patchMemorySource(idx, 'paths', lines($event.target.value))" />
            <button type="button" class="btn btn-sm" @click="removeMemorySource(idx)">删除来源</button>
          </div>
          <button type="button" class="btn btn-sm" @click="addMemorySource">添加来源</button>
          <div class="row row-2">
            <input class="input" type="number" :value="Number(local.memory?.long_term?.chunk_size || 800)" @input="setPath('memory.long_term.chunk_size', Number($event.target.value || 800))" />
            <input class="input" type="number" :value="Number(local.memory?.long_term?.chunk_overlap || 100)" @input="setPath('memory.long_term.chunk_overlap', Number($event.target.value || 100))" />
          </div>
          <div class="row row-2">
            <select class="input" :value="local.memory?.long_term?.retrieval?.strategy || 'hybrid'" @change="setPath('memory.long_term.retrieval.strategy', $event.target.value)">
              <option value="vector">向量</option><option value="keyword">关键词</option><option value="hybrid">混合</option>
            </select>
            <input class="input" type="number" min="1" :value="Number(local.memory?.long_term?.retrieval?.top_k || 5)" @input="setPath('memory.long_term.retrieval.top_k', Number($event.target.value || 5))" />
          </div>
        </div>
        <label><input type="checkbox" :checked="Boolean(local.memory?.profile?.enabled)" @change="togglePath('memory.profile', $event.target.checked, { enabled: true, fields: [] })" /> 用户画像</label>
        <label><input type="checkbox" :checked="Boolean(local.memory?.experience?.enabled)" @change="togglePath('memory.experience', $event.target.checked, { enabled: true, stores: [] })" /> 经验库</label>
        </div>
      </div>

      <div v-if="showAllConfigs || selectedModule === 'cognition'" class="cfg-card">
        <div class="cfg-head">
          <h4 class="cfg-title">认知</h4>
          <span :class="['cfg-badge', isModuleEnabled('cognition') ? 'ok' : 'off']">{{ moduleStatusLabel('cognition') }}</span>
          <span class="cfg-meta">{{ moduleMeta('cognition') }}</span>
          <button type="button" class="btn btn-sm" @click="toggleModuleEnabled('cognition')">{{ isModuleEnabled('cognition') ? '停用' : '启用' }}</button>
          <button type="button" class="btn btn-sm" @click="toggleCollapse('cognition')">{{ isCollapsed('cognition') ? '展开' : '折叠' }}</button>
        </div>
        <div v-show="!isCollapsed('cognition') && isModuleEnabled('cognition')" class="cfg-body">
        <input class="input" :value="local.cognition?.agent?.role?.name || ''" placeholder="角色名称" @input="setPath('cognition.agent.role.name', $event.target.value)" />
        <textarea class="input" :value="local.cognition?.agent?.role?.persona || ''" placeholder="人设描述" @input="setPath('cognition.agent.role.persona', $event.target.value)" />
        <select class="input" :value="local.cognition?.agent?.role?.tone || 'professional'" @change="setPath('cognition.agent.role.tone', $event.target.value)">
          <option value="formal">正式</option><option value="friendly">友好</option><option value="professional">专业</option><option value="casual">活泼</option>
        </select>
        <input class="input" :value="(local.cognition?.agent?.role?.expertise || []).join(',')" placeholder="专业领域（逗号分隔）" @input="setPath('cognition.agent.role.expertise', splitTags($event.target.value))" />
        <textarea class="input" :value="local.cognition?.agent?.system_prompt || ''" placeholder="系统提示词（支持 {user_name} {task_type} {context}）" @input="setPath('cognition.agent.system_prompt', $event.target.value)" />
        <p class="hint">提示词字数：{{ String(local.cognition?.agent?.system_prompt || '').length }}</p>
        <div class="ops">
          <button type="button" class="btn btn-sm" @click="optimizePrompt">AI 优化提示词</button>
          <button type="button" class="btn btn-sm" @click="setPath('cognition.agent.system_prompt','')">清空</button>
        </div>
        <h5 class="sub">行为规则</h5>
        <div v-for="(rule, idx) in behaviorRules" :key="`r-${idx}`" class="cfg-card">
          <input class="input" :value="rule.name || ''" placeholder="规则名称" @input="patchBehaviorRule(idx, 'name', $event.target.value)" />
          <input class="input" :value="rule.description || ''" placeholder="规则描述" @input="patchBehaviorRule(idx, 'description', $event.target.value)" />
          <div class="row row-2">
            <select class="input" :value="rule.priority || 'medium'" @change="patchBehaviorRule(idx, 'priority', $event.target.value)">
              <option value="high">高</option><option value="medium">中</option><option value="low">低</option>
            </select>
            <select class="input" :value="rule.action || 'warn'" @change="patchBehaviorRule(idx, 'action', $event.target.value)">
              <option value="filter">过滤</option><option value="enforce">强制执行</option><option value="warn">警告</option><option value="reject">拒绝</option>
            </select>
          </div>
          <button type="button" class="btn btn-sm" @click="removeBehaviorRule(idx)">删除规则</button>
        </div>
        <button type="button" class="btn btn-sm" @click="addBehaviorRule">添加规则</button>
        <h5 class="sub">Few-Shot 示例</h5>
        <div v-for="(item, idx) in fewShotExamples" :key="`ex-${idx}`" class="cfg-card">
          <textarea class="input" :value="item.input || ''" placeholder="用户输入" @input="patchFewShot(idx, 'input', $event.target.value)" />
          <textarea class="input" :value="item.output || ''" placeholder="期望输出" @input="patchFewShot(idx, 'output', $event.target.value)" />
          <input class="input" :value="item.explanation || ''" placeholder="说明（可选）" @input="patchFewShot(idx, 'explanation', $event.target.value)" />
          <button type="button" class="btn btn-sm" @click="removeFewShot(idx)">删除示例</button>
        </div>
        <button type="button" class="btn btn-sm" @click="addFewShot">添加示例</button>
        <SkillSelector :model-value="local.cognition?.skills || []" @update:model-value="setPath('cognition.skills', $event)" />
        <div class="row">
          <select class="input" :value="local.cognition?.agent?.model?.provider || 'deepseek'" @change="setPath('cognition.agent.model.provider', $event.target.value)">
            <option value="deepseek">deepseek</option><option value="openai">openai</option><option value="anthropic">anthropic</option><option value="local">local</option>
          </select>
          <input class="input" :value="local.cognition?.agent?.model?.model_name || 'deepseek-chat'" placeholder="model.model_name" @input="setPath('cognition.agent.model.model_name', $event.target.value)" />
          <input class="input" type="range" min="0" max="1" step="0.05" :value="Number(local.cognition?.agent?.model?.temperature || 0.7)" @input="setPath('cognition.agent.model.temperature', Number($event.target.value || 0.7))" />
        </div>
        <div class="row row-3">
          <input class="input" type="number" min="1" :value="Number(local.cognition?.agent?.model?.max_tokens || 4000)" placeholder="max_tokens" @input="setPath('cognition.agent.model.max_tokens', Number($event.target.value || 4000))" />
          <input class="input" type="range" min="0" max="1" step="0.05" :value="Number(local.cognition?.agent?.model?.top_p || 0.9)" @input="setPath('cognition.agent.model.top_p', Number($event.target.value || 0.9))" />
          <label><input type="checkbox" :checked="Boolean(local.cognition?.agent?.model?.stream)" @change="setPath('cognition.agent.model.stream', $event.target.checked)" /> 流式输出</label>
        </div>
        </div>
      </div>

      <div v-if="showAllConfigs || selectedModule === 'actions'" class="cfg-card">
        <div class="cfg-head">
          <h4 class="cfg-title">行动</h4>
          <span :class="['cfg-badge', isModuleEnabled('actions') ? 'ok' : 'off']">{{ moduleStatusLabel('actions') }}</span>
          <span class="cfg-meta">{{ moduleMeta('actions') }}</span>
          <button type="button" class="btn btn-sm" @click="toggleModuleEnabled('actions')">{{ isModuleEnabled('actions') ? '停用' : '启用' }}</button>
          <button type="button" class="btn btn-sm" @click="toggleCollapse('actions')">{{ isCollapsed('actions') ? '展开' : '折叠' }}</button>
        </div>
        <div v-show="!isCollapsed('actions') && isModuleEnabled('actions')" class="cfg-body">
        <label><input type="checkbox" :checked="Boolean(local.actions?.text_output?.enabled)" @change="togglePath('actions.text_output', $event.target.checked, { enabled: true, formats: ['text', 'json'] })" /> 文本输出</label>
        <label><input type="checkbox" :checked="Boolean(local.actions?.voice_output?.enabled)" @change="togglePath('actions.voice_output', $event.target.checked, { enabled: true, voice_cloning: { voice_id: '', voice_name: '', source_type: 'preset', source_files: [], settings: { speed: 1, pitch: 0, emotion: 'neutral', language: 'zh-CN' }, status: 'untrained' }, tts: { provider: 'aliyun', voice_name: '', sample_rate: 24000 } })" /> 语音</label>
        <div v-if="local.actions?.voice_output?.enabled" class="cfg-card">
          <h5 class="sub">声音克隆配置</h5>
          <select class="input" :value="local.actions?.voice_output?.voice_cloning?.source_type || 'preset'" @change="setPath('actions.voice_output.voice_cloning.source_type', $event.target.value)">
            <option value="upload">上传样本</option><option value="preset">预设声音</option><option value="api">API训练</option>
          </select>
          <input class="input" :value="(local.actions?.voice_output?.voice_cloning?.source_files || []).join(',')" placeholder="样本路径（逗号分隔）" @input="setPath('actions.voice_output.voice_cloning.source_files', splitTags($event.target.value))" />
          <input class="input" type="range" min="0.5" max="2" step="0.1" :value="Number(local.actions?.voice_output?.voice_cloning?.settings?.speed || 1)" @input="setPath('actions.voice_output.voice_cloning.settings.speed', Number($event.target.value || 1))" />
          <input class="input" type="range" min="-10" max="10" step="1" :value="Number(local.actions?.voice_output?.voice_cloning?.settings?.pitch || 0)" @input="setPath('actions.voice_output.voice_cloning.settings.pitch', Number($event.target.value || 0))" />
          <select class="input" :value="local.actions?.voice_output?.voice_cloning?.settings?.emotion || 'neutral'" @change="setPath('actions.voice_output.voice_cloning.settings.emotion', $event.target.value)">
            <option value="neutral">中性</option><option value="enthusiastic">热情</option><option value="professional">专业</option><option value="gentle">温和</option>
          </select>
          <input class="input" :value="voiceTestText" placeholder="测试文本" @input="voiceTestText = $event.target.value" />
          <button type="button" class="btn btn-sm" @click="playVoiceTest">播放试听</button>
          <p class="hint">训练状态：{{ local.actions?.voice_output?.voice_cloning?.status || 'untrained' }}</p>
        </div>
        <label><input type="checkbox" :checked="Boolean(local.actions?.rpa?.enabled)" @change="togglePath('actions.rpa', $event.target.checked, { enabled: true, scripts: [] })" /> RPA</label>
        <label><input type="checkbox" :checked="Boolean(local.actions?.messaging?.enabled)" @change="togglePath('actions.messaging', $event.target.checked, { enabled: true, channels: [] })" /> 消息</label>
        <label><input type="checkbox" :checked="Boolean(local.actions?.api?.enabled)" @change="togglePath('actions.api', $event.target.checked, { enabled: true, endpoints: [] })" /> API</label>
        <label><input type="checkbox" :checked="Boolean(local.actions?.reporting?.enabled)" @change="togglePath('actions.reporting', $event.target.checked, { enabled: true, templates: [] })" /> 报表</label>
        </div>
      </div>

      <div v-if="showAllConfigs || selectedModule === 'collaboration'" class="cfg-card">
        <div class="cfg-head">
          <h4 class="cfg-title">协作（心脏）</h4>
          <span :class="['cfg-badge', Number(local?.collaboration?.workflow?.workflow_id || 0) > 0 ? 'ok' : 'warn']">{{ moduleStatusLabel('collaboration') }}</span>
          <span class="cfg-meta">{{ moduleMeta('collaboration') }}</span>
          <button type="button" class="btn btn-sm" @click="toggleCollapse('collaboration')">{{ isCollapsed('collaboration') ? '展开' : '折叠' }}</button>
        </div>
        <div v-show="!isCollapsed('collaboration')" class="cfg-body">
        <input class="input" type="number" min="1" :value="Number(local?.collaboration?.workflow?.workflow_id || 0)" placeholder="workflow_id（心脏）" @input="setPath('collaboration.workflow.workflow_id', Number($event.target.value || 0))" />
        <select class="input" :value="Number(local?.collaboration?.workflow?.workflow_id || 0)" @change="setPath('collaboration.workflow.workflow_id', Number($event.target.value || 0))">
          <option value="0">选择工作流</option>
          <option v-for="w in workflowOptions" :key="w.id" :value="w.id">{{ w.name }} (#{{ w.id }})</option>
        </select>
        <label><input type="checkbox" :checked="Boolean(local.collaboration?.handoff?.enabled)" @change="togglePath('collaboration.handoff', $event.target.checked, { enabled: true, conditions: [], targets: [] })" /> 启用任务交接</label>
        <input class="input" :value="(local.collaboration?.handoff?.conditions || []).join(',')" placeholder="交接条件（逗号分隔）" @input="setPath('collaboration.handoff.conditions', splitTags($event.target.value))" />
        <input class="input" :value="(local.collaboration?.handoff?.targets || []).join(',')" placeholder="交接目标（逗号分隔）" @input="setPath('collaboration.handoff.targets', splitTags($event.target.value))" />
        <label><input type="checkbox" :checked="Boolean(local.collaboration?.human_collaboration?.enabled)" @change="togglePath('collaboration.human_collaboration', $event.target.checked, { enabled: true, require_approval: [], timeout_handoff: false, timeout_seconds: 60 })" /> 启用人机协作</label>
        <input class="input" :value="(local.collaboration?.human_collaboration?.require_approval || []).join(',')" placeholder="人工确认场景（逗号分隔）" @input="setPath('collaboration.human_collaboration.require_approval', splitTags($event.target.value))" />
        <label><input type="checkbox" :checked="Boolean(local.collaboration?.human_collaboration?.timeout_handoff)" @change="setPath('collaboration.human_collaboration.timeout_handoff', $event.target.checked)" /> 超时交接</label>
        <input class="input" type="number" min="1" :value="Number(local.collaboration?.human_collaboration?.timeout_seconds || 60)" @input="setPath('collaboration.human_collaboration.timeout_seconds', Number($event.target.value || 60))" />
        <select class="input" :value="local.collaboration?.permissions?.access_level || 'read_only'" @change="setPath('collaboration.permissions.access_level', $event.target.value)">
          <option value="read_only">只读</option><option value="read_write">读写</option><option value="admin">管理员</option>
        </select>
        <input class="input" :value="(local.collaboration?.permissions?.data_scope || []).join(',')" placeholder="数据范围" @input="setPath('collaboration.permissions.data_scope', splitTags($event.target.value))" />
        <input class="input" :value="(local.collaboration?.permissions?.operation_whitelist || []).join(',')" placeholder="操作白名单" @input="setPath('collaboration.permissions.operation_whitelist', splitTags($event.target.value))" />
        <input class="input" :value="(local.collaboration?.permissions?.operation_blacklist || []).join(',')" placeholder="操作黑名单" @input="setPath('collaboration.permissions.operation_blacklist', splitTags($event.target.value))" />
        </div>
      </div>

      <div v-if="showAllConfigs || selectedModule === 'management'" class="cfg-card">
        <div class="cfg-head">
          <h4 class="cfg-title">管理</h4>
          <span :class="['cfg-badge', isModuleEnabled('management') ? 'ok' : 'off']">{{ moduleStatusLabel('management') }}</span>
          <span class="cfg-meta">{{ moduleMeta('management') }}</span>
          <button type="button" class="btn btn-sm" @click="toggleModuleEnabled('management')">{{ isModuleEnabled('management') ? '停用' : '启用' }}</button>
          <button type="button" class="btn btn-sm" @click="toggleCollapse('management')">{{ isCollapsed('management') ? '展开' : '折叠' }}</button>
        </div>
        <div v-show="!isCollapsed('management') && isModuleEnabled('management')" class="cfg-body">
        <label><input type="checkbox" :checked="Boolean(local.management?.scheduler?.enabled)" @change="togglePath('management.scheduler', $event.target.checked, { enabled: true, jobs: [] })" /> 调度</label>
        <label><input type="checkbox" :checked="Boolean(local.management?.error_handling)" @change="togglePath('management.error_handling', $event.target.checked, { retry_policy: { max_retries: 3, backoff: 'exponential', initial_delay_ms: 1000 }, fallback_strategy: 'human_handoff' })" /> 异常处理</label>
        <label><input type="checkbox" :checked="Boolean(local.management?.security)" @change="togglePath('management.security', $event.target.checked, { enabled: true, policies: [] })" /> 安全</label>
        <label><input type="checkbox" :checked="Boolean(local.management?.monitoring)" @change="togglePath('management.monitoring', $event.target.checked, { enabled: true, metrics: [] })" /> 监控</label>
        </div>
      </div>

      <h4>employee_config_v2 JSON</h4>
      <pre class="json">{{ jsonPreview }}</pre>

      <h4>实时预览/调试（P2-7）</h4>
      <p class="hint">使用当前认知配置（system prompt + 模型）进行即时测试，可保存测试用例。</p>
      <input class="input" :value="testCaseName" placeholder="测试用例名称（可选）" @input="testCaseName = $event.target.value" />
      <textarea class="input" :value="promptInput" placeholder="输入测试内容，例如：请输出退款工单处理步骤" @input="promptInput = $event.target.value" />
      <div class="ops">
        <button type="button" class="btn btn-sm btn-primary" :disabled="promptLoading" @click="runPromptTest">
          {{ promptLoading ? '测试中…' : '运行提示词测试' }}
        </button>
        <button type="button" class="btn btn-sm" :disabled="!promptInput.trim()" @click="savePromptCase">保存测试用例</button>
      </div>
      <p class="hint">当前模型：{{ llmProvider }} / {{ llmModel }}</p>
      <div v-if="promptErr" class="flash flash-err">{{ promptErr }}</div>
      <pre v-if="promptOutput" class="json preview">{{ promptOutput }}</pre>

      <div v-if="testCases.length" class="case-list">
        <h4>已保存测试用例</h4>
        <div v-for="c in testCases" :key="c.id" class="case-item">
          <button type="button" class="btn btn-sm" @click="applyPromptCase(c.id)">载入：{{ c.name }}</button>
          <button type="button" class="btn btn-sm" @click="removePromptCase(c.id)">删除</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../../api'
import SkillSelector from './SkillSelector.vue'

const props = defineProps({
  config: { type: Object, required: true },
  templateId: { type: String, default: 'workflow' },
  guideTarget: { type: String, default: '' },
  immersive: { type: Boolean, default: false },
})
const emit = defineEmits(['update:config', 'template-change', 'export-zip'])
const moduleDefs = [
  { key: 'identity', label: '身份' }, { key: 'perception', label: '感知' }, { key: 'memory', label: '记忆' },
  { key: 'cognition', label: '认知' }, { key: 'actions', label: '行动' }, { key: 'management', label: '管理' }, { key: 'collaboration', label: '协作(心脏)' },
]
const clone = (v) => JSON.parse(JSON.stringify(v))
const local = ref(clone(props.config || {}))
const canvasModules = ref(['identity', 'cognition', 'collaboration'])
const selectedModule = ref('collaboration')
const edgeFrom = ref('cognition')
const edgeTo = ref('collaboration')
const edgeCondition = ref('')
const editingEdgeIndex = ref(-1)
const editingEdgeCondition = ref('')
const workflowOptions = ref([])
const voiceTestText = ref('你好，这是一段声音克隆测试文本。')
const nodePositions = ref({})
const viewport = ref({ x: 0, y: 0, scale: 1 })
const nodeDrag = ref({ key: '', startX: 0, startY: 0, ox: 0, oy: 0 })
const panDrag = ref({ active: false, startX: 0, startY: 0, ox: 0, oy: 0 })
const promptInput = ref('')
const promptOutput = ref('')
const promptErr = ref('')
const promptLoading = ref(false)
const testCaseName = ref('')
const testCases = ref([])
const TEST_CASES_KEY = 'employee_block_builder_prompt_cases_v1'
const showAllConfigs = ref(false)
const collapsed = ref({})
const showLibraryDrawer = ref(false)
const showConfigDrawer = ref(false)
const showEdgeDrawer = ref(false)
watch(() => props.config, (v) => { local.value = clone(v || {}); ensureCanvasFromConfig() }, { deep: true })
watch(canvasModules, () => ensureNodePositions(), { deep: true })
watch(selectedModule, (key) => {
  if (key) {
    collapsed.value = { ...collapsed.value, [key]: false }
  }
})

function ensureCanvasFromConfig() {
  const keys = ['identity', 'cognition', 'collaboration']
  if (local.value.perception) keys.push('perception')
  if (local.value.memory) keys.push('memory')
  if (local.value.actions) keys.push('actions')
  if (local.value.management) keys.push('management')
  canvasModules.value = [...new Set(keys)]
  ensureNodePositions()
}
const emitConfig = () => emit('update:config', clone(local.value))
const labelOf = (key) => moduleDefs.find((x) => x.key === key)?.label || key
const isInCanvas = (key) => canvasModules.value.includes(key)
function addModule(key) { if (!isInCanvas(key)) canvasModules.value.push(key); if (!local.value[key] && key !== 'collaboration') local.value[key] = {}; selectedModule.value = key; emitConfig() }
function removeModule(key) { if (key === 'collaboration') return; canvasModules.value = canvasModules.value.filter((x) => x !== key); local.value[key] = undefined; emitConfig() }
function moveUp(idx) { const a = [...canvasModules.value]; [a[idx - 1], a[idx]] = [a[idx], a[idx - 1]]; canvasModules.value = a }
function moveDown(idx) { const a = [...canvasModules.value]; [a[idx + 1], a[idx]] = [a[idx], a[idx + 1]]; canvasModules.value = a }
function ensureNodePositions() {
  const next = { ...(nodePositions.value || {}) }
  canvasModules.value.forEach((k, idx) => {
    if (!next[k]) next[k] = { x: 80 + (idx % 3) * 210, y: 70 + Math.floor(idx / 3) * 130 }
  })
  Object.keys(next).forEach((k) => { if (!canvasModules.value.includes(k)) delete next[k] })
  nodePositions.value = next
}
function nodeStyle(key) {
  const p = nodePositions.value[key] || { x: 80, y: 70 }
  return {
    transform: `translate(${viewport.value.x + p.x * viewport.value.scale}px, ${viewport.value.y + p.y * viewport.value.scale}px) scale(${viewport.value.scale})`,
    transformOrigin: 'top left',
  }
}
function startNodeDrag(evt, key) {
  const p = nodePositions.value[key] || { x: 0, y: 0 }
  nodeDrag.value = { key, startX: evt.clientX, startY: evt.clientY, ox: p.x, oy: p.y }
  window.addEventListener('mousemove', onNodeDrag)
  window.addEventListener('mouseup', stopNodeDrag, { once: true })
}
function onNodeDrag(evt) {
  const d = nodeDrag.value
  if (!d.key) return
  const dx = (evt.clientX - d.startX) / viewport.value.scale
  const dy = (evt.clientY - d.startY) / viewport.value.scale
  nodePositions.value = { ...nodePositions.value, [d.key]: { x: d.ox + dx, y: d.oy + dy } }
}
function stopNodeDrag() {
  nodeDrag.value = { key: '', startX: 0, startY: 0, ox: 0, oy: 0 }
  window.removeEventListener('mousemove', onNodeDrag)
}
function startPan(evt) {
  panDrag.value = { active: true, startX: evt.clientX, startY: evt.clientY, ox: viewport.value.x, oy: viewport.value.y }
  window.addEventListener('mousemove', onPanMove)
  window.addEventListener('mouseup', stopPan, { once: true })
}
function onPanMove(evt) {
  if (!panDrag.value.active) return
  viewport.value = {
    ...viewport.value,
    x: panDrag.value.ox + (evt.clientX - panDrag.value.startX),
    y: panDrag.value.oy + (evt.clientY - panDrag.value.startY),
  }
}
function stopPan() {
  panDrag.value.active = false
  window.removeEventListener('mousemove', onPanMove)
}
function onWheel(evt) {
  const delta = evt.deltaY > 0 ? -0.08 : 0.08
  const next = Math.max(0.55, Math.min(1.8, viewport.value.scale + delta))
  const host = evt.currentTarget
  if (!host || typeof host.getBoundingClientRect !== 'function') {
    viewport.value = { ...viewport.value, scale: next }
    return
  }
  const rect = host.getBoundingClientRect()
  const mx = evt.clientX - rect.left
  const my = evt.clientY - rect.top
  const worldX = (mx - viewport.value.x) / viewport.value.scale
  const worldY = (my - viewport.value.y) / viewport.value.scale
  viewport.value = {
    x: mx - worldX * next,
    y: my - worldY * next,
    scale: next,
  }
}
function resetView() {
  viewport.value = { x: 0, y: 0, scale: 1 }
}
function fitToNodes() {
  const keys = canvasModules.value
  if (!keys.length) return
  const points = keys.map((k) => nodePositions.value[k]).filter(Boolean)
  if (!points.length) return
  const minX = Math.min(...points.map((p) => p.x))
  const minY = Math.min(...points.map((p) => p.y))
  const maxX = Math.max(...points.map((p) => p.x + 164))
  const maxY = Math.max(...points.map((p) => p.y + 90))
  const boardW = 1000
  const boardH = 680
  const padding = 80
  const spanW = Math.max(220, maxX - minX)
  const spanH = Math.max(160, maxY - minY)
  const scale = Math.max(0.55, Math.min(1.4, Math.min((boardW - padding) / spanW, (boardH - padding) / spanH)))
  const tx = (boardW - spanW * scale) / 2 - minX * scale
  const ty = (boardH - spanH * scale) / 2 - minY * scale
  viewport.value = { x: tx, y: ty, scale }
}
function autoLayout() {
  const next = { ...(nodePositions.value || {}) }
  canvasModules.value.forEach((key, idx) => {
    next[key] = { x: 80 + (idx % 3) * 220, y: 70 + Math.floor(idx / 3) * 140 }
  })
  nodePositions.value = next
}
function lines(s) { return String(s || '').split('\n').map((x) => x.trim()).filter(Boolean) }
function splitTags(s) { return String(s || '').split(',').map((x) => x.trim()).filter(Boolean) }
function patchIdentity(field, value) { local.value.identity = { ...(local.value.identity || {}), [field]: value }; emitConfig() }
function patchIdentityTags(value) { patchIdentity('tags', String(value || '').split(',').map((x) => x.trim()).filter(Boolean)) }
function setPath(path, value) {
  const parts = path.split('.')
  let cur = local.value
  for (let i = 0; i < parts.length - 1; i += 1) {
    const p = parts[i]
    if (!cur[p] || typeof cur[p] !== 'object') cur[p] = {}
    cur = cur[p]
  }
  cur[parts[parts.length - 1]] = value
  emitConfig()
}
function setJson(path, text) { try { setPath(path, JSON.parse(String(text || '{}'))) } catch { } }
function togglePath(path, enabled, defaultValue) { if (enabled) setPath(path, defaultValue); else setPath(path, undefined) }
function isCollapsed(key) { return Boolean(collapsed.value[key]) }
function toggleCollapse(key) { collapsed.value = { ...collapsed.value, [key]: !collapsed.value[key] } }
function isModuleEnabled(key) {
  if (key === 'identity' || key === 'collaboration') return true
  return Boolean(local.value?.[key])
}
function toggleModuleEnabled(key) {
  if (key === 'identity' || key === 'collaboration') return
  if (isModuleEnabled(key)) {
    local.value[key] = undefined
    canvasModules.value = canvasModules.value.filter((x) => x !== key)
  } else {
    addModule(key)
    return
  }
  emitConfig()
}
function moduleStatusLabel(key) {
  if (key === 'collaboration') {
    const ok = Number(local.value?.collaboration?.workflow?.workflow_id || 0) > 0
    return ok ? '已配置' : '缺 workflow_id'
  }
  if (key === 'identity') {
    const ok = String(local.value?.identity?.id || '').trim() && String(local.value?.identity?.name || '').trim()
    return ok ? '已配置' : '信息缺失'
  }
  return isModuleEnabled(key) ? '已启用' : '已停用'
}
function moduleMeta(key) {
  if (key === 'identity') return String(local.value?.identity?.id || '未设置ID')
  if (key === 'cognition') return `${String(local.value?.cognition?.agent?.model?.provider || '-')}/${String(local.value?.cognition?.agent?.model?.model_name || '-')}`
  if (key === 'memory') return `ctx:${Number(local.value?.memory?.short_term?.context_window || 0)}`
  if (key === 'collaboration') return `workflow_id:${Number(local.value?.collaboration?.workflow?.workflow_id || 0)}`
  if (key === 'actions') return `channels:${Array.isArray(local.value?.actions?.messaging?.channels) ? local.value.actions.messaging.channels.length : 0}`
  if (key === 'perception') return `edges:${edgeEntries.value.length}`
  if (key === 'management') return `retry:${Number(local.value?.management?.error_handling?.retry_policy?.max_retries || 0)}`
  return ''
}
const behaviorRules = computed(() => (Array.isArray(local.value?.cognition?.agent?.behavior_rules) ? local.value.cognition.agent.behavior_rules : []))
const fewShotExamples = computed(() => (Array.isArray(local.value?.cognition?.agent?.few_shot_examples) ? local.value.cognition.agent.few_shot_examples : []))
const memorySources = computed(() => (Array.isArray(local.value?.memory?.long_term?.sources) ? local.value.memory.long_term.sources : []))
function patchBehaviorRule(idx, field, value) {
  const list = [...behaviorRules.value]
  list[idx] = { ...(list[idx] || {}), rule_id: list[idx]?.rule_id || `rule_${idx + 1}`, [field]: value }
  setPath('cognition.agent.behavior_rules', list)
}
function addBehaviorRule() { setPath('cognition.agent.behavior_rules', [...behaviorRules.value, { rule_id: `rule_${Date.now()}`, name: '', description: '', priority: 'medium', action: 'warn' }]) }
function removeBehaviorRule(idx) { const list = [...behaviorRules.value]; list.splice(idx, 1); setPath('cognition.agent.behavior_rules', list) }
function patchFewShot(idx, field, value) { const list = [...fewShotExamples.value]; list[idx] = { ...(list[idx] || {}), [field]: value }; setPath('cognition.agent.few_shot_examples', list) }
function addFewShot() { setPath('cognition.agent.few_shot_examples', [...fewShotExamples.value, { input: '', output: '', explanation: '' }]) }
function removeFewShot(idx) { const list = [...fewShotExamples.value]; list.splice(idx, 1); setPath('cognition.agent.few_shot_examples', list) }
function addMemorySource() { setPath('memory.long_term.sources', [...memorySources.value, { source_id: `src_${Date.now()}`, name: '', type: 'document', paths: [] }]) }
function patchMemorySource(idx, field, value) { const list = [...memorySources.value]; list[idx] = { ...(list[idx] || {}), [field]: value }; setPath('memory.long_term.sources', list) }
function removeMemorySource(idx) { const list = [...memorySources.value]; list.splice(idx, 1); setPath('memory.long_term.sources', list) }
function optimizePrompt() {
  const current = String(local.value?.cognition?.agent?.system_prompt || '').trim()
  if (!current) return
  setPath('cognition.agent.system_prompt', `${current}\n\n请先澄清需求，再分步回答，最后给出可执行建议。`)
}
const edgeEntries = computed(() => {
  const primary = local.value?.collaboration?.workflow?.edges
  if (Array.isArray(primary)) return primary
  return Array.isArray(local.value?.workflow_employees) ? local.value.workflow_employees : []
})
function setEdgeEntries(list) {
  if (!local.value.collaboration || typeof local.value.collaboration !== 'object') local.value.collaboration = {}
  if (!local.value.collaboration.workflow || typeof local.value.collaboration.workflow !== 'object') local.value.collaboration.workflow = {}
  local.value.collaboration.workflow.edges = list
  local.value.workflow_employees = list
  emitConfig()
}
function addEdge() {
  const from = String(edgeFrom.value || ''); const to = String(edgeTo.value || '')
  if (!from || !to || from === to) return
  const list = [...edgeEntries.value]
  if (list.some((x) => x?.from === from && x?.to === to)) return
  list.push({ from, to, condition: String(edgeCondition.value || '').trim(), workflow_id: Number(local.value?.collaboration?.workflow?.workflow_id || 0), title: `${labelOf(from)}到${labelOf(to)}`, enabled: true })
  setEdgeEntries(list)
}
function removeEdge(i) { const list = [...edgeEntries.value]; list.splice(i, 1); setEdgeEntries(list) }
function openEdgeConfig(i) {
  const row = edgeEntries.value[i] || null
  editingEdgeIndex.value = Number(i)
  editingEdgeCondition.value = String(row?.condition || '')
}
function saveEdgeConfig() {
  const i = Number(editingEdgeIndex.value)
  const list = [...edgeEntries.value]
  if (!Number.isFinite(i) || i < 0 || i >= list.length) return
  list[i] = { ...(list[i] || {}), condition: String(editingEdgeCondition.value || '').trim() }
  setEdgeEntries(list)
}
function playVoiceTest() {
  setPath('actions.voice_output.voice_cloning.status', 'trained')
}
function loadSampleEmployee() {
  local.value = {
    identity: { id: 'employee.sample.cs-assistant', version: '1.0.0', artifact: 'employee_pack', name: '样板员工-客服协作助手', description: '演示完整模块配置', icon: 'robot', tags: ['客服', '协作'], author: 'modstore' },
    perception: { vision: { enabled: true, supported_formats: ['png', 'jpg'] }, audio: { enabled: true, asr: { enabled: true, languages: ['zh-CN'] } }, document: { enabled: true, supported_formats: ['pdf', 'docx'] }, data_input: { enabled: true, api_sources: [] }, event_listener: { enabled: true, topics: [] } },
    memory: { short_term: { context_window: 12000, session_timeout: 2400, keep_history: true }, long_term: { enabled: true, sources: [], retrieval: { strategy: 'hybrid', top_k: 5, similarity_threshold: 0.75, rerank_enabled: true } }, profile: { enabled: true, fields: [] }, experience: { enabled: true, stores: [] } },
    cognition: { agent: { system_prompt: '你是一名专业客服协作助手，优先澄清需求并给出可执行方案。', role: { name: '客服协作助手', persona: '冷静专业', tone: 'professional', expertise: ['客服', '工单'] }, behavior_rules: ['先确认目标', '再给步骤'], few_shot_examples: ['用户问退款流程 -> 先核验订单再给模板'], model: { provider: 'deepseek', model_name: 'deepseek-chat', temperature: 0.6, max_tokens: 4000, top_p: 0.9 } }, skills: [] },
    actions: { text_output: { enabled: true, formats: ['text', 'json'] }, voice_output: { enabled: true, tts: { provider: 'aliyun', voice_name: '', sample_rate: 24000 } }, messaging: { enabled: true, channels: ['wechat'] }, api: { enabled: true, endpoints: [] }, reporting: { enabled: true, templates: [] } },
    collaboration: { workflow: { workflow_id: Number(local.value?.collaboration?.workflow?.workflow_id || 1), auto_dispatch: true, edges: [{ from: 'perception', to: 'cognition', condition: '', workflow_id: 1, title: '感知到认知', enabled: true }, { from: 'cognition', to: 'actions', condition: '', workflow_id: 1, title: '认知到执行', enabled: true }] }, handoff: { enabled: true, conditions: ['复杂问题'], targets: ['人工'] }, permissions: { access_level: 'read_write', data_scope: ['all'], operation_whitelist: ['tickets.read'], operation_blacklist: [] } },
    management: { scheduler: { enabled: true, jobs: [] }, error_handling: { retry_policy: { max_retries: 3, backoff: 'exponential', initial_delay_ms: 1000 }, fallback_strategy: 'human_handoff' }, security: { enabled: true, policies: [] }, monitoring: { enabled: true, metrics: [] } },
    workflow_employees: [{ from: 'perception', to: 'cognition', workflow_id: 1, title: '感知到认知', enabled: true }, { from: 'cognition', to: 'actions', workflow_id: 1, title: '认知到执行', enabled: true }],
    metadata: { framework_version: '2.0.0', created_by: 'employee_block_builder_sample' },
  }
  canvasModules.value = ['identity', 'perception', 'memory', 'cognition', 'actions', 'management', 'collaboration']; selectedModule.value = 'identity'; emitConfig()
  autoLayout()
}
function loadDataAnalystSample() {
  local.value = {
    identity: { id: 'employee.sample.data-analyst', version: '1.0.0', artifact: 'employee_pack', name: '样板员工-数据分析师', description: '用于演示数据输入与报表输出', icon: 'chart', tags: ['数据', '分析'], author: 'modstore' },
    perception: { data_input: { enabled: true, api_sources: [] }, document: { enabled: true, supported_formats: ['csv', 'xlsx', 'pdf'] } },
    memory: { short_term: { context_window: 10000, session_timeout: 1800, keep_history: true } },
    cognition: { agent: { system_prompt: '你是一名数据分析师，输出结论、依据和建议。', role: { name: '数据分析师', persona: '严谨客观', tone: 'professional', expertise: ['数据清洗', '报表'] }, behavior_rules: ['先给结论再给依据'], few_shot_examples: [], model: { provider: 'deepseek', model_name: 'deepseek-chat', temperature: 0.3, max_tokens: 4000, top_p: 0.9 } }, skills: [] },
    actions: { text_output: { enabled: true, formats: ['json', 'markdown'] }, reporting: { enabled: true, templates: [] } },
    collaboration: { workflow: { workflow_id: Number(local.value?.collaboration?.workflow?.workflow_id || 1), auto_dispatch: true, edges: [{ from: 'perception', to: 'cognition', workflow_id: 1, title: '采集到分析', enabled: true }, { from: 'cognition', to: 'actions', workflow_id: 1, title: '分析到输出', enabled: true }] } },
    management: { monitoring: { enabled: true, metrics: ['latency', 'quality'] } },
    workflow_employees: [{ from: 'perception', to: 'cognition', workflow_id: 1, title: '采集到分析', enabled: true }, { from: 'cognition', to: 'actions', workflow_id: 1, title: '分析到输出', enabled: true }],
    metadata: { framework_version: '2.0.0', created_by: 'employee_block_builder_sample' },
  }
  canvasModules.value = ['identity', 'perception', 'memory', 'cognition', 'actions', 'management', 'collaboration']; selectedModule.value = 'identity'; emitConfig()
  autoLayout()
}
const jsonPreview = computed(() => JSON.stringify(local.value, null, 2))
const renderedEdges = computed(() => {
  const list = edgeEntries.value
  return list.map((edge, index) => {
    const from = nodePositions.value[edge?.from] || { x: 0, y: 0 }
    const to = nodePositions.value[edge?.to] || { x: 0, y: 0 }
    const x1 = viewport.value.x + (from.x + 164) * viewport.value.scale
    const y1 = viewport.value.y + (from.y + 38) * viewport.value.scale
    const x2 = viewport.value.x + (to.x + 0) * viewport.value.scale
    const y2 = viewport.value.y + (to.y + 38) * viewport.value.scale
    const c1 = x1 + 64 * viewport.value.scale
    const c2 = x2 - 64 * viewport.value.scale
    return {
      index,
      condition: edge?.condition,
      d: `M ${x1} ${y1} C ${c1} ${y1}, ${c2} ${y2}, ${x2} ${y2}`,
      lx1: x2 - 8,
      ly1: y2 - 6,
      lx2: x2,
      ly2: y2,
    }
  })
})
const llmProvider = computed(() => String(local.value?.cognition?.agent?.model?.provider || 'deepseek'))
const llmModel = computed(() => String(local.value?.cognition?.agent?.model?.model_name || 'deepseek-chat'))
const isEmptyWorkbench = computed(() => {
  const id = String(local.value?.identity?.id || '').trim()
  const name = String(local.value?.identity?.name || '').trim()
  const wid = Number(local.value?.collaboration?.workflow?.workflow_id || 0)
  return !id && !name && wid <= 0
})

function loadPromptCases() {
  try {
    const raw = localStorage.getItem(TEST_CASES_KEY) || '[]'
    const parsed = JSON.parse(raw)
    testCases.value = Array.isArray(parsed) ? parsed.filter((x) => x && typeof x === 'object') : []
  } catch {
    testCases.value = []
  }
}

function persistPromptCases() {
  try {
    localStorage.setItem(TEST_CASES_KEY, JSON.stringify(testCases.value.slice(0, 30)))
  } catch {
    /* ignore localStorage errors */
  }
}

function savePromptCase() {
  const name = String(testCaseName.value || '').trim()
  const input = String(promptInput.value || '').trim()
  if (!name || !input) return
  const row = {
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name,
    input,
    output: String(promptOutput.value || ''),
    provider: llmProvider.value,
    model: llmModel.value,
    created_at: new Date().toISOString(),
  }
  testCases.value = [row, ...testCases.value].slice(0, 30)
  persistPromptCases()
}

function applyPromptCase(id) {
  const hit = testCases.value.find((x) => x.id === id)
  if (!hit) return
  promptInput.value = String(hit.input || '')
  promptOutput.value = String(hit.output || '')
}

function removePromptCase(id) {
  testCases.value = testCases.value.filter((x) => x.id !== id)
  persistPromptCases()
}

async function runPromptTest() {
  const input = String(promptInput.value || '').trim()
  const systemPrompt = String(local.value?.cognition?.agent?.system_prompt || '').trim()
  if (!input) {
    promptErr.value = '请输入测试输入'
    return
  }
  promptErr.value = ''
  promptOutput.value = ''
  promptLoading.value = true
  try {
    const messages = []
    if (systemPrompt) messages.push({ role: 'system', content: systemPrompt })
    messages.push({ role: 'user', content: input })
    const ret = await api.llmChat(llmProvider.value, llmModel.value, messages, Number(local.value?.cognition?.agent?.model?.max_tokens || 1200))
    promptOutput.value = String(ret?.content || '')
  } catch (e) {
    promptErr.value = e.message || String(e)
  } finally {
    promptLoading.value = false
  }
}

loadPromptCases()
ensureNodePositions()
onMounted(async () => {
  try {
    const ret = await api.listWorkflows()
    workflowOptions.value = Array.isArray(ret) ? ret : Array.isArray(ret?.items) ? ret.items : []
  } catch {
    workflowOptions.value = []
  }
})
</script>

<style scoped>
.builder{display:grid;grid-template-columns:220px 1fr 1.08fr;gap:.8rem}
.builder--immersive{grid-template-columns:1fr}
.canvas-toolbar{grid-column:1/-1;display:flex;gap:.5rem;align-items:center;padding:.55rem .65rem;border:1px solid rgba(255,255,255,.12);border-radius:12px;background:linear-gradient(180deg,rgba(18,18,18,.95),rgba(10,10,10,.92));box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 10px 20px rgba(0,0,0,.45)}
.builder--immersive .canvas-toolbar{
  position: fixed;
  left: 12px;
  bottom: 12px;
  z-index: 95;
  width: fit-content;
  max-width: calc(100vw - 24px);
  padding: .32rem .4rem;
  gap: .3rem;
  border-radius: 10px;
  display: inline-flex;
}
.builder--immersive .canvas{padding:.55rem}
.builder--immersive .canvas h3{margin:.05rem 0 .45rem}
.builder--immersive .board-grid{min-height:0}
.builder--immersive .canvas.col{border:none;background:transparent;box-shadow:none;padding:.2rem}
.builder--immersive .canvas{overflow:visible}
.canvas-fab-group{
  position:absolute;
  right:12px;
  top:12px;
  display:flex;
  gap:.35rem;
  z-index:22;
}
.canvas-fab-group .btn{
  height:36px;
  padding:.28rem .55rem;
  border-radius:8px;
}
.tool-group{display:flex;gap:.35rem;padding:.25rem;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.1);border-radius:9px}
.btn-tool{min-width:64px}
.zoom-chip{margin-left:auto;font-size:11px;padding:.18rem .55rem;border-radius:999px;border:1px solid rgba(255,255,255,.15);color:rgba(255,255,255,.82);background:rgba(255,255,255,.06)}
.builder--immersive .tool-group{gap:.2rem;padding:.18rem}
.builder--immersive .btn-tool{min-width:46px;padding:.3rem .42rem;font-size:12px}
.builder--immersive .zoom-chip{font-size:10px;padding:.14rem .42rem}
.col{border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:.75rem;background:linear-gradient(180deg,rgba(18,18,18,.95) 0%,rgba(10,10,10,.93) 100%);box-shadow:0 14px 30px rgba(0,0,0,.42)}
.col h3{margin:.1rem 0 .55rem;color:#fff;font-size:14px}
.library,.config{display:flex;flex-direction:column;gap:.45rem}
.lib-item{justify-content:flex-start;display:flex;align-items:center;gap:.45rem}
.dot{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.6);display:inline-block}
.whiteboard{position:relative;height:clamp(560px, 68vh, 820px);border:none;border-radius:0;overflow:hidden;cursor:grab;background:linear-gradient(180deg,rgba(11,11,11,.98),rgba(7,7,7,.98))}
.builder--immersive .whiteboard{width:100%;aspect-ratio:16/9;height:auto;max-height:calc(100vh - 210px);min-height:min(56.25vw,420px)}
.whiteboard:active{cursor:grabbing}
.wb-edges{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.wb-title{position:absolute;left:12px;top:10px;font-size:11px;letter-spacing:.08em;color:rgba(255,255,255,.72);padding:.2rem .45rem;border:1px solid rgba(255,255,255,.2);border-radius:999px;background:rgba(0,0,0,.52)}
.wb-node{position:absolute;width:198px;border:1px solid rgba(255,255,255,.18);padding:.52rem .56rem;border-radius:14px;background:linear-gradient(180deg,rgba(38,38,38,.78),rgba(19,19,19,.76));backdrop-filter:blur(8px);cursor:move;box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 10px 24px rgba(0,0,0,.5)}
.wb-node.active{border-color:rgba(255,255,255,.42);box-shadow:0 0 0 1px rgba(255,255,255,.24),0 14px 30px rgba(0,0,0,.55)}
.node-title{font-size:13px;font-weight:700;color:#f8fafc}
.node-meta{font-size:11px;color:rgba(255,255,255,.74);margin-top:.12rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.drawer-floating{position:fixed;top:130px;width:min(330px,calc(100vw - 24px));max-height:calc(100vh - 160px);overflow:auto;z-index:40}
.drawer-floating--left{left:12px}
.drawer-floating--right{right:12px}
.edge-drawer--floating{position:fixed;right:12px;bottom:12px;width:min(480px,calc(100vw - 24px));max-height:38vh;overflow:auto;padding:.55rem .65rem;border:1px solid rgba(148,163,184,.25);border-radius:10px;background:rgba(15,23,42,.92);z-index:41}
.ops{display:flex;gap:.32rem;margin-top:.4rem}
.wb-node .ops .btn{flex:1 1 0;min-width:0;height:44px;white-space:nowrap;padding:.2rem .25rem;font-size:13px}
.wb-node .ops .btn:last-child{flex:0 0 58px}
.hint{font-size:12px;color:rgba(255,255,255,.45)}
.sub{margin:.7rem 0 .35rem;font-size:13px;color:#dbeafe}
.row{display:grid;grid-template-columns:1fr 1fr auto;gap:.35rem;margin:.35rem 0}
.row-2{grid-template-columns:1fr 1fr}
.row-3{grid-template-columns:1fr 1fr 1fr}
.edge-item{display:flex;justify-content:space-between;gap:.45rem;font-size:12px;margin:.3rem 0}
.board-grid{min-height:720px;background-image:radial-gradient(rgba(255,255,255,.08) 1px, transparent 1px);background-size:16px 16px;background-position:0 0}
.right-drawer{box-shadow:inset 0 0 0 1px rgba(56,189,248,.18),0 10px 22px rgba(2,6,23,.35)}
.cfg-card{border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:.55rem;margin:.35rem 0}
.cfg-title{margin:0 0 .45rem;color:#c7d2fe;font-size:13px}
.cfg-head{display:flex;align-items:center;gap:.35rem;flex-wrap:wrap;margin-bottom:.35rem}
.cfg-badge{font-size:11px;padding:.1rem .4rem;border-radius:999px;border:1px solid rgba(255,255,255,.2)}
.cfg-meta{font-size:11px;color:rgba(255,255,255,.62)}
.cfg-badge.ok{background:rgba(74,222,128,.16);color:#86efac;border-color:rgba(74,222,128,.4)}
.cfg-badge.warn{background:rgba(250,204,21,.16);color:#fde047;border-color:rgba(250,204,21,.35)}
.cfg-badge.off{background:rgba(148,163,184,.12);color:#cbd5e1;border-color:rgba(148,163,184,.35)}
.cfg-body{display:flex;flex-direction:column;gap:.35rem}
.json{max-height:260px;overflow:auto;font-size:11px;background:rgba(0,0,0,.25);padding:.5rem;border-radius:8px}
.preview{max-height:180px}
.case-list{display:flex;flex-direction:column;gap:.35rem}
.case-item{display:flex;gap:.35rem;flex-wrap:wrap}
.empty-helper{margin-top:.6rem;border:1px dashed rgba(56,189,248,.45);border-radius:8px;padding:.55rem;background:rgba(2,132,199,.08)}
.spotlight{box-shadow:0 0 0 2px rgba(56,189,248,.45),0 0 18px rgba(56,189,248,.22)}
@media (max-width:1100px){.builder{grid-template-columns:1fr}}
</style>
