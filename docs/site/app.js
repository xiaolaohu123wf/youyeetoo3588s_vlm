"use strict";
(() => {
  const data = window.projectData;
  const source = (path) => `${data.repo}/blob/${data.ref}/${path.split("/").map(encodeURIComponent).join("/")}`;
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const link = (path, label = path) => {
    const a = element("a", label, "code-link");
    a.href = source(path);
    return a;
  };
  const selectButton = (list, index) => {
    [...list.children].forEach((button, i) => {
      button.classList.toggle("active", i === index);
      button.setAttribute("aria-pressed", String(i === index));
    });
  };
  const pipeline = document.querySelector("#pipeline");
  const detail = document.querySelector("#node-detail");
  function showNode(index) {
    const n = data.nodes[index];
    selectButton(pipeline, index);
    const heading = element("div");
    heading.append(element("span", n.host, "chip"), element("h3", n.name));
    const description = element("div");
    description.append(element("p", n.text), element("p", n.note), link(n.file));
    detail.replaceChildren(heading, description);
  }
  data.nodes.forEach((n, index) => {
    const button = element("button", undefined, "node");
    button.type = "button";
    button.append(element("span", String(index + 1).padStart(2, "0"), "num"), element("strong", n.name), element("small", n.tag));
    button.addEventListener("click", () => showNode(index));
    pipeline.append(button);
  });
  showNode(0);
  const modules = document.querySelector("#module-list");
  const moduleDetail = document.querySelector("#module-detail");
  function showModule(index) {
    const m = data.modules[index];
    selectButton(modules, index);
    const files = element("ul", undefined, "file-list");
    m.files.forEach(([path, label]) => {
      const li = element("li");
      li.append(link(path), element("small", label));
      files.append(li);
    });
    moduleDetail.replaceChildren(element("span", m.path, "chip"), element("h3", m.title), element("p", m.text), files);
  }
  data.modules.forEach((m, index) => {
    const button = element("button", undefined, "module-button");
    button.type = "button";
    button.append(element("span", m.path, "folder"), element("span", m.label, "label"));
    button.addEventListener("click", () => showModule(index));
    modules.append(button);
  });
  showModule(0);
  const stages = document.querySelector("#stages");
  const stageElements = data.stages.map(s => {
    const row = element("details", undefined, "stage");
    row.dataset.state = s.state;
    const summary = element("summary");
    summary.append(element("span", s.id, "stage-id"), element("strong", s.name), element("span", s.status, `badge${s.state === "done" ? "" : " open"}`));
    const body = element("div", undefined, "stage-body");
    body.append(element("p", s.text), element("p", s.evidence, "evidence"), link(s.file, "查看依据 ↗"));
    row.append(summary, body);
    stages.append(row);
    return row;
  });
  const completed = data.stages.filter(s => s.state === "done").length;
  document.querySelector("#progress-summary").textContent = `${data.stages.length} 个阶段 · ${completed} 个已完成 · ${data.stages.length - completed} 个原型或推进阶段`;
  const filters = [...document.querySelectorAll("[data-filter]")];
  filters.forEach(button => button.addEventListener("click", () => {
    const filter = button.dataset.filter;
    filters.forEach(b => {
      b.classList.toggle("active", b === button);
      b.setAttribute("aria-pressed", String(b === button));
    });
    stageElements.forEach(row => { row.hidden = filter !== "all" && row.dataset.state !== filter; });
    document.querySelector("#empty").hidden = stageElements.some(row => !row.hidden);
  }));
})();
