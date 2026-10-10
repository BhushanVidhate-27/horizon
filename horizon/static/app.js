// Horizon UI — renders one daily alert as an immersive "sky" screen.
// Talks to the FastAPI backend at /api/*.

const $ = (id) => document.getElementById(id);
const resultEl = $("result");
const goBtn = $("go");
const statusEl = $("status");

const icon = (name) => `<svg class="ic"><use href="#i-${name}"/></svg>`;

// --- theme (dark / light) -------------------------------------------------
const THEME_KEY = "horizon_theme";
let themeMode = localStorage.getItem(THEME_KEY);
if (themeMode !== "light" && themeMode !== "dark") {
  themeMode = window.matchMedia?.("(prefers-color-scheme: light)")?.matches ? "light" : "dark";
}

function applyMode(mode) {
  themeMode = mode;
  document.body.classList.toggle("light", mode === "light");
  const btn = $("theme-toggle");
  if (!btn) return;
  btn.querySelector("use")?.setAttribute("href", mode === "light" ? "#i-moon" : "#i-sun");
  btn.title = mode === "light" ? "Switch to dark" : "Switch to light";
}

applyMode(themeMode);

let currentTz = null;
let hourlyPoints = [];

// --- formatting -----------------------------------------------------------
function fmtTime(iso, tz) {
  if (!iso) return "--:--";
  try {
    return new Date(iso).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: tz || undefined,
    });
  } catch {
    return "--:--";
  }
}

function hourIn(iso, tz) {
  const t = fmtTime(iso, tz);
  return parseInt(t.slice(0, 2), 10);
}

// Rich one-line description of *where* this alert is for.
function locationMeta(loc) {
  const bits = [];
  if (loc.latitude != null && loc.longitude != null) {
    const ns = loc.latitude >= 0 ? "N" : "S";
    const ew = loc.longitude >= 0 ? "E" : "W";
    bits.push(
      `${Math.abs(loc.latitude).toFixed(3)}°${ns}, ${Math.abs(loc.longitude).toFixed(3)}°${ew}`
    );
  }
  if (loc.elevation != null) bits.push(`${Math.round(loc.elevation)} m`);
  if (loc.timezone) bits.push(loc.timezone);
  return bits.join(" · ");
}

// --- theme ----------------------------------------------------------------
function applyTheme(alert) {
  const tz = alert.location?.timezone;
  const w = alert.best_window;
  const body = document.body;
  const classes = ["theme-night", "theme-dawn", "theme-day", "theme-dusk", "theme-rain"];
  let theme = "theme-night";

  if (w && w.precipitation_probability >= 50) {
    theme = "theme-rain";
  } else {
    const h = w ? hourIn(w.start, tz) : new Date().getHours();
    if (h >= 5 && h < 8) theme = "theme-dawn";
    else if (h >= 8 && h < 17) theme = "theme-day";
    else if (h >= 17 && h < 20) theme = "theme-dusk";
  }
  body.classList.remove(...classes);
  body.classList.add(theme);
}

// --- render helpers -------------------------------------------------------
function sunArc(sunrise, sunset) {
  if (!sunrise || !sunset) return "";
  const rise = new Date(sunrise).getTime();
  const set = new Date(sunset).getTime();
  let p = (Date.now() - rise) / (set - rise);
  p = Math.max(0, Math.min(1, p));
  const theta = Math.PI * (1 - p);
  const cx = 100 + 90 * Math.cos(theta);
  const cy = 90 - 90 * Math.sin(theta);
  const len = Math.PI * 90;
  return `<svg class="arc" viewBox="0 0 200 100" preserveAspectRatio="xMidYMid meet">
    <path class="track" d="M10 90 A 90 90 0 0 1 190 90" fill="none" stroke-width="3" stroke-linecap="round"/>
    <path class="done" d="M10 90 A 90 90 0 0 1 190 90" fill="none" stroke-width="3" stroke-linecap="round"
          stroke-dasharray="${len}" stroke-dashoffset="${len * (1 - p)}"/>
    <circle class="dot" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="5"/>
  </svg>`;
}

function tile(title, iconName, bodyHtml, more = "", wide = false) {
  const chev = more ? `<span class="chev">${icon("chevron")}</span>` : "";
  return `<section class="tile glass ${wide ? "wide" : ""} ${more ? "expandable" : ""}">
    <div class="tile-title">${icon(iconName)}<span>${title}</span>${chev}</div>
    ${bodyHtml}
    ${more ? `<div class="more">${more}</div>` : ""}
  </section>`;
}

