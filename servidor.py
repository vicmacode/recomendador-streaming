"""
Recomendador de Contenido para Streaming - Backend Flask
Curso: 1ACC0184 - Complejidad Algorítmica
Ejecutar: python servidor.py
"""

from __future__ import annotations

import csv
import time
import urllib.request
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

import sys
sys.setrecursionlimit(15000)

from flask import Flask, jsonify, render_template, request

NOMBRES = ["Ana","Carlos","María","Juan","Valentina","Sebastián","Camila","Diego",
           "Sofía","Alejandro","Isabella","Mateo","Lucía","Andrés","Daniela",
           "Felipe","Paula","Javier","Natalia","Miguel","Laura","Gabriel",
           "Adriana","Rodrigo","Fernanda"]
APELLIDOS = ["García","López","Martínez","Rodríguez","González","Fernández",
             "Pérez","Sánchez","Ramírez","Torres","Flores","Rivera","Morales",
             "Ortiz","Cruz","Reyes","Gutiérrez","Herrera","Mendoza","Vargas",
             "Castro","Ríos","Moreno","Jiménez","Ruiz"]

def get_user_name(uid: int) -> str:
    i = uid - 1
    return f"{NOMBRES[i % len(NOMBRES)]} {APELLIDOS[(i // len(NOMBRES)) % len(APELLIDOS)]}"

# ============================================================
# Datos
# ============================================================
DATASET_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
DATASET_ZIP = "ml-latest-small.zip"
DATASET_DIR = "ml-latest-small"


@dataclass(frozen=True)
class Movie:
    movie_id: int
    title: str
    genres: Tuple[str, ...]


@dataclass(frozen=True)
class Recommendation:
    movie_id: int
    title: str
    genres: Tuple[str, ...]
    score: float
    reason: str

    def to_dict(self):
        return {
            "movie_id": self.movie_id,
            "title": self.title,
            "genres": list(self.genres),
            "score": round(self.score, 3),
            "reason": self.reason,
        }


# ============================================================
# Merge Sort
# ============================================================
def merge_sort_pairs_desc(values):
    if len(values) <= 1:
        return values
    mid = len(values) // 2
    left = merge_sort_pairs_desc(values[:mid])
    right = merge_sort_pairs_desc(values[mid:])
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if left[i][1] >= right[j][1]:
            result.append(left[i]); i += 1
        else:
            result.append(right[j]); j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


def merge_sort_recs_desc(values):
    if len(values) <= 1:
        return values
    mid = len(values) // 2
    left = merge_sort_recs_desc(values[:mid])
    right = merge_sort_recs_desc(values[mid:])
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if left[i].score >= right[j].score:
            result.append(left[i]); i += 1
        else:
            result.append(right[j]); j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


