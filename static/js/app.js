const API = "";
let currentUser = 1;

// --- Navigation ---
function showPanel(name) {
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.querySelectorAll(".nav button").forEach(b => b.classList.remove("active"));
    document.getElementById("panel-" + name).classList.add("active");
    document.querySelector(`.nav button[data-panel="${name}"]`).classList.add("active");

    if (name === "bellman") loadBellmanMovies();
    if (name === "recs" && $("rec-results").querySelector(".empty-state")) generateRecs();
}

// --- Modo técnico ---
function toggleTech() {
    document.body.classList.toggle("tech-mode", $("tech-toggle").checked);
}

// --- Helpers ---
function $(id) { return document.getElementById(id); }
function html(id, content) { $(id).innerHTML = content; }
function loading(id) {
    html(id, `<div class="loading"><span class="spinner"></span> Analizando datos...</div>`);
}
function formatNum(n) { return n.toLocaleString("es-PE"); }

function genreTags(genres) {
    return genres.filter(g => g !== "(no genres listed)").map(g => {
        const cls = g.replace(/[^a-zA-Z]/g, "-");
        return `<span class="tag tag-${cls}">${g}</span>`;
    }).join("");
}

function errMsg(id) {
    html(id, `<div class="empty-state"><div class="empty-icon">⚠️</div><div class="empty-text">Error al conectar con el servidor. Verifica que esté ejecutándose e intenta de nuevo.</div></div>`);
}

// --- Global user change ---
async function onUserChange(uid) {
    currentUser = parseInt(uid);
    $("global-user-info").textContent = "Cargando...";

    const onRecsPanel = document.getElementById("panel-recs").classList.contains("active");
    html("rec-results", `<div class="empty-state"><div class="empty-icon">🎬</div><div class="empty-text">Buscando películas para ti...</div></div>`);
    html("flow-results", `<div class="empty-state"><div class="empty-icon">🍿</div><div class="empty-text">Haz clic en <strong>"Repartir películas"</strong> para ver qué le toca a cada uno</div></div>`);
    html("bf-results", `<div class="empty-state"><div class="empty-icon">▶️</div><div class="empty-text">Elige una película que te haya gustado y haz clic en <strong>"Qué ver después"</strong></div></div>`);

    try {
        const info = await fetch(API + `/api/user/${currentUser}`).then(r => r.json());
        $("global-user-info").textContent = `${info.total_ratings} películas · ★ ${info.avg_rating}`;
        loadUserProfile(info);
    } catch {
        $("global-user-info").textContent = "Error al cargar";
    }
    loadBellmanMovies();
    if (onRecsPanel) generateRecs();
}

// --- Init ---
async function init() {
    try {
        const [summary, users] = await Promise.all([
            fetch(API + "/api/summary").then(r => r.json()),
            fetch(API + "/api/users").then(r => r.json()),
        ]);

        html("stats", `
            <div class="stat-card"><div class="icon">👤</div><div class="value">${formatNum(summary.usuarios)}</div><div class="label">Usuarios</div></div>
            <div class="stat-card"><div class="icon">🎬</div><div class="value">${formatNum(summary.peliculas)}</div><div class="label">Películas</div></div>
            <div class="stat-card"><div class="icon">⭐</div><div class="value">${formatNum(summary.ratings)}</div><div class="label">Calificaciones</div></div>
            <div class="stat-card tech-detail"><div class="icon">🔵</div><div class="value">${formatNum(summary.nodos)}</div><div class="label">Nodos del grafo</div></div>
            <div class="stat-card tech-detail"><div class="icon">🔗</div><div class="value">${formatNum(summary.aristas)}</div><div class="label">Aristas del grafo</div></div>
        `);

        const opts = users.map(u => `<option value="${u.id}" ${u.id === 1 ? "selected" : ""}>${u.name}</option>`).join("");
        $("global-user-select").innerHTML = opts;

        onUserChange(1);
    } catch {
        html("stats", `<div class="empty-state"><div class="empty-text">⚠️ No se pudo conectar con el servidor. Verifica que esté ejecutándose.</div></div>`);
    }
}