function daylightSpan(sunrise, sunset) {
  if (!sunrise || !sunset) return "";
  const diff = Math.max(0, new Date(sunset) - new Date(sunrise));
  const h = Math.floor(diff / 3600000);
  const m = Math.round((diff % 3600000) / 60000);
  return `${h}h ${String(m).padStart(2, "0")}m`;
}

function row(k, v, iconName) {
  return `<div class="row"><span class="k">${iconName ? icon(iconName) : ""}${k}</span><span class="v">${v}</span></div>`;
}

function renderHourly(alert) {
  const tz = alert.location?.timezone;
  const pts = alert.hourly || [];
  hourlyPoints = pts;
  $("hourly-card").hidden = pts.length === 0;
  $("hourly").innerHTML = pts
    .map((p, i) => {
      const cls = ["hour", p.is_best ? "best" : "", i === 0 ? "now" : ""].join(" ");
      return `<div class="${cls}" data-idx="${i}" title="Outside score ${Math.round(p.score)}/100">
        <div class="hour-time">${i === 0 ? "Now" : fmtTime(p.time, tz)}</div>
        ${icon(p.icon)}
        <div class="hour-score">${Math.round(p.score)}</div>
        <div class="hour-temp">${Math.round(p.temperature_c)}°</div>
      </div>`;
    })
    .join("");
}

function showHourDetail(idx) {
  const el = $("hourly-detail");
  const p = hourlyPoints[idx];
  if (!p) {
    el.classList.remove("show");
    return;
  }
  el.innerHTML =
    `<b>${fmtTime(p.time, currentTz)}</b> · ${Math.round(p.temperature_c)}° ` +
    `(feels ${Math.round(p.feels_like_c)}°) · rain ${p.precipitation_probability}% · ` +
    `wind ${Math.round(p.wind_kph)} km/h · cloud ${p.cloud_cover}% · ` +
    `UV ${Math.round(p.uv_index)} · outside score <b>${Math.round(p.score)}/100</b>`;
  el.classList.add("show");
}

function renderTiles(alert) {
  const sky = alert.sky_report || {};
  const w = alert.best_window;
  const tiles = [];

  // Sun
  tiles.push(
    tile(
      "Sun",
      "sun",
      `${row("Sunrise", fmtTime(sky.sunrise), "sunrise")}
       ${row("Sunset", fmtTime(sky.sunset), "sunset")}
       ${sunArc(sky.sunrise, sky.sunset)}`,
      `<div class="row"><span class="k">${icon("sun")}Daylight</span><span class="v">${daylightSpan(sky.sunrise, sky.sunset)}</span></div>
       ${row("Solar noon", fmtTime(sky.solar_noon), "sun")}
       ${row("Twilight ends", fmtTime(sky.civil_twilight_end), "sunset")}`
    )
  );

  // Moon
  const lit = Math.round((sky.moon_illumination || 0) * 100);
  tiles.push(
    tile(
      "Moon",
      "moon",
      `<div class="big">${sky.moon_phase_name || "Unknown"}</div>
       <div><div class="muted" style="margin-bottom:6px">${lit}% illuminated</div>
       <div class="bar"><i style="width:${lit}%"></i></div></div>
       ${row("Rises", fmtTime(sky.moonrise), "sunrise")}
       ${row("Sets", fmtTime(sky.moonset), "sunset")}`,
      `<div class="row"><span class="k">${icon("moon")}Age</span><span class="v">${sky.moon_age_days != null ? sky.moon_age_days + " days" : "—"}</span></div>
       <div class="row"><span class="k">${icon("moon")}Best view</span><span class="v">${sky.moon_phase_name === "New Moon" ? "new moon — dark skies" : "when it's high and the Sun is down"}</span></div>`
    )
  );

  // Planets
  const visibles = (sky.planets || []).filter((p) => p.visible);
  const allPlanets = (sky.planets || [])
    .map((p) =>
      row(p.name, `${p.visible ? "up · " : "down · "}${p.direction} ${Math.round(p.altitude_deg)}° · ${p.magnitude != null ? "mag " + p.magnitude : ""}`, "star")
    )
    .join("");
  tiles.push(
    tile(
      "Planets",
      "planet",
      visibles.length
        ? visibles
            .map((p) =>
              row(p.name, `${p.direction} · ${Math.round(p.altitude_deg)}°`, "star")
            )
            .join("")
        : `<div class="muted">No bright planets are well placed right now.</div>`,
      allPlanets || `<div class="muted">No planet data for right now.</div>`
    )
  );

  // Constellations
  const cons = sky.constellations || [];
  const allCons = cons
    .map((c) => row(c.name, `${c.star} · ${c.direction} ${Math.round(c.altitude_deg)}°`, "star"))
    .join("");
  tiles.push(
    tile(
      "Overhead",
      "star",
      cons.length
        ? `<div class="chips">${cons
            .map((c) => `<span class="chip">${c.name}</span>`)
            .join("")}</div>`
        : `<div class="muted">No notable constellations high up yet.</div>`,
      allCons || `<div class="muted">No constellation data for right now.</div>`
    )
  );

  // Conditions (wide)
  if (w) {
    const stats = [
      ["Temp", `${Math.round(w.temperature_c)}°`, "thermo"],
      ["Feels", `${Math.round(w.feels_like_c)}°`, "thermo"],
      ["Rain", `${w.precipitation_probability}%`, "drop"],
      ["Wind", `${Math.round(w.wind_kph)} km/h`, "wind"],
      ["Cloud", `${w.cloud_cover}%`, "cloud"],
      ["UV", `${Math.round(w.uv_index)}`, "uv"],
    ];
    tiles.push(
      tile(
        "Conditions at the best window",
        "clipboard",
        `<div class="stats">${stats
          .map(
            ([k, v, ic]) =>
              `<div class="stat"><div class="k">${icon(ic)}${k}</div><div class="v">${v}</div></div>`
          )
          .join("")}</div>`,
        "",
        true
      )
    );
  }

  // Meteors (wide)
  const showers = sky.meteor_showers || [];
  const near = showers.filter((m) => m.near_peak);
  const allMeteors = showers
    .map((m) => row(m.name, `peak ${m.peak} · ZHR ${m.zhr} · ${m.active}`, "meteor"))
    .join("");
  tiles.push(
    tile(
      "Meteor showers",
      "meteor",
      near.length
        ? near
            .map(
              (m) =>
                `<div class="row"><span class="k">${icon("meteor")}${m.name} · near peak</span>
                 <span class="v">ZHR ${m.zhr}</span></div>
                 <div class="muted" style="margin:4px 0 8px">${m.description} Look towards ${m.radiant}.</div>`
            )
            .join("")
        : showers.length
          ? `<div class="chips">${showers
              .map((m) => `<span class="chip meteor">${m.name} · ${m.active}</span>`)
              .join("")}</div>`
          : `<div class="muted">No major shower near its peak right now.</div>`,
      allMeteors || `<div class="muted">No shower data right now.</div>`,
      true
    )
  );

  $("grid").innerHTML = tiles.join("");
}

