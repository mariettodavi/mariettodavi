const state = {
  currentPath: "",
  photos: [],
  lightboxIndex: -1,
};

const treeEl = document.getElementById("tree");
const gridEl = document.getElementById("grid");
const breadcrumbEl = document.getElementById("breadcrumb");
const emptyMsgEl = document.getElementById("empty-msg");
const refreshBtn = document.getElementById("refresh-btn");

const lightboxEl = document.getElementById("lightbox");
const lbImg = document.getElementById("lb-img");
const lbCaption = document.getElementById("lb-caption");

document.getElementById("lb-close").addEventListener("click", closeLightbox);
document.getElementById("lb-prev").addEventListener("click", () => moveLightbox(-1));
document.getElementById("lb-next").addEventListener("click", () => moveLightbox(1));
lightboxEl.addEventListener("click", (e) => {
  if (e.target === lightboxEl) closeLightbox();
});
document.addEventListener("keydown", (e) => {
  if (lightboxEl.classList.contains("hidden")) return;
  if (e.key === "Escape") closeLightbox();
  if (e.key === "ArrowLeft") moveLightbox(-1);
  if (e.key === "ArrowRight") moveLightbox(1);
});

refreshBtn.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  refreshBtn.title = "Aggiornamento in corso...";
  try {
    await postJSON("/api/reindex", {});
    await loadTreeRoot();
    await loadPhotos(state.currentPath, true);
  } catch (err) {
    alert(`Aggiornamento non riuscito: ${err.message}`);
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.title = "Aggiorna";
  }
});

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Errore ${res.status}`);
  return res.json();
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Errore ${res.status}`);
  return data;
}

// ---- albero cartelle ----

function makeFolderNode(folder, container, options) {
  options = options || {};
  const showActions = options.showActions !== false;
  const onSelect = options.onSelect || ((f) => loadPhotos(f.path));
  const rootEl = options.rootEl || container;

  const node = document.createElement("div");
  node.className = "tree-node";

  const row = document.createElement("div");
  row.className = "tree-row";

  const toggle = document.createElement("span");
  toggle.className = "toggle";
  toggle.textContent = folder.hasChildren ? "▸" : "";
  row.appendChild(toggle);

  const label = document.createElement("span");
  label.className = "folder-label";
  label.textContent = folder.name;
  row.appendChild(label);

  if (showActions) {
    const actions = document.createElement("span");
    actions.className = "folder-actions";

    const renameBtn = document.createElement("button");
    renameBtn.className = "icon-btn";
    renameBtn.title = "Rinomina";
    renameBtn.textContent = "✎";
    renameBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      renameFolder(folder);
    });
    actions.appendChild(renameBtn);

    const moveBtn = document.createElement("button");
    moveBtn.className = "icon-btn";
    moveBtn.title = "Sposta...";
    moveBtn.textContent = "⇒";
    moveBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openMoveModal(folder);
    });
    actions.appendChild(moveBtn);

    row.appendChild(actions);
  }

  node.appendChild(row);

  const childrenEl = document.createElement("div");
  childrenEl.className = "tree-children hidden";
  node.appendChild(childrenEl);

  let expanded = false;
  let loaded = false;

  async function expand() {
    if (!loaded) {
      const children = await fetchJSON(`/api/tree?path=${encodeURIComponent(folder.path)}`);
      children.forEach((child) => makeFolderNode(child, childrenEl, options));
      loaded = true;
    }
    expanded = true;
    childrenEl.classList.remove("hidden");
    toggle.textContent = "▾";
  }

  function collapse() {
    expanded = false;
    childrenEl.classList.add("hidden");
    toggle.textContent = "▸";
  }

  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    if (!folder.hasChildren) return;
    if (expanded) collapse(); else expand();
  });

  label.addEventListener("click", () => {
    rootEl.querySelectorAll(".folder-label.selected").forEach((el) => el.classList.remove("selected"));
    label.classList.add("selected");
    onSelect(folder, label);
    if (folder.hasChildren && !expanded) expand();
  });

  container.appendChild(node);
  return node;
}

async function loadTreeRoot() {
  treeEl.innerHTML = "";
  const roots = await fetchJSON("/api/tree?path=");
  const options = { rootEl: treeEl };
  roots.forEach((folder) => makeFolderNode(folder, treeEl, options));
}