// --- User profile ---
function loadUserProfile(info) {
    html("user-info", `
        <div class="stats-row" style="margin-bottom:16px">
            <div class="stat-card"><div class="icon">🎬</div><div class="value">${info.total_ratings}</div><div class="label">Películas vistas</div></div>
            <div class="stat-card"><div class="icon">⭐</div><div class="value">${info.avg_rating}</div><div class="label">Rating promedio</div></div>
        </div>
        <h3>Películas favoritas</h3>
        <div class="movie-list">
            ${info.top_movies.map((m, i) => `
                <div class="movie-row">
                    <span class="movie-rank">${i + 1}</span>
                    <div class="movie-details">
                        <div class="movie-title">${m.title}</div>
                        <div>${genreTags(m.genres)}</div>
                    </div>
                    <div class="movie-rating">
                        <span class="rating-stars">${"★".repeat(Math.round(m.rating))}${"☆".repeat(5 - Math.round(m.rating))}</span>
                        <span class="rating-num">${m.rating}</span>
                    </div>
                </div>
            `).join("")}
        </div>
    `);
}

// --- Recommendations ---
async function generateRecs() {
    const k = parseInt($("rec-k").value) || 5;
    loading("rec-results");
    const btn = document.querySelector('[onclick="generateRecs()"]');
    if (btn) btn.disabled = true;

    try {
        const data = await fetch(API + `/api/recommend/${currentUser}?k=${k}`).then(r => r.json());

        // Vista simple: lista limpia con resultados de Programación Dinámica
        const simpleView = `
            <div class="simple-rec-view">
                <div class="rec-summary">
                    Encontramos <strong>${data.dp.recs.length} películas</strong> pensadas para ti.
                </div>
                <div class="movie-list">
                    ${data.dp.recs.map((r, i) => `
                        <div class="movie-row">
                            <span class="movie-rank">${i + 1}</span>
                            <div class="movie-details">
                                <div class="movie-title">${r.title}</div>
                                <div>${genreTags(r.genres)}</div>
                            </div>
                        </div>
                    `).join("")}
                </div>
            </div>
        `;

        // Vista técnica: 3 columnas con comparación de algoritmos
        function recColumn(algoName, method, color, emoji) {
            const d = data[method];
            const maxScore = Math.max(...d.recs.map(r => r.score), 1);
            return `
                <div class="rec-column" style="border-top: 3px solid ${color}">
                    <h3>${emoji} ${algoName}</h3>
                    <div style="font-size:0.75rem;color:var(--text-secondary);margin-bottom:8px">${d.time}s | Score total: ${d.total_score}</div>
                    <div class="meta">${d.recs.length} películas</div>
                    ${d.recs.map((r, i) => `
                        <div class="rec-item">
                            <div class="rec-item-header">
                                <div class="rank" style="background:${color}20;color:${color}">#${i + 1}</div>
                                <div class="title">${r.title}</div>
                            </div>
                            <div class="info">${genreTags(r.genres)}</div>
                            <div style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px">Score: ${r.score}</div>
                            <div class="score-bar"><div class="fill" style="width:${(r.score / maxScore * 100)}%;background:${color}"></div></div>
                        </div>
                    `).join("")}
                </div>
            `;
        }

        const techView = `
            <div class="tech-view">
                <div class="rec-summary">
                    Se analizaron <strong>${formatNum(data.total_candidates)}</strong> candidatos en ${data.scoring_time}s
                    (Fuerza Bruta + BFS + Merge Sort)
                </div>
                <div class="grid-3">
                    ${recColumn("Backtracking", "backtracking", "#4f9cf7", "🔄")}
                    ${recColumn("Greedy (Voraz)", "greedy", "#f59e0b", "⚡")}
                    ${recColumn("Programación Dinámica", "dp", "#34d399", "📦")}
                </div>
                <div class="section" style="margin-top:20px">
                    <h3>👥 Usuarios con gustos parecidos</h3>
                    <p style="font-size:0.78rem;color:var(--text-secondary);margin-bottom:12px">Fuerza Bruta (similitud coseno) + Merge Sort</p>
                    <table class="data-table">
                        <thead><tr><th>Usuario</th><th>Compatibilidad</th><th>Similitud coseno</th></tr></thead>
                        <tbody>${data.similar_users.map(u => `
                            <tr>
                                <td>Usuario ${u.user_id}</td>
                                <td><div class="compat-bar"><div class="compat-fill" style="width:${u.similarity * 100}%"></div><span>${(u.similarity * 100).toFixed(1)}%</span></div></td>
                                <td>${u.similarity}</td>
                            </tr>
                        `).join("")}</tbody>
                    </table>
                </div>
            </div>
        `;

        html("rec-results", simpleView + techView);
        toggleTech();
    } catch {
        errMsg("rec-results");
    } finally {
        if (btn) btn.disabled = false;
    }
}