async function updateFoot(alert) {
  const p = alert?.providers;
  const bits = [];
  if (p) {
    bits.push(p.gemma ? `Gemma (${p.llm_provider})` : "template narrator");
    if (p.elevenlabs) bits.push("ElevenLabs voice");
    if (p.mongodb) bits.push("MongoDB Atlas");
    if (p.serpapi) bits.push("SerpApi");
    if (p.sentry) bits.push("Sentry tracing");
    bits.push(`host: ${p.hosting}`);
  }
  try {
    const h = await (await fetch("/api/health")).json();
    if (!p && h.integrations) bits.push(`Gemma (${h.integrations.gemma_provider})`);
    if (h.storage?.backend) bits.push(`storage: ${h.storage.backend}`);
  } catch {
    /* ignore */
  }
  $("foot-info").textContent = bits.length ? "Powered by " + bits.join(" · ") : "Powered by open data";
}

function render(alert) {
  const w = alert.best_window;
  const tz = (currentTz = alert.location?.timezone);

  $("place").textContent = alert.location.display_name || alert.location.name;
  $("hero-meta").textContent = locationMeta(alert.location);
  $("window-start").textContent = w ? fmtTime(w.start, tz) : "--:--";
  $("window-end").textContent = w ? "–" + fmtTime(w.end, tz) : "";
  $("hero-cond").textContent = alert.weather_summary.replace(/\.$/, "");

  // hero icon from the first hourly point (or sun)
  const firstIcon = ((alert.hourly || [])[0] || {}).icon || "sun";
  $("hero-icon").innerHTML = icon(firstIcon);

  const score = w ? Math.round(w.score) : 0;
  $("ring").style.setProperty("--p", score);
  $("score-num").textContent = w ? score : "–";

  $("message").textContent = alert.message;
  $("nudge").textContent = alert.nudge;

  renderHourly(alert);
  renderTiles(alert);
  applyTheme(alert);

  const audio = $("audio");
  if (alert.audio_url) {
    audio.src = alert.audio_url;
    audio.hidden = false;
  } else {
    audio.hidden = true;
    audio.removeAttribute("src");
  }

  updateFoot(alert);
  resultEl.classList.remove("hidden");
}