async function loadPhotos(path, silent) {
  state.currentPath = path;
  breadcrumbEl.textContent = path ? path.split("/").join(" / ") : "(cartella principale)";
  if (!silent) gridEl.innerHTML = "";
  const photos = await fetchJSON(`/api/photos?path=${encodeURIComponent(path)}`);
  state.photos = photos;
  renderGrid(photos);
}

function renderGrid(photos) {
  gridEl.innerHTML = "";
  emptyMsgEl.classList.toggle("hidden", photos.length > 0);
  photos.forEach((photo, index) => {
    const cell = document.createElement("button");
    cell.className = "thumb";
    cell.title = photo.name;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = `/api/thumb?path=${encodeURIComponent(photo.path)}`;
    img.alt = photo.name;
    cell.appendChild(img);
    cell.addEventListener("click", () => openLightbox(index));
    gridEl.appendChild(cell);
  });
}

// ---- lightbox ----

function openLightbox(index) {
  state.lightboxIndex = index;
  showLightboxImage();
  lightboxEl.classList.remove("hidden");
}

function closeLightbox() {
  lightboxEl.classList.add("hidden");
  lbImg.src = "";
}

function moveLightbox(delta) {
  if (!state.photos.length) return;
  state.lightboxIndex = (state.lightboxIndex + delta + state.photos.length) % state.photos.length;
  showLightboxImage();
}

function showLightboxImage() {
  const photo = state.photos[state.lightboxIndex];
  if (!photo) return;
  lbImg.src = `/api/full?path=${encodeURIComponent(photo.path)}`;
  lbCaption.textContent = `${photo.name} (${state.lightboxIndex + 1}/${state.photos.length})`;
}

// ---- rinomina / sposta cartelle ----

async function afterFolderChanged(oldPath, newPath) {
  await loadTreeRoot();
  if (state.currentPath === oldPath) {
    await loadPhotos(newPath);
  } else if (state.currentPath.startsWith(oldPath + "/")) {
    await loadPhotos(newPath + state.currentPath.slice(oldPath.length));
  }
}

async function renameFolder(folder) {
  const input = window.prompt(`Nuovo nome per "${folder.name}":`, folder.name);
  if (input === null) return;
  const newName = input.trim();
  if (!newName || newName === folder.name) return;
  try {
    const data = await postJSON("/api/folder/rename", { path: folder.path, newName });
    await afterFolderChanged(folder.path, data.path);
  } catch (err) {
    alert(err.message);
  }
}

const moveModalEl = document.getElementById("move-modal");
const moveModalTitleEl = document.getElementById("move-modal-title");
const moveTreeRootEl = document.getElementById("move-tree-root");
const moveTreeEl = document.getElementById("move-tree");
const moveErrorEl = document.getElementById("move-error");
const moveConfirmBtn = document.getElementById("move-confirm");
const moveCancelBtn = document.getElementById("move-cancel");

const moveState = { sourcePath: "", destPath: "" };

async function openMoveModal(folder) {
  moveState.sourcePath = folder.path;
  moveState.destPath = "";
  moveModalTitleEl.textContent = folder.name;
  moveErrorEl.classList.add("hidden");
  moveTreeEl.innerHTML = "";
  moveTreeRootEl.classList.add("selected");
  moveModalEl.classList.remove("hidden");

  const roots = await fetchJSON("/api/tree?path=");
  const options = {
    rootEl: moveTreeEl,
    showActions: false,
    onSelect: (f) => {
      moveTreeRootEl.classList.remove("selected");
      moveState.destPath = f.path;
    },
  };
  roots.forEach((f) => makeFolderNode(f, moveTreeEl, options));
}

function closeMoveModal() {
  moveModalEl.classList.add("hidden");
}

moveTreeRootEl.addEventListener("click", () => {
  moveTreeEl.querySelectorAll(".folder-label.selected").forEach((el) => el.classList.remove("selected"));
  moveTreeRootEl.classList.add("selected");
  moveState.destPath = "";
});

moveCancelBtn.addEventListener("click", closeMoveModal);
moveModalEl.addEventListener("click", (e) => {
  if (e.target === moveModalEl) closeMoveModal();
});

moveConfirmBtn.addEventListener("click", async () => {
  moveErrorEl.classList.add("hidden");
  try {
    const data = await postJSON("/api/folder/move", {
      path: moveState.sourcePath,
      destPath: moveState.destPath,
    });
    closeMoveModal();
    await afterFolderChanged(moveState.sourcePath, data.path);
  } catch (err) {
    moveErrorEl.textContent = err.message;
    moveErrorEl.classList.remove("hidden");
  }
});

loadTreeRoot();
loadPhotos("");
