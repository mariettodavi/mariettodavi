const state = {
  currentPath: "",
  photos: [],
  lightboxIndex: -1,
  showHidden: false,
};

const ICON_CHEVRON =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 6 15 12 9 18" /></svg>';
const ICON_RENAME =
  '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>';
const ICON_MOVE =
  '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h16" /><path d="m13 6 6 6-6 6" /></svg>';
const ICON_EYE =
  '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z" /><circle cx="12" cy="12" r="3" /></svg>';
const ICON_EYE_OFF =
  '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a18.5 18.5 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>';
const ICON_TRASH =
  '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" /></svg>';
const ICON_IMMICH_BADGE =
  '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10" /><polyline points="16 9 10.5 15 8 12.5" /></svg>';

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

const showHiddenCheckbox = document.getElementById("show-hidden-checkbox");
showHiddenCheckbox.addEventListener("change", () => {
  state.showHidden = showHiddenCheckbox.checked;
  loadTreeRoot();
});

const immichStatusEl = document.getElementById("immich-status");

async function loadImmichStatus() {
  try {
    const status = await fetchJSON("/api/immich/status");
    if (!status.configured) {
      immichStatusEl.classList.add("hidden");
      return;
    }
    immichStatusEl.classList.remove("hidden");
    if (status.ok) {
      immichStatusEl.textContent = `Immich: ${status.albumCount} album trovati`;
      immichStatusEl.className = "immich-ok";
    } else {
      immichStatusEl.textContent = `Immich: ${status.error || "errore sconosciuto"}`;
      immichStatusEl.className = "immich-error";
    }
  } catch (err) {
    // Non e' grave se questa chiamata fallisce: i badge restano quelli
    // che c'erano, la navigazione delle foto non dipende da questo.
  }
}

const precacheStatusEl = document.getElementById("precache-status");

async function pollPrecacheStatus() {
  try {
    const status = await fetchJSON("/api/precache/status");
    if (status.running && status.total > 0) {
      precacheStatusEl.classList.remove("hidden");
      precacheStatusEl.textContent = `Precaricamento miniature: ${status.done}/${status.total}`;
    } else {
      precacheStatusEl.classList.add("hidden");
    }
  } catch (err) {
    // Non e' grave se questa chiamata fallisce: la navigazione delle
    // foto non dipende da questo, e' solo un indicatore di progresso.
  }
}
setInterval(pollPrecacheStatus, 2000);