function simplifyReason(reason) {
    if (!reason) return "";
    return reason
        .replace(/cerca en grafo \(\d+ conex\.\)/g, "Popular entre personas similares a ti")
        .replace(/usuario \d+ \(sim:[\d.]+\)/g, "Le gustó a alguien con tus mismos gustos")
        .replace(/; /g, " · ");
}

// --- UFDS ---
async function runUFDS() {
    loading("ufds-results");
    const btn = document.querySelector('[onclick="runUFDS()"]');
    if (btn) btn.disabled = true;
    try {
        const data = await fetch(API + "/api/ufds").then(r => r.json());
        html("ufds-results", `
            <div class="stats-row">
                <div class="stat-card"><div class="value">${data.total_clusters}</div><div class="label">Grupos encontrados</div></div>
                <div class="stat-card"><div class="value">${data.multi_clusters}</div><div class="label">Grupos con 2+ personas</div></div>
                <div class="stat-card tech-detail"><div class="value">${formatNum(data.unions)}</div><div class="label">Uniones UFDS</div></div>
                <div class="stat-card tech-detail"><div class="value">${data.time}s</div><div class="label">Tiempo</div></div>
            </div>
            <h3>Grupos más grandes</h3>
            ${data.top_clusters.map((c, i) => `
                <div class="community-item">
                    <div class="comm-header">
                        <span class="comm-badge" style="background:var(--accent-purple)">${c.size}</span>
                        <span>Grupo ${i + 1} — ${c.size} personas con gustos similares</span>
                    </div>
                    <div class="members">Usuarios: ${c.members.join(", ")}${c.size > 15 ? "..." : ""}</div>
                </div>
            `).join("")}
        `);
        toggleTech();
    } catch {
        errMsg("ufds-results");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// --- SCC ---
async function runSCC() {
    loading("scc-results");
    const btn = document.querySelector('[onclick="runSCC()"]');
    if (btn) btn.disabled = true;
    try {
        const data = await fetch(API + "/api/scc").then(r => r.json());
        html("scc-results", `
            <div class="stats-row">
                <div class="stat-card"><div class="value">${data.total_communities}</div><div class="label">Círculos encontrados</div></div>
                <div class="stat-card tech-detail"><div class="value">${data.time}s</div><div class="label">Tiempo Kosaraju</div></div>
            </div>
            ${data.communities.length === 0
                ? '<div class="empty-state-sm">No se encontraron círculos con los parámetros actuales.</div>'
                : data.communities.map((c, i) => `
                    <div class="community-item">
                        <div class="comm-header">
                            <span class="comm-badge" style="background:var(--accent-orange)">${c.size}</span>
                            <span>Círculo ${i + 1} — ${c.size} personas que se influyen entre sí</span>
                        </div>
                        <div class="members">Miembros: ${c.members.join(", ")}${c.size > 15 ? "..." : ""}</div>
                    </div>
                `).join("")
            }
        `);
        toggleTech();
    } catch {
        errMsg("scc-results");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// --- MST ---
async function runMST() {
    loading("mst-results");
    const btn = document.querySelector('[onclick="runMST()"]');
    if (btn) btn.disabled = true;
    try {
        const data = await fetch(API + "/api/mst").then(r => r.json());
        html("mst-results", `
            <div class="stats-row">
                <div class="stat-card"><div class="value">${data.total_edges}</div><div class="label">Conexiones en la red</div></div>
                <div class="stat-card tech-detail"><div class="value">${data.total_weight}</div><div class="label">Costo total MST</div></div>
                <div class="stat-card tech-detail"><div class="value">${data.time}s</div><div class="label">Tiempo Kruskal</div></div>
            </div>
            <h3>Parejas más compatibles</h3>
            ${data.top_edges.map(e => `
                <div class="mst-edge">
                    <span class="edge-label">Usuario ${e.u1} — Usuario ${e.u2}</span>
                    <div class="sim-bar"><div class="fill" style="width:${e.similarity * 100}%"></div></div>
                    <span class="sim-val">${(e.similarity * 100).toFixed(1)}%</span>
                </div>
            `).join("")}
        `);
        toggleTech();
    } catch {
        errMsg("mst-results");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// --- Ford-Fulkerson ---
async function runFlow() {
    loading("flow-results");
    const btn = document.querySelector('[onclick="runFlow()"]');
    if (btn) btn.disabled = true;
    try {
        const data = await fetch(API + `/api/flow/${currentUser}`).then(r => r.json());
        html("flow-results", `
            <div class="stats-row">
                <div class="stat-card"><div class="icon">🎬</div><div class="value">${data.max_flow}</div><div class="label">Películas repartidas</div></div>
                <div class="stat-card tech-detail"><div class="value">${data.time}s</div><div class="label">Tiempo Ford-Fulkerson</div></div>
            </div>
            <h3>¿Qué le toca ver a cada uno?</h3>
            ${Object.entries(data.assignments).map(([uid, asn]) => `
                <div class="flow-user">
                    <div class="user-label">👤 ${asn.name}</div>
                    ${asn.movies.map(m => `
                        <div class="movie-item">🎬 ${m.title}</div>
                    `).join("")}
                </div>
            `).join("")}
        `);
        toggleTech();
    } catch {
        errMsg("flow-results");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// --- Bellman-Ford ---
async function loadBellmanMovies() {
    try {
        const movies = await fetch(API + `/api/user_top_movies/${currentUser}`).then(r => r.json());
        const sel = $("bf-movie-select");
        sel.innerHTML = movies.map(m =>
            `<option value="${m.movie_id}">${m.title} (★ ${m.rating})</option>`
        ).join("");
    } catch {
        $("bf-movie-select").innerHTML = `<option>Error al cargar películas</option>`;
    }
}

async function runBellman() {
    const mid = parseInt($("bf-movie-select").value);
    if (!mid) return;
    loading("bf-results");
    const btn = document.querySelector('[onclick="runBellman()"]');
    if (btn) btn.disabled = true;
    try {
        const data = await fetch(API + `/api/bellman/${currentUser}/${mid}`).then(r => r.json());
        html("bf-results", `
            <div class="bf-start">
                Porque te gustó: <strong>${data.start_movie}</strong>
                <span class="tech-detail"> | Bellman-Ford: ${data.time}s</span>
            </div>
            ${data.path.length === 0
                ? '<div class="empty-state"><div class="empty-icon">😕</div><div class="empty-text">No se encontraron películas similares. Prueba con otra película.</div></div>'
                : data.path.map((p, i) => `
                    <div class="path-item">
                        <div class="number">${i + 1}</div>
                        <div class="details">
                            <div class="title">${p.title}</div>
                            <div>${genreTags(p.genres)}</div>
                        </div>
                        <div class="dist-badge">${(Math.max(0, 100 - p.distance * 80)).toFixed(0)}% afín</div>
                    </div>
                `).join("")
            }
        `);
        toggleTech();
    } catch {
        errMsg("bf-results");
    } finally {
        if (btn) btn.disabled = false;
    }
}

// --- Boot ---
document.addEventListener("DOMContentLoaded", init);
