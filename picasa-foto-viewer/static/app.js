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

refreshBtn.addEventListener("click", () => {
  loadTreeRoot();
  loadPhotos(state.currentPath, true);
});

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Errore ${res.status}`);
  return res.json();
}

function makeFolderNode(folder, container) {
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

  node.appendChild(row);

  const childrenEl = document.createElement("div");
  childrenEl.className = "tree-children hidden";
  node.appendChild(childrenEl);

  let expanded = false;
  let loaded = false;

  async function expand() {
    if (!loaded) {
      const children = await fetchJSON(`/api/tree?path=${encodeURIComponent(folder.path)}`);
      children.forEach((child) => makeFolderNode(child, childrenEl));
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
    document.querySelectorAll(".folder-label.selected").forEach((el) => el.classList.remove("selected"));
    label.classList.add("selected");
    loadPhotos(folder.path);
    if (folder.hasChildren && !expanded) expand();
  });

  container.appendChild(node);
  return node;
}

async function loadTreeRoot() {
  treeEl.innerHTML = "";
  const roots = await fetchJSON("/api/tree?path=");
  roots.forEach((folder) => makeFolderNode(folder, treeEl));
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

loadTreeRoot();
loadPhotos("");