// --- status + actions -----------------------------------------------------
function setStatus(text, isError = false) {
  statusEl.textContent = text || "";
  statusEl.classList.toggle("error", isError);
}

let coords = null;

async function getHorizon(cityOverride) {
  const city = (cityOverride ?? $("city").value).trim();
  const speak = $("speak").checked;
  if (!city && !coords) {
    setStatus("Type a city, or tap the pin to use your location.", true);
    return;
  }

  goBtn.disabled = true;
  setStatus("Reading the sky…");

  const params = new URLSearchParams({ speak: String(speak) });
  if (city) params.set("city", city);
  else if (coords) {
    params.set("latitude", coords[0]);
    params.set("longitude", coords[1]);
  }

  try {
    const res = await fetch(`/api/alert?${params.toString()}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }
    render(await res.json());
    setStatus("");
  } catch (e) {
    setStatus(e.message || "Something went wrong. Try again.", true);
  } finally {
    goBtn.disabled = false;
  }
}

// --- location -------------------------------------------------------------
function secureForGeo() {
  // Browsers only expose precise geolocation in a secure context: HTTPS, or
  // localhost (which is treated as secure). Plain http:// on a LAN IP is not.
  const host = location.hostname;
  const isLocal =
    host === "localhost" || host === "127.0.0.1" || host === "::1" || host.endsWith(".localhost");
  return window.isSecureContext || isLocal;
}

function browserPosition() {
  return new Promise((resolve) => {
    if (!("geolocation" in navigator)) return resolve({ error: "unsupported" });
    if (!secureForGeo()) return resolve({ error: "insecure" });
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          coords: [pos.coords.latitude, pos.coords.longitude],
          accuracy: pos.coords.accuracy,
        }),
      (err) =>
        resolve({
          error:
            err && err.code === 1 ? "denied" : err && err.code === 3 ? "timeout" : "unavailable",
        }),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 300000 }
    );
  });
}

async function networkPosition() {
  // Coarse, IP-based fallback so the pin still works when precise GPS is blocked.
  const sources = [
    { url: "https://get.geojs.io/v1/ip/geo.json", pick: (d) => [d.latitude, d.longitude] },
    { url: "https://ipwho.is/", pick: (d) => [d.latitude, d.longitude] },
  ];
  for (const source of sources) {
    try {
      const res = await fetch(source.url, { headers: { Accept: "application/json" } });
      if (!res.ok) continue;
      const [lat, lon] = source.pick(await res.json());
      if (lat != null && lon != null) return [Number(lat), Number(lon)];
    } catch {
      /* blocked or offline — try the next source */
    }
  }
  return null;
}

function applyCoords(pair) {
  coords = [Number(pair[0]).toFixed(4), Number(pair[1]).toFixed(4)];
  $("city").value = "";
  getHorizon("");
}

async function useMyLocation() {
  goBtn.disabled = true;
  setStatus("Finding your location…");

  // 1) Precise browser location.
  const precise = await browserPosition();
  if (precise.coords) {
    applyCoords(precise.coords);
    return;
  }

  // 2) Coarse network location, so the pin still does something useful.
  setStatus(
    precise.error === "insecure"
      ? "Precise location needs HTTPS — estimating from your network…"
      : "Precise location unavailable — estimating from your network…"
  );
  const approx = await networkPosition();
  if (approx) {
    applyCoords(approx);
    return;
  }

  // 3) Give an accurate, actionable message.
  goBtn.disabled = false;
  const messages = {
    denied: "Location permission is blocked. Allow it for this site, or type a city below.",
    insecure:
      "This page isn't served over HTTPS, so the browser hides your location. Open it via https:// or localhost, or type a city below.",
    timeout: "Location took too long. Try again, or type a city below.",
    unsupported: "This browser doesn't support geolocation — type a city below.",
    unavailable: "Your location isn't available right now — type a city below.",
  };
  setStatus(messages[precise.error] || "Couldn't get your location — type a city below.", true);
}

// --- sky calendar ---------------------------------------------------------
// Notable upcoming events (importance 2+ gets highlighted). Location-independent,
// so it renders instantly from /api/events without needing an alert first.
let calByDate = new Map();
let calCursor = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let calSelected = null;

function localDateIso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fmtDayLong(iso) {
  try {
    return new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function kindLabel(k) {
  return { moon: "Moon", meteor: "Meteor", season: "Season", planet: "Planet" }[k] || k;
}

async function loadCalendar() {
  try {
    const res = await fetch("/api/events?days=120");
    if (!res.ok) return;
    const data = await res.json();
    calByDate = new Map();
    for (const e of data.events || []) {
      if (!calByDate.has(e.date)) calByDate.set(e.date, []);
      calByDate.get(e.date).push(e);
    }
  } catch {
    /* calendar stays blank rather than breaking the page */
  }
  renderCalendar();
}

function renderCalendar() {
  const y = calCursor.getFullYear();
  const m = calCursor.getMonth();
  $("cal-title").textContent = calCursor.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  const startDow = new Date(y, m, 1).getDay();
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const todayIso = localDateIso(new Date());
  const cells = [];

  for (let i = 0; i < startDow; i++) cells.push('<div class="cal-day blank"></div>');
  for (let d = 1; d <= daysInMonth; d++) {
    const iso = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const important = (calByDate.get(iso) || []).filter((e) => e.importance >= 2);
    const cls = [
      "cal-day",
      iso < todayIso ? "dim" : "",
      iso === todayIso ? "today" : "",
      important.length ? "clickable" : "",
      calSelected === iso && important.length ? "selected" : "",
    ].join(" ");
    const dots = important
      .slice(0, 3)
      .map((e) => `<i class="${e.importance >= 3 ? "major" : "notable"}"></i>`)
      .join("");
    cells.push(
      `<div class="${cls}" data-iso="${iso}"><span>${d}</span><div class="dots">${dots}</div></div>`
    );
  }
  $("cal-grid").innerHTML = cells.join("");

  if (calSelected && calByDate.has(calSelected)) {
    showCalDay(calSelected);
  } else {
    $("cal-detail").innerHTML =
      '<div class="muted">Highlighted dates have something worth looking up for — tap one.</div>';
  }
}

function showCalDay(iso) {
  calSelected = iso;
  const all = (calByDate.get(iso) || []).slice().sort((a, b) => b.importance - a.importance);
  if (!all.length) {
    $("cal-detail").innerHTML =
      `<div class="muted">Nothing major planned for ${fmtDayLong(iso)} — pure sky, all to yourself.</div>`;
    return;
  }
  $("cal-detail").innerHTML =
    `<div class="muted" style="margin-bottom:8px">${fmtDayLong(iso)}</div>` +
    all
      .map(
        (e) =>
          `<div class="ev"><div class="ev-title"><span class="kind">${kindLabel(e.kind)}</span>${e.title}${
            e.time ? `<span class="ev-time"> · ${e.time} UTC</span>` : ""
          }</div><p>${e.detail}</p></div>`
      )
      .join("");
}

// --- wiring ---------------------------------------------------------------
$("search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  getHorizon();
});
$("locate").addEventListener("click", useMyLocation);
$("theme-toggle").addEventListener("click", () => {
  applyMode(themeMode === "light" ? "dark" : "light");
  try {
    localStorage.setItem(THEME_KEY, themeMode);
  } catch {
    /* private mode — keep the in-memory choice */
  }
});
$("city").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    getHorizon();
  }
});

// Interactive tiles: tap an expandable card to reveal more.
$("grid").addEventListener("click", (e) => {
  const tileEl = e.target.closest(".tile.expandable");
  if (tileEl) tileEl.classList.toggle("open");
});

// Interactive hourly strip: tap an hour for its conditions.
$("hourly").addEventListener("click", (e) => {
  const hour = e.target.closest(".hour");
  if (!hour) return;
  [...$("hourly").children].forEach((h) => h.classList.remove("selected"));
  hour.classList.add("selected");
  showHourDetail(Number(hour.dataset.idx));
});

// Sky calendar navigation + day selection.
$("cal-prev").addEventListener("click", () => {
  calCursor.setMonth(calCursor.getMonth() - 1);
  renderCalendar();
});
$("cal-next").addEventListener("click", () => {
  calCursor.setMonth(calCursor.getMonth() + 1);
  renderCalendar();
});
$("cal-grid").addEventListener("click", (e) => {
  const day = e.target.closest(".cal-day.clickable");
  if (!day) return;
  calSelected = day.dataset.iso;
  renderCalendar();
});

// Warm up a location in the background so the first tap is instant.
if (!localStorage.getItem("horizon_geo_asked")) {
  localStorage.setItem("horizon_geo_asked", "1");
  browserPosition().then((p) => {
    if (p.coords) coords = [Number(p.coords[0]).toFixed(4), Number(p.coords[1]).toFixed(4)];
  });
}

loadCalendar();
updateFoot();
