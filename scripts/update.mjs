// Rebuilds the live sections of README.md from the GitHub API:
// system status, project activity ("signal") and the recent-activity feed.
// Runs in GitHub Actions every few hours; needs GITHUB_TOKEN in the environment.
import { readFileSync, writeFileSync } from "node:fs";

const USER = "BhanuPrasadPalella-01";
const TOKEN = process.env.GITHUB_TOKEN;
if (!TOKEN) throw new Error("GITHUB_TOKEN is not set");

// Projects shown in `top -p projects`. `repo` enables a live commit signal.
const PROJECTS = [
  { name: "VaultSphere", status: "LIVE", repo: null },
  { name: "Portfolio", status: "LIVE", repo: "Portfolio" },
  { name: "ProteinAI", status: "LIVE", repo: "protein-ss-frontend", repo2: "protein-ss-backend" },
  { name: "GNN-RL", status: "RESEARCH", repo: "gnn-aoi-scheduler" },
  { name: "RescueBot", status: "HARDWARE", repo: null },
  { name: "SwarmBot", status: "DEMO", repo: null },
  { name: "AdaptivePSO", status: "REVIEW", repo: null },
  { name: "MissionSDR", status: "RESEARCH", repo: null },
  { name: "Complaints", status: "ML", repo: null },
  { name: "FractalLab", status: "DONE", repo: null },
];

const headers = { Authorization: `Bearer ${TOKEN}`, "User-Agent": USER, Accept: "application/vnd.github+json" };

async function gql(query, variables) {
  const res = await fetch("https://api.github.com/graphql", {
    method: "POST",
    headers,
    body: JSON.stringify({ query, variables }),
  });
  const json = await res.json();
  if (json.errors) throw new Error(JSON.stringify(json.errors));
  return json.data;
}

async function rest(path) {
  const res = await fetch(`https://api.github.com${path}`, { headers });
  if (!res.ok) return null;
  return res.json();
}

const pad = (s, n) => String(s).padEnd(n).slice(0, n);
const W = 50; // inner width of the boxes

function box(title, lines) {
  const top = `┌─ ${title} ${"─".repeat(Math.max(0, W - title.length - 3))}┐`;
  const body = lines.map((l) => `│ ${pad(l, W - 1)}│`);
  return [top, ...body, `└${"─".repeat(W)}┘`].join("\n");
}

function ago(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} hours`;
  return `${Math.round(hours / 24)} days`;
}

function ist(date = new Date()) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function replaceBlock(readme, key, content) {
  const re = new RegExp(`(<!-- ${key}:START -->)[\\s\\S]*?(<!-- ${key}:END -->)`);
  return readme.replace(re, `$1\n${content}\n$2`);
}

const data = await gql(
  `query($login: String!) {
    user(login: $login) {
      followers { totalCount }
      repositories(ownerAffiliations: OWNER, privacy: PUBLIC, first: 100, orderBy: {field: PUSHED_AT, direction: DESC}) {
        totalCount
        nodes { name stargazerCount pushedAt }
      }
      contributionsCollection {
        contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
      }
    }
  }`,
  { login: USER }
);

const u = data.user;
const repos = u.repositories.nodes;
const stars = repos.reduce((n, r) => n + r.stargazerCount, 0);
const cal = u.contributionsCollection.contributionCalendar;
const days = cal.weeks.flatMap((w) => w.contributionDays);

// Current streak: consecutive days with contributions, allowing today to be empty so far.
let streak = 0;
for (let i = days.length - 1; i >= 0; i--) {
  if (days[i].contributionCount > 0) streak++;
  else if (i === days.length - 1) continue;
  else break;
}
const latest = repos[0];

const status = box("SYSTEM STATUS", [
  "● ONLINE  —  rescuebot.service active (running)",
  "",
  `${pad("public repos", 18)}${u.repositories.totalCount}`,
  `${pad("stars", 18)}${stars}`,
  `${pad("followers", 18)}${u.followers.totalCount}`,
  `${pad("contributions", 18)}${cal.totalContributions} (12mo)`,
  `${pad("streak", 18)}${streak} day${streak === 1 ? "" : "s"}`,
  "",
  "last push",
  latest ? `└── ${latest.name} · ${ago(latest.pushedAt)} ago` : "└── —",
]);

// Commit signal per project over the last 30 days.
const since = new Date(Date.now() - 30 * 86400000).toISOString();
async function commits(repo) {
  if (!repo) return null;
  const list = await rest(`/repos/${USER}/${repo}/commits?since=${since}&per_page=100`);
  return Array.isArray(list) ? list.length : 0;
}
const counts = [];
for (const p of PROJECTS) {
  const a = await commits(p.repo);
  const b = await commits(p.repo2);
  counts.push(a === null ? null : a + (b ?? 0));
}
const peak = Math.max(1, ...counts.filter((c) => c !== null));
const bars = (c) => (c === null ? "············ private" : "▓".repeat(Math.round((c / peak) * 12)).padEnd(12, "░") + ` ${c}`);
const top = box("top -p projects", [
  `${pad("PID", 5)}${pad("PROJECT", 13)}${pad("STATUS", 10)}SIGNAL`,
  "",
  ...PROJECTS.map((p, i) => `${pad(String(i + 1).padStart(3, "0"), 5)}${pad(p.name, 13)}${pad(p.status, 10)}${bars(counts[i])}`),
  "",
  `signal = commits in the last 30 days (peak ${peak})`,
]);

// Recent public activity.
const events = ((await rest(`/users/${USER}/events/public?per_page=30`)) ?? []).sort(
  (a, b) => new Date(b.created_at) - new Date(a.created_at)
);
const lines = [];
for (const e of events) {
  const repo = e.repo.name.split("/")[1];
  const when = ist(new Date(e.created_at));
  let line = null;
  if (e.type === "PushEvent") {
    const n = e.payload.size ?? e.payload.commits?.length ?? 1;
    line = `[${when}] push     ${repo} · ${n} commit${n === 1 ? "" : "s"}`;
  } else if (e.type === "CreateEvent") {
    line = `[${when}] create   ${repo}${e.payload.ref_type === "repository" ? " (new repo)" : ` · ${e.payload.ref_type} ${e.payload.ref ?? ""}`}`;
  } else if (e.type === "ReleaseEvent") {
    line = `[${when}] release  ${repo} · ${e.payload.release?.tag_name ?? ""}`;
  } else if (e.type === "WatchEvent") {
    line = `[${when}] starred  ${e.repo.name}`;
  } else if (e.type === "PublicEvent") {
    line = `[${when}] public   ${repo} is now open source`;
  }
  if (line && !lines.includes(line)) lines.push(line);
  if (lines.length >= 6) break;
}
const feed = lines.length ? lines.join("\n") : "[--] no public events yet — the robot is recharging";

let readme = readFileSync("README.md", "utf8");
readme = replaceBlock(readme, "STATUS", "```text\n" + status + "\n```");
readme = replaceBlock(readme, "TOP", "```text\n" + top + "\n```");
readme = replaceBlock(readme, "FEED", "```text\n" + feed + "\n```");
readme = replaceBlock(readme, "UPDATED", `<sub>⟳ this README rebuilds itself every 6 hours · last run ${ist()} IST</sub>`);
writeFileSync("README.md", readme);
console.log("README updated");
