const stepContent = {
  data: {
    kicker: "DATA INGESTION",
    status: "traceable",
    title: "把原始执行结果变成统一数据条目",
    copy: "工具结果、用户行为和手动配置进入统一模型，记录来源、时间、类型、质量等级、标签和任务 ID。",
    code: "entry = ingest_tool_result(tool, params, result)\nvalidate_data(entry)\nappend_jsonl(raw_data)"
  },
  preference: {
    kicker: "PREFERENCE CAPTURE",
    status: "versioned",
    title: "从行为模式里提取可回溯偏好",
    copy: "高频工具、常用输出格式和安全动作被归入操作习惯、输出风格、安全策略等类别，并保存版本历史。",
    code: "prefs = extract_preferences_from_data(entries)\nset_preference(category, key, value)\nrecord_version_history()"
  },
  knowledge: {
    kicker: "KNOWLEDGE STRUCTURE",
    status: "indexed",
    title: "把任务经验沉淀成结构化知识",
    copy: "工作流、成功案例、模板、事实和规则被写入知识库，带来源、置信度、标签和版本字段。",
    code: "add_knowledge(type, title, content, tags)\n_detect_conflicts(entry)\n_upsert_vector(entry)"
  },
  retrieval: {
    kicker: "HYBRID RETRIEVAL",
    status: "fast path",
    title: "用关键词和向量一起提高召回",
    copy: "检索链路结合标题、正文、标签、置信度和 embedding 向量；银河麒麟 SDK 可用时优先使用系统能力。",
    code: "query_vector = embedding_provider.embed(query)\nscore = vector_score + keyword_score\nreturn ranked_results"
  },
  safety: {
    kicker: "SAFETY CONTROL",
    status: "approved",
    title: "敏感动作可审批，记忆可定向清理",
    copy: "命令类数据入库前执行危险模式校验；偏好、知识、数据和历史记忆均有清理入口，用于精准遗忘。",
    code: "if dangerous_command(params): reject()\nif user_requests_forget(scope): clear_scope(scope)\nask_before_execute(risky_tool)"
  },
  eval: {
    kicker: "EVALUATION",
    status: "measurable",
    title: "把功能效果变成可报告指标",
    copy: "围绕偏好准确率、知识召回率、检索延迟和冲突处理正确率设计数据集与测试报告。",
    code: "measure(preference_accuracy)\nmeasure(knowledge_recall)\nmeasure(search_latency_ms)\nmeasure(conflict_resolution_accuracy)"
  }
};

const nodes = document.querySelectorAll(".loop-node");
const kicker = document.querySelector("#consoleKicker");
const statusText = document.querySelector(".console-status");
const title = document.querySelector("#consoleTitle");
const copy = document.querySelector("#consoleCopy");
const code = document.querySelector("#consoleCode code");
const consolePanel = document.querySelector(".execution-console");
const navLinks = document.querySelectorAll(".nav-links a");
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const stepOrder = Object.keys(stepContent);
let activeStepIndex = 0;
let autoStepTimer;
let userPausedAutoStep = false;

function setActiveStep(step) {
  const content = stepContent[step];
  if (!content) return;
  activeStepIndex = stepOrder.indexOf(step);

  nodes.forEach((node) => {
    node.classList.toggle("active", node.dataset.step === step);
  });

  if (consolePanel && !reduceMotion.matches) {
    consolePanel.classList.remove("step-swap");
    void consolePanel.offsetWidth;
    consolePanel.classList.add("step-swap");
  }

  kicker.textContent = content.kicker;
  statusText.textContent = content.status;
  title.textContent = content.title;
  copy.textContent = content.copy;
  code.textContent = content.code;
}

function startAutoStep() {
  if (reduceMotion.matches || userPausedAutoStep || autoStepTimer) return;

  autoStepTimer = window.setInterval(() => {
    activeStepIndex = (activeStepIndex + 1) % stepOrder.length;
    setActiveStep(stepOrder[activeStepIndex]);
  }, 3600);
}

function stopAutoStep() {
  window.clearInterval(autoStepTimer);
  autoStepTimer = undefined;
}

nodes.forEach((node) => {
  node.addEventListener("click", () => {
    userPausedAutoStep = true;
    stopAutoStep();
    setActiveStep(node.dataset.step);
  });
  node.addEventListener("mouseenter", () => {
    userPausedAutoStep = true;
    stopAutoStep();
    setActiveStep(node.dataset.step);
  });
});

const revealTargets = document.querySelectorAll([
  ".foundation-card",
  ".agent-diagram",
  ".capability-card",
  ".tool-copy",
  ".tool-matrix span",
  ".loop-rail",
  ".execution-console",
  ".desktop-shot",
  ".proof-list article",
  ".metric-copy",
  ".metric-card",
  ".start-panel",
  ".cli-shot"
].join(", "));

revealTargets.forEach((element, index) => {
  element.classList.add("reveal-ready");
  element.style.setProperty("--reveal-index", index % 8);
});

const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("in-view");
      revealObserver.unobserve(entry.target);
    }
  });
}, {
  threshold: 0.18,
  rootMargin: "0px 0px -8% 0px"
});

revealTargets.forEach((element) => revealObserver.observe(element));

const sectionObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) return;

    const id = entry.target.id;
    navLinks.forEach((link) => {
      link.classList.toggle("active", link.getAttribute("href") === `#${id}`);
    });
  });
}, {
  threshold: 0.44
});

document.querySelectorAll("section[id]").forEach((section) => sectionObserver.observe(section));

const pipeline = document.querySelector("#pipeline");
if (pipeline) {
  const pipelineObserver = new IntersectionObserver((entries) => {
    const visible = entries.some((entry) => entry.isIntersecting);
    if (visible) {
      startAutoStep();
    } else {
      stopAutoStep();
    }
  }, { threshold: 0.42 });

  pipelineObserver.observe(pipeline);
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopAutoStep();
  } else if (!userPausedAutoStep) {
    startAutoStep();
  }
});