# ============================================================
# Motor del recomendador
# ============================================================
class StreamingRecommender:
    def __init__(self, movies, ratings):
        self.movies = movies
        self.ratings = ratings
        self.user_ratings: Dict[int, Dict[int, float]] = defaultdict(dict)
        self.movie_users: Dict[int, Dict[int, float]] = defaultdict(dict)

        # Grafo bipartito como lista de adyacencia
        self.graph: Dict[str, List[str]] = defaultdict(list)

        for uid, mid, rating in ratings:
            self.user_ratings[uid][mid] = rating
            self.movie_users[mid][uid] = rating
            u_node = f"U{uid}"
            m_node = f"M{mid}"
            self.graph[u_node].append(m_node)
            self.graph[m_node].append(u_node)

    def summary(self):
        return {
            "usuarios": len(self.user_ratings),
            "peliculas": len(self.movies),
            "ratings": len(self.ratings),
            "nodos": len(self.user_ratings) + len(self.movies),
            "aristas": len(self.ratings),
        }

    def user_info(self, uid):
        if uid not in self.user_ratings:
            return None
        rats = self.user_ratings[uid]
        top = sorted(rats.items(), key=lambda x: -x[1])[:10]
        return {
            "user_id": uid,
            "name": get_user_name(uid),
            "total_ratings": len(rats),
            "avg_rating": round(sum(rats.values()) / len(rats), 2),
            "top_movies": [
                {"title": self.movies[mid].title, "rating": r, "genres": list(self.movies[mid].genres)}
                for mid, r in top if mid in self.movies
            ],
        }

    # ================================================================
    # Fuerza Bruta
    # ================================================================
    def brute_force_similar(self, target, min_common=3):
        t = self.user_ratings[target]
        sims = []
        for other, r2 in self.user_ratings.items():
            if other == target:
                continue
            common = set(t).intersection(r2)
            if len(common) < min_common:
                continue
            num = sum(t[m] * r2[m] for m in common)
            n1 = sum(t[m] ** 2 for m in common) ** 0.5
            n2 = sum(r2[m] ** 2 for m in common) ** 0.5
            if n1 > 0 and n2 > 0:
                sims.append((other, num / (n1 * n2)))
        return merge_sort_pairs_desc(sims)

    # ================================================================
    # BFS
    # ================================================================
    def bfs_candidates(self, target, max_depth=3, min_rating=4.0):
        start = f"U{target}"
        watched = set(self.user_ratings[target])
        n_nodes = len(self.graph)
        visited = {start: True}
        queue = [(start, 0)]
        cands = defaultdict(int)

        while queue:
            node, depth = queue.pop(0)
            if depth == max_depth:
                continue
            for nb in self.graph[node]:
                if nb not in visited:
                    visited[nb] = True
                    queue.append((nb, depth + 1))
                    if nb.startswith("M"):
                        mid = int(nb[1:])
                        if mid not in watched:
                            cands[mid] += 1
                    if nb.startswith("U") and depth + 1 <= max_depth:
                        uid = int(nb[1:])
                        for mid, r in self.user_ratings[uid].items():
                            if r >= min_rating and mid not in watched:
                                cands[mid] += 1
        return dict(cands)

    # ================================================================
    # DFS
    # ================================================================
    def connected_components(self, limit=1500):
        nodes = list(self.graph)[:limit]
        allowed = set(nodes)
        visited = {}
        comps = []

        def _dfs(u, component):
            visited[u] = True
            component.append(u)
            for v in self.graph[u]:
                if v in allowed and v not in visited:
                    _dfs(v, component)

        for node in nodes:
            if node not in visited:
                comp = []
                _dfs(node, comp)
                comps.append(comp)
        return comps

    # ================================================================
    # Scoring
    # ================================================================
    def score_candidates(self, target, top_similar=25, max_depth=3):
        similar = self.brute_force_similar(target)[:top_similar]
        bfs = self.bfs_candidates(target, max_depth=max_depth)
        watched = set(self.user_ratings[target])
        scores = defaultdict(float)
        reasons = defaultdict(list)
        for mid, freq in bfs.items():
            scores[mid] += freq * 0.25
            reasons[mid].append(f"cerca en grafo ({freq} conex.)")
        for uid, sim in similar:
            for mid, r in self.user_ratings[uid].items():
                if mid in watched or r < 4.0:
                    continue
                scores[mid] += sim * r
                reasons[mid].append(f"usuario {uid} (sim:{sim:.2f})")
        recs = [
            Recommendation(mid, self.movies[mid].title, self.movies[mid].genres,
                           score, "; ".join(reasons[mid][:2]))
            for mid, score in scores.items() if mid in self.movies
        ]
        return merge_sort_recs_desc(recs)

    # ================================================================
    # Backtracking
    # ================================================================
    def backtracking_recs(self, candidates, k=5, max_per_genre=2):
        limited = candidates[:20]
        best, best_score = [], -1.0

        def genre_counts(sel):
            c = defaultdict(int)
            for r in sel:
                for g in r.genres:
                    if g != "(no genres listed)":
                        c[g] += 1
            return c

        def is_valid(sel, cand):
            c = genre_counts(sel)
            for g in cand.genres:
                if g != "(no genres listed)" and c[g] >= max_per_genre:
                    return False
            return True

        def bt(idx, sel, sc):
            nonlocal best, best_score
            if len(sel) == k or idx == len(limited):
                if len(sel) > len(best) or (len(sel) == len(best) and sc > best_score):
                    best, best_score = sel[:], sc
                return
            if len(sel) + len(limited) - idx < k:
                return
            cand = limited[idx]
            if is_valid(sel, cand):
                sel.append(cand)
                bt(idx + 1, sel, sc + cand.score)
                sel.pop()
            bt(idx + 1, sel, sc)

        bt(0, [], 0.0)
        return best

    # ================================================================
    # Greedy
    # ================================================================
    def greedy_recs(self, candidates, k=5, max_per_genre=2):
        genre_counts = defaultdict(int)
        sel = []
        for c in candidates:
            if len(sel) >= k:
                break
            valid = True
            for g in c.genres:
                if g != "(no genres listed)" and genre_counts[g] >= max_per_genre:
                    valid = False
                    break
            if valid:
                sel.append(c)
                for g in c.genres:
                    if g != "(no genres listed)":
                        genre_counts[g] += 1
        return sel

    # ================================================================
    # DP Mochila
    # ================================================================
    def dp_knapsack_recs(self, candidates, k=5, genre_limit=10):
        limited = candidates[:30]
        n = len(limited)
        if n == 0:
            return []

        V = [int(r.score * 100) for r in limited]
        W = [max(1, len([g for g in r.genres if g != "(no genres listed)"])) for r in limited]
        M = genre_limit
        C = {}

        def knapsack(i, j):
            if (i, j) in C:
                return C[(i, j)]
            if i == 0 or j == 0:
                C[(i, j)] = 0
                return 0
            if W[i - 1] > j:
                C[(i, j)] = knapsack(i - 1, j)
            else:
                C[(i, j)] = max(V[i - 1] + knapsack(i - 1, j - W[i - 1]), knapsack(i - 1, j))
            return C[(i, j)]

        knapsack(n, M)

        selected = []
        j = M
        for i in range(n, 0, -1):
            if C.get((i, j), 0) != C.get((i - 1, j), 0):
                selected.append(i - 1)
                j -= W[i - 1]
                if len(selected) >= k:
                    break

        return [limited[i] for i in reversed(selected)][:k]

    # ================================================================
    # UFDS Quick-Union Ponderado
    # ================================================================
    def ufds_clusters(self, threshold=0.99, min_common=20):
        users = list(self.user_ratings.keys())
        n = len(users)
        s = [-1] * n

        def find(a):
            i = a
            while s[i] >= 0:
                i = s[i]
            return i

        def union(a, b):
            pa = find(a)
            pb = find(b)
            if pa == pb:
                return
            if s[pa] < s[pb]:
                s[pa] += s[pb]
                s[pb] = pa
            elif s[pb] < s[pa]:
                s[pb] += s[pa]
                s[pa] = pb
            else:
                s[pa] += s[pb]
                s[pb] = pa

        ct = 0
        for i in range(n):
            r1 = self.user_ratings[users[i]]
            for j in range(i + 1, n):
                r2 = self.user_ratings[users[j]]
                common = set(r1).intersection(r2)
                if len(common) < min_common:
                    continue
                num = sum(r1[m] * r2[m] for m in common)
                n1 = sum(r1[m] ** 2 for m in common) ** 0.5
                n2 = sum(r2[m] ** 2 for m in common) ** 0.5
                if n1 > 0 and n2 > 0 and num / (n1 * n2) >= threshold:
                    union(i, j)
                    ct += 1

        clusters = defaultdict(list)
        for i in range(n):
            root = find(i)
            clusters[users[root]].append(users[i])
        return dict(clusters), ct

    # ================================================================
    # SCC Kosaraju
    # ================================================================
    def kosaraju_scc(self, threshold=0.8, min_common=5, max_users=200):
        users = list(self.user_ratings.keys())[:max_users]
        n = len(users)

        G = [[] for _ in range(n)]
        G_t = [[] for _ in range(n)]

        for i in range(n):
            r1 = self.user_ratings[users[i]]
            for j in range(n):
                if i == j:
                    continue
                r2 = self.user_ratings[users[j]]
                common = set(r1).intersection(r2)
                if len(common) < min_common:
                    continue
                high = {m for m in common if r1[m] >= 4.0}
                if not high:
                    continue
                if sum(1 for m in high if r2[m] >= 4.0) / len(high) >= threshold:
                    G[i].append(j)
                    G_t[j].append(i)

        # Paso 1: toposort con DFS
        visited = [False] * n
        ts = []

        def dfs(u):
            visited[u] = True
            for v in G[u]:
                if not visited[v]:
                    dfs(v)
            ts.append(u)

        for u in range(n):
            if not visited[u]:
                dfs(u)

        # Paso 2: DFS en grafo transpuesto en orden inverso
        visited = [False] * n
        sccs = []

        def dfs_t(u, comp):
            visited[u] = True
            comp.append(users[u])
            for v in G_t[u]:
                if not visited[v]:
                    dfs_t(v, comp)

        for u in reversed(ts):
            if not visited[u]:
                comp = []
                dfs_t(u, comp)
                if len(comp) > 1:
                    sccs.append(comp)

        return sccs

    # ================================================================
    # MST Kruskal
    # ================================================================
    def kruskal_mst(self, max_users=100, min_common=5):
        users = list(self.user_ratings.keys())[:max_users]
        V = len(users)

        graph_edges = []
        for i in range(V):
            r1 = self.user_ratings[users[i]]
            for j in range(i + 1, V):
                r2 = self.user_ratings[users[j]]
                common = set(r1).intersection(r2)
                if len(common) < min_common:
                    continue
                num = sum(r1[m] * r2[m] for m in common)
                n1 = sum(r1[m] ** 2 for m in common) ** 0.5
                n2 = sum(r2[m] ** 2 for m in common) ** 0.5
                if n1 > 0 and n2 > 0:
                    w = 1.0 - num / (n1 * n2)
                    graph_edges.append([i, j, w])

        graph_edges = sorted(graph_edges, key=lambda item: item[2])

        parent = list(range(V))
        rank = [0] * V

        def find(i):
            if parent[i] == i:
                return i
            return find(parent[i])

        def apply_union(x, y):
            xroot = find(x)
            yroot = find(y)
            if rank[xroot] < rank[yroot]:
                parent[xroot] = yroot
            elif rank[xroot] > rank[yroot]:
                parent[yroot] = xroot
            else:
                parent[yroot] = xroot
                rank[xroot] += 1

        result = []
        e = 0
        i = 0
        while e < V - 1 and i < len(graph_edges):
            u, v, w = graph_edges[i]
            i += 1
            x = find(u)
            y = find(v)
            if x != y:
                e += 1
                result.append((users[u], users[v], round(w, 4)))
                apply_union(x, y)

        return result

    # ================================================================
    # Ford-Fulkerson
    # ================================================================
    def ford_fulkerson(self, user_ids, movie_ids, max_per_user=3):
        nu, nm = len(user_ids), len(movie_ids)
        total = 1 + nu + nm + 1
        s_node = 0
        t_node = total - 1

        un = {u: i + 1 for i, u in enumerate(user_ids)}
        mn = {m: nu + 1 + i for i, m in enumerate(movie_ids)}

        graph = [[0] * total for _ in range(total)]

        for u in user_ids:
            graph[s_node][un[u]] = max_per_user
        for u in user_ids:
            for m in movie_ids:
                if m in self.movie_users and u in self.movie_users[m]:
                    if self.movie_users[m][u] >= 3.5:
                        graph[un[u]][mn[m]] = 1
                elif m not in self.user_ratings.get(u, {}):
                    graph[un[u]][mn[m]] = 1
        for m in movie_ids:
            graph[mn[m]][t_node] = max(1, nu // 2)

        def BFS(graph, s, t, parent):
            visited = [False] * len(graph)
            queue = [s]
            visited[s] = True
            while queue:
                u = queue.pop(0)
                for ind in range(len(graph[u])):
                    if visited[ind] is False and graph[u][ind] > 0:
                        queue.append(ind)
                        visited[ind] = True
                        parent[ind] = u
            return True if visited[t] else False

        parent = [-1] * total
        max_flow = 0

        while BFS(graph, s_node, t_node, parent):
            path_flow = float("Inf")
            s = t_node
            while s != s_node:
                path_flow = min(path_flow, graph[parent[s]][s])
                s = parent[s]
            max_flow += path_flow
            v = t_node
            while v != s_node:
                u = parent[v]
                graph[u][v] -= path_flow
                graph[v][u] += path_flow
                v = parent[v]
            parent = [-1] * total

        assign = defaultdict(list)
        for u in user_ids:
            for m in movie_ids:
                if graph[mn[m]][un[u]] > 0:
                    assign[u].append(m)
        return max_flow, dict(assign)

    # ================================================================
    # Bellman-Ford
    # ================================================================
    def bellman_ford_path(self, start_movie, target_user, max_movies=150):
        watched = set(self.user_ratings[target_user])

        seed = {start_movie}
        top_rated = sorted(self.user_ratings[target_user].items(), key=lambda x: -x[1])
        for mid, _ in top_rated[:30]:
            seed.add(mid)

        unwatched = [(m, len(self.movie_users[m])) for m in self.movies
                     if m not in watched and m in self.movie_users]
        unwatched.sort(key=lambda x: -x[1])
        cands = set(seed)
        for m, _ in unwatched[:max_movies - len(seed)]:
            cands.add(m)

        movies_list = list(cands)
        movie_to_idx = {m: i for i, m in enumerate(movies_list)}
        n = len(movies_list)

        if start_movie not in movie_to_idx:
            return []

        # Construir grafo como diccionario
        graph = {}
        for i in range(n):
            graph[i] = [{}, False]
        for i in range(n):
            users_i = set(self.movie_users.get(movies_list[i], {}).keys())
            for j in range(n):
                if i == j:
                    continue
                users_j = set(self.movie_users.get(movies_list[j], {}).keys())
                common_users = users_i.intersection(users_j)
                if len(common_users) < 2:
                    continue
                diff = sum(abs(self.movie_users[movies_list[i]][u] - self.movie_users[movies_list[j]][u])
                           for u in common_users)
                w = diff / len(common_users)
                graph[i][0][j] = w

        # Bellman-Ford
        source = movie_to_idx[start_movie]
        keys = list(graph.keys())
        index_keys = {keys[i]: i for i in range(len(keys))}

        cache = [[float('Inf') if key != source else 0 for key in keys]]
        for iteration in range(1, len(keys) + 1):
            cache.append([])
            stable = True
            for j in range(len(keys)):
                temp = [float('Inf')]
                for key in keys:
                    if keys[j] in graph[key][0]:
                        temp.append(cache[iteration - 1][index_keys[key]] + graph[key][0][keys[j]])
                cache[iteration].append(min(cache[iteration - 1][j], min(temp)))
                if cache[iteration][j] != cache[iteration - 1][j]:
                    stable = False
            if stable:
                break

        last = cache[-1]
        results = []
        for i in range(n):
            mid = movies_list[i]
            if mid == start_movie or mid in watched:
                continue
            idx_i = index_keys.get(i, -1)
            if idx_i >= 0 and last[idx_i] < float('Inf') and mid in self.movies:
                results.append({"movie_id": mid, "title": self.movies[mid].title,
                                "genres": list(self.movies[mid].genres),
                                "distance": round(last[idx_i], 3)})
        results.sort(key=lambda x: x["distance"])
        return results[:10]


# ============================================================
# Cargar dataset
# ============================================================
def load_data():
    ds = Path(DATASET_DIR)
    if not ds.exists():
        print("Descargando MovieLens...")
        urllib.request.urlretrieve(DATASET_URL, DATASET_ZIP)
        with zipfile.ZipFile(DATASET_ZIP, "r") as zf:
            zf.extractall(".")
    movies = {}
    with open(ds / "movies.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mid = int(row["movieId"])
            movies[mid] = Movie(mid, row["title"], tuple(row["genres"].split("|")))
    ratings = []
    with open(ds / "ratings.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ratings.append((int(row["userId"]), int(row["movieId"]), float(row["rating"])))
    return StreamingRecommender(movies, ratings)


# ============================================================
# Flask App
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(BASE_DIR / "static"), template_folder=str(BASE_DIR / "templates"))

import os
os.chdir(BASE_DIR)

print("Cargando dataset...")
rec = load_data()
print("Dataset cargado.")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/summary")
def api_summary():
    return jsonify(rec.summary())


@app.route("/api/users")
def api_users():
    users = sorted(rec.user_ratings.keys())
    return jsonify([{"id": u, "name": get_user_name(u)} for u in users])


@app.route("/api/user/<int:uid>")
def api_user(uid):
    info = rec.user_info(uid)
    if not info:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify(info)


@app.route("/api/recommend/<int:uid>")
def api_recommend(uid):
    k = request.args.get("k", 5, type=int)
    t0 = time.time()
    candidates = rec.score_candidates(uid)
    t_score = time.time() - t0

    t0 = time.time()
    bt = rec.backtracking_recs(candidates, k=k)
    t_bt = time.time() - t0

    t0 = time.time()
    gr = rec.greedy_recs(candidates, k=k)
    t_gr = time.time() - t0

    t0 = time.time()
    dp = rec.dp_knapsack_recs(candidates, k=k)
    t_dp = time.time() - t0

    similar = rec.brute_force_similar(uid)[:10]

    return jsonify({
        "user_id": uid,
        "total_candidates": len(candidates),
        "scoring_time": round(t_score, 4),
        "backtracking": {
            "recs": [r.to_dict() for r in bt],
            "time": round(t_bt, 6),
            "total_score": round(sum(r.score for r in bt), 3),
        },
        "greedy": {
            "recs": [r.to_dict() for r in gr],
            "time": round(t_gr, 6),
            "total_score": round(sum(r.score for r in gr), 3),
        },
        "dp": {
            "recs": [r.to_dict() for r in dp],
            "time": round(t_dp, 6),
            "total_score": round(sum(r.score for r in dp), 3),
        },
        "similar_users": [{"user_id": u, "similarity": round(s, 4)} for u, s in similar],
    })


@app.route("/api/ufds")
def api_ufds():
    t0 = time.time()
    clusters, n_unions = rec.ufds_clusters(threshold=0.99, min_common=20)
    elapsed = time.time() - t0
    multi = {str(k): v for k, v in clusters.items() if len(v) > 1}
    return jsonify({
        "time": round(elapsed, 3),
        "total_clusters": len(clusters),
        "multi_clusters": len(multi),
        "unions": n_unions,
        "top_clusters": [
            {"root": int(k), "size": len(v), "members": v[:15]}
            for k, v in sorted(multi.items(), key=lambda x: -len(x[1]))[:10]
        ],
    })


@app.route("/api/scc")
def api_scc():
    t0 = time.time()
    sccs = rec.kosaraju_scc(threshold=0.8, max_users=200)
    elapsed = time.time() - t0
    sccs.sort(key=len, reverse=True)
    return jsonify({
        "time": round(elapsed, 3),
        "total_communities": len(sccs),
        "communities": [
            {"size": len(c), "members": c[:15]} for c in sccs[:10]
        ],
    })


@app.route("/api/mst")
def api_mst():
    t0 = time.time()
    mst = rec.kruskal_mst(max_users=100)
    elapsed = time.time() - t0
    return jsonify({
        "time": round(elapsed, 3),
        "total_edges": len(mst),
        "total_weight": round(sum(w for _, _, w in mst), 4),
        "top_edges": [
            {"u1": u1, "u2": u2, "weight": w, "similarity": round(1 - w, 4)}
            for u1, u2, w in mst[:20]
        ],
    })


@app.route("/api/flow/<int:uid>")
def api_flow(uid):
    candidates = rec.score_candidates(uid)
    test_users = list(rec.user_ratings.keys())[:10]
    test_movies = [r.movie_id for r in candidates[:15]]
    t0 = time.time()
    flow, assign = rec.ford_fulkerson(test_users, test_movies)
    elapsed = time.time() - t0
    result = {}
    for u, mids in assign.items():
        result[str(u)] = {
            "name": get_user_name(u),
            "movies": [{"movie_id": m, "title": rec.movies[m].title} for m in mids if m in rec.movies]
        }
    return jsonify({"time": round(elapsed, 3), "max_flow": flow, "assignments": result})


@app.route("/api/bellman/<int:uid>/<int:movie_id>")
def api_bellman(uid, movie_id):
    t0 = time.time()
    path = rec.bellman_ford_path(movie_id, uid, max_movies=150)
    elapsed = time.time() - t0
    start_title = rec.movies[movie_id].title if movie_id in rec.movies else "Desconocida"
    return jsonify({"time": round(elapsed, 3), "start_movie": start_title, "path": path})


@app.route("/api/user_top_movies/<int:uid>")
def api_user_top_movies(uid):
    if uid not in rec.user_ratings:
        return jsonify([])
    top = sorted(rec.user_ratings[uid].items(), key=lambda x: -x[1])[:20]
    return jsonify([
        {"movie_id": mid, "title": rec.movies[mid].title, "rating": r}
        for mid, r in top if mid in rec.movies
    ])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if port == 5000:
        import webbrowser
        import threading
        threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(debug=False, use_reloader=False, host="0.0.0.0", port=port)