refreshBtn.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  refreshBtn.title = "Aggiornamento in corso...";
  try {
    await postJSON("/api/reindex", {});
    await loadTreeRoot();
    await loadPhotos(state.currentPath, true);
    loadImmichStatus();
    // L'aggiornamento di Immich gira in background sul server: dopo
    // qualche secondo ricontrolliamo lo stato e i badge.
    setTimeout(() => {
      loadImmichStatus();
      loadTreeRoot();
    }, 3000);
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

async function fetchTree(path) {
  const qs = state.showHidden ? "&showHidden=1" : "";
  return fetchJSON(`/api/tree?path=${encodeURIComponent(path)}${qs}`);
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
  if (folder.hasChildren) toggle.innerHTML = ICON_CHEVRON;
  row.appendChild(toggle);

  const label = document.createElement("span");
  label.className = "folder-label";
  if (folder.hidden) label.classList.add("is-hidden-folder");

  const labelText = document.createElement("span");
  labelText.className = "folder-label-text";
  labelText.textContent = folder.name;
  label.appendChild(labelText);

  if (folder.inImmich) {
    const badge = document.createElement("span");
    badge.className = "immich-badge";
    badge.title = "Già caricata su Immich";
    badge.innerHTML = ICON_IMMICH_BADGE;
    label.appendChild(badge);
  }

  if (folder.photoCount > 0) {
    const count = document.createElement("span");
    count.className = "photo-count";
    count.textContent = folder.photoCount;
    count.title = `${folder.photoCount} foto in questa cartella`;
    label.appendChild(count);
  }

  row.appendChild(label);

  if (showActions) {
    const actions = document.createElement("span");
    actions.className = "folder-actions";

    const renameBtn = document.createElement("button");
    renameBtn.className = "icon-btn";
    renameBtn.title = "Rinomina";
    renameBtn.innerHTML = ICON_RENAME;
    renameBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      renameFolder(folder);
    });
    actions.appendChild(renameBtn);

    const moveBtn = document.createElement("button");
    moveBtn.className = "icon-btn";
    moveBtn.title = "Sposta...";
    moveBtn.innerHTML = ICON_MOVE;
    moveBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openMoveModal(folder);
    });
    actions.appendChild(moveBtn);

    const hideBtn = document.createElement("button");
    hideBtn.className = "icon-btn";
    hideBtn.title = folder.hidden ? "Mostra" : "Nascondi";
    hideBtn.innerHTML = folder.hidden ? ICON_EYE : ICON_EYE_OFF;
    hideBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleHideFolder(folder);
    });
    actions.appendChild(hideBtn);

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "icon-btn icon-btn-danger";
    deleteBtn.title = "Elimina";
    deleteBtn.innerHTML = ICON_TRASH;
    deleteBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openDeleteModal(folder);
    });
    actions.appendChild(deleteBtn);

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
      const children = await fetchTree(folder.path);
      children.forEach((child) => makeFolderNode(child, childrenEl, options));
      loaded = true;
    }
    expanded = true;
    childrenEl.classList.remove("hidden");
    toggle.classList.add("expanded");
  }

  function collapse() {
    expanded = false;
    childrenEl.classList.add("hidden");
    toggle.classList.remove("expanded");
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
  const roots = await fetchTree("");
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

async function toggleHideFolder(folder) {
  try {
    await postJSON(folder.hidden ? "/api/folder/unhide" : "/api/folder/hide", {
      path: folder.path,
    });
    const wasCurrentOrParent =
      state.currentPath === folder.path || state.currentPath.startsWith(folder.path + "/");
    await loadTreeRoot();
    if (!folder.hidden && wasCurrentOrParent) {
      // La cartella che stavi guardando e' appena stata nascosta.
      await loadPhotos("");
    }
  } catch (err) {
    alert(err.message);
  }
}

const deleteModalEl = document.getElementById("delete-modal");
const deleteModalTitleEl = document.getElementById("delete-modal-title");
const deleteConfirmInput = document.getElementById("delete-confirm-input");
const deleteErrorEl = document.getElementById("delete-error");
const deleteConfirmBtn = document.getElementById("delete-confirm");
const deleteCancelBtn = document.getElementById("delete-cancel");

let deleteTarget = null;

function openDeleteModal(folder) {
  deleteTarget = folder;
  deleteModalTitleEl.textContent = folder.name;
  deleteConfirmInput.value = "";
  deleteConfirmBtn.disabled = true;
  deleteErrorEl.classList.add("hidden");
  deleteModalEl.classList.remove("hidden");
  deleteConfirmInput.focus();
}

function closeDeleteModal() {
  deleteModalEl.classList.add("hidden");
  deleteTarget = null;
}

deleteConfirmInput.addEventListener("input", () => {
  deleteConfirmBtn.disabled = !deleteTarget || deleteConfirmInput.value !== deleteTarget.name;
});

deleteCancelBtn.addEventListener("click", closeDeleteModal);
deleteModalEl.addEventListener("click", (e) => {
  if (e.target === deleteModalEl) closeDeleteModal();
});

deleteConfirmBtn.addEventListener("click", async () => {
  if (!deleteTarget) return;
  deleteErrorEl.classList.add("hidden");
  try {
    await postJSON("/api/folder/delete", {
      path: deleteTarget.path,
      confirmName: deleteConfirmInput.value,
    });
    const deletedPath = deleteTarget.path;
    closeDeleteModal();
    await loadTreeRoot();
    if (state.currentPath === deletedPath || state.currentPath.startsWith(deletedPath + "/")) {
      await loadPhotos("");
    }
  } catch (err) {
    deleteErrorEl.textContent = err.message;
    deleteErrorEl.classList.remove("hidden");
  }
});

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
loadImmichStatus();
pollPrecacheStatus();
// All'avvio, in background sul server ripartono sia il controllo di
// Immich sia il ricontrollo del NAS (per le cartelle aggiunte da fuori):
// ricarichiamo l'albero un paio di volte nei secondi successivi per
// prendere i risultati senza dover premere "Aggiorna" a mano.
setTimeout(() => {
  loadImmichStatus();
  loadTreeRoot();
}, 3000);
setTimeout(() => {
  loadTreeRoot();
}, 8000);
